import os
import pandas as pd
from synthetix import Synthetix
from synthetix.utils.multicall import multicall_erc7412
from dotenv import load_dotenv

load_dotenv()

RPC = os.getenv("NETWORK_42161_RPC")


def get_account_ids(snx):
    """Fetch a list of accounts that have some collateral and have open positions"""
    account_proxy = snx.perps.account_proxy
    market_proxy = snx.perps.market_proxy

    # get the total number of accounts
    total_supply = account_proxy.functions.totalSupply().call()

    # fetch the account ids
    account_ids = []
    supply_chunks = [
        range(x, min(x + 500, total_supply)) for x in range(0, total_supply, 500)
    ]
    for supply_chunk in supply_chunks:
        accounts = multicall_erc7412(snx, account_proxy, "tokenByIndex", supply_chunk)
        account_ids.extend(accounts)

    return account_ids


def get_debts(snx, account_ids):
    # create chunks
    chunks = [account_ids[x : x + 500] for x in range(0, len(account_ids), 500)]

    # run a query for each chunk
    debts = []
    for chunk in chunks:
        fn_inputs = [(account_id,) for account_id in chunk]
        account_debt = multicall_erc7412(
            snx,
            snx.perps.market_proxy,
            "debt",
            fn_inputs,
        )
        account_debt = [x / 1e18 for x in account_debt]
        debts.extend(zip(chunk, account_debt))

    return debts


def main():
    snx = Synthetix(
        provider_rpc=RPC,
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "main",
        },
    )

    # get the contracts
    accounts = snx.contracts["perpsFactory"]["PerpsAccountProxy"]["contract"]
    perps = snx.perps.market_proxy

    # get all of the account ids
    account_ids = get_account_ids(snx)
    debts = get_debts(snx, account_ids)

    # convert to pandas and save to csv
    df_debts = pd.DataFrame(debts, columns=["account_id", "debt"])
    df_debts.to_csv("data/debts.csv", index=False)


if __name__ == "__main__":
    main()
