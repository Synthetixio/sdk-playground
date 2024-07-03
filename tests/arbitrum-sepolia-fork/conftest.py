import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain

# constants
SNX_DEPLOYER_ADDRESS = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
USDC_WHALE = "0x6ED0C4ADDC308bb800096B8DaA41DE5ae219cd36"


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("arbitrum:sepolia-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="package")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=421614,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "11",
            "preset": "main",
        },
    )
    update_prices(snx)
    mint_token(snx, "arb")
    mint_token(snx, "USDe")
    steal_usdc(snx)
    wrap_eth(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]
    usdc = snx.contracts["USDC"]["contract"]
    arb = snx.contracts["arb_mock_collateral"]["MintableToken"]["contract"]
    usde = snx.contracts["USDe_mock_collateral"]["MintableToken"]["contract"]
    return {
        "WETH": weth,
        "USDC": usdc,
        "ARB": arb,
        "USDe": usde,
    }


@chain_fork
def mint_token(snx, token_name):
    """The instance can mint mintable tokens"""
    # check arb balance
    token_contract = snx.contracts[f"{token_name}_mock_collateral"]["MintableToken"][
        "contract"
    ]
    token_balance = token_contract.functions.balanceOf(snx.address).call()
    token_balance = token_balance / 10**18

    # mint some arb
    mint_amount = max(100000 - token_balance, 0)
    if mint_amount > 0:
        snx.web3.provider.make_request(
            "anvil_impersonateAccount", [SNX_DEPLOYER_ADDRESS]
        )

        mint_amount = ether_to_wei(mint_amount)
        tx_params = token_contract.functions.mint(
            mint_amount, snx.address
        ).build_transaction(
            {
                "from": SNX_DEPLOYER_ADDRESS,
                "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER_ADDRESS),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception(f"{token_name} Mint failed")
        else:
            snx.logger.info(f"{token_name} minted")


@chain_fork
def update_prices(snx):
    pyth_contract = snx.contracts["Pyth"]["contract"]

    # get feed ids
    feed_ids = list(snx.pyth.price_feed_ids.values())

    pyth_response = snx.pyth.get_price_from_ids(feed_ids)
    price_update_data = pyth_response["price_update_data"]

    # create the tx
    tx_params = snx._get_tx_params(value=len(feed_ids))
    tx_params = pyth_contract.functions.updatePriceFeeds(
        price_update_data
    ).build_transaction(tx_params)

    # submit the tx
    tx_hash = snx.execute_transaction(tx_params)
    tx_receipt = snx.wait(tx_hash)
    if tx_receipt["status"] != 1:
        raise Exception("Price feed update failed")
    else:
        snx.logger.info("Price feeds updated")


@chain_fork
def steal_usdc(snx):
    """The instance can steal USDC tokens"""
    # check usdc balance
    usdc_contract = snx.contracts["USDC"]["contract"]
    usdc_balance = usdc_contract.functions.balanceOf(snx.address).call()
    usdc_balance = usdc_balance / 10**6

    # get some usdc
    if usdc_balance < 100000:
        transfer_amount = int((100000 - usdc_balance) * 10**6)
        snx.web3.provider.make_request("anvil_impersonateAccount", [USDC_WHALE])

        tx_params = usdc_contract.functions.transfer(
            snx.address, transfer_amount
        ).build_transaction(
            {
                "from": USDC_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(USDC_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("USDC Transfer failed")

        assert tx_hash is not None
        assert receipt is not None
        assert receipt.status == 1
        snx.logger.info(f"Stole USDC from {USDC_WHALE}")


@chain_fork
def steal_usde(snx):
    """The instance can steal USDe tokens"""
    # check USDe balance
    usde_contract = snx.contracts["USDe"]["contract"]
    usde_balance = usde_contract.functions.balanceOf(snx.address).call()
    usde_balance = usde_balance / 10**18

    # get some usde
    if usde_balance < 100000:
        # send some eth to the whale
        send_tx_params = snx._get_tx_params(to=USDE_WHALE, value=ether_to_wei(1))
        send_tx_hash = snx.execute_transaction(send_tx_params)
        send_tx_receipt = snx.wait(send_tx_hash)

        assert send_tx_hash is not None
        assert send_tx_receipt is not None
        assert send_tx_receipt.status == 1

        transfer_amount = int((100000 - usde_balance) * 10**18)
        snx.web3.provider.make_request("anvil_impersonateAccount", [USDE_WHALE])

        tx_params = usde_contract.functions.transfer(
            snx.address, transfer_amount
        ).build_transaction(
            {
                "from": USDE_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(USDE_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("USDe Transfer failed")

        assert tx_hash is not None
        assert receipt is not None
        assert receipt.status == 1
        snx.logger.info(f"Stole USDe from {USDE_WHALE}")


@chain_fork
def wrap_eth(snx):
    """The instance can wrap ETH"""
    # check balance
    eth_balance = snx.get_eth_balance()
    if eth_balance["weth"] < 10:
        tx_hash = snx.wrap_eth(10, submit=True)
        tx_receipt = snx.wait(tx_hash)

        assert tx_hash is not None
        assert tx_receipt is not None
        assert tx_receipt.status == 1
        snx.logger.info(f"Wrapped ETH")


@chain_fork
@pytest.fixture(scope="function")
def core_account_id(snx):
    # create a core account
    tx_hash = snx.core.create_account(submit=True)
    tx_receipt = snx.wait(tx_hash)

    assert tx_hash is not None
    assert tx_receipt is not None
    assert tx_receipt.status == 1

    account_id = snx.core.account_ids[-1]
    snx.logger.info(f"Created core account: {account_id}")
    return account_id
