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
    
    Delegates to Pillow generator when image_generator is "pillow" or empty.
    Falls back to stub generator for other cases.
    """
    
    def __init__(self):
        """Initialize the image generator."""
        self.output_dir = OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Lazy import to avoid requiring Pillow if not needed
        self._pillow_generator = None
    
    def _get_pillow_generator(self):
        """Get or create Pillow generator instance."""
        if self._pillow_generator is None:
            from app.services.image_generator_pillow import ImageGeneratorPillow
            self._pillow_generator = ImageGeneratorPillow()
        return self._pillow_generator
    
    def render(self, task: "Task") -> str:
        """Render an image for the given task.
        
        Uses Pillow generator if task.image_generator is "pillow" or empty/None.
        Otherwise falls back to stub generator.
        
        Args:
            task: The task containing quote_text to render
            
        Returns:
            Path to the generated image file (as string)
        """
        # Use Pillow generator if image_generator is "pillow" or empty/None
        generator_type = (task.image_generator or "").lower()
        if generator_type == "pillow" or generator_type == "":
            pillow_gen = self._get_pillow_generator()
            return pillow_gen.render(task)
        
        # Fallback to stub generator for other types
        image_filename = f"{task.id}.png"
        image_path = self.output_dir / image_filename
        image_path.touch()
        return str(image_path)

