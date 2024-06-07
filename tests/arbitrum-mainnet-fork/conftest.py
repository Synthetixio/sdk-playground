import os
from functools import wraps
import pytest
from dotenv import load_dotenv
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from ape import networks, chain

load_dotenv()

# constants
SNX_DEPLOYER_ADDRESS = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
USDC_WHALE = "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D"
ARB_WHALE = "0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D"

def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("arbitrum:mainnet-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


# fixtures
@chain_fork
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "main",
        },
    )
    steal_arb(snx)
    steal_usdc(snx)
    wrap_eth(snx)
    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]
    usdc = snx.contracts["USDC"]["contract"]
    arb = snx.contracts["ARB"]["contract"]
    return {
        "WETH": weth,
        "USDC": usdc,
        "ARB": arb,
    }


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
