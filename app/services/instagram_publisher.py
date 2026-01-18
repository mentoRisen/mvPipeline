"""Instagram publishing service using Instagram Graph API."""

import os
import requests
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT


class InstagramPublisher:
    """Publishes images to Instagram using the Instagram Graph API.
    
    Requires Instagram Business Account and Facebook App credentials.
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        instagram_account_id: Optional[str] = None,
    ):
        """Initialize Instagram publisher.
        
        Args:
            access_token: Instagram Graph API access token (long-lived)
            instagram_account_id: Instagram Business Account ID
        """
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_account_id = instagram_account_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
        
        if not self.access_token:
            raise ValueError("Instagram access token not provided. Set INSTAGRAM_ACCESS_TOKEN environment variable.")
        if not self.instagram_account_id:
            raise ValueError("Instagram account ID not provided. Set INSTAGRAM_ACCOUNT_ID environment variable.")
        
        self.base_url = "https://graph.facebook.com/v18.0"
    
    def publish_image(
        self,
        image_path: str | Path,
        caption: Optional[str] = None,
    ) -> dict:
        """Publish an image to Instagram.
        
        Args:
            image_path: URL (http/https) or path to the image file to upload
            caption: Caption text for the post (optional)
            
        Returns:
            Dictionary with 'id' (media ID) and 'permalink' (post URL)
            
        Raises:
            ValueError: If image file doesn't exist (for local paths) or invalid URL
            requests.RequestException: If API request fails
        """
        # Check if it's a URL
        image_path_str = str(image_path)
        if image_path_str.startswith(("http://", "https://")):
            # It's a URL, use it directly
            image_url = image_path_str
        else:
            # It's a local file path - Instagram API requires public URLs
            # So we'll raise an error for local files
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                raise ValueError(f"Image file not found: {image_path_obj}")
            raise ValueError(
                f"Local file path provided: {image_path_obj}. "
                "Instagram Graph API requires a publicly accessible image URL. "
                "Please upload the image to a public URL first or set image_path to a URL in the database."
            )
        
        # Step 1: Create media container
        container_id = self._create_media_container(image_url, caption or "")
        
        # Step 2: Publish the container
        media_id = self._publish_media_container(container_id)
        
        # Step 3: Get media details (including permalink)
        media_info = self._get_media_info(media_id)
        
        return {
            "id": media_id,
            "permalink": media_info.get("permalink", ""),
        }
    
    def _create_media_container(
        self,
        image_url: str,
        caption: str,
    ) -> str:
        """Create a media container for image upload.
        
        Args:
            image_url: Publicly accessible URL to the image
            caption: Caption text
            
        Returns:
            Container ID
            
        Raises:
            requests.RequestException: If API request fails
        """
        # Create media container
        url = f"{self.base_url}/{self.instagram_account_id}/media"
        
        params = {
            "access_token": self.access_token,
            "image_url": image_url,
            "caption": caption,
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        result = response.json()
        if "id" not in result:
            raise ValueError(f"Failed to create media container: {result}")
        
        return result["id"]
    
    def _publish_media_container(self, container_id: str) -> str:
        """Publish a media container to Instagram.
        
        Args:
            container_id: Container ID from create_media_container
            
        Returns:
            Media ID of published post
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
        
        params = {
            "access_token": self.access_token,
            "creation_id": container_id,
        }
        
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        result = response.json()
        if "id" not in result:
            raise ValueError(f"Failed to publish media: {result}")
        
        return result["id"]
    
    def _get_media_info(self, media_id: str) -> dict:
        """Get media information including permalink.
        
        Args:
            media_id: Media ID of published post
            
        Returns:
            Media information dictionary
        """
        url = f"{self.base_url}/{media_id}"
        
        params = {
            "access_token": self.access_token,
            "fields": "id,permalink,media_type,timestamp",
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
