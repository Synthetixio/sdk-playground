from conftest import chain_fork

# tests
ETH_LP_AMOUNT = 10


@chain_fork
def test_snx_lite(snx_lite):
    """The instance has a Synthetix lite instance"""
    assert snx_lite is not None


@chain_fork
def test_delegate(snx_lite):
    """The instance can delegate collateral"""
    # set snx
    snx = snx_lite

    # set up token contracts
    token = snx.contracts["WETH"]["contract"]
    token_decimals = token.functions.decimals().call()

    susd = snx.contracts["system"]["USDProxy"]["contract"]
    susd_decimals = susd.functions.decimals().call()

    # get an account
    create_account_tx = snx.core.create_account(submit=True)
    snx.wait(create_account_tx)
    new_account_id = snx.core.account_ids[-1]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < ETH_LP_AMOUNT:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        ETH_LP_AMOUNT,
        decimals=token_decimals,
        account_id=new_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        ETH_LP_AMOUNT,
        1,
        account_id=new_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)
    assert delegate_tx_receipt.status == 1
