# Copyright 2026, Pulumi Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test options for Pulumi testing framework.

Matches the Go providertest/opttest naming convention. Options control
how PulumiProgram initializes and runs Pulumi programs.
"""

import os
import copy
from dataclasses import dataclass, field
from typing import Callable, Protocol
from abc import abstractmethod


@dataclass
class Options:
    """Configuration options for Pulumi testing."""

    stack_name: str = "test"
    skip_install: bool = False
    skip_stack_create: bool = False
    test_in_place: bool = False
    temp_dir: str = field(default_factory=lambda: os.getenv("PULUMITEST_TEMP_DIR", ""))
    config_passphrase: str = "correct horse battery staple"
    use_ambient_backend: bool = False
    custom_env: dict[str, str] = field(default_factory=dict)

    def copy(self) -> "Options":
        """Create a deep copy of the current options."""
        return copy.deepcopy(self)


class Option(Protocol):
    """Protocol for option functions."""

    @abstractmethod
    def apply(self, options: Options) -> None:
        """Apply this option to the given Options instance."""
        ...


class OptionFunc:
    """Function-based option implementation."""

    def __init__(self, func: Callable[[Options], None]):
        self.func = func

    def apply(self, options: Options) -> None:
        self.func(options)


def stack_name(name: str) -> Option:
    """Set the stack name to use when running the program under test."""

    def apply_option(o: Options) -> None:
        o.stack_name = name

    return OptionFunc(apply_option)


def skip_install() -> Option:
    """Skip running `pulumi install` before running the program under test."""

    def apply_option(o: Options) -> None:
        o.skip_install = True

    return OptionFunc(apply_option)


def skip_stack_create() -> Option:
    """Skip creating the stack before running the program under test."""

    def apply_option(o: Options) -> None:
        o.skip_stack_create = True

    return OptionFunc(apply_option)


def test_in_place() -> Option:
    """Run the program from its current location, rather than copying to a temporary directory."""

    def apply_option(o: Options) -> None:
        o.test_in_place = True

    return OptionFunc(apply_option)


def temp_dir(directory: str) -> Option:
    """Set the temporary directory for copying the program under test."""

    def apply_option(o: Options) -> None:
        o.temp_dir = directory

    return OptionFunc(apply_option)


def config_passphrase(passphrase: str) -> Option:
    """Set the config passphrase to use when running the program under test."""

    def apply_option(o: Options) -> None:
        o.config_passphrase = passphrase

    return OptionFunc(apply_option)


def use_ambient_backend() -> Option:
    """Use whatever backend configuration has been set via `pulumi login` or PULUMI_BACKEND_URL."""

    def apply_option(o: Options) -> None:
        o.use_ambient_backend = True

    return OptionFunc(apply_option)


def env(key: str, value: str) -> Option:
    """Set a custom environment variable to use when running the program under test."""

    def apply_option(o: Options) -> None:
        o.custom_env[key] = value

    return OptionFunc(apply_option)


def default_options() -> Options:
    """Create a new Options instance with default values."""
    return Options()
