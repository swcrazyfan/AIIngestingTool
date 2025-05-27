"""
Upload thumbnails to Supabase storage.

This module handles uploading generated thumbnails to Supabase storage,
organizing them by user and video file.
"""

import os
import mimetypes
from typing import Any, Dict, List

from ...pipeline.registry import register_step
from ...auth import AuthManager

@register_step(
    name="thumbnail_upload",
    enabled=False,  # Disabled by default, must be explicitly enabled
    description="Upload thumbnails to Supabase storage"
)
def upload_thumbnails_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Upload thumbnails to Supabase storage.
    
    Args:
        data: Pipeline data containing thumbnail_paths and clip_id
        logger: Optional logger
        
    Returns:
        Dict with uploaded thumbnail URLs
    """
    # Check if we have the required data
    thumbnail_paths = data.get('thumbnail_paths', [])
    clip_id = data.get('clip_id')
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for upload")
        return {
            'thumbnail_upload_skipped': True,
            'reason': 'no_thumbnails'
        }
    
    if not clip_id:
        if logger:
            logger.warning("No clip_id available, thumbnails cannot be uploaded")
        return {
            'thumbnail_upload_skipped': True,
            'reason': 'no_clip_id'
        }
    
    # Check authentication
    auth_manager = AuthManager()
    client = auth_manager.get_authenticated_client()
    
    if not client:
        if logger:
            logger.warning("Skipping thumbnail upload - not authenticated")
        return {
            'thumbnail_upload_skipped': True,
            'reason': 'not_authenticated'
        }
    
    try:
        # Get user ID for storage path
        user_response = client.auth.get_user()
        if not user_response.user or not user_response.user.id:
            if logger:
                logger.error("Unable to get authenticated user ID")
            return {
                'thumbnail_upload_failed': True,
                'reason': 'no_user_id'
            }
        
        user_id = user_response.user.id
        
        # Create storage path structure: users/{user_id}/videos/{clip_id}/thumbnails/
        storage_path = f"users/{user_id}/videos/{clip_id}/thumbnails"
        
        # Upload each thumbnail
        thumbnail_urls = []
        for thumbnail_path in thumbnail_paths:
            if not os.path.exists(thumbnail_path):
                if logger:
                    logger.warning(f"Thumbnail file not found: {thumbnail_path}")
                continue
            
            # Get the filename from the path
            filename = os.path.basename(thumbnail_path)
            
            # Determine content type (should be image/jpeg for most thumbnails)
            content_type, _ = mimetypes.guess_type(thumbnail_path)
            if not content_type:
                content_type = "image/jpeg"  # Default to JPEG if can't determine
            
            # Read file content
            with open(thumbnail_path, 'rb') as file:
                file_content = file.read()
            
            # Upload file to Supabase Storage
            storage_path_with_file = f"{storage_path}/{filename}"
            
            # Check if the file already exists by trying to get its metadata
            try:
                # Check if the file already exists
                file_exists = False
                try:
                    # List files in the path to check if the file exists
                    files = client.storage.from_('videos').list(storage_path)
                    file_exists = any(file_obj.get('name') == filename for file_obj in files)
                except Exception as e:
                    # If the directory doesn't exist, this will raise an exception
                    file_exists = False
                
                if file_exists:
                    if logger:
                        logger.info(f"Thumbnail already exists, skipping upload: {storage_path_with_file}")
                else:
                    # Upload the file to storage
                    upload_result = client.storage.from_('videos').upload(
                        path=storage_path_with_file,
                        file=file_content,
                        file_options={"content-type": content_type}
                    )
                    if logger:
                        logger.info(f"Uploaded thumbnail: {storage_path_with_file}")
                
                # Get the public URL in either case
                thumbnail_url = client.storage.from_('videos').get_public_url(storage_path_with_file)
                thumbnail_urls.append(thumbnail_url)
                
            except Exception as e:
                if "Duplicate" in str(e):
                    # File already exists, just get the URL
                    thumbnail_url = client.storage.from_('videos').get_public_url(storage_path_with_file)
                    thumbnail_urls.append(thumbnail_url)
                    if logger:
                        logger.info(f"Using existing thumbnail: {thumbnail_url}")
                else:
                    # Real error occurred
                    if logger:
                        logger.error(f"Error uploading thumbnail {filename}: {str(e)}")
        
        # Update the clip record with the thumbnail URLs if any were uploaded or found
        if thumbnail_urls:
            # Take the first thumbnail as the main thumbnail for the clip
            main_thumbnail_url = thumbnail_urls[0] if thumbnail_urls else None
            
            try:
                # Update the clips table with the thumbnail URL
                update_result = client.table('clips').update({
                    "thumbnail_url": main_thumbnail_url,
                    "all_thumbnail_urls": thumbnail_urls
                }).eq('id', clip_id).execute()
                
                if logger:
                    logger.info(f"Updated clip record with thumbnail URLs: {clip_id}")
            except Exception as db_error:
                if logger:
                    logger.error(f"Failed to update clips table: {str(db_error)}")
                # Continue processing as thumbnails are still uploaded
        
        return {
            'thumbnail_upload_success': True,
            'thumbnail_urls': thumbnail_urls
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Thumbnail upload failed: {str(e)}")
        return {
            'thumbnail_upload_failed': True,
            'error': str(e)
        } 