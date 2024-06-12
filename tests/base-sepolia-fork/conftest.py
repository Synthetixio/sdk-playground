import os
from functools import wraps
import pytest
from dotenv import load_dotenv
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain


load_dotenv()

# find an address with a lot of usdc
SNX_DEPLOYER = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
KWENTA_REFERRER = "0x3bD64247d879AF879e6f6e62F81430186391Bdb8"


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("base:sepolia-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="module")
def snx():
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=84532,
        referrer=KWENTA_REFERRER,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "33",
            "preset": "andromeda",
        },
    )

    # check usdc balance
    usdc_package = snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"]
    usdc_contract = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    usdc_balance = usdc_contract.functions.balanceOf(snx.address).call()
    usdc_balance = usdc_balance / 10**6

    # get some usdc
    if usdc_balance < 100000:
        snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

        mint_amount = int((100000 - usdc_balance) * 10**6)
        tx_params = usdc_contract.functions.mint(
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
            raise Exception("USDC Mint failed")

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

    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]

    usdc_package = snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"]
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
def new_account_id(snx):
    snx.logger.info("Creating a new perps account")
    create_tx = snx.perps.create_account(submit=True)
    snx.wait(create_tx)

    account_ids = snx.perps.get_account_ids()
    new_account_id = account_ids[-1]

    yield new_account_id
