import click
import re
from functools import wraps
from ape import accounts, networks, chain, Contract
from synthetix import Synthetix


# functions
def format_key(key):
    # Remove 'D18' suffix and capitalize 'oracle' to 'Oracle'
    key = key.replace("D18", "").replace("oracle", "Oracle")

    # Split camelCase into separate words
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]{2,}(?=[A-Z][a-z]|\d|\W|$)|\d+", key)

    # Capitalize each word and join them with spaces
    return " ".join(word.capitalize() for word in words)


def format_value(key, value):
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if "D18" in key:
        return f"{value / 1e18:.6f}"
    return str(value)


def print_collateral_config(snx, collateral_config):
    click.echo("\n--- Collateral Configuration ---")
    token = Contract(
        address=collateral_config.tokenAddress,
        abi=snx.contracts['common']['ERC20']['abi'],
    )
    token_name = token.call_view_method("name")
    click.echo(f"Token: {token_name}")
    
    for key, value in collateral_config.items():
        formatted_key = format_key(key)
        formatted_value = format_value(key, value)
        click.echo(f"{formatted_key}: {formatted_value}")


# wrapper for chain fork
def chain_fork(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with networks.parse_network_choice("arbitrum:sepolia-fork:foundry"):
            return func(*args, **kwargs)

    return wrapper


@chain_fork
def main():
    click.echo(
        f"""
    Fork provider started: {chain.provider.uri}
    Network name: {chain.provider.network.name}
    """
    )

    snx = Synthetix(
        provider_rpc=chain.provider.uri,
        is_fork=True,
        request_kwargs={"timeout": 120},
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "main",
        },
    )

    PerpsProxy = Contract(
        address=snx.perps.market_proxy.address,
        abi=snx.perps.market_proxy.abi,
    )

    CoreProxy = Contract(
        address=snx.core.core_proxy.address,
        abi=snx.core.core_proxy.abi,
    )

    collateral_configurations = CoreProxy.call_view_method(
        "getCollateralConfigurations", False
    )
    for index, collateral in enumerate(collateral_configurations, 1):
        click.echo(f"\nCollateral #{index}")
        print_collateral_config(snx, collateral)

    click.echo(f"\nTotal Collateral Configurations: {len(collateral_configurations)}")
    pass


@click.command()
def cli():
    click.echo("Starting the script...")
    main()
    click.prompt(
        "Press enter to stop",
        default="exit",
        show_default=False,
    )
