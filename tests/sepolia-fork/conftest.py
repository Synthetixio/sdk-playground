import os
import time
from functools import wraps
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain

# constants
SNX_DEPLOYER_ADDRESS = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"

SNX_LIQUIDITY_AMOUNT = 500000
SUSD_MINT_AMOUNT = 500

def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("ethereum:sepolia-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


def mine_block(snx, chain, seconds=3):
    time.sleep(seconds)
    timestamp = int(time.time())

    chain.mine(1, timestamp=timestamp)
    snx.logger.info(f"Block mined at timestamp {timestamp}")


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
        # local deployment
        ipfs_gateway="http://127.0.0.1:8080/ipfs/",
        cannon_config={"ipfs_hash": "QmV8mQ7cE5JJ8ZTHn8PQGR7SLFNL6sFFijBYaPsDbrBMvy"},
    )
    mine_block(snx, chain)
    update_prices(snx)
    mint_weth(snx)
    set_timeout(snx)
    add_snx_liquidity(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    snx_contract = snx.contracts["SNX"]["contract"]
    susd = snx.contracts["system"]["USDProxy"]["contract"]
    weth = snx.contracts["weth_mock_collateral"]["MintableToken"]["contract"]
    return {
        "SNX": snx_contract,
        "sUSD": susd,
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
    mint_amount = max(1000 - token_balance, 0)
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


def add_snx_liquidity(snx):
    """Add liquidity to the pool"""
    token = snx.contracts["SNX"]["contract"]
    susd = snx.contracts["system"]["USDProxy"]["contract"]

    # get balance
    balance = token.functions.balanceOf(snx.address).call() / 1e18

    # steal from deployer
    if balance < 1000000:
        transfer_amount = int((1000000 - balance) * 1e18)
        snx.web3.provider.make_request(
            "anvil_impersonateAccount", [SNX_DEPLOYER_ADDRESS]
        )

        tx_params = token.functions.transfer(
            snx.address, transfer_amount
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
            raise Exception("SNX Transfer failed")
        else:
            snx.logger.info("SNX transferred")

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < SNX_LIQUIDITY_AMOUNT:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        approve_receipt = snx.wait(approve_core_tx)
        assert approve_receipt["status"] == 1

    # make an account
    core_tx = snx.core.create_account(submit=True)
    core_receipt = snx.wait(core_tx)
    assert core_receipt.status == 1

    # deposit the token
    core_account_id = snx.core.account_ids[-1]
    deposit_tx_hash = snx.core.deposit(
        token.address,
        SNX_LIQUIDITY_AMOUNT,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        SNX_LIQUIDITY_AMOUNT,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)
    assert delegate_tx_receipt.status == 1

    # mint sUSD
    mint_tx_hash = snx.core.mint_usd(
        token.address,
        SUSD_MINT_AMOUNT,
        1,
        account_id=core_account_id,
        submit=True,
    )

    mint_tx_receipt = snx.wait(mint_tx_hash)
    assert mint_tx_receipt.status == 1

    # withdraw
    withdraw_tx_hash = snx.core.withdraw(
        SUSD_MINT_AMOUNT,
        token_address=susd.address,
        account_id=core_account_id,
        submit=True,
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)
    assert withdraw_tx_receipt.status == 1

    # check balance
    susd_balance = snx.get_susd_balance()["balance"]
    assert susd_balance >= SUSD_MINT_AMOUNT


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


@pytest.fixture(scope="function")
def perps_account_id(snx):
    snx.logger.info("Creating a new perps account")
    create_tx = snx.perps.create_account(submit=True)
    snx.wait(create_tx)

    account_ids = snx.perps.get_account_ids()
    new_account_id = account_ids[-1]

    yield new_account_id
