from conftest import chain_fork

# tests


@chain_fork
def test_snx(snx):
    """The instance has a Synthetix instance"""
    assert snx is not None


@chain_fork
def test_contracts(contracts):
    """The instance has necessary contracts"""
    assert contracts["WETH"] is not None
    # assert contracts["USDC"] is not None
    # assert contracts["ARB"] is not None
    # assert contracts["USDe"] is not None
