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

"""Framework-independent Pulumi program wrapper.

PulumiProgram wraps the Pulumi Automation API with ZERO test framework
dependencies. It can be used with pytest, unittest, or standalone.

Example usage in pytest:
    def test_my_stack(request):
        program = PulumiProgram("test_stack")
        request.addfinalizer(program.cleanup)
        result = program.up()
        assert "bucket_name" in result.outputs

Example usage in unittest:
    class TestStack(unittest.TestCase):
        def test_deployment(self):
            program = PulumiProgram("test_stack")
            self.addCleanup(program.cleanup)
            program.up()

Example usage standalone:
    program = PulumiProgram("test_stack")
    try:
        program.up()
    finally:
        program.cleanup()
"""

import os
import sys
import logging
import platform
import uuid
from pathlib import Path
from typing import Optional

from pulumi import automation as auto

from . import opttest
from .results import UpdateResult, PreviewResult, RefreshResult


def _copy_file(src: str, dst: str) -> None:
    src_path, dst_path = Path(src), Path(dst)
    dst_path.write_bytes(src_path.read_bytes())
    dst_path.chmod(src_path.stat().st_mode)


def _copy_symlink(src: str, dst: str) -> None:
    Path(dst).symlink_to(Path(src).readlink())


def _copy_directory(src_dir: str, dest: str) -> None:
    src_path, dest_path = Path(src_dir), Path(dest)
    for entry in src_path.iterdir():
        dest_entry = dest_path / entry.name
        if entry.is_dir():
            dest_entry.mkdir(mode=0o755, parents=True, exist_ok=True)
            _copy_directory(str(entry), str(dest_entry))
        elif entry.is_symlink():
            _copy_symlink(str(entry), str(dest_entry))
        else:
            _copy_file(str(entry), str(dest_entry))
        # Preserve ownership on Unix
        if platform.system() != "Windows":
            try:
                stat = entry.stat()
                os.lchown(str(dest_entry), stat.st_uid, stat.st_gid)
            except (OSError, AttributeError):
                pass


class PulumiProgram:
    """Framework-independent Pulumi program wrapper.

    Wraps Pulumi Automation API operations without any test framework
    dependencies. Provides a cleanup callback for registration with
    any test framework or manual invocation.
    """

    working_dir: str
    options: opttest.Options
    logger: logging.Logger
    current_stack: auto.Stack | None
    local_workspace: auto.LocalWorkspace | None
    _env_vars: dict[str, str]

    defaultStackName = "test"

    def __init__(
        self,
        working_dir: str,
        *opts: opttest.Option,
        options: Optional[opttest.Options] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.working_dir = working_dir

        if options:
            self.options = options
        else:
            self.options = opttest.default_options()
        for opt in opts:
            opt.apply(self.options)

        if logger:
            self.logger = logger
        else:
            self.logger = self._create_default_logger()

        self._env_vars = {
            "PULUMI_BACKEND_URL": os.environ.get("PULUMI_BACKEND_URL", ""),
            "PULUMI_CONFIG_PASSPHRASE": self.options.config_passphrase
            or "correct horse battery staple",
        }

        if not self.options.test_in_place:
            destination = self._create_temp_dir()
            self._copy_to_internal(destination)
            self.working_dir = destination

        self.current_stack = None
        self.local_workspace = None
        self._init_stack()

    def _create_default_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"PulumiProgram-{id(self)}")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        )
        if not logger.handlers:
            logger.addHandler(handler)
        return logger

    def _create_temp_dir(self) -> str:
        if self.options.temp_dir:
            base_dir = Path(self.options.temp_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = Path.cwd() / "tmp"
            base_dir.mkdir(exist_ok=True)

        temp_path = base_dir / f"programDir_{uuid.uuid4().hex[:8]}"
        self.logger.info(f"Creating temp directory {temp_path.name}")

        source_base = Path(self.working_dir).name
        destination = temp_path / source_base
        destination.mkdir(mode=0o755, parents=True, exist_ok=True)
        return str(destination)

    def _copy_to_internal(self, directory: str) -> None:
        try:
            _copy_directory(self.working_dir, directory)
        except OSError as e:
            raise RuntimeError(f"Error copying program to {directory}: {e.strerror}")

    def _init_stack(self) -> None:
        self.logger.info("Creating local workspace...")
        self.local_workspace = auto.LocalWorkspace(work_dir=self.working_dir)

        if not self.options.skip_install:
            self.logger.info("Running pulumi install...")
            self.local_workspace.install()

        if not self.options.skip_stack_create:
            stack_name = self.options.stack_name or self.defaultStackName
            self.logger.info(f"Running pulumi stack init... (stack: {stack_name})")
            self.current_stack = auto.create_or_select_stack(
                stack_name,
                work_dir=self.working_dir,
            )
        else:
            self.logger.info("Skipping stack creation (skip_stack_create=True)")

    def cleanup(self) -> None:
        """Destroy and remove stack. Register with your test framework's cleanup."""
        if self.current_stack is not None:
            self.logger.info("Running pulumi destroy and removing stack...")
            try:
                self.current_stack.destroy(remove=True)
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
        else:
            self.logger.info("No current stack, skipping destroy...")

    def up(self) -> UpdateResult:
        """Run pulumi up."""
        if self.current_stack is None:
            raise RuntimeError("Stack not initialized")
        self.logger.info(f"Running pulumi up on stack: {self.current_stack.name}")
        return UpdateResult(self.current_stack.up())

    def preview(self) -> PreviewResult:
        """Run pulumi preview."""
        if self.current_stack is None:
            raise RuntimeError("Stack not initialized")
        self.logger.info(f"Running pulumi preview on stack: {self.current_stack.name}")
        return PreviewResult(self.current_stack.preview())

    def refresh(self) -> RefreshResult:
        """Run pulumi refresh."""
        if self.current_stack is None:
            raise RuntimeError("Stack not initialized")
        self.logger.info(f"Running pulumi refresh on stack: {self.current_stack.name}")
        return RefreshResult(self.current_stack.refresh())

    def destroy(self) -> auto.DestroyResult:
        """Run pulumi destroy."""
        if self.current_stack is None:
            raise RuntimeError("Stack not initialized")
        self.logger.info(f"Running pulumi destroy on stack: {self.current_stack.name}")
        return self.current_stack.destroy()

    def update_source(self, source_dir: str) -> None:
        """Update working directory from source, preserving stack state."""
        self.logger.info(f"Updating source from {source_dir} to {self.working_dir}")
        source_path = Path(source_dir)
        working_path = Path(self.working_dir)
        preserve_paths = {".pulumi", "Pulumi.yaml", "Pulumi.test.yaml"}

        def copy_selective(src: Path, dst: Path) -> None:
            for entry in src.iterdir():
                if entry.name in preserve_paths and src == source_path:
                    continue
                dest_path = dst / entry.name
                if entry.is_dir():
                    dest_path.mkdir(mode=0o755, parents=True, exist_ok=True)
                    copy_selective(entry, dest_path)
                elif entry.is_symlink():
                    if dest_path.exists() or dest_path.is_symlink():
                        dest_path.unlink()
                    _copy_symlink(str(entry), str(dest_path))
                else:
                    _copy_file(str(entry), str(dest_path))

        try:
            copy_selective(source_path, working_path)
        except OSError as e:
            raise RuntimeError(f"Error updating source from {source_dir}: {e.strerror}")

    def add_environments(self, *environment_names: str) -> None:
        """Add ESC environments to stack."""
        if self.current_stack is None:
            raise RuntimeError("Stack not initialized")
        self.current_stack.add_environments(*environment_names)

    def get_env_vars(self) -> dict[str, str]:
        """Get environment variables for this workspace."""
        return self._env_vars.copy()

    def copy_to_temp_dir(self, *opts: opttest.Option) -> "PulumiProgram":
        """Copy program to a new temporary directory."""
        destination = self._create_temp_dir()
        return self.copy_to(destination, *opts)

    def copy_to(self, directory: str, *opts: opttest.Option) -> "PulumiProgram":
        """Copy program to specified directory."""
        self._copy_to_internal(directory)
        options = self.options.copy()
        for opt in opts:
            opt.apply(options)
        opttest.test_in_place().apply(options)
        return PulumiProgram(directory, options=options, logger=self.logger)
