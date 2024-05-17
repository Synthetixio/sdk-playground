import os
from dotenv import load_dotenv
from synthetix import Synthetix

# load environment variables
load_dotenv(override=True)

# initialize the client
snx = Synthetix(
    provider_rpc=os.getenv("PROVIDER_RPC"),
    private_key=os.getenv("PRIVATE_KEY"),
)


def main():
    # print information about the current state
    before_accounts = len(snx.perps.account_ids)
    snx.logger.info(f"{snx.address} owns {before_accounts} accounts")

    # create a perps account
    submit = False
    tx = snx.perps.create_account(submit=submit)

    if submit:
        # wait for the transaction to be mined
        receipt = snx.wait(tx)

        # fetch the account ids again to confirm the new account
        snx.perps.get_account_ids()
        after_accounts = len(snx.perps.account_ids)
        snx.logger.info(f"{snx.address} owns {after_accounts} accounts")
        if after_accounts - before_accounts == 1:
            snx.logger.info(f"account {snx.perps.account_ids[-1]} created")

    else:
        snx.logger.info(
            "Transaction not submitted. Set `submit=True` or sign this transaction offline."
        )
        snx.logger.info(tx)


if __name__ == "__main__":
    main()
