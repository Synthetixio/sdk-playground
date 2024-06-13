from conftest import chain_fork
from synthetix.utils import ether_to_wei, wei_to_ether

# tests


@chain_fork
def test_snx(snx):
    """The instance has a Synthetix instance"""
    assert snx is not None


@chain_fork
def test_contracts(contracts):
    """The instance has necessary contracts"""
    assert contracts["WETH"] is not None
    assert contracts["USDC"] is not None


@chain_fork
def test_wrap_eth(snx):
    """The instance can wrap ETH"""
    tx_hash_wrap = snx.wrap_eth(0.01, submit=True)
    tx_receipt_wrap = snx.wait(tx_hash_wrap)

    assert tx_hash_wrap is not None
    assert tx_receipt_wrap is not None
    assert tx_receipt_wrap.status == 1

    tx_hash_unwrap = snx.wrap_eth(-0.01, submit=True)
    tx_receipt_unwrap = snx.wait(tx_hash_unwrap)

    assert tx_hash_unwrap is not None
    assert tx_receipt_unwrap is not None
    assert tx_receipt_unwrap.status == 1
