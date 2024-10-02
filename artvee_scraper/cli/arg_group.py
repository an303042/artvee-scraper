# arg_group.py

import argparse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List

from artvee_scraper.scraper import CategoryType


class ArgGroup(ABC):
    """The abstract group of command line arguments for this command.

    Attributes:
        subparsers (argparse._SubParsersAction): Action object used to create subparsers.
        parents (List[argparse.ArgumentParser], optional): List of parent parsers to inherit arguments from.
    """

    def __init__(self, subparsers: argparse._SubParsersAction, parents: Optional[List[argparse.ArgumentParser]] = None) -> None:
        """Constructs a new `ArgGroup` instance."""
        self.subparsers = subparsers
        self.parents = parents  # Store the parent parsers

    @abstractmethod
    def get_name(self) -> str:
        """Returns the argument group name."""
        pass

    @abstractmethod
    def get_help(self) -> str:
        """Returns the help message for this argument group."""
        pass

    @abstractmethod
    def add_arguments(self, subparser: argparse.ArgumentParser) -> None:
        """Populates the subparser with command line arguments associated with this group."""
        pass

    def get_description(self) -> Optional[str]:
        """Brief description of this argument group."""
        return None  # Return None if no description is provided

    def register(self) -> argparse.ArgumentParser:
        """Creates a subparser for this command with command-line arguments defined.

        Returns:
            argparse.ArgumentParser: The configured argparse subparser.
        """
        subparser = self.subparsers.add_parser(
            self.get_name(),
            help=self.get_help(),
            description=self.get_description(),
            parents=self.parents,  # Include parent parsers to inherit common arguments
            add_help=True  # Allow subparser to have its own --help option
        )
        subparser.set_defaults(command=self.get_name())

        # Do not call _add_program_args here; common arguments are handled by the parent parser

        # Populate subparser with command-specific arguments
        self.add_arguments(subparser)

        return subparser


class IsInRangeAction(argparse.Action):
    """Custom argparse Action to check if a value is within a specified range."""

    def __init__(self, minInclusive: int, maxInclusive: int, *args, **kwargs):
        self.minInclusive = minInclusive
        self.maxInclusive = maxInclusive
        super(IsInRangeAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if not self.minInclusive <= value <= self.maxInclusive:
            parser.error(
                f"argument {option_string}: invalid choice: {value} (must be in range [{self.minInclusive}-{self.maxInclusive}])"
            )
        setattr(namespace, self.dest, value)


class IsDirAction(argparse.Action):
    """Custom argparse Action to check if a value is a directory, creating it if necessary."""

    def __call__(self, parser, namespace, value, option_string=None):
        path = Path(value)

        if not path.exists():
            # Create the directory if it doesn't exist
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory '{value}'")
            except Exception as e:
                parser.error(
                    f"argument {option_string}: unable to create directory '{value}'; {e}"
                )
        elif not path.is_dir():
            parser.error(
                f"argument {option_string}: invalid choice: '{value}' is not a directory"
            )

        setattr(namespace, self.dest, value)
