from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

import app.config as app_config
from app.services.jobs import processor_runway_video


def _mock_response(*, status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.raise_for_status = MagicMock()
    response.iter_content = lambda chunk_size=8192: [b"mp4-bytes"]
    return response


def test_generate_video_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    image_path = tmp_path / "task-1" / "job-img.jpeg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-jpeg")

    submit_response = _mock_response(
        json_data={"id": "rw-task-1"},
    )
    poll_response = _mock_response(
        json_data={
            "id": "rw-task-1",
            "status": "SUCCEEDED",
            "output": ["https://runway.example/video.mp4"],
        },
    )
    download_response = _mock_response()

    monkeypatch.setattr(
        processor_runway_video.requests,
        "post",
        lambda *args, **kwargs: submit_response,
    )
    monkeypatch.setattr(
        processor_runway_video.requests,
        "get",
        lambda *args, **kwargs: poll_response
        if "tasks" in args[0]
        else download_response,
    )
    monkeypatch.setattr(processor_runway_video.time, "sleep", lambda _seconds: None)

    result = processor_runway_video.generate_video(
        image_path=image_path,
        prompt_text="camera pans slowly",
        model="gen4_turbo",
        task_id="task-1",
        job_id="job-1",
        api_key="test-key",
        timeout_seconds=60,
    )

    assert result["video_path"] == "/output/task-1/job-1.mp4"
    assert result["runway_task_id"] == "rw-task-1"
    assert (tmp_path / "task-1" / "job-1.mp4").exists()


def test_generate_video_poll_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    image_path = tmp_path / "image.jpeg"
    image_path.write_bytes(b"fake-jpeg")

    submit_response = _mock_response(json_data={"id": "rw-task-1"})
    poll_response = _mock_response(
        json_data={"id": "rw-task-1", "status": "FAILED", "failure": "bad input"},
    )

    monkeypatch.setattr(
        processor_runway_video.requests,
        "post",
        lambda *args, **kwargs: submit_response,
    )
    monkeypatch.setattr(
        processor_runway_video.requests,
        "get",
        lambda *args, **kwargs: poll_response,
    )
    monkeypatch.setattr(processor_runway_video.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Runway task failed"):
        processor_runway_video.generate_video(
            image_path=image_path,
            prompt_text="move",
            model="gen4_turbo",
            task_id="task-1",
            job_id="job-1",
            api_key="test-key",
            timeout_seconds=60,
        )


def test_generate_video_poll_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    image_path = tmp_path / "image.jpeg"
    image_path.write_bytes(b"fake-jpeg")

    submit_response = _mock_response(json_data={"id": "rw-task-1"})
    poll_response = _mock_response(
        json_data={"id": "rw-task-1", "status": "RUNNING"},
    )

    monkeypatch.setattr(
        processor_runway_video.requests,
        "post",
        lambda *args, **kwargs: submit_response,
    )
    monkeypatch.setattr(
        processor_runway_video.requests,
        "get",
        lambda *args, **kwargs: poll_response,
    )
    monkeypatch.setattr(processor_runway_video.time, "sleep", lambda _seconds: None)
    times = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr(processor_runway_video.time, "monotonic", lambda: next(times))

    with pytest.raises(RuntimeError, match="timed out"):
        processor_runway_video.generate_video(
            image_path=image_path,
            prompt_text="move",
            model="gen4_turbo",
            task_id="task-1",
            job_id="job-1",
            api_key="test-key",
            timeout_seconds=10,
        )


def test_generate_video_missing_api_key(tmp_path: Path):
    image_path = tmp_path / "image.jpeg"
    image_path.write_bytes(b"fake-jpeg")

    with pytest.raises(ValueError, match="RUNWAY_API_KEY not set"):
        processor_runway_video.generate_video(
            image_path=image_path,
            prompt_text="move",
            model="gen4_turbo",
            task_id="task-1",
            job_id="job-1",
            api_key="",
            timeout_seconds=60,
        )


def test_generate_video_non_200_submit_logs_without_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    image_path = tmp_path / "image.jpeg"
    image_path.write_bytes(b"fake-jpeg")

    response = _mock_response(status_code=401)
    monkeypatch.setattr(
        processor_runway_video.requests,
        "post",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(RuntimeError, match="Runway submit failed"):
        processor_runway_video.generate_video(
            image_path=image_path,
            prompt_text="move",
            model="gen4_turbo",
            task_id="task-1",
            job_id="job-1",
            api_key="secret-key",
            timeout_seconds=60,
        )

    assert "secret-key" not in caplog.text
    assert "Authorization" not in caplog.text


def test_generate_video_request_exception_wraps_runtime_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    image_path = tmp_path / "image.jpeg"
    image_path.write_bytes(b"fake-jpeg")

    def _raise_request_error(*args, **kwargs):
        raise requests.exceptions.RequestException("network down")

    monkeypatch.setattr(processor_runway_video.requests, "post", _raise_request_error)

    with pytest.raises(RuntimeError, match="Runway API error"):
        processor_runway_video.generate_video(
            image_path=image_path,
            prompt_text="move",
            model="gen4_turbo",
            task_id="task-1",
            job_id="job-1",
            api_key="test-key",
            timeout_seconds=60,
        )
