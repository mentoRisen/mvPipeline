"""GPT-Image-1.5 job processor.

Contains only API calls for GPT-Image-1.5 image generation.
No database operations are performed here.
"""

import base64
import logging
import requests

from app.config import OUTPUT_DIR, OPENAI_API_KEY

logger = logging.getLogger(__name__)


def generate_image(prompt_text: str, task_id: str, job_id: str) -> str:
    """Generate an image using GPT-Image-1.5 API and save it to disk.
    
    Args:
        prompt_text: The prompt text for image generation
        task_id: Task ID for organizing output directory
        job_id: Job ID for naming the output file
        
    Returns:
        image_path: Path to the saved image file
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
        RuntimeError: If GPT-Image-1.5 API call fails
    """
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
        "model": "gpt-image-1.5",
        "prompt": prompt_text,
        "n": 1,
        "size": "1024x1024",  # Square format for Instagram
        "quality": "high",    # GPT-Image-1.5 supports: 'low', 'medium', 'high', 'auto'
        # GPT-Image-1.5 returns base64 by default, no response_format parameter
    }
    
    api_url = "https://api.openai.com/v1/images/generations"
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        # GPT-Image-1.5 returns base64-encoded image data
        image_b64 = data["data"][0]["b64_json"]
        
        # Decode base64 and save to file: output/{taskid}/{jobid}.jpeg
        output_dir = OUTPUT_DIR / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_path = output_dir / f"{job_id}.jpeg"
        image_data = base64.b64decode(image_b64)
        with open(image_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"Generated GPT-Image-1.5 image saved to {image_path}")
        
        # Return relative path (served by FastAPI under /output)
        image_path_relative = f"/output/{task_id}/{job_id}.jpeg"
        return image_path_relative
    except requests.exceptions.RequestException as e:
        # Try to include API error payload for easier debugging
        error_msg = f"GPT-Image-1.5 API error: {str(e)}"
        error_detail = None
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except Exception:
                error_msg += f" - Status: {e.response.status_code}"
        # Log full request context (minus auth header) to simplify debugging
        safe_headers = {**headers}
        safe_headers.pop("Authorization", None)
        logger.error(
            "GPT-Image-1.5 request failed. "
            f"task_id={task_id}, job_id={job_id}, "
            f"payload={payload}, headers={safe_headers}, error={error_msg}"
        )
        # Attach parsed API error detail (if any) to the exception so the caller can store it
        err = RuntimeError(error_msg)
        if error_detail is not None:
            setattr(err, "api_error", error_detail)
        raise err from e

