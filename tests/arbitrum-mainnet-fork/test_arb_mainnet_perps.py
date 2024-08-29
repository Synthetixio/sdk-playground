import pytest
import time
import math
from conftest import chain_fork, liquidation_setup
from ape import chain
from utils.chain_helpers import mine_block

# tests
MARKET_NAMES = [
    "ETH",
    "BTC",
    "SOL",
    "WIF",
]
TEST_USD_COLLATERAL_AMOUNT = 1000
TEST_ETH_COLLATERAL_AMOUNT = 0.5
TEST_BTC_COLLATERAL_AMOUNT = 0.01
TEST_POSITION_SIZE_USD = 50


@chain_fork
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
@pytest.mark.parametrize(
    "collateral_name, collateral_amount",
    [
        ("sUSD", TEST_USD_COLLATERAL_AMOUNT),
        # ("sBTC", TEST_BTC_COLLATERAL_AMOUNT),
        ("sETH", TEST_ETH_COLLATERAL_AMOUNT),
    ],
)
def test_modify_collateral(
    snx, contracts, perps_account_id, collateral_name, collateral_amount
):
    """Test modify collateral"""
    # get collateral market id
    collateral_id, collateral_name = snx.spot._resolve_market(
        market_id=None, market_name=collateral_name
    )

    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(perps_account_id)
    susd_balance_start = snx.get_susd_balance()

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name=collateral_name
    )
    if allowance < collateral_amount:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name=collateral_name, submit=True
        )
        snx.wait(approve_tx)

    # if not sUSD, wrap the asset first
    if collateral_name != "sUSD":
        # get the token
        token_name = collateral_name[1:] if collateral_name != "sETH" else "WETH"
        token = contracts[token_name]

        # check the allowance
        allowance = snx.allowance(token.address, snx.spot.market_proxy.address)
        if allowance < collateral_amount:
            # approve
            approve_tx = snx.approve(
                token.address, snx.spot.market_proxy.address, submit=True
            )
            snx.wait(approve_tx)

        wrap_tx = snx.spot.wrap(
            collateral_amount, market_name=collateral_name, submit=True
        )
        wrap_receipt = snx.wait(wrap_tx)
        assert wrap_receipt.status == 1

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        market_name=collateral_name,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the result
    margin_info_end = snx.perps.get_margin_info(perps_account_id)

    assert (
        margin_info_end["total_collateral_value"]
        > margin_info_start["total_collateral_value"]
    )
    assert margin_info_end["collateral_balances"][collateral_id] == collateral_amount

    # modify collateral
    modify_tx_2 = snx.perps.modify_collateral(
        -collateral_amount,
        market_name=collateral_name,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt_2 = snx.wait(modify_tx_2)
    assert modify_receipt_2["status"] == 1

    # check the result
    margin_info_final = snx.perps.get_margin_info(perps_account_id)

    assert margin_info_final["total_collateral_value"] == 0
    assert margin_info_final["collateral_balances"] == {}


@chain_fork
@pytest.mark.parametrize(
    "market_name, collateral_name, collateral_amount",
    [
        ("ETH", "sUSD", TEST_USD_COLLATERAL_AMOUNT),
        ("BTC", "sUSD", TEST_USD_COLLATERAL_AMOUNT),
        # ("SOL", "sUSD", TEST_USD_COLLATERAL_AMOUNT),
        # ("WIF", "sUSD", TEST_USD_COLLATERAL_AMOUNT),
    ],
)
def test_usd_account_flow(
    snx, perps_account_id, market_name, collateral_name, collateral_amount
):
    # get block and print
    block = snx.web3.eth.get_block("latest")
    susd_balance = snx.get_susd_balance()

    snx.logger.info(f"Block: {block.number} - sUSD balance: {susd_balance}")

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name=collateral_name
    )
    if allowance < collateral_amount:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name=collateral_name, submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        market_name=collateral_name,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1
    snx.logger.info(snx.perps.get_margin_info(perps_account_id))

    # get an updated price
    index_price = snx.perps.markets_by_name[market_name]["index_price"]

    # commit order
    mine_block(snx, chain)
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
    mine_block(snx, chain)
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
        withdrawable_margin,
        market_name=collateral_name,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt_2 = snx.wait(modify_tx_2)
    assert modify_receipt_2["status"] == 1


@chain_fork
@pytest.mark.parametrize(
    "market_name, collateral_name, collateral_amount",
    [
        ("ETH", "stBTC", TEST_BTC_COLLATERAL_AMOUNT),
        ("ETH", "sETH", TEST_ETH_COLLATERAL_AMOUNT),
    ],
)
def test_alt_account_flow(
    snx, contracts, perps_account_id, market_name, collateral_name, collateral_amount
):
    # get the token
    token_name = collateral_name[1:] if collateral_name != "sETH" else "WETH"
    token = contracts[token_name]

    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)
    if allowance < collateral_amount:
        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        approve_receipt = snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(collateral_amount, market_name=collateral_name, submit=True)
    wrap_receipt = snx.wait(wrap_tx)
    assert wrap_receipt.status == 1

    # check allowances
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name=collateral_name
    )
    if allowance < collateral_amount:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name=collateral_name, submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        collateral_amount,
        market_name=collateral_name,
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the price
    index_price = snx.perps.markets_by_name[market_name]["index_price"]

    # commit order
    mine_block(snx, chain)
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
    mine_block(snx, chain)
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

    # check debt and repay
    debt = snx.perps.get_margin_info(perps_account_id)["debt"]
    if debt > 0:
        # check allowance
        allowance_usd = snx.spot.get_allowance(
            snx.perps.market_proxy.address, market_id=0
        )
        if allowance_usd < debt:
            approve_usd_tx = snx.spot.approve(
                snx.perps.market_proxy.address, market_id=0, submit=True
            )
            snx.wait(approve_usd_tx)

        # pay debt
        mine_block(snx, chain)
        paydebt_tx = snx.perps.pay_debt(
            account_id=perps_account_id,
            submit=True,
        )
        paydebt_receipt = snx.wait(paydebt_tx)
        assert paydebt_receipt["status"] == 1

    # check the margin and withdraw
    margin_info = snx.perps.get_margin_info(perps_account_id)
    snx.logger.info(f"Margin info: {margin_info}")

    # withdraw for each collateral type
    for collateral_id, collateral_amount in margin_info["collateral_balances"].items():
        if collateral_amount > 0:
            withdrawal_amount = math.floor(collateral_amount * 1e8) / 1e8
            modify_tx = snx.perps.modify_collateral(
                -withdrawal_amount,
                market_id=collateral_id,
                account_id=perps_account_id,
                submit=True,
            )
            modify_receipt = snx.wait(modify_tx)
            snx.logger.info(f"Modify receipt: {modify_receipt}")

            if modify_receipt["status"] != 1:
                # trace the failed transaction
                chain_receipt = chain.get_receipt(modify_tx)
                snx.logger.info(f"{chain_receipt.show_trace()}")
            assert modify_receipt["status"] == 1


@chain_fork
@pytest.mark.parametrize(
    ["market_1", "market_2"],
    [
        ("ETH", "BTC"),
    ],
)
def test_multiple_positions(snx, perps_account_id, market_1, market_2):
    mine_block(snx, chain)

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_USD_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_USD_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    ## order 1
    # check the price
    index_price_1 = snx.perps.markets_by_name[market_1]["index_price"]

    # commit order
    position_size_1 = TEST_POSITION_SIZE_USD / index_price_1
    commit_tx_1 = snx.perps.commit_order(
        position_size_1,
        market_name=market_1,
        account_id=perps_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_1 = snx.wait(commit_tx_1)
    assert commit_receipt_1["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain)
    settle_tx_1 = snx.perps.settle_order(
        account_id=perps_account_id, max_tx_tries=5, submit=True
    )
    settle_receipt_1 = snx.wait(settle_tx_1)

    ## order 2
    # check the price
    index_price_2 = snx.perps.markets_by_name[market_2]["index_price"]

    # commit order
    position_size_2 = TEST_POSITION_SIZE_USD / index_price_2
    commit_tx_2 = snx.perps.commit_order(
        position_size_2,
        market_name=market_2,
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

    # get the position sizes
    positions = snx.perps.get_open_positions(account_id=perps_account_id)
    size_1 = positions[market_1]["position_size"]
    size_2 = positions[market_2]["position_size"]
    assert round(size_1, 12) == round(position_size_1, 12)
    assert round(size_2, 12) == round(position_size_2, 12)

    ## order 1
    # commit order
    commit_tx_3 = snx.perps.commit_order(
        -size_1,
        market_name=market_1,
        account_id=perps_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_3 = snx.wait(commit_tx_3)
    assert commit_receipt_3["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain)
    settle_tx_3 = snx.perps.settle_order(
        account_id=perps_account_id, max_tx_tries=5, submit=True
    )
    settle_receipt_3 = snx.wait(settle_tx_3)

    ## order 2
    # commit order
    commit_tx_4 = snx.perps.commit_order(
        -size_2,
        market_name=market_2,
        account_id=perps_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_4 = snx.wait(commit_tx_4)
    assert commit_receipt_4["status"] == 1

    # wait for the order settlement
    mine_block(snx, chain)
    settle_tx_4 = snx.perps.settle_order(
        account_id=perps_account_id, max_tx_tries=5, submit=True
    )
    settle_receipt_4 = snx.wait(settle_tx_4)

    # check the result
    positions = snx.perps.get_open_positions(account_id=perps_account_id)
    assert market_1 not in positions
    assert market_2 not in positions


@chain_fork
def test_usd_liquidation(snx, perps_account_id):
    market_name = "ETH"
    market_id, market_name = snx.perps._resolve_market(None, market_name)
    mine_block(snx, chain)

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_USD_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_USD_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=perps_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the price
    index_price = snx.perps.markets_by_name[market_name]["index_price"]

    position_size = (TEST_USD_COLLATERAL_AMOUNT * 2) / index_price
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
    assert settle_receipt["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=perps_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # set the liquidation parameters
    liquidation_setup(snx, market_id)

    # liquidate the account
    liquidate_tx = snx.perps.liquidate(perps_account_id, submit=True)
    liquidate_receipt = snx.wait(liquidate_tx)
    assert liquidate_receipt["status"] == 1


@chain_fork
def test_alts_liquidation(snx, contracts, perps_account_id):
    perps_market_name = "ETH"
    perps_market_id, perps_market_name = snx.perps._resolve_market(
        None, perps_market_name
    )

    # deposit both ETH and BTC
    collaterals = [
        {
            "market_name": "ETH",
            "token_name": "WETH",
            "collateral_amount": TEST_ETH_COLLATERAL_AMOUNT,
        },
        {
            "market_name": "tBTC",
            "token_name": "tBTC",
            "collateral_amount": TEST_BTC_COLLATERAL_AMOUNT,
        },
    ]
    for collateral in collaterals:
        token_name = collateral["token_name"]
        market_name = collateral["market_name"]
        wrapped_token_name = f"s{market_name}"
        collateral_amount = collateral["collateral_amount"]

        token = contracts[token_name]

        # check spot market allowance
        allowance = snx.allowance(token.address, snx.spot.market_proxy.address)
        if allowance < collateral_amount:
            # approve
            approve_tx = snx.approve(
                token.address, snx.spot.market_proxy.address, submit=True
            )
            approve_receipt = snx.wait(approve_tx)
            assert approve_receipt.status == 1

        wrap_tx = snx.spot.wrap(
            collateral_amount, market_name=wrapped_token_name, submit=True
        )
        wrap_receipt = snx.wait(wrap_tx)
        if wrap_receipt.status != 1:
            chain_receipt = chain.get_receipt(wrap_tx)
            snx.logger.info(f"{chain_receipt.show_trace()}")
        assert wrap_receipt.status == 1

        # check perps market allowance
        allowance = snx.spot.get_allowance(
            snx.perps.market_proxy.address, market_name=wrapped_token_name
        )
        if allowance < collateral_amount:
            approve_tx = snx.spot.approve(
                snx.perps.market_proxy.address,
                market_name=wrapped_token_name,
                submit=True,
            )
            snx.wait(approve_tx)

        # deposit collateral
        modify_tx = snx.perps.modify_collateral(
            collateral_amount,
            market_name=wrapped_token_name,
            account_id=perps_account_id,
            submit=True,
        )
        modify_receipt = snx.wait(modify_tx)
        assert modify_receipt["status"] == 1

    # check the price
    index_price = snx.perps.markets_by_name[perps_market_name]["index_price"]

    mine_block(snx, chain)
    position_size = (TEST_ETH_COLLATERAL_AMOUNT * 5) / index_price
    commit_tx = snx.perps.commit_order(
        position_size,
        market_name=perps_market_name,
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
    assert settle_receipt["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_name=perps_market_name, account_id=perps_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # set the liquidation parameters
    liquidation_setup(snx, perps_market_id)

    # liquidate the account
    liquidate_tx = snx.perps.liquidate(perps_account_id, submit=True)
    liquidate_receipt = snx.wait(liquidate_tx)
    assert liquidate_receipt["status"] == 1

    # log the RewardDistributed events
    reward_events = snx.core.core_proxy.events.RewardsDistributed().process_receipt(
        liquidate_receipt
    )
    assert len(reward_events) >= 1
    for event in reward_events:
        snx.logger.info(event)
