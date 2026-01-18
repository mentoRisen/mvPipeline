"""GPT-Image-1.5 image generator for quotes.

Uses OpenAI's GPT-Image-1.5 API to generate images from prompts.
"""

import base64
from pathlib import Path
from typing import TYPE_CHECKING
import requests

from app.config import OUTPUT_DIR, OPENAI_API_KEY

if TYPE_CHECKING:
    from app.models.task import Task


class ImageGeneratorGptimage15:
    """GPT-Image-1.5 API-based image generator for rendering quotes as images."""
    
    def __init__(self):
        """Initialize the GPT-Image-1.5 image generator."""
        self.output_dir = OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not set. "
                "Get your API key from https://platform.openai.com/api-keys "
                "and set it in .env file or environment variable."
            )
        
        self.api_key = OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1/images/generations"
    
    def render(self, task: "Task") -> str:
        """Render an image using GPT-Image-1.5 API.
        
        Args:
            task: The task containing image_generator_prompt to use
            
        Returns:
            Path to the generated image file (as string)
            
        Raises:
            ValueError: If image_generator_prompt is not set
            requests.RequestException: If API call fails
        """
        if not task.image_generator_prompt:
            raise ValueError("Task must have image_generator_prompt to use GPT-Image-1.5 generator")
        
        # Call GPT-Image-1.5 API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-image-1.5",
            "prompt": task.image_generator_prompt,
            "n": 1,
            "size": "1024x1024",  # Square format for Instagram
            "quality": "high"  # GPT-Image-1.5 supports: 'low', 'medium', 'high', 'auto'
            # Note: GPT-Image-1.5 returns base64 by default, no response_format parameter
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            # GPT-Image-1.5 returns base64-encoded image data
            image_b64 = data["data"][0]["b64_json"]
            
            # Create task-specific folder
            task_dir = self.output_dir / str(task.id)
            task_dir.mkdir(parents=True, exist_ok=True)
            
            # Decode base64 and save to file
            image_filename = f"{task.id}.png"
            image_path = task_dir / image_filename
            
            image_data = base64.b64decode(image_b64)
            with open(image_path, "wb") as f:
                f.write(image_data)
            
            return str(image_path)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"GPT-Image-1.5 API error: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            raise RuntimeError(error_msg) from e

