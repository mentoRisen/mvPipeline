from __future__ import annotations

import pytest

from app.models.task import Task, TaskStatus


def test_try_again_after_failure_moves_failed_to_ready():
    task = Task(status=TaskStatus.FAILED)
    task.try_again_after_failure()
    assert task.status == TaskStatus.READY


def test_try_again_after_failure_rejects_non_failed_status():
    task = Task(status=TaskStatus.READY)
    with pytest.raises(ValueError, match="Cannot try again"):
        task.try_again_after_failure()
