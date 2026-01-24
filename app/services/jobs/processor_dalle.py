"""DALL-E job processor.

Contains only API calls for DALL-E image generation.
No database operations are performed here.
"""

import logging
from pathlib import Path
import requests

from app.config import OUTPUT_DIR, OPENAI_API_KEY

logger = logging.getLogger(__name__)


def generate_image(prompt_text: str, task_id: str, job_id: str) -> tuple[str, str]:
    """Generate an image using DALL-E API and save it to disk.
    
    Args:
        prompt_text: The prompt text for image generation
        task_id: Task ID for organizing output directory
        job_id: Job ID for naming the output file
        
    Returns:
        Tuple of (image_path, image_url) where:
        - image_path: Path to the saved image file
        - image_url: Original URL from DALL-E API
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
        RuntimeError: If DALL-E API call fails
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY not set. "
            "Get your API key from https://platform.openai.com/api-keys "
            "and set it in .env file or environment variable."
        )
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "dall-e-3",
        "prompt": prompt_text,
        "n": 1,
        "size": "1024x1024",  # Square format for Instagram
        "quality": "standard",
        "response_format": "url"  # Get URL, then download
    }
    
    api_url = "https://api.openai.com/v1/images/generations"
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        image_url = data["data"][0]["url"]
        
        # Download the image
        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Log full request context for easier debugging
        error_msg = f"DALL-E API error: {str(e)}"
        error_detail = None
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except Exception:
                error_msg += f" - Status: {e.response.status_code}"
        logger.error(
            "DALL-E request failed. "
            f"task_id={task_id}, job_id={job_id}, "
            f"payload={payload}, error={error_msg}"
        )
        # Attach structured API error, if any, so upper layers can persist it
        err = RuntimeError(error_msg)
        if error_detail is not None:
            setattr(err, "api_error", error_detail)
        raise err from e
    
    # Create output directory structure: output/{taskid}/{jobid}.jpeg
    output_dir = OUTPUT_DIR / str(task_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save image as JPEG
    image_path = output_dir / f"{job_id}.jpeg"
    with open(image_path, "wb") as f:
        f.write(image_response.content)
    
    logger.info(f"Generated image saved to {image_path}")
    
    # Return relative path (served by FastAPI under /output)
    image_path_relative = f"/output/{task_id}/{job_id}.jpeg"
    return image_path_relative, image_url
