import os
from dotenv import load_dotenv
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain
from utils.arb_helpers import mock_arb_precompiles
from utils.chain_helpers import mine_block

load_dotenv()

# constants
SNX_DEPLOYER = "0xD3DFa13CDc7c133b1700c243f03A8C6Df513A93b"
USDC_WHALE = "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D"
ARB_WHALE = "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D"
USDE_WHALE = "0xb3C24D9dcCC2Ec5f778742389ffe448E295B84e0"
TBTC_WHALE = "0xa79a356B01ef805B3089b4FE67447b96c7e6DD4C"

USDC_MINT_AMOUNT = 1000000
USDC_LP_AMOUNT = 500000
USDX_MINT_AMOUNT = 100000


def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("arbitrum:mainnet-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="package")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        network_id=42161,
        is_fork=True,
        price_service_endpoint=os.getenv("PRICE_SERVICE_ENDPOINT"),
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "26",
            "preset": "main",
        },
    )
    mock_arb_precompiles(snx)
    set_timeout(snx)
    steal_arb(snx)
    steal_usdc(snx)
    steal_usde(snx)
    steal_tbtc(snx)
    mint_usdx_with_usdc(snx)
    wrap_eth(snx)
    mine_block(snx, chain)
    update_prices(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]
    usdc = snx.contracts["USDC"]["contract"]
    arb = snx.contracts["ARB"]["contract"]
    usde = snx.contracts["USDe"]["contract"]
    tbtc = snx.contracts["tBTC"]["contract"]
    return {
        "WETH": weth,
        "USDC": usdc,
        "ARB": arb,
        "USDe": usde,
        "tBTC": tbtc,
    }


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
def steal_arb(snx):
    """The instance can steal ARB tokens"""
    # check arb balance
    arb_contract = snx.contracts["ARB"]["contract"]
    arb_balance = arb_contract.functions.balanceOf(snx.address).call()
    arb_balance = arb_balance / 10**18

    # get some arb
    if arb_balance < 100000:
        transfer_amount = int((100000 - arb_balance) * 10**18)
        snx.web3.provider.make_request("anvil_impersonateAccount", [ARB_WHALE])

        tx_params = arb_contract.functions.transfer(
            snx.address, transfer_amount
        ).build_transaction(
            {
                "from": ARB_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(ARB_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("ARB Transfer failed")

        assert tx_hash is not None
        assert receipt is not None
        assert receipt.status == 1
        snx.logger.info(f"Stole ARB from {ARB_WHALE}")


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
def steal_tbtc(snx):
    """The instance can steal tBTC tokens"""
    # check USDe balance
    tbtc_contract = snx.contracts["tBTC"]["contract"]
    tbtc_balance = tbtc_contract.functions.balanceOf(snx.address).call()
    tbtc_balance = tbtc_balance / 10**18

    # get some tbtc
    if tbtc_balance < 2:
        # send some eth to the whale
        send_tx_params = snx._get_tx_params(to=TBTC_WHALE, value=ether_to_wei(1))
        send_tx_hash = snx.execute_transaction(send_tx_params)
        send_tx_receipt = snx.wait(send_tx_hash)

        assert send_tx_hash is not None
        assert send_tx_receipt is not None
        assert send_tx_receipt.status == 1

        transfer_amount = int((2 - tbtc_balance) * 10**18)
        snx.web3.provider.make_request("anvil_impersonateAccount", [TBTC_WHALE])

        tx_params = tbtc_contract.functions.transfer(
            snx.address, transfer_amount
        ).build_transaction(
            {
                "from": TBTC_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(TBTC_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("tBTC Transfer failed")

        assert tx_hash is not None
        assert receipt is not None
        assert receipt.status == 1
        snx.logger.info(f"Stole tBTC from {TBTC_WHALE}")


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
def wrap_eth(snx):
    """The instance can wrap ETH"""
    # check balance
    eth_balance = snx.get_eth_balance()
    if eth_balance["weth"] < 100:
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)
        tx_hash = snx.wrap_eth(100, submit=True)
        tx_receipt = snx.wait(tx_hash)

        assert tx_hash is not None
        assert tx_receipt is not None
        assert tx_receipt.status == 1
        snx.logger.info(f"Wrapped ETH")


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
