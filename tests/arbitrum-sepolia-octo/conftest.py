import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei, wei_to_ether, format_wei, format_ether
from ape import networks, chain


# constants

# fixtures
@pytest.fixture(scope="package")
def snx():
    # set up the snx instance
    print(os.getenv("NETWORK_421614_RPC"))
    snx = Synthetix(
        provider_rpc=os.getenv("NETWORK_421614_RPC"),
        private_key=os.getenv("PRIVATE_KEY"),
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "octopus",
        },
    )
    # assume the user already has some BTC
    # mint_usdx(snx)
    return snx


def mint_usdx(snx):
    """The instance can mint USDX tokens"""
    # check usdc balance
    usdc_package = snx.contracts["usdc_mock_collateral"]["MintableToken"]
    usdc_contract = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    usdc_balance = usdc_contract.functions.balanceOf(snx.address).call()
    usdc_balance = format_wei(usdc_balance)

    # get some usdc
    mint_amount = max(USDC_MINT_AMOUNT - usdc_balance, 0)
    if mint_amount > 0:
        snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

        mint_amount = format_ether(mint_amount, 18)
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
        else:
            snx.logger.info(f"USDC minted")


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]

    # USDC token
    usdc_package = snx.contracts["usdc_mock_collateral"]["MintableToken"]
    usdc = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    # BTC token
    btc_package = snx.contracts["btc_mock_collateral"]["MintableToken"]
    btc = snx.web3.eth.contract(address=btc_package["address"], abi=btc_package["abi"])

    return {
        "WETH": weth,
        "USDC": usdc,
        "BTC": btc,
    }


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


@pytest.fixture(scope="function")
def new_account_id(snx):
    snx.logger.info("Creating a new perps account")
    create_tx = snx.perps.create_account(submit=True)
    snx.wait(create_tx)

    account_ids = snx.perps.get_account_ids()
    new_account_id = account_ids[-1]

    yield new_account_id


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
