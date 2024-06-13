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
    mint_usdc(snx)
    mint_ausdc(snx)
    return snx


@chain_fork
def mint_usdc(snx):
    """The instance can mint USDC tokens"""
    # check usdc balance
    usdc_package = snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"]
    usdc_contract = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    usdc_balance = usdc_contract.functions.balanceOf(snx.address).call()
    usdc_balance = format_wei(usdc_balance)

    # get some usdc
    mint_amount = max(100000 - usdc_balance, 0)
    if mint_amount > 0:
        snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER])

        mint_amount = format_ether(mint_amount, 6)
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

        # wrap some USDC
        approve_tx_1 = snx.approve(
            usdc_contract.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx_1)

        wrap_tx = snx.spot.wrap(75000, market_name="sUSDC", submit=True)
        snx.wait(wrap_tx)
        snx.logger.info(f"sUSDC wrapped")

        # sell some for sUSD
        approve_tx_2 = snx.spot.approve(
            snx.spot.market_proxy.address, market_name="sUSDC", submit=True
        )
        snx.wait(approve_tx_2)

        susd_tx = snx.spot.atomic_order("sell", 50000, market_name="sUSDC", submit=True)
        snx.wait(susd_tx)
        snx.logger.info(f"sUSDC sold for sUSD")


@chain_fork
def mint_ausdc(snx):
    """The instance can mint aUSDC tokens and vault tokens"""
    # check ausdc balance
    # aUSDC token
    ausdc_package = snx.contracts["packages"]["ausdc_token_mock"]["MintableToken"]
    ausdc = snx.web3.eth.contract(
        address=ausdc_package["address"], abi=ausdc_package["abi"]
    )

    # stataUSDC oracle
    statausdc_oracle_package = snx.contracts["packages"][
        "erc_4626_to_assets_ratio_oracle"
    ]["ERC4626ToAssetsRatioOracle"]
    statausdc_oracle = snx.web3.eth.contract(
        address=statausdc_oracle_package["address"],
        abi=statausdc_oracle_package["abi"],
    )

    # stataUSDC vault
    vault_address = statausdc_oracle.functions.VAULT_ADDRESS().call()
    vault = snx.web3.eth.contract(
        address=vault_address,
        abi=snx.contracts["ERC4626"]["abi"],
    )

    ausdc_balance = ausdc.functions.balanceOf(snx.address).call()
    ausdc_balance = format_wei(ausdc_balance, 6)

    deposit_amount = 100000
    mint_amount = max(deposit_amount - ausdc_balance, 0)
    if mint_amount > 0:
        mint_amount = format_ether(mint_amount, 6)
        tx_params = ausdc.functions.mint(mint_amount, snx.address).build_transaction(
            {
                "from": snx.address,
                "nonce": snx.web3.eth.get_transaction_count(snx.address),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("aUSDC Mint failed")
        else:
            snx.logger.info(f"aUSDC minted")

        # deposit to the vault
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)
        approve_tx = snx.approve(ausdc.address, vault.address, submit=True)
        snx.wait(approve_tx)

    deposit_tx_params = vault.functions.mint(
        format_ether(deposit_amount, 6), snx.address
    ).build_transaction(
        {
            "from": snx.address,
            "nonce": snx.web3.eth.get_transaction_count(snx.address),
        }
    )
    deposit_tx = snx.web3.eth.send_transaction(deposit_tx_params)
    deposit_receipt = snx.wait(deposit_tx)
    snx.logger.info(f"aUSDC deposited")

@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]

    # USDC token
    usdc_package = snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"]
    usdc = snx.web3.eth.contract(
        address=usdc_package["address"], abi=usdc_package["abi"]
    )

    # aUSDC token
    ausdc_package = snx.contracts["packages"]["ausdc_token_mock"]["MintableToken"]
    ausdc = snx.web3.eth.contract(
        address=ausdc_package["address"], abi=ausdc_package["abi"]
    )

    # stataUSDC oracle
    statausdc_oracle_package = snx.contracts["packages"][
        "erc_4626_to_assets_ratio_oracle"
    ]["ERC4626ToAssetsRatioOracle"]
    statausdc_oracle = snx.web3.eth.contract(
        address=statausdc_oracle_package["address"],
        abi=statausdc_oracle_package["abi"],
    )

    # stataUSDC vault
    vault_address = statausdc_oracle.functions.VAULT_ADDRESS().call()
    vault = snx.web3.eth.contract(
        address=vault_address,
        abi=snx.contracts["ERC4626"]["abi"],
    )

    return {
        "WETH": weth,
        "USDC": usdc,
        "aUSDC": ausdc,
        "stataUSDCOracle": statausdc_oracle,
        "StataUSDC": vault,
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
