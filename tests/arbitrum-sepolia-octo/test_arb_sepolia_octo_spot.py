import time
import pytest
from synthetix.utils import ether_to_wei, wei_to_ether, format_wei
from ape import chain

# constants
TEST_AMOUNT = 0.01


# tests
def test_spot_module(snx):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None


def test_spot_markets(snx):
    """The instance has spot markets"""
    snx.logger.info(f"Markets: {snx.spot.markets_by_name}")
    assert snx.spot.markets_by_name is not None
    assert len(snx.spot.markets_by_name) == len(snx.spot.markets_by_id)
    assert "sUSD" in snx.spot.markets_by_name
    assert "sETH" in snx.spot.markets_by_name
    assert "sBTC" in snx.spot.markets_by_name


@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        # ("WETH", TEST_AMOUNT, 18),
        ("BTC", TEST_AMOUNT, 18),
    ],
)
def test_spot_wrapper(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap and unwrap an asset"""
    wrapped_token_name = 'sETH' if token_name == 'WETH' else f's{token_name}'
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[wrapped_token_name]["market_id"]
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
    wrap_receipt = snx.wait(wrap_tx)
    assert wrap_receipt.status == 1

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
    unwrap_receipt = snx.wait(unwrap_tx)
    assert unwrap_receipt.status == 1


@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        # ("WETH", TEST_AMOUNT, 18),
        ("BTC", TEST_AMOUNT, 18),
    ],
)
def test_spot_atomic_order(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap USDC for sUSDC and commit an atomic order to sell for sUSD"""
    wrapped_token_name = "sETH" if token_name == "WETH" else f"s{token_name}"
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[wrapped_token_name]["market_id"]
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
    wrap_receipt = snx.wait(wrap_tx)
    assert wrap_receipt.status == 1

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
        "sell", test_amount, slippage_tolerance=0.001, market_id=market_id, submit=True
    )
    swap_receipt = snx.wait(swap_tx)

    assert swap_receipt is not None
    assert swap_receipt.status == 1
