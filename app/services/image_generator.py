"""Image generation service for quotes.

Generates images with quote text overlaid on templates. Delegates to appropriate
generator based on task.image_generator field.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from app.config import OUTPUT_DIR, TEMPLATES_DIR, FONTS_DIR

if TYPE_CHECKING:
    from app.models.task import Task


class ImageGenerator:
    """Generates images with quote text for Instagram post tasks.
    
    Delegates to appropriate generator based on task.image_generator:
    - "pillow" or empty: Uses Pillow to render quote on template
    - "dalle": Uses OpenAI DALL-E API to generate image from prompt
    - "gptimage15": Uses OpenAI GPT-Image-1.5 API to generate image from prompt
    - Other: Falls back to stub generator
    """
    
    def __init__(self):
        """Initialize the image generator."""
        self.output_dir = OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Lazy import to avoid requiring dependencies if not needed
        self._pillow_generator = None
        self._dalle_generator = None
        self._gptimage15_generator = None
    
    def _get_pillow_generator(self):
        """Get or create Pillow generator instance."""
        if self._pillow_generator is None:
            from app.services.image_generator_pillow import ImageGeneratorPillow
            self._pillow_generator = ImageGeneratorPillow()
        return self._pillow_generator
    
    def _get_dalle_generator(self):
        """Get or create DALL-E generator instance."""
        if self._dalle_generator is None:
            from app.services.image_generator_dalle import ImageGeneratorDalle
            self._dalle_generator = ImageGeneratorDalle()
        return self._dalle_generator
    
    def _get_gptimage15_generator(self):
        """Get or create GPT-Image-1.5 generator instance."""
        if self._gptimage15_generator is None:
            from app.services.image_generator_gptimage15 import ImageGeneratorGptimage15
            self._gptimage15_generator = ImageGeneratorGptimage15()
        return self._gptimage15_generator
    
    def render(self, task: "Task") -> str:
        """Render an image for the given task.
        
        Uses generator based on task.image_generator:
        - "pillow" or empty: Pillow generator (renders quote on template)
        - "dalle": DALL-E API generator (generates image from prompt)
        - "gptimage15": GPT-Image-1.5 API generator (generates image from prompt)
        - Other: Stub generator (placeholder)
        
        Args:
            task: The task containing quote_text and/or image_generator_prompt
            
        Returns:
            Path to the generated image file (as string)
        """
        generator_type = (task.image_generator or "").lower()
        
        if generator_type == "dalle":
            dalle_gen = self._get_dalle_generator()
            return dalle_gen.render(task)
        elif generator_type == "gptimage15":
            gptimage15_gen = self._get_gptimage15_generator()
            return gptimage15_gen.render(task)
        elif generator_type == "pillow" or generator_type == "":
            pillow_gen = self._get_pillow_generator()
            return pillow_gen.render(task)
        
        # Fallback to stub generator for other types
        # Create task-specific folder
        task_dir = self.output_dir / str(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        
        image_filename = f"{task.id}.png"
        image_path = task_dir / image_filename
        image_path.touch()
        return str(image_path)

