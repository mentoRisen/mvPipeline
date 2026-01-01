"""DALL-E image generator for quotes.

Uses OpenAI's DALL-E API to generate images from prompts.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING
import requests

from app.config import OUTPUT_DIR, OPENAI_API_KEY

if TYPE_CHECKING:
    from app.models.task import Task


class ImageGeneratorDalle:
    """DALL-E API-based image generator for rendering quotes as images."""
    
    def __init__(self):
        """Initialize the DALL-E image generator."""
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
        """Render an image using DALL-E API.
        
        Args:
            task: The task containing image_generator_prompt to use
            
        Returns:
            Path to the generated image file (as string)
            
        Raises:
            ValueError: If image_generator_prompt is not set
            requests.RequestException: If API call fails
        """
        if not task.image_generator_prompt:
            raise ValueError("Task must have image_generator_prompt to use DALL-E generator")
        
        # Call DALL-E API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "dall-e-3",
            "prompt": task.image_generator_prompt,
            "n": 1,
            "size": "1024x1024",  # Square format for Instagram
            "quality": "standard",
            "response_format": "url"  # Get URL, then download
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            image_url = data["data"][0]["url"]
            
            # Download the image
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()
            
            # Save to file
            image_filename = f"{task.id}.png"
            image_path = self.output_dir / image_filename
            
            with open(image_path, "wb") as f:
                f.write(image_response.content)
            
            return str(image_path)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"DALL-E API error: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            raise RuntimeError(error_msg) from e

