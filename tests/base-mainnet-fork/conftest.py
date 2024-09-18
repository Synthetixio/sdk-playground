import os
from dotenv import load_dotenv
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain

load_dotenv()

# find an address with a lot of usdc
SNX_DEPLOYER = "0xbb63CA5554dc4CcaCa4EDd6ECC2837d5EFe83C82"
USDC_WHALE = "0xD34EA7278e6BD48DefE656bbE263aEf11101469c"
KWENTA_REFERRER = "0x3bD64247d879AF879e6f6e62F81430186391Bdb8"


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("base:mainnet-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="package")
def snx():
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=8453,
        referrer=KWENTA_REFERRER,
        is_fork=True,
        price_service_endpoint=os.getenv("PRICE_SERVICE_ENDPOINT"),
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "43",
            "preset": "andromeda",
        },
    )

    # send ETH to deployer
    tx_params = snx._get_tx_params(value=ether_to_wei(1), to=SNX_DEPLOYER)
    tx_hash = snx.execute_transaction(tx_params)
    tx_receipt = snx.wait(tx_hash)
    if tx_receipt["status"] != 1:
        raise Exception("ETH transfer to deployer failed")

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

        # wrap some USDC
        approve_tx_1 = snx.approve(
            usdc_contract.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx_1)

        wrap_tx = snx.spot.wrap(75000, market_name="sUSDC", submit=True)
        snx.wait(wrap_tx)

        # sell some for sUSD
        approve_tx_2 = snx.spot.approve(
            snx.spot.market_proxy.address, market_name="sUSDC", submit=True
        )
        snx.wait(approve_tx_2)

        susd_tx = snx.spot.atomic_order("sell", 50000, market_name="sUSDC", submit=True)
        snx.wait(susd_tx)

    update_prices(snx)
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


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]
    usdc = snx.contracts["USDC"]["contract"]
    return {
        "WETH": weth,
        "USDC": usdc,
    }


@chain_fork
@pytest.fixture(scope="function")
def new_account_id(snx):
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
