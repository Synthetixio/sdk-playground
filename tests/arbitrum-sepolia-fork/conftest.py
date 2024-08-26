import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain
from utils.arb_helpers import mock_arb_precompiles

# constants
SNX_DEPLOYER = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
USDC_WHALE = "0x6ED0C4ADDC308bb800096B8DaA41DE5ae219cd36"

USDC_MINT_AMOUNT = 1000000
USDC_LP_AMOUNT = 500000
USDX_MINT_AMOUNT = 100000


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
            "version": "latest",
            "preset": "main",
        },
    )
    mock_arb_precompiles(snx)
    set_timeout(snx)
    mint_token(snx, "arb")
    mint_token(snx, "USDe")
    mint_token(snx, "btc")
    steal_usdc(snx)
    mint_usdx_with_usdc(snx)
    wrap_eth(snx)
    update_prices(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]
    usdc = snx.contracts["USDC"]["contract"]
    arb = snx.contracts["arb_mock_collateral"]["MintableToken"]["contract"]
    usde = snx.contracts["USDe_mock_collateral"]["MintableToken"]["contract"]
    btc = snx.contracts["btc_mock_collateral"]["MintableToken"]["contract"]
    return {
        "WETH": weth,
        "USDC": usdc,
        "ARB": arb,
        "USDe": usde,
        "BTC": btc,
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
        snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

        mint_amount = ether_to_wei(mint_amount)
        tx_params = token_contract.functions.mint(
            mint_amount, snx.address
        ).build_transaction(
            {
                "from": SNX_DEPLOYER,
                "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER),
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
def set_timeout(snx):
    """Set the account activity timeout to zero"""
    snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

    tx_params = snx.core.core_proxy.functions.setConfig(
        "0x6163636f756e7454696d656f7574576974686472617700000000000000000000",
        "0x0000000000000000000000000000000000000000000000000000000000000000",
    ).build_transaction(
        {
            "from": SNX_DEPLOYER,
            "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER),
        }
    )

    # Send the transaction directly without signing
    tx_hash = snx.web3.eth.send_transaction(tx_params)
    receipt = snx.wait(tx_hash)
    if receipt["status"] != 1:
        raise Exception(f"Set timeout failed")
    else:
        snx.logger.info(f"Timeout set")


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
    if usdc_balance < USDC_MINT_AMOUNT:
        transfer_amount = int((USDC_MINT_AMOUNT - usdc_balance) * 10**6)
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
def mint_usdx_with_usdc(snx):
    """The instance can mint USDx tokens using USDC as collateral"""
    # set up token contracts
    token = snx.contracts["USDC"]["contract"]
    usdc_decimals = token.functions.decimals().call()

    susd = snx.contracts["system"]["USDProxy"]["contract"]
    susd_decimals = susd.functions.decimals().call()

    # get an account
    create_account_tx = snx.core.create_account(submit=True)
    snx.wait(create_account_tx)
    new_account_id = snx.core.account_ids[-1]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < USDC_LP_AMOUNT:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        USDC_LP_AMOUNT,
        decimals=usdc_decimals,
        account_id=new_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        USDC_LP_AMOUNT,
        1,
        account_id=new_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)
    assert delegate_tx_receipt.status == 1

    # mint sUSD
    mint_tx_hash = snx.core.mint_usd(
        token.address,
        USDX_MINT_AMOUNT,
        1,
        account_id=new_account_id,
        submit=True,
    )
    mint_tx_receipt = snx.wait(mint_tx_hash)
    assert mint_tx_receipt.status == 1

    # withdraw
    withdraw_tx_hash = snx.core.withdraw(
        USDX_MINT_AMOUNT,
        token_address=susd.address,
        decimals=susd_decimals,
        account_id=new_account_id,
        submit=True,
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)
    assert withdraw_tx_receipt.status == 1

    # check balance
    usdx_balance = snx.get_susd_balance()["balance"]
    assert usdx_balance >= USDX_MINT_AMOUNT


@chain_fork
def liquidation_setup(snx, market_id):
    snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

    market = snx.perps.market_proxy
    parameters = market.functions.getLiquidationParameters(market_id).call()
    parameters[-1] = int(10**6 * 10**20)

    tx_params = market.functions.setLiquidationParameters(
        market_id, *parameters
    ).build_transaction(
        {
            "from": SNX_DEPLOYER,
            "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER),
        }
    )

    # Send the transaction
    tx_hash = snx.web3.eth.send_transaction(tx_params)
    receipt = snx.wait(tx_hash)
    if receipt["status"] != 1:
        raise Exception("Set liquidation parameters failed")


@chain_fork
@pytest.fixture(scope="function")
def perps_account_id(snx):
    snx.logger.info("Creating a new perps account")
    create_tx = snx.perps.create_account(submit=True)
    snx.wait(create_tx)

    account_ids = snx.perps.get_account_ids()
    new_account_id = account_ids[-1]

    yield new_account_id


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
