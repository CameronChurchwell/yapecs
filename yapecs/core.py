import argparse
import importlib.util
import itertools
import os
import sys
from copy import copy
from pathlib import Path
from types import ModuleType
from typing import List, Optional, Tuple, Union


###############################################################################
# Configuration
###############################################################################


def configure(
    module_name: str,
    config_module: ModuleType,
    config: Optional[Union[str, Path]] = None
) -> None:
    """Update the configuration values

    Arguments
        module_name
            The name of the module to configure
        config_module
            The submodule containing configuration values
        config
            The Python file containing the updated configuration values.
            If not provided and the ``--config`` parameter is a command-line
            argument, the corresponding argument is used as the configuration
    """
    # Get config file
    if config is None:

        # Get argv index of configuration
        try:
            index = sys.argv.index('--config')
        except:
            return
        if index == -1 or index + 1 == len(sys.argv):
            return

        # Get all configurations
        configs = []
        i = index + 1
        while i < len(sys.argv) and not str(sys.argv[i]).startswith('--'):
            path = Path(sys.argv[i])

            # Raise if config file doesn't exist
            if not path.is_file():
                raise FileNotFoundError(
                    f'Configuration file {path} does not exist')

            configs.append(path)
            i += 1

    else:
        configs  = [config]

    # Find the configuration with the matching module name
    for config in configs:

        # Load config file as a module
        updated_module = import_from_path('config', config)

        # Only update when the module name matches
        if updated_module.MODULE != module_name:
            continue

        # Merge config module and default config module
        for parameter in dir(updated_module):
            if hasattr(config_module, parameter):
                setattr(
                    config_module,
                    parameter,
                    getattr(updated_module, parameter))


###############################################################################
# Compose a configured module from an existing module
###############################################################################


def compose(
    name: str,
    config_paths: List[Union[str, Path]]
) -> ModuleType:
    """Compose a configured module from a base module and list of configs

    Arguments
        name
            Name of the base module to configure
        config_paths
            A list of paths to yapecs config files

    Returns
        composed
            A new module made from the base module and configurations
    """
    # TODO create a lock to prevent potential issues when using multithreading

    # Handle sys.argv changes by adding
    # `--config config_paths[0] config_paths[1]...`
    original_argv_len = len(sys.argv)
    if '--config' in sys.argv:
        raise ValueError(
            'cannot replace --config, --config must not be set in sys.argv')
    sys.argv.append('--config')
    assert len(config_paths) >= 1
    for config_path in config_paths:
        sys.argv.append(config_path)

    # Temporarily remove configured modules from sys.modules to ensure
    # that other modules are configured properly
    to_restore = {}
    config_module_names = []
    for config_path in config_paths:
        config_module = import_from_path('config', config_path)
        config_module_names.append(config_module.MODULE)
    to_delete = []
    for module_name in copy(sys.modules).keys():
        if module_name.split('.')[0] in config_module_names:
            to_delete.append(module_name)
    for module_name in to_delete:
        to_restore[module_name] = sys.modules[module_name]
        del sys.modules[module_name]

    # Import the module
    module = importlib.import_module(name)

    # Revert sys.modules
    for module_name, module_object in to_restore.items():
        sys.modules[module_name] = module_object

    # Revert sys.argv
    while len(sys.argv) > original_argv_len:
        del sys.argv[-1]

    return module


###############################################################################
# Argument parsing
###############################################################################


class ArgumentParser(argparse.ArgumentParser):

    def __init__(
        self,
        prog=None,
        usage=None,
        description=None,
        epilog=None,
        parents=[],
        formatter_class=argparse.HelpFormatter,
        prefix_chars='-',
        fromfile_prefix_chars=None,
        argument_default=None,
        conflict_handler='error',
        add_help=True,
        allow_abbrev=True,
        exit_on_error=True
    ):
        """Command-line argument parsing for yapecs. If you manually define
        a '--config' argument for use elsewhere, use argparse.ArgumentParser.

        Arguments
            prog
                The name of the program
                (default: ``os.path.basename(sys.argv[0])``)
            usage
                A usage message (default: auto-generated from arguments)
            description
                A description of what the program does
            epilog
                Text following the argument descriptions
            parents
                Parsers whose arguments should be copied into this one
            formatter_class
                HelpFormatter class for printing help messages
            prefix_chars
                Characters that prefix optional arguments
            fromfile_prefix_chars
                Characters that prefix files containing additional arguments
            argument_default
                The default value for all arguments
            conflict_handler
                String indicating how to handle conflicts
            add_help
                Add a -h/-help option
            allow_abbrev
                Allow long options to be abbreviated unambiguously
            exit_on_error
                Determines whether or not ArgumentParser exits with error info
                when an error occurs
        """
        result = super().__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            exit_on_error=exit_on_error)
        self.add_argument(
            '--config',
            help='Yapecs configuration file; added by yapecs.ArgumentParser',
            type=Path,
            nargs='*',
            required=False)
        return result

    def parse_args(
        self,
        args: Optional[List[str]] = None,
        namespace: Optional[argparse.Namespace] = None
    ) -> argparse.Namespace:
        """Parse arguments while allowing unregistered config argument

        Arguments
            args
                Arguments to parse. Default is taken from sys.argv.
            namespace
                Object to hold the attributes. Default is an empty Namespace.

        Returns
            Namespace containing program arguments
        """
        arguments = super().parse_args(args, namespace)

        if 'config' in arguments:
            del arguments.__dict__['config']

        return arguments


###############################################################################
# Hyperparameter search
###############################################################################


def grid_search(progress_file: Union[str, os.PathLike], *args: Tuple) -> Tuple:
    """Perform a grid search over configuration arguments

    Arguments
        progress_file
            File to store current search progress
        args
            Lists of argument values to perform grid search over

    Returns
        current_args
            The arguments that should be used by the current process
    """
    # Get current progress
    progress_file = Path(progress_file)
    if not progress_file.exists():
        progress = 0
    else:
        with open(progress_file) as f:
            progress = int(f.read())

    # Raise if finished
    combinations = list(itertools.product(*args))
    if progress >= len(combinations):
        raise IndexError('Finished grid search')

    # Write updated progress
    with open(progress_file, 'w+') as file:
        file.write(str(progress + 1))

    # Get corresponding argument combination
    return combinations[progress]


###############################################################################
# Utilities
###############################################################################


def import_from_path(name: str, path: Union[Path, str]) -> ModuleType:
    """Import module from a filesystem path

    Arguments
        name
            The name of the module
        path
            The configuration file to import

    Returns
        module
            The imported module
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
