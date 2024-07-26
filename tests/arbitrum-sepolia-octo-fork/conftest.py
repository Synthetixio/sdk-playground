import os
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei, wei_to_ether, format_wei, format_ether
from ape import networks, chain
from utils.arb_helpers import mock_arb_precompiles

# constants
SNX_DEPLOYER = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
KWENTA_REFERRER = "0x3bD64247d879AF879e6f6e62F81430186391Bdb8"

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
# @chain_fork
@pytest.fixture(scope="package")
def snx():
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=421614,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "octopus",
        },
    )
    mock_arb_precompiles(snx)
    update_prices(snx)
    set_timeout(snx)
    wrap_eth(snx)
    mint_btc(snx)
    mint_usdc(snx)
    mint_usdx_with_usdc(snx)
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
def mint_usdc(snx):
    """The instance can mint USDC tokens"""
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
def mint_usdx_with_usdc(snx):
    """The instance can mint USDx tokens using USDC as collateral"""
    # set up token contracts
    usdc_package = snx.contracts["usdc_mock_collateral"]["MintableToken"]
    token = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )
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
    usdx_balance = snx.get_susd_balance(account_id)["balance"]
    assert usdx_balance >= USDX_MINT_AMOUNT


@chain_fork
def mint_btc(snx):
    """The instance can mint BTC tokens"""
    # check usdc balance
    btc_package = snx.contracts["btc_mock_collateral"]["MintableToken"]
    btc_contract = snx.web3.eth.contract(
        address=btc_package["address"], abi=btc_package["abi"]
    )

    btc_balance = btc_contract.functions.balanceOf(snx.address).call()
    btc_balance = wei_to_ether(btc_balance)

    # get some usdc
    mint_amount = max(5 - btc_balance, 0)
    if mint_amount > 0:
        snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

        tx_params = btc_contract.functions.mint(
            ether_to_wei(mint_amount), snx.address
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
            raise Exception("BTC Mint failed")
        else:
            snx.logger.info(f"BTC minted")


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


@chain_fork
def wrap_eth(snx):
    """The instance can wrap ETH"""
    # check balance
    eth_balance = snx.get_eth_balance()
    if eth_balance["weth"] < 10:
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)
        tx_hash = snx.wrap_eth(10, submit=True)
        tx_receipt = snx.wait(tx_hash)

        assert tx_hash is not None
        assert tx_receipt is not None
        assert tx_receipt.status == 1
        snx.logger.info(f"Wrapped ETH")


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
