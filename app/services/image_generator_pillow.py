"""Pillow-based image generator for quotes.

Uses Pillow (PIL) to render quote text on template images.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PIL import Image, ImageDraw, ImageFont

from app.config import OUTPUT_DIR, TEMPLATES_DIR, FONTS_DIR

if TYPE_CHECKING:
    from app.models.task import Task


class ImageGeneratorPillow:
    """Pillow-based image generator for rendering quotes on templates."""
    
    def __init__(self):
        """Initialize the Pillow image generator."""
        self.output_dir = OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Default template path
        self.default_template = TEMPLATES_DIR / "default.png"
        
        # Try to load default font, fallback to default if not found
        self.default_font = self._load_default_font()
    
    def _load_default_font(self, size: int = 60) -> Optional[ImageFont.FreeTypeFont]:
        """Load default font from FONTS_DIR or use system default.
        
        Args:
            size: Font size in points
            
        Returns:
            ImageFont object or None to use default
        """
        # Look for common font files in FONTS_DIR
        font_extensions = [".ttf", ".otf"]
        for ext in font_extensions:
            font_files = list(FONTS_DIR.glob(f"*{ext}"))
            if font_files:
                try:
                    return ImageFont.truetype(str(font_files[0]), size)
                except Exception:
                    pass
        
        # Fallback to default font
        try:
            return ImageFont.load_default()
        except Exception:
            return None
    
    def _wrap_text(self, text: str, max_width: int, font: Optional[ImageFont.FreeTypeFont]) -> list[str]:
        """Wrap text to fit within max_width pixels.
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            font: Font to use for measuring
            
        Returns:
            List of wrapped text lines
        """
        if not font:
            # Simple character-based wrapping if no font
            words = text.split()
            lines = []
            current_line = []
            current_width = 0
            
            for word in words:
                word_width = len(word) * 10  # Rough estimate
                if current_width + word_width > max_width and current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_width = word_width
                else:
                    current_line.append(word)
                    current_width += word_width + 10  # Add space width
            
            if current_line:
                lines.append(" ".join(current_line))
            return lines
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width > max_width and current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def render(self, task: "Task") -> str:
        """Render an image with quote text using Pillow.
        
        Args:
            task: The task containing quote_text to render
            
        Returns:
            Path to the generated image file (as string)
        """
        if not task.quote_text:
            raise ValueError("Task must have quote_text to render image")
        
        # Load template image
        if not self.default_template.exists():
            raise FileNotFoundError(f"Template not found: {self.default_template}")
        
        img = Image.open(self.default_template)
        
        # Create drawing context
        draw = ImageDraw.Draw(img)
        
        # Get image dimensions
        img_width, img_height = img.size
        
        # Font settings
        font_size = 60
        font = self._load_default_font(font_size)
        
        # Text settings
        text_color = (255, 255, 255)  # White text
        text_margin = 80  # Margin from edges
        max_text_width = img_width - (text_margin * 2)
        
        # Wrap text
        wrapped_lines = self._wrap_text(task.quote_text, max_text_width, font)
        
        # Calculate text position (centered vertically)
        if font:
            line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
        else:
            line_height = font_size + 10
        
        total_text_height = len(wrapped_lines) * line_height
        start_y = (img_height - total_text_height) // 2
        
        # Draw each line
        for i, line in enumerate(wrapped_lines):
            if font:
                bbox = font.getbbox(line)
                text_width = bbox[2] - bbox[0]
            else:
                text_width = len(line) * 10  # Rough estimate
            
            x = (img_width - text_width) // 2
            y = start_y + (i * line_height)
            
            draw.text((x, y), line, fill=text_color, font=font)
        
        # Create task-specific folder
        task_dir = self.output_dir / str(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Save image
        image_filename = f"{task.id}.png"
        image_path = task_dir / image_filename
        img.save(image_path, "PNG")
        
        return str(image_path)

