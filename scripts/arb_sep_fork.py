import click
from functools import wraps
from ape import accounts, networks, chain
from synthetix import Synthetix


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
