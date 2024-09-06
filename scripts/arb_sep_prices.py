import os
import click
from ape import accounts, networks, chain
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()


def main():
    # get the client
    snx = Synthetix(
        provider_rpc=os.getenv("NETWORK_421614_RPC"),
        private_key=os.getenv("PRIVATE_KEY"),
    )

    # update all of the prices
    pyth_contract = snx.contracts["Pyth"]["contract"]

    # get feed ids
    snx.logger.info(f"Updating feeds for {snx.pyth.price_feed_ids.keys()}")
    feed_ids = list(snx.pyth.price_feed_ids.values())

    pyth_response = snx.pyth.get_price_from_ids(feed_ids)
    price_update_data = pyth_response["price_update_data"]

    # create the tx
    tx_params = snx._get_tx_params(value=len(feed_ids))
    tx_params = pyth_contract.functions.updatePriceFeeds(
        price_update_data
    ).build_transaction(tx_params)

    # submit the tx
    tx_hash = snx.execute_transaction(tx_params)
    tx_receipt = snx.wait(tx_hash)
    snx.logger.info(f"Prices updated: {tx_receipt}")


if __name__ == "__main__":
    main()
