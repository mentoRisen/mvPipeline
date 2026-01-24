"""Instagram post template."""

from app.template.base import Template


class InstagramPost(Template):
    """Template for Instagram post tasks."""
    
    @property
    def name(self) -> str:
        """Return the template name."""
        return "instagram_post"
    
    def getEmptyMeta(self) -> dict:
        """Return an empty meta JSON template for Instagram posts.
        
        Returns:
            Dictionary with empty/default meta structure for Instagram posts
        """
        return {
            "theme": None,
        }
    
    def getEmptyPost(self) -> dict:
        """Return an empty post JSON template for Instagram posts.
        
        Matches the requirements of InstagramPublisher.publish_image():
        - caption: Caption text for the Instagram post (optional)
        
        Returns:
            Dictionary with empty/default post structure for Instagram posts
        """
        return {
            "caption": None,  # Caption text for Instagram post - optional
        }
