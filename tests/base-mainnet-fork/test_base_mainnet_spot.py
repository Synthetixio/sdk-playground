import pytest
from synthetix.utils import format_wei
from conftest import chain_fork

# constants
TEST_AMOUNT = 100

# tests


@chain_fork
def test_spot_module(snx):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None


@chain_fork
def test_spot_markets(snx):
    """The instance has spot markets"""
    snx.logger.info(f"Markets: {snx.spot.markets_by_name}")
    assert snx.spot.markets_by_name is not None
    assert len(snx.spot.markets_by_name) == len(snx.spot.markets_by_id)
    assert "sUSD" in snx.spot.markets_by_name
    assert "sUSDC" in snx.spot.markets_by_name


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("USDC", TEST_AMOUNT, 6),
    ],
)
def test_spot_wrapper(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap and unwrap an asset"""
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[f"s{token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]

    # make sure we have some USDC
    starting_balance_wei = token.functions.balanceOf(snx.address).call()
    starting_balance = format_wei(starting_balance_wei, decimals)

    starting_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert starting_balance > test_amount

    ## wrap
    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)

    if allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(test_amount, market_id=market_id, submit=True)
    snx.wait(wrap_tx)

    # get new balances
    wrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    wrapped_balance = format_wei(wrapped_balance_wei, decimals)

    wrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert wrapped_balance == starting_balance - test_amount
    assert wrapped_synth_balance == starting_synth_balance + test_amount

    ## unwrap
    # check the allowance
    wrapped_allowance = snx.allowance(
        wrapped_token.address, snx.spot.market_proxy.address
    )

    if wrapped_allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            wrapped_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    unwrap_tx = snx.spot.wrap(-test_amount, market_id=market_id, submit=True)
    snx.wait(unwrap_tx)

    # get new balances
    unwrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    unwrapped_balance = format_wei(unwrapped_balance_wei, decimals)

    unwrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert unwrapped_balance == wrapped_balance + test_amount
    assert unwrapped_synth_balance == wrapped_synth_balance - test_amount


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("USDC", TEST_AMOUNT, 6),
    ],
)
def test_spot_atomic_order(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap USDC for sUSDC and commit an atomic order to sell for sUSD"""
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[f"s{token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]
    susd_token = snx.spot.markets_by_id[0]["contract"]

    # make sure we have some USDC
    starting_balance_wei = token.functions.balanceOf(snx.address).call()
    starting_balance = format_wei(starting_balance_wei, decimals)

    starting_synth_balance = snx.spot.get_balance(market_id=market_id)
    starting_susd_balance = snx.spot.get_balance(market_id=0)

    assert starting_balance > test_amount

    ## wrap
    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)

    if allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(test_amount, market_id=market_id, submit=True)
    snx.wait(wrap_tx)

    # get new balances
    wrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    wrapped_balance = format_wei(wrapped_balance_wei, decimals)

    wrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert wrapped_balance == starting_balance - test_amount
    assert wrapped_synth_balance == starting_synth_balance + test_amount

    ## sell for sUSD
    # check the allowance
    wrapped_allowance = snx.allowance(
        wrapped_token.address, snx.spot.market_proxy.address
    )

    if wrapped_allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            wrapped_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # atomic swap
    swap_tx = snx.spot.atomic_order(
        "sell", test_amount, market_id=market_id, submit=True
    )
    swap_receipt = snx.wait(swap_tx)

    assert swap_receipt is not None
    assert swap_receipt.status == 1

    # check balances
    swapped_balance_wei = token.functions.balanceOf(snx.address).call()
    swapped_balance = format_wei(swapped_balance_wei, decimals)

    swapped_synth_balance = snx.spot.get_balance(market_id=market_id)
    swapped_susd_balance = snx.spot.get_balance(market_id=0)

    assert swapped_balance == starting_balance - test_amount
    assert swapped_synth_balance == wrapped_synth_balance - test_amount
    assert swapped_susd_balance == starting_susd_balance + test_amount

    ## buy wrapped token back
    # check the allowance
    susd_allowance = snx.allowance(susd_token.address, snx.spot.market_proxy.address)

    if susd_allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            susd_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # atomic swap
    buy_tx = snx.spot.atomic_order(
        "buy",
        test_amount,
        market_id=market_id,
        submit=True,
    )
    buy_receipt = snx.wait(buy_tx)

    assert buy_receipt is not None
    assert buy_receipt.status == 1

    # check balances
    bought_balance_wei = token.functions.balanceOf(snx.address).call()
    bought_balance = format_wei(bought_balance_wei, decimals)

    bought_synth_balance = snx.spot.get_balance(market_id=market_id)
    bought_susd_balance = snx.spot.get_balance(market_id=0)

    assert bought_balance == swapped_balance
    assert bought_synth_balance == swapped_synth_balance + test_amount
    assert bought_susd_balance == swapped_susd_balance - test_amount

    ## unwrap
    # check the allowance
    wrapped_allowance = snx.allowance(
        wrapped_token.address, snx.spot.market_proxy.address
    )

    if wrapped_allowance < bought_synth_balance:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            wrapped_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    unwrap_tx = snx.spot.wrap(-test_amount, market_id=market_id, submit=True)
    unwrap_receipt = snx.wait(unwrap_tx)

    assert unwrap_tx is not None
    assert unwrap_receipt is not None
    assert unwrap_receipt.status == 1

    # get new balances
    unwrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    unwrapped_balance = format_wei(unwrapped_balance_wei, decimals)

    unwrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert unwrapped_balance == starting_balance
    assert unwrapped_synth_balance == bought_synth_balance - test_amount
