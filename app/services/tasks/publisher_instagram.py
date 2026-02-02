"""Instagram carousel post publisher for tasks.

Publishes tasks as Instagram carousel posts using the Instagram Graph API.
Similar to the preview shown in TaskDetail.vue, creates a carousel with
all imagecontent jobs from the task.
"""

import logging
import os
import time
from typing import Optional

import requests
from sqlmodel import Session, select

from app.models.task import Task
from app.models.job import Job
from app.services.instagram_publisher import (
    InstagramPublisher,
    PUBLISH_INITIAL_DELAY,
)
from app.db.engine import engine

logger = logging.getLogger(__name__)


def publish_task_instagram(task: Task) -> dict:
    """Publish a task as an Instagram carousel post.
    
    Creates a carousel post with all images from jobs with purpose="imagecontent".
    Uses public URLs from job.result.public_url or constructs them from image_path.
    
    Args:
        task: The task entity to publish
        
    Returns:
        Dictionary with 'id' (media ID) and 'permalink' (post URL)
        
    Raises:
        ValueError: If task has no imagecontent jobs or no images available
        requests.RequestException: If Instagram API request fails
    """
    logger.info(f"Publishing task {task.id} to Instagram as carousel post")
    
    # Load jobs for this task ordered by custom order (descending), then by creation time (oldest first)
    with Session(engine) as session:
        statement = select(Job).where(
            Job.task_id == task.id,
            Job.purpose == "imagecontent"
        ).order_by(Job.order.desc(), Job.created_at.asc())
        jobs = list(session.exec(statement).all())
    
    if not jobs:
        raise ValueError(f"Task {task.id} has no imagecontent jobs to publish")
    
    logger.info(f"Found {len(jobs)} imagecontent jobs for task {task.id}")
    
    # Collect image URLs from jobs
    image_urls = []
    for i, job in enumerate(jobs, 1):
        logger.info(f"Processing job {i}/{len(jobs)}: {job.id}")
        if not job.result:
            logger.warning(f"Job {job.id} has no result, skipping")
            continue
        
        logger.debug(f"Job {job.id} result keys: {list(job.result.keys())}")
        
        # Try to get public_url first, then fall back to constructing from image_path
        public_url = job.result.get("public_url")
        if public_url:
            image_urls.append(public_url)
            logger.info(f"Job {job.id}: Using public_url: {public_url}")
        else:
            logger.debug(f"Job {job.id}: No public_url found, trying to construct from image_path")
            # Try to construct public URL from image_path using environment variable
            image_path = job.result.get("image_path") or job.result.get("image_path_relative")
            logger.debug(f"Job {job.id}: image_path = {image_path}")
            if image_path:
                # Try to get PUBLIC_URL from environment
                import os
                public_url_base = os.getenv("PUBLIC_URL")
                logger.debug(f"PUBLIC_URL from env: {public_url_base}")
                if public_url_base:
                    base = str(public_url_base).rstrip("/")
                    path = str(image_path).lstrip("/")
                    constructed_url = f"{base}/{path}"
                    image_urls.append(constructed_url)
                    logger.info(f"Job {job.id}: Constructed public URL: {constructed_url}")
                else:
                    logger.warning(f"PUBLIC_URL not configured, cannot construct URL for job {job.id}")
            else:
                logger.warning(f"Job {job.id} has no image_path or public_url, skipping")
    
    if not image_urls:
        raise ValueError(f"Task {task.id} has no valid image URLs to publish")
    
    logger.info(f"Collected {len(image_urls)} image URLs for carousel:")
    for i, url in enumerate(image_urls, 1):
        logger.info(f"  {i}. {url}")
    
    # Get caption from task.post.caption and add AI-generated disclosure
    caption = ""
    if task.post and isinstance(task.post, dict):
        caption = task.post.get("caption", "") or ""
    # Add Meta's AI disclosure tag (required for AI-generated content)
    ai_disclosure = " #ImaginedWithAI"
    if caption and not caption.strip().endswith("#ImaginedWithAI"):
        caption = caption.rstrip() + ai_disclosure
    elif not caption.strip():
        caption = ai_disclosure.strip()
    
    logger.info(f"Caption for post: {caption[:100] if caption else '(empty)'}")
    
    # Initialize Instagram publisher
    logger.info("Initializing Instagram publisher...")
    publisher = InstagramPublisher()
    logger.info(f"Instagram account ID: {publisher.instagram_account_id}")
    logger.info(f"Base URL: {publisher.base_url}")
    
    # Create carousel post
    if len(image_urls) == 1:
        # Single image - use regular publish_image method
        logger.info("Single image detected, using regular image post")
        result = publisher.publish_image(image_urls[0], caption)
        # Enrich with full media info from Instagram
        media_info = publisher._get_media_info(result["id"])
        return {"id": result["id"], "permalink": result["permalink"], "media_info": media_info}
    else:
        # Multiple images - create carousel
        logger.info(f"Creating carousel post with {len(image_urls)} images")
        return _publish_carousel(publisher, image_urls, caption)


def _publish_carousel(
    publisher: InstagramPublisher,
    image_urls: list[str],
    caption: str,
) -> dict:
    """Publish a carousel post to Instagram.
    
    Args:
        publisher: InstagramPublisher instance
        image_urls: List of publicly accessible image URLs
        caption: Caption text for the carousel
        
    Returns:
        Dictionary with 'id' (media ID) and 'permalink' (post URL)
        
    Raises:
        requests.RequestException: If API request fails
    """
    # Step 1: Create individual media containers for each image (without caption)
    container_ids = []
    for i, image_url in enumerate(image_urls, 1):
        logger.info(f"Creating media container {i}/{len(image_urls)} for image: {image_url}")
        try:
            container_id = publisher._create_media_container(image_url, "")
            container_ids.append(container_id)
            logger.info(f"Successfully created container {i}/{len(image_urls)}: {container_id}")
        except Exception as e:
            logger.error(f"Failed to create media container {i}/{len(image_urls)} for URL {image_url}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
    
    logger.info(f"Successfully created {len(container_ids)} media containers: {container_ids}")
    
    # Step 2: Create carousel container
    logger.info(f"Creating carousel container with {len(container_ids)} children...")
    try:
        carousel_container_id = _create_carousel_container(
            publisher,
            container_ids,
            caption,
        )
        logger.info(f"Successfully created carousel container: {carousel_container_id}")
    except Exception as e:
        logger.error(f"Failed to create carousel container: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        raise

    # Wait for Instagram to have the container ready before publishing
    logger.info(f"Waiting {PUBLISH_INITIAL_DELAY}s for media to be ready...")
    time.sleep(PUBLISH_INITIAL_DELAY)

    # Step 3: Publish the carousel container (with retry on "Media ID not available")
    logger.info(f"Publishing carousel container {carousel_container_id}...")
    try:
        media_id = publisher._publish_media_container(carousel_container_id)
        logger.info(f"Successfully published carousel post: {media_id}")
    except Exception as e:
        logger.error(f"Failed to publish carousel container: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        raise
    
    # Step 4: Get media details (including permalink)
    logger.info(f"Fetching media info for {media_id}...")
    media_info = publisher._get_media_info(media_id)
    logger.info(f"Media info: {media_info}")
    
    permalink = media_info.get("permalink", "")
    logger.info(f"Published carousel post permalink: {permalink}")
    
    return {
        "id": media_id,
        "permalink": permalink,
        "media_info": media_info,
        "container_ids": container_ids,
        "carousel_container_id": carousel_container_id,
    }


def _create_carousel_container(
    publisher: InstagramPublisher,
    container_ids: list[str],
    caption: str,
) -> str:
    """Create a carousel container with multiple images.
    
    Args:
        publisher: InstagramPublisher instance
        container_ids: List of media container IDs to include in carousel
        caption: Caption text for the carousel
        
    Returns:
        Carousel container ID
        
    Raises:
        requests.RequestException: If API request fails
    """
    url = f"{publisher.base_url}/{publisher.instagram_account_id}/media"
    logger.debug(f"Carousel container URL: {url}")
    
    # Build children parameter - comma-separated list of container IDs
    children = ",".join(container_ids)
    logger.debug(f"Children container IDs: {children}")
    logger.debug(f"Caption length: {len(caption)} characters")
    
    params = {
        "access_token": publisher.access_token,
        "media_type": "CAROUSEL",
        "children": children,
        "caption": caption,
    }
    
    logger.debug(f"Request params (without token): media_type=CAROUSEL, children={children}, caption={caption[:50]}...")
    
    response = requests.post(url, params=params)
    logger.debug(f"Response status: {response.status_code}")
    logger.debug(f"Response headers: {dict(response.headers)}")
    
    if not response.ok:
        logger.error(f"Failed to create carousel container. Status: {response.status_code}")
        logger.error(f"Response body: {response.text}")
    
    response.raise_for_status()
    
    result = response.json()
    logger.debug(f"Response JSON: {result}")
    
    if "id" not in result:
        logger.error(f"Response missing 'id' field: {result}")
        raise ValueError(f"Failed to create carousel container: {result}")
    
    return result["id"]
