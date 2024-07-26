import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei, format_wei, format_ether
from ape import networks, chain


# find an address with a lot of usdc
SNX_DEPLOYER = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
KWENTA_REFERRER = "0x3bD64247d879AF879e6f6e62F81430186391Bdb8"


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("base:sepolia:alchemy"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="package")
def snx():
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        address=os.getenv("ADDRESS"),
        private_key=os.getenv("PRIVATE_KEY"),
        network_id=84532,
        referrer=KWENTA_REFERRER,
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "45",
            "preset": "limit",
        },
    )
    # mint_usd(snx)
    return snx


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
def mint_usd(snx):
    """The instance can mint sUSD tokens from USDC"""
    # get contracts
    usdc = snx.contracts["usdc_mock_collateral"]["MintableToken"]['contract']
    
    # log USDC balance
    usdc_balance = usdc.functions.balanceOf(snx.address).call() / 1e6
    snx.logger.info(f"USDC balance: {usdc_balance}")

    # wrap some USDC
    approve_tx_1 = snx.approve(usdc.address, snx.spot.market_proxy.address, submit=True)
    snx.wait(approve_tx_1)

    wrap_tx = snx.spot.wrap(100000, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # sell some for sUSD
    approve_tx_2 = snx.spot.approve(
        snx.spot.market_proxy.address, market_name="sUSDC", submit=True
    )
    snx.wait(approve_tx_2)

    susd_tx = snx.spot.atomic_order("sell", 100000, market_name="sUSDC", submit=True)
    snx.wait(susd_tx)


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]

    # USDC token
    usdc_package = snx.contracts["usdc_mock_collateral"]["MintableToken"]
    usdc = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    return {
        "WETH": weth,
        "USDC": usdc,
    }


@chain_fork
@pytest.fixture(scope="module")
def account_id(snx):
    # check if an account exists
    account_ids = snx.perps.get_account_ids()

    final_account_id = None
    for account_id in account_ids:
        margin_info = snx.perps.get_margin_info(account_id)
        positions = snx.perps.get_open_positions(account_id=account_id)

        if margin_info["total_collateral_value"] == 0 and len(positions) == 0:
            snx.logger.info(f"Account {account_id} is empty")
            final_account_id = account_id
            break
        else:
            snx.logger.info(f"Account {account_id} has margin")

    if final_account_id is None:
        snx.logger.info("Creating a new perps account")

        create_tx = snx.perps.create_account(submit=True)
        snx.wait(create_tx)

        account_ids = snx.perps.get_account_ids()
        final_account_id = account_ids[-1]

    yield final_account_id


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
