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
    assert contracts["SNX"] is not None
    assert contracts["sUSD"] is not None
