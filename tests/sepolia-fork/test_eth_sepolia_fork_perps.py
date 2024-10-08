import pytest
import math
from conftest import chain_fork, mine_block, liquidation_setup
from ape import chain

# tests
MARKET_ID = 3
MARKET_NAMES = [
    "ETHPERP",
]
ASSET_NAMES = [
    "ETH",
]
TEST_USD_COLLATERAL_AMOUNT = 20000
TEST_ETH_COLLATERAL_AMOUNT = 5
TEST_POSITION_SIZE_USD = 10000


def test_perps_module(snx):
    """The instance has a perps module"""
    assert snx.perps is not None
    assert snx.perps.market_proxy is not None
    assert snx.perps.account_proxy is not None
    assert snx.perps.account_ids is not None
    assert snx.perps.markets_by_id is not None
    assert snx.perps.markets_by_name is not None


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
        assert market_summary["oracle_price"] > 0


def test_perps_account_fetch(snx, perps_account_id):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    snx.logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}"
    )
    assert len(account_ids) > 0


@pytest.mark.parametrize(
    "collateral_name, collateral_amount",
    [
        ("sUSD", TEST_USD_COLLATERAL_AMOUNT),
        ("WETH", TEST_ETH_COLLATERAL_AMOUNT),
    ],
)
def test_modify_collateral(
    snx, contracts, perps_account_id, collateral_name, collateral_amount
):
    """Test modify collateral"""
    # get the collateral
    collateral = contracts[collateral_name]
    collateral_address = collateral.address
    snx.logger.info(f"Collateral: {collateral_name} - {collateral_address}")

    # get starting collateral and sUSD balance
    snx.logger.info(f"Account: {perps_account_id}")
    margin_info_start = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)
    collateral_balance_start = collateral.functions.balanceOf(snx.address).call() / 1e18
    snx.logger.info(f"Margin: {margin_info_start}")
    snx.logger.info(f"{collateral_name} balance: {collateral_balance_start}")

    # check allowance
    allowance = snx.allowance(collateral_address, snx.perps.market_proxy.address)
    if allowance < collateral_amount:
        approve_tx = snx.approve(
            collateral_address, snx.perps.market_proxy.address, submit=True
        )
        approve_receipt = snx.wait(approve_tx)
        assert approve_receipt["status"] == 1

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        collateral_address=collateral_address,
        market_id=MARKET_ID,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the result
    margin_info_end = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)

    assert margin_info_end["collateral_usd"] > margin_info_start["collateral_usd"]
    snx.logger.info(f"Margin: {margin_info_end}")
    assert (
        margin_info_end["collateral_balances"][collateral_address]["available"]
        == collateral_amount
    )

    # modify collateral
    modify_tx_2 = snx.perps.modify_collateral(
        -collateral_amount,
        collateral_address=collateral_address,
        market_id=MARKET_ID,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt_2 = snx.wait(modify_tx_2)
    assert modify_receipt_2["status"] == 1

    # check the result
    margin_info_final = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)

    assert margin_info_final["collateral_usd"] == 0
    assert (
        margin_info_final["collateral_balances"][collateral_address]["available"] == 0
    )
    snx.logger.info(f"Margin: {margin_info_final}")


@chain_fork
@pytest.mark.parametrize(
    "collateral_name, collateral_amount",
    [
        ("sUSD", TEST_USD_COLLATERAL_AMOUNT),
        ("WETH", TEST_ETH_COLLATERAL_AMOUNT),
    ],
)
def test_account_flow(
    snx, contracts, perps_account_id, collateral_name, collateral_amount
):
    # mine a block
    mine_block(snx, chain)

    # get the collateral
    collateral = contracts[collateral_name]
    collateral_address = collateral.address
    pyth_feed_id = snx.perps.markets_by_id[MARKET_ID]["feed_id"]

    # check allowance
    allowance = snx.allowance(collateral_address, snx.perps.market_proxy.address)
    if allowance < collateral_amount:
        approve_tx = snx.approve(
            collateral_address, snx.perps.market_proxy.address, submit=True
        )
        approve_receipt = snx.wait(approve_tx)
        assert approve_receipt["status"] == 1

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        collateral_address=collateral_address,
        market_id=MARKET_ID,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    margin_info = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)
    snx.logger.info(f"Margin: {margin_info}")

    # check the price
    pyth_data = snx.pyth.get_price_from_ids([pyth_feed_id])
    oracle_price = pyth_data["meta"][pyth_feed_id]["price"]

    # commit order
    position_size = TEST_POSITION_SIZE_USD / oracle_price
    limit_price = oracle_price * 1.01

    commit_tx = snx.perps.commit_order(
        position_size,
        market_id=MARKET_ID,
        limit_price=limit_price,
        account_id=perps_account_id,
        submit=True,
    )
    commit_receipt = snx.wait(commit_tx)
    assert commit_receipt["status"] == 1

    # check the order
    order = snx.perps.get_order(perps_account_id, market_id=MARKET_ID)
    snx.logger.info(f"Order: {order}")

    # wait for the order settlement
    mine_block(snx, chain, seconds=15)
    settle_tx = snx.perps.settle_order(
        account_id=perps_account_id, market_id=MARKET_ID, submit=True
    )
    settle_receipt = snx.wait(settle_tx)
    assert settle_receipt["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_id=MARKET_ID, account_id=perps_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # check the price
    mine_block(snx, chain)
    pyth_data = snx.pyth.get_price_from_ids([pyth_feed_id])
    oracle_price = pyth_data["meta"][pyth_feed_id]["price"]

    # commit order
    limit_price = oracle_price * 0.99
    size = -position["position_size"]
    commit_tx_2 = snx.perps.commit_order(
        size,
        market_id=MARKET_ID,
        limit_price=limit_price,
        account_id=perps_account_id,
        submit=True,
    )
    commit_receipt_2 = snx.wait(commit_tx_2)
    assert commit_receipt_2["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain, seconds=15)
    settle_tx_2 = snx.perps.settle_order(
        account_id=perps_account_id, market_id=MARKET_ID, submit=True
    )
    settle_receipt_2 = snx.wait(settle_tx_2)
    assert settle_receipt_2["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_id=MARKET_ID, account_id=perps_account_id
    )
    assert position["position_size"] == 0

    # pay down any debt
    margin_info = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)
    debt = margin_info["debt_usd"]
    if debt > 0:
        # check allowance
        allowance_usd = snx.spot.get_allowance(
            snx.perps.market_proxy.address, market_id=0
        )
        if allowance_usd < debt:
            approve_usd_tx = snx.spot.approve(
                snx.perps.market_proxy.address, market_id=0, submit=True
            )
            approve_usd_receipt = snx.wait(approve_usd_tx)
            assert approve_usd_receipt["status"] == 1

        # pay debt
        paydebt_tx = snx.perps.pay_debt(
            account_id=perps_account_id,
            market_id=MARKET_ID,
            submit=True,
        )
        paydebt_receipt = snx.wait(paydebt_tx)
        assert paydebt_receipt["status"] == 1

    # modify collateral
    margin_info = snx.perps.get_margin_info(perps_account_id, market_id=MARKET_ID)
    withdraw_amount = margin_info["collateral_balances"][collateral_address][
        "available"
    ]
    modify_tx_2 = snx.perps.modify_collateral(
        -withdraw_amount,
        collateral_address=collateral_address,
        market_id=MARKET_ID,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt_2 = snx.wait(modify_tx_2)
    assert modify_receipt_2["status"] == 1


@chain_fork
@pytest.mark.parametrize(
    "collateral_name, collateral_amount",
    [
        ("sUSD", TEST_USD_COLLATERAL_AMOUNT),
        ("WETH", TEST_ETH_COLLATERAL_AMOUNT),
    ],
)
# @pytest.mark.skip
def test_liquidation(
    snx, contracts, perps_account_id, collateral_name, collateral_amount
):
    # mine a block
    mine_block(snx, chain)

    # get the collateral
    collateral = contracts[collateral_name]
    collateral_address = collateral.address
    pyth_feed_id = snx.perps.markets_by_id[MARKET_ID]["feed_id"]

    # check allowance
    allowance = snx.allowance(collateral_address, snx.perps.market_proxy.address)
    if allowance < collateral_amount:
        approve_tx = snx.approve(
            collateral_address, snx.perps.market_proxy.address, submit=True
        )
        approve_receipt = snx.wait(approve_tx)
        assert approve_receipt["status"] == 1

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        collateral_address=collateral_address,
        market_id=MARKET_ID,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the price
    pyth_data = snx.pyth.get_price_from_ids([pyth_feed_id])
    oracle_price = pyth_data["meta"][pyth_feed_id]["price"]

    # commit order
    position_size = TEST_ETH_COLLATERAL_AMOUNT * 5
    limit_price = oracle_price * 1.01

    commit_tx = snx.perps.commit_order(
        position_size,
        market_id=MARKET_ID,
        limit_price=limit_price,
        account_id=perps_account_id,
        submit=True,
    )
    commit_receipt = snx.wait(commit_tx)
    assert commit_receipt["status"] == 1

    # check the order
    order = snx.perps.get_order(perps_account_id, market_id=MARKET_ID)
    snx.logger.info(f"Order: {order}")

    # wait for the order settlement
    mine_block(snx, chain, seconds=15)
    settle_tx = snx.perps.settle_order(
        account_id=perps_account_id, market_id=MARKET_ID, submit=True
    )
    settle_receipt = snx.wait(settle_tx)
    assert settle_receipt["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_id=MARKET_ID, account_id=perps_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # check account is liquidatable before
    liquidatable_before = snx.perps.get_can_liquidate(
        account_id=perps_account_id, market_id=MARKET_ID
    )
    assert liquidatable_before["is_margin_liquidatable"] == False
    assert liquidatable_before["is_position_liquidatable"] == False

    # set up liquidation
    liquidation_setup(snx, MARKET_ID)
    mine_block(snx, chain)

    # check account is liquidatable after
    liquidatable_after = snx.perps.get_can_liquidate(
        account_id=perps_account_id, market_id=MARKET_ID
    )
    assert liquidatable_after["is_position_liquidatable"] == True
    snx.logger.info(f"Liquidatable: {liquidatable_after}")

    # flag the account
    mine_block(snx, chain)
    flag_tx = snx.perps.flag(
        account_id=perps_account_id, market_id=MARKET_ID, submit=True
    )
    flag_receipt = snx.wait(flag_tx)
    assert flag_receipt["status"] == 1

    # liquidate the account
    mine_block(snx, chain)
    liquidate_tx = snx.perps.liquidate(
        account_id=perps_account_id, market_id=MARKET_ID, submit=True
    )
    liquidate_receipt = snx.wait(liquidate_tx)
    assert liquidate_receipt["status"] == 1

    position = snx.perps.get_open_position(
        market_id=MARKET_ID, account_id=perps_account_id
    )
    assert position["position_size"] == 0
