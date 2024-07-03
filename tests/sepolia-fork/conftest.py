import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain

# constants
SNX_DEPLOYER_ADDRESS = "0x431D454Bd4d352A0b1f45AE11EF1182bBEec6a7B"
USDC_WHALE = "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D"


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("ethereum:sepolia-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=11155111,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={"ipfs_hash": "QmWNC8PGBTwXc2DgjVXDpN1A9TxNR9UusKyyoyNmm2j982"},
    )
    mint_weth(snx)
    set_timeout(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["weth_mock_collateral"]["MintableToken"]["contract"]
    return {
        "WETH": weth,
    }


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
def set_timeout(snx):
    """Set the account activity timeout to zero"""
    snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER_ADDRESS])

    tx_params = snx.core.core_proxy.functions.setConfig(
        "0x6163636f756e7454696d656f7574576974686472617700000000000000000000",
        "0x0000000000000000000000000000000000000000000000000000000000000000",
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
        raise Exception(f"Set timeout failed")
    else:
        snx.logger.info(f"Timeout set")


@chain_fork
def mint_weth(snx):
    """The instance can mint the WETH mintable tokens"""
    # check arb balance
    token_contract = snx.contracts["weth_mock_collateral"]["MintableToken"]["contract"]
    token_balance = token_contract.functions.balanceOf(snx.address).call()
    token_balance = token_balance / 10**18

    # mint some arb
    mint_amount = max(100 - token_balance, 0)
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
            raise Exception(f"WETH Mint failed")
        else:
            snx.logger.info(f"WETH minted")


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
