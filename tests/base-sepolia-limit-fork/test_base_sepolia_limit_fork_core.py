import pytest
from conftest import chain_fork

# constants
USD_TEST_AMOUNT = 1000

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
        ("USDC", USD_TEST_AMOUNT, 6),
    ],
)
def test_wrap_deposit_flow(
    snx,
    contracts,
    core_account_id,
    token_name,
    test_amount,
    decimals,
):
    """The instance can deposit token"""
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[f"s{token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]

    ## wrap
    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)

    if allowance < test_amount:
        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(test_amount, market_id=market_id, submit=True)
    snx.wait(wrap_tx)

    # approve collateral
    allowance = snx.allowance(wrapped_token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            wrapped_token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        wrapped_token.address,
        test_amount,
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
        token_address=wrapped_token.address,
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
        ("USDC", USD_TEST_AMOUNT, 6),
    ],
)
def test_wrap_delegate_flow(
    snx,
    contracts,
    core_account_id,
    token_name,
    test_amount,
    decimals,
):
    """The instance can delegate token"""
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[f"s{token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]

    ## wrap
    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)

    if allowance < test_amount:
        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(test_amount, market_id=market_id, submit=True)
    snx.wait(wrap_tx)

    # approve collateral
    allowance = snx.allowance(wrapped_token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            wrapped_token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        wrapped_token.address,
        test_amount,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        wrapped_token.address,
        test_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)

    assert delegate_tx_hash is not None
    assert delegate_tx_receipt is not None
    assert delegate_tx_receipt.status == 1
