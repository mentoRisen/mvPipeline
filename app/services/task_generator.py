"""Task generation service for cosplay kittens.

Generates cosplay kitten prompts for Instagram posts. Randomly selects from
popular pop culture cosplay themes featuring cute kittens.
"""

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.task import Task


class TaskGenerator:
    """Generates cosplay kitten prompts for Instagram post tasks.
    
    Randomly selects from 5 popular pop culture cosplay themes featuring cute kittens.
    """
    
    # Popular cosplay kitten prompts
    _COSPLAY_KITTEN_PROMPTS = [
        "A cute adorable kitten dressed as Harry Potter with tiny round glasses, a small wizard robe, and a mini wand, magical sparkles around, photorealistic, high quality",
        "An adorable fluffy kitten cosplaying as a Jedi from Star Wars with a tiny lightsaber, wearing a small brown robe, cute and photorealistic, cinematic lighting",
        "A super cute kitten dressed as Spider-Man with a tiny red and blue costume, hanging from a web, adorable expression, photorealistic, high detail, vibrant colors",
        "An irresistibly cute kitten cosplaying as a superhero with a tiny cape, wearing a small mask, heroic pose, photorealistic, professional photography, 1080x1080",
        "A precious kitten dressed as a character from anime, with colorful hair accessories and cute outfit, kawaii style, photorealistic, high quality, Instagram-worthy"
    ]
    
    def __init__(self):
        """Initialize the task generator."""
        pass
    
    def generate(self, task: "Task") -> str:
        """Generate a cosplay kitten prompt for the given task.
        
        Randomly selects from 5 popular cosplay kitten prompts.
        
        Args:
            task: The task to generate a prompt for
            
        Returns:
            Generated cosplay kitten prompt text
        """
        # Randomly select from the 5 popular cosplay kitten prompts
        return random.choice(self._COSPLAY_KITTEN_PROMPTS)
    
    def generate_image_prompt(self, prompt_text: str) -> str:
        """Generate an AI image generation prompt based on the cosplay kitten prompt.
        
        Creates a prompt suitable for external AI image generators (DALL-E, Midjourney,
        Stable Diffusion, etc.) that will generate an image of a cute kitten in cosplay.
        
        Args:
            prompt_text: The cosplay kitten prompt text to create an image prompt for
            
        Returns:
            Image generation prompt string
        """
        # Enhance the prompt for image generation with additional details
        enhanced_prompt = (
            f"{prompt_text}, "
            f"Instagram square format 1080x1080, professional photography, "
            f"sharp focus, vibrant colors, cute and adorable, trending on Instagram"
        )
        return enhanced_prompt

