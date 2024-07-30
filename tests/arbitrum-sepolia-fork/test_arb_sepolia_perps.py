import pytest
import time
import math
from conftest import chain_fork
from ape import chain
from utils.chain_helpers import mine_block

# tests
MARKET_NAMES = [
    "ETH",
]
TEST_COLLATERAL_AMOUNT = 1000
TEST_POSITION_SIZE_USD = 500


def test_perps_module(snx):
    """The instance has a perps module"""
    assert snx.perps is not None
    assert snx.perps.market_proxy is not None
    assert snx.perps.account_proxy is not None
    assert snx.perps.account_ids is not None
    assert snx.perps.markets_by_id is not None
    assert snx.perps.markets_by_name is not None


@chain_fork
def test_perps_markets(snx):
    markets_by_id, markets_by_name = snx.perps.get_markets()

    snx.logger.info(f"Markets by id: {markets_by_id}")
    snx.logger.info(f"Markets by name: {markets_by_name}")

    assert markets_by_id is not None
    assert markets_by_name is not None

    for market in MARKET_NAMES:
        assert (
            market in markets_by_name
        ), f"Market {market} is missing in markets_by_name"

        market_summary = markets_by_name[market]
        assert market_summary["market_name"] == market
        assert market_summary["index_price"] > 0
        assert market_summary["feed_id"] is not None


@chain_fork
def test_perps_account_fetch(snx, perps_account_id):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    snx.logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}"
    )
    assert len(account_ids) > 0
    assert perps_account_id in account_ids


@chain_fork
def test_modify_collateral(snx, account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(account_id)
    susd_balance_start = snx.get_susd_balance()

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_COLLATERAL_AMOUNT, market_name="sUSD", account_id=account_id, submit=True
    )
    snx.wait(modify_tx)

    # check the result
    margin_info_end = snx.perps.get_margin_info(account_id)
    susd_balance_end = snx.get_susd_balance()

    assert (
        margin_info_end["total_collateral_value"]
        > margin_info_start["total_collateral_value"]
    )
    assert susd_balance_end["balance"] < susd_balance_start["balance"]
    assert (
        susd_balance_end["balance"]
        == susd_balance_start["balance"] - TEST_COLLATERAL_AMOUNT
    )


@chain_fork
@pytest.mark.parametrize(
    "market_name",
    MARKET_NAMES,
)
def test_account_flow(snx, perps_account_id, market_name):
    mine_block(snx, chain, seconds=0)

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the price
    index_price = snx.perps.markets_by_name[market_name]["index_price"]

    position_size = TEST_POSITION_SIZE_USD / index_price
    commit_tx = snx.perps.commit_order(
        position_size,
        market_name=market_name,
        account_id=perps_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt = snx.wait(commit_tx)
    assert commit_receipt["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain)
    settle_tx = snx.perps.settle_order(
        account_id=perps_account_id, max_tx_tries=5, submit=True
    )
    settle_receipt = snx.wait(settle_tx)

    # check the result
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=perps_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # get the position size
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=perps_account_id
    )
    size = position["position_size"]

    # commit order
    commit_tx_2 = snx.perps.commit_order(
        -size,
        market_name=market_name,
        account_id=perps_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_2 = snx.wait(commit_tx_2)
    assert commit_receipt_2["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain)
    settle_tx_2 = snx.perps.settle_order(
        account_id=perps_account_id, max_tx_tries=5, submit=True
    )
    settle_receipt_2 = snx.wait(settle_tx_2)

    # check the result
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=perps_account_id
    )
    assert position["position_size"] == 0

    # check the margin and withdraw
    margin_info = snx.perps.get_margin_info(perps_account_id)
    withdrawable_margin = margin_info["withdrawable_margin"]
    withdrawable_margin = math.floor(withdrawable_margin * 1e8) / 1e8

    modify_tx_2 = snx.perps.modify_collateral(
        -withdrawable_margin,
        market_name="sUSD",
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt_2 = snx.wait(modify_tx_2)
    assert modify_receipt_2["status"] == 1
