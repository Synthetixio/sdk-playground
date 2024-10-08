import time
import pytest
from synthetix.utils import ether_to_wei, wei_to_ether, format_wei
from conftest import chain_fork
from ape import chain
from utils.chain_helpers import mine_block

# constants
TEST_USD_AMOUNT = 100
TEST_ETH_AMOUNT = 1
TEST_BTC_AMOUNT = 0.25
TEST_SOL_AMOUNT = 10


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
        ("USDC", TEST_USD_AMOUNT, 6),
        ("WETH", TEST_ETH_AMOUNT, 18),
        ("BTC", TEST_BTC_AMOUNT, 18),
        ("USDe", TEST_USD_AMOUNT, 18),
        ("SOL", TEST_SOL_AMOUNT, 18),
    ],
)
def test_spot_wrapper(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap and unwrap an asset"""
    token = contracts[token_name]
    wrapped_token_name = "ETH" if token_name == "WETH" else token_name
    market_id = snx.spot.markets_by_name[f"s{wrapped_token_name}"]["market_id"]
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
    unwrap_receipt = snx.wait(unwrap_tx)
    assert unwrap_receipt.status == 1

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
        ("USDC", TEST_USD_AMOUNT, 6),
    ],
)
def test_spot_async_order(snx, contracts, token_name, test_amount, decimals):
    """The instance can wrap USDC for sUSDC and commit an async order to sell for sUSD"""
    token = contracts[token_name]
    wrapped_token_name = "ETH" if token_name == "WETH" else token_name
    market_id = snx.spot.markets_by_name[f"s{wrapped_token_name}"]["market_id"]

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

    # check balances
    wrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    wrapped_balance = format_wei(wrapped_balance_wei, decimals)

    wrapped_synth_balance = snx.spot.get_balance(market_id=market_id)
    wrapped_susd_balance = snx.spot.get_balance(market_id=0)

    assert wrapped_balance == starting_balance - test_amount
    assert wrapped_synth_balance == starting_synth_balance + test_amount
    assert wrapped_susd_balance == starting_susd_balance

    ## sell it
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

    # commit order
    mine_block(snx, chain)
    commit_tx = snx.spot.commit_order(
        "sell",
        test_amount,
        slippage_tolerance=0.001,
        market_id=market_id,
        submit=True,
    )
    commit_receipt = snx.wait(commit_tx)

    assert commit_tx is not None
    assert commit_receipt is not None
    assert commit_receipt.status == 1

    # get the event to check the order id
    event_data = snx.spot.market_proxy.events.OrderCommitted().process_receipt(
        commit_receipt
    )
    assert len(event_data) == 1

    # unpack the event
    event = event_data[0]["args"]
    async_order_id = event["asyncOrderId"]

    # settle the order
    mine_block(snx, chain)
    snx.logger.info(f"Settling order {async_order_id} {event}")
    settle_tx = snx.spot.settle_order(async_order_id, market_id=market_id, submit=True)
    settle_receipt = snx.wait(settle_tx)

    assert settle_tx is not None
    assert settle_receipt is not None

    # check balances
    sold_balance_wei = token.functions.balanceOf(snx.address).call()
    sold_balance = format_wei(sold_balance_wei, decimals)

    sold_synth_balance = snx.spot.get_balance(market_id=market_id)
    sold_susd_balance = snx.spot.get_balance(market_id=0)

    assert sold_balance == wrapped_balance
    assert sold_synth_balance >= wrapped_synth_balance - test_amount - 1
    assert sold_susd_balance >= wrapped_susd_balance

    ## buy it back
    # check the allowance
    sold_allowance = snx.allowance(susd_token.address, snx.spot.market_proxy.address)

    if sold_allowance < test_amount:
        # reset nonce manually to avoid nonce issues
        snx.nonce = snx.web3.eth.get_transaction_count(snx.address)

        # approve
        approve_tx = snx.approve(
            susd_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # commit order
    mine_block(snx, chain)
    commit_buy_tx = snx.spot.commit_order(
        "buy",
        test_amount - 1,
        slippage_tolerance=0.001,
        market_id=market_id,
        submit=True,
    )
    commit_buy_receipt = snx.wait(commit_buy_tx)

    # get the event to check the order id
    event_data_buy = snx.spot.market_proxy.events.OrderCommitted().process_receipt(
        commit_buy_receipt
    )
    assert len(event_data_buy) == 1

    # unpack the event
    event_buy = event_data_buy[0]["args"]
    async_order_id_buy = event_buy["asyncOrderId"]

    # settle the order
    mine_block(snx, chain)
    settle_buy_tx = snx.spot.settle_order(
        async_order_id_buy, market_id=market_id, submit=True
    )
    settle_buy_receipt = snx.wait(settle_buy_tx)

    assert settle_buy_tx is not None
    assert settle_buy_receipt is not None

    # check balances
    buy_balance_wei = token.functions.balanceOf(snx.address).call()
    buy_balance = format_wei(buy_balance_wei, decimals)

    buy_synth_balance = snx.spot.get_balance(market_id=market_id)
    buy_susd_balance = snx.spot.get_balance(market_id=0)

    assert buy_balance == sold_balance
    assert buy_synth_balance >= sold_synth_balance + test_amount - 3
    assert buy_susd_balance >= sold_susd_balance - test_amount

    ## unwrap
    unwrap_tx = snx.spot.wrap(-test_amount + 2, market_id=market_id, submit=True)
    unwrap_receipt = snx.wait(unwrap_tx)

    assert unwrap_tx is not None
    assert unwrap_receipt is not None
    assert unwrap_receipt.status == 1

    # get new balances
    unwrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    unwrapped_balance = format_wei(unwrapped_balance_wei, decimals)

    unwrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert unwrapped_balance == starting_balance - 2
    assert unwrapped_synth_balance >= buy_synth_balance - test_amount - 1


@chain_fork
@pytest.mark.parametrize(
    "token_name, test_amount, decimals, slippage_tolerance",
    [
        ("USDC", TEST_USD_AMOUNT, 6, 0.002),
        ("USDe", TEST_USD_AMOUNT, 18, 0.05),
        ("WETH", TEST_ETH_AMOUNT, 18, 0.05),
        ("BTC", TEST_BTC_AMOUNT, 18, 0.05),
        ("SOL", TEST_SOL_AMOUNT, 18, 0.05),
    ],
)
def test_spot_atomic_order(
    snx, contracts, token_name, test_amount, decimals, slippage_tolerance
):
    """The instance can wrap USDC for sUSDC and commit an atomic order to sell for sUSD"""
    token = contracts[token_name]
    wrapped_token_name = "ETH" if token_name == "WETH" else token_name
    market_id = snx.spot.markets_by_name[f"s{wrapped_token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]
    susd_token = snx.spot.markets_by_id[0]["contract"]

    # get the price
    feed_id = snx.pyth.price_feed_ids[wrapped_token_name]
    price_data = snx.pyth.get_price_from_ids([feed_id])
    price = price_data["meta"][feed_id]["price"]
    snx.logger.info(f"Price {price}")

    # check asset balances
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
        "sell",
        test_amount,
        slippage_tolerance=slippage_tolerance,
        market_id=market_id,
        submit=True,
    )
    swap_receipt = snx.wait(swap_tx)

    assert swap_receipt is not None
    assert swap_receipt.status == 1

    # check balances
    swapped_balance_wei = token.functions.balanceOf(snx.address).call()
    swapped_balance = format_wei(swapped_balance_wei, decimals)

    swapped_synth_balance = snx.spot.get_balance(market_id=market_id)
    swapped_susd_balance = snx.spot.get_balance(market_id=0)

    # assert swapped_balance == starting_balance - test_amount
    # assert swapped_synth_balance == wrapped_synth_balance - test_amount
    # assert swapped_susd_balance > starting_susd_balance + (test_amount * 0.999)

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
        test_amount * price,
        slippage_tolerance=slippage_tolerance,
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

    # assert bought_balance == swapped_balance
    # assert bought_synth_balance >= swapped_synth_balance + test_amount
    # assert bought_susd_balance == 0

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

    unwrap_tx = snx.spot.wrap(-test_amount * 0.95, market_id=market_id, submit=True)
    unwrap_receipt = snx.wait(unwrap_tx)

    assert unwrap_tx is not None
    assert unwrap_receipt is not None
    assert unwrap_receipt.status == 1

    # get new balances
    unwrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    unwrapped_balance = format_wei(unwrapped_balance_wei, decimals)

    unwrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    # assert unwrapped_balance == starting_balance
    # assert unwrapped_synth_balance == bought_synth_balance - test_amount
