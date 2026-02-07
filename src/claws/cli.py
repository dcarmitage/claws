"""Main CLI entry point for claws."""

import click

from claws import __version__
from claws.commands.init import init
from claws.commands.agent import agent
from claws.commands.run import run
from claws.commands.status import status
from claws.commands.evaluate import evaluate
from claws.commands.curriculum import curriculum


@click.group()
@click.version_option(version=__version__, prog_name="claws")
def main():
    """claws — The operating system for human-AI teams.

    Your agents build software, evaluate their own work, and get better
    over time. You review PRs.
    """


main.add_command(init)
main.add_command(agent)
main.add_command(run)
main.add_command(status)
main.add_command(evaluate)
main.add_command(curriculum)
