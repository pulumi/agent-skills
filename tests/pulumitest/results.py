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

"""Result classes for Pulumi operations.

Each result wraps the corresponding Pulumi Automation API result and adds
assertion methods that raise AssertionError directly (works with both
pytest and unittest).
"""

from pulumi import automation as auto
from pulumi.automation.events import OpType
from typing import MutableMapping


class _ChangeSummary:
    """Helper for filtering operation counts."""

    def __init__(self, op_map: MutableMapping[OpType, int]):
        self.change_summary = op_map

    def where_op_not_equals(self, *op_types: OpType) -> dict[OpType, int]:
        return {k: v for k, v in self.change_summary.items() if k not in op_types}

    def where_op_equals(self, *op_types: OpType) -> dict[OpType, int]:
        return {k: v for k, v in self.change_summary.items() if k in op_types}


class PreviewResult:
    def __init__(self, preview_result: auto.PreviewResult):
        self.preview_result = preview_result

    @property
    def change_summary(self) -> MutableMapping[OpType, int]:
        return self.preview_result.change_summary

    def has_no_deletes(self) -> None:
        cs = _ChangeSummary(self.preview_result.change_summary)
        deletes = cs.where_op_equals(OpType.DELETE, OpType.DELETE_REPLACED)
        if deletes:
            raise AssertionError(
                f"expected no deletes, got {deletes}\n{self.preview_result.stdout}"
            )

    def has_no_changes(self) -> None:
        cs = _ChangeSummary(self.preview_result.change_summary)
        unexpected = cs.where_op_not_equals(OpType.SAME)
        if unexpected:
            raise AssertionError(
                f"expected no changes, got {unexpected}\n{self.preview_result.stdout}"
            )

    def has_no_replacements(self) -> None:
        cs = _ChangeSummary(self.preview_result.change_summary)
        replacements = cs.where_op_equals(
            OpType.REPLACE,
            OpType.CREATE_REPLACEMENT,
            OpType.DELETE_REPLACED,
            OpType.DISCARD_REPLACED,
            OpType.IMPORT_REPLACEMENT,
            OpType.READ_REPLACEMENT,
        )
        if replacements:
            raise AssertionError(
                f"expected no replacements, got {replacements}\n{self.preview_result.stdout}"
            )


class RefreshResult:
    def __init__(self, refresh_result: auto.RefreshResult):
        self.refresh_result = refresh_result

    @property
    def change_summary(self) -> MutableMapping[OpType, int] | None:
        return self.refresh_result.summary.resource_changes

    @property
    def summary(self) -> auto.UpdateSummary:
        return self.refresh_result.summary

    def has_no_changes(self) -> None:
        resource_changes = self.refresh_result.summary.resource_changes
        if resource_changes is None:
            return
        cs = _ChangeSummary(resource_changes)
        unexpected = cs.where_op_not_equals(OpType.SAME)
        if unexpected:
            raise AssertionError(
                f"expected no changes, got {unexpected}\n{self.refresh_result.stdout}"
            )


class UpdateResult:
    def __init__(self, update_result: auto.UpResult):
        self.update_result = update_result

    @property
    def outputs(self) -> MutableMapping[str, auto.OutputValue]:
        return self.update_result.outputs

    @property
    def summary(self) -> auto.UpdateSummary:
        return self.update_result.summary

    @property
    def change_summary(self) -> MutableMapping[OpType, int] | None:
        return self.update_result.summary.resource_changes

    def has_no_deletes(self) -> None:
        resource_changes = self.update_result.summary.resource_changes
        if resource_changes is None:
            return
        cs = _ChangeSummary(resource_changes)
        deletes = cs.where_op_equals(OpType.DELETE, OpType.DELETE_REPLACED)
        if deletes:
            raise AssertionError(
                f"expected no deletes, got {deletes}\n{self.update_result.stdout}"
            )

    def has_no_changes(self) -> None:
        resource_changes = self.update_result.summary.resource_changes
        if resource_changes is None:
            return
        cs = _ChangeSummary(resource_changes)
        unexpected = cs.where_op_not_equals(OpType.SAME)
        if unexpected:
            raise AssertionError(
                f"expected no changes, got {unexpected}\n{self.update_result.stdout}"
            )

    def has_no_replacements(self) -> None:
        resource_changes = self.update_result.summary.resource_changes
        if resource_changes is None:
            return
        cs = _ChangeSummary(resource_changes)
        replacements = cs.where_op_equals(
            OpType.REPLACE,
            OpType.CREATE_REPLACEMENT,
            OpType.DELETE_REPLACED,
            OpType.DISCARD_REPLACED,
            OpType.IMPORT_REPLACEMENT,
            OpType.READ_REPLACEMENT,
        )
        if replacements:
            raise AssertionError(
                f"expected no replacements, got {replacements}\n{self.update_result.stdout}"
            )
