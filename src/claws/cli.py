"""Main CLI entry point for claws."""

import click

from claws import __version__
from claws.commands.init import init
from claws.commands.agent import agent
from claws.commands.run import run
from claws.commands.status import status
from claws.commands.evaluate import evaluate
from claws.commands.curriculum import curriculum
from claws.commands.doctor import doctor
from claws.commands.scratchpad import scratchpad


@click.group(epilog="New to claws? Start with: claws init my-project")
@click.version_option(version=__version__, prog_name="claws")
def main():
    """claws — Build, train, and manage AI agents.

    Create agents, train them through structured curricula, evaluate
    their work with two-pass scoring, and build trust over time.
    """


main.add_command(init)
main.add_command(agent)
main.add_command(run)
main.add_command(status)
main.add_command(evaluate)
main.add_command(curriculum)
main.add_command(doctor)
main.add_command(scratchpad)
