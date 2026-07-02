"""Runway image-to-video job processor.

Contains only Runway API calls and local file writes. No database access.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import time
from pathlib import Path

import requests

import app.config as app_config

logger = logging.getLogger(__name__)

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"
RUNWAY_DEFAULT_RATIO = "1280:720"
RUNWAY_DEFAULT_DURATION = 5
RUNWAY_POLL_INTERVAL_SECONDS = 5


def _image_data_uri(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    safe = dict(headers)
    safe.pop("Authorization", None)
    return safe


def generate_video(
    *,
    image_path: Path,
    prompt_text: str,
    model: str,
    task_id: str,
    job_id: str,
    api_key: str,
    timeout_seconds: int,
) -> dict:
    """Generate a video from a local image and save MP4 under output/."""
    if not api_key:
        raise ValueError(
            "RUNWAY_API_KEY not set. "
            "Add RUNWAY_API_KEY to tenant env or set it in .env / environment variable."
        )
    if not image_path.is_file():
        raise ValueError(f"Image file not found: {image_path}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }
    payload = {
        "model": model,
        "promptText": prompt_text,
        "promptImage": _image_data_uri(image_path),
        "ratio": RUNWAY_DEFAULT_RATIO,
        "duration": RUNWAY_DEFAULT_DURATION,
    }

    submit_url = f"{RUNWAY_API_BASE}/image_to_video"
    try:
        submit_response = requests.post(
            submit_url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
        if submit_response.status_code != 200:
            raise RuntimeError(
                f"Runway submit failed with status {submit_response.status_code}"
            )

        submit_data = submit_response.json()
        runway_task_id = submit_data.get("id")
        if not runway_task_id:
            raise RuntimeError("Runway submit response missing task id")

        deadline = time.monotonic() + timeout_seconds
        task_url = f"{RUNWAY_API_BASE}/tasks/{runway_task_id}"
        runway_url = None
        while time.monotonic() < deadline:
            poll_response = requests.get(
                task_url,
                headers=headers,
                timeout=min(RUNWAY_POLL_INTERVAL_SECONDS, timeout_seconds),
            )
            if poll_response.status_code != 200:
                raise RuntimeError(
                    f"Runway poll failed with status {poll_response.status_code}"
                )

            task_data = poll_response.json()
            status = str(task_data.get("status", "")).upper()
            if status == "SUCCEEDED":
                outputs = task_data.get("output") or []
                if not outputs:
                    raise RuntimeError("Runway task succeeded but returned no output")
                runway_url = outputs[0]
                break
            if status == "FAILED":
                failure = task_data.get("failure") or task_data.get("failureCode")
                raise RuntimeError(f"Runway task failed: {failure or 'unknown error'}")

            time.sleep(RUNWAY_POLL_INTERVAL_SECONDS)

        if not runway_url:
            raise RuntimeError("Runway video generation timed out")

        output_dir = app_config.OUTPUT_DIR / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        video_path = output_dir / f"{job_id}.mp4"
        download_response = requests.get(
            runway_url,
            timeout=timeout_seconds,
            stream=True,
        )
        download_response.raise_for_status()
        with open(video_path, "wb") as file_obj:
            for chunk in download_response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)

        web_path = f"/output/{task_id}/{job_id}.mp4"
        logger.info("Generated Runway video saved to %s", video_path)
        return {
            "video_path": web_path,
            "runway_task_id": runway_task_id,
            "runway_url": runway_url,
        }
    except requests.exceptions.RequestException as exc:
        error_msg = f"Runway API error: {exc}"
        if hasattr(exc, "response") and exc.response is not None:
            error_msg += f" - Status: {exc.response.status_code}"

        logger.error(
            "Runway request failed. task_id=%s, job_id=%s, headers=%s, error=%s",
            task_id,
            job_id,
            _safe_headers(headers),
            error_msg,
        )
        raise RuntimeError(error_msg) from exc


__all__ = ["generate_video"]
