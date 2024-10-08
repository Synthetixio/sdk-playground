import pytest
from conftest import chain_fork

# constants
USD_TEST_AMOUNT = 1000
USD_MINT_AMOUNT = 100

WETH_TEST_AMOUNT = 5
WETH_MINT_AMOUNT = 1000

SNX_TEST_AMOUNT = 10000
SNX_MINT_AMOUNT = 1000

ARB_TEST_AMOUNT = 1000


# tests
@chain_fork
def test_core_module(snx):
    """The instance has a core module"""
    assert snx.core is not None
    assert snx.core.core_proxy is not None


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("SNX", SNX_TEST_AMOUNT, 18),
        ("WETH", WETH_TEST_AMOUNT, 18),
    ],
)
def test_deposit_flow(
    snx,
    contracts,
    core_account_id,
    token_name,
    test_amount,
    decimals,
):
    """The instance can deposit token"""
    token = contracts[token_name]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        test_amount,
        decimals=decimals,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # withdraw the token
    withdraw_tx_hash = snx.core.withdraw(
        test_amount,
        token_address=token.address,
        decimals=decimals,
        account_id=core_account_id,
        submit=True,
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("SNX", SNX_TEST_AMOUNT, 18),
        ("WETH", WETH_TEST_AMOUNT, 18),
    ],
)
def test_delegate_flow(
    snx,
    contracts,
    core_account_id,
    token_name,
    test_amount,
    decimals,
):
    """The instance can delegate token"""
    token = contracts[token_name]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    withdrawable_usd_start = (
        snx.core.core_proxy.functions.getWithdrawableMarketUsd(3).call() / 1e18
    )

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        test_amount,
        decimals=decimals,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        test_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)

    assert delegate_tx_hash is not None
    assert delegate_tx_receipt is not None
    assert delegate_tx_receipt.status == 1

    withdrawable_usd_end = (
        snx.core.core_proxy.functions.getWithdrawableMarketUsd(3).call() / 1e18
    )
    snx.logger.info(f"withdrawable_usd_start: {withdrawable_usd_start}")
    snx.logger.info(f"withdrawable_usd_end: {withdrawable_usd_end}")


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, mint_amount, decimals",
    [
        ("SNX", SNX_TEST_AMOUNT, SNX_MINT_AMOUNT, 18),
        ("WETH", WETH_TEST_AMOUNT, WETH_MINT_AMOUNT, 18),
    ],
)
def test_account_delegate_mint(
    snx,
    contracts,
    core_account_id,
    token_name,
    test_amount,
    mint_amount,
    decimals,
):
    """The instance can deposit and delegate"""
    token = contracts[token_name]
    susd = snx.contracts["system"]["USDProxy"]["contract"]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        test_amount,
        decimals=decimals,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        test_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)

    assert delegate_tx_hash is not None
    assert delegate_tx_receipt is not None
    assert delegate_tx_receipt.status == 1

    # mint sUSD
    mint_tx_hash = snx.core.mint_usd(
        token.address,
        mint_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )

    mint_tx_receipt = snx.wait(mint_tx_hash)

    assert mint_tx_hash is not None
    assert mint_tx_receipt is not None
    assert mint_tx_receipt.status == 1

    # withdraw the token
    withdraw_tx_hash = snx.core.withdraw(
        mint_amount,
        token_address=susd.address,
        account_id=core_account_id,
        submit=True,
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1
