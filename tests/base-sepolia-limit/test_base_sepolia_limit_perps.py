import pytest
import time
import math
from conftest import chain_fork
from ape import chain

# tests
MARKET_NAMES = [
    "ETH",
]
TEST_COLLATERAL_AMOUNT = 5000
TEST_POSITION_SIZE_USD = 500


def mine_block(snx, chain, seconds=3):
    time.sleep(seconds)
    timestamp = int(time.time())

    chain.mine(1, timestamp=timestamp)
    snx.logger.info(f"Block mined at timestamp {timestamp}")


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
def test_perps_owners(snx):
    account = snx.contracts["perpsFactory"]["PerpsAccountProxy"]["contract"]

    account_1 = 170141183460469231731687303715884105727
    account_2 = 170141183460469231731687303715884105728

    owner_1 = snx.perps.market_proxy.functions.getAccountOwner(
        account_1
    ).call()

    owner_2 = snx.perps.market_proxy.functions.getAccountOwner(
        account_2
    ).call()

    snx.logger.info(f"Owner 1: {owner_1} for account {account_1}")
    snx.logger.info(f"Owner 2: {owner_2} for account {account_2}")


@chain_fork
@pytest.mark.parametrize(
    "deliver_address",
    [
        "0xB484748E3e6406fB845dc06FED02D578533c45D7",
        "0xCf2E738a01E1977233353795168029FD7FE7A048",
    ],
)
def test_modify_collateral(snx, deliver_address, perps_account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(perps_account_id)
    susd_balance_start = snx.get_susd_balance()
    snx.logger.info(f"Starting sUSD balance: {susd_balance_start}")

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
        TEST_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=perps_account_id,
        submit=True,
    )
    snx.wait(modify_tx)

    # check the result
    margin_info_end = snx.perps.get_margin_info(perps_account_id)
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

    # # transfer the account
    # account = snx.contracts["perpsFactory"]["PerpsAccountProxy"]["contract"]

    # # approve the transfer
    # snx.logger.info(f"{account.functions.balanceOf(snx.address).call()}")
    # snx.logger.info(f"{account.functions.balanceOf(snx.address).call()}")

    # tx_params = snx._get_tx_params()
    # tx_params = account.functions.approve(
    #     snx.address, perps_account_id
    # ).build_transaction(tx_params)

    # tx_hash = snx.execute_transaction(tx_params)
    # tx_receipt = snx.wait(tx_hash)
    # assert tx_receipt.status == 1

    # # transfer the token
    # tx_params = snx._get_tx_params()
    # tx_params = account.functions.transferFrom(
    #     snx.address, deliver_address, perps_account_id
    # ).build_transaction(tx_params)

    # tx_hash = snx.execute_transaction(tx_params)
    # tx_receipt = snx.wait(tx_hash)
    # assert tx_receipt.status == 1
