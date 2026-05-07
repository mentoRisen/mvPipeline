"""GPT-Image-2 job processor.

Contains only API calls for GPT-Image-2 image generation.
No database operations are performed here.
"""

import base64
import logging

import requests

from app.config import OPENAI_API_KEY, OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_image(prompt_text: str, task_id: str, job_id: str) -> str:
    """Generate an image using GPT-Image-2 API and save it to disk."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY not set. "
            "Get your API key from https://platform.openai.com/api-keys "
            "and set it in .env file or environment variable."
        )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt_text,
        "n": 1,
        "size": "1024x1024",
        "quality": "high",
    }

    api_url = "https://api.openai.com/v1/images/generations"
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        image_b64 = data["data"][0]["b64_json"]

        output_dir = OUTPUT_DIR / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f"{job_id}.jpeg"

        with open(image_path, "wb") as file_obj:
            file_obj.write(base64.b64decode(image_b64))

        logger.info("Generated GPT-Image-2 image saved to %s", image_path)
        return f"/output/{task_id}/{job_id}.jpeg"
    except requests.exceptions.RequestException as exc:
        error_msg = f"GPT-Image-2 API error: {exc}"
        error_detail = None
        if hasattr(exc, "response") and exc.response is not None:
            try:
                error_detail = exc.response.json()
                error_msg += f" - {error_detail}"
            except Exception:
                error_msg += f" - Status: {exc.response.status_code}"

        safe_headers = {**headers}
        safe_headers.pop("Authorization", None)
        logger.error(
            "GPT-Image-2 request failed. "
            "task_id=%s, job_id=%s, payload=%s, headers=%s, error=%s",
            task_id,
            job_id,
            payload,
            safe_headers,
            error_msg,
        )

        err = RuntimeError(error_msg)
        if error_detail is not None:
            setattr(err, "api_error", error_detail)
        raise err from exc
