"""
Upload thumbnails to Supabase storage.

This module handles uploading generated thumbnails to Supabase storage,
organizing them by user and video file.
"""

import os
import mimetypes
from typing import Any, Dict, List
from ...auth import AuthManager
from prefect import task

@task
def upload_thumbnails_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Upload thumbnails to Supabase storage.
    
    Args:
        data: Pipeline data containing thumbnail_paths, ai_thumbnail_paths, and clip_id
        logger: Optional logger
        
    Returns:
        Dict with uploaded thumbnail URLs
    """
    # Check if we have the required data
    thumbnail_paths = data.get('thumbnail_paths', [])
    ai_thumbnail_paths = data.get('ai_thumbnail_paths', [])
    ai_thumbnail_metadata = data.get('ai_thumbnail_metadata', [])
    clip_id = data.get('clip_id')
    
    has_thumbnails = bool(thumbnail_paths) or bool(ai_thumbnail_paths)
    
    if not has_thumbnails:
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
        
        # Upload regular thumbnails
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
            
            try:
                # Check if the file already exists by trying to get its metadata
                file_exists = False
                try:
                    # List files in the path to check if the file exists
                    files = client.storage.from_('clips').list(storage_path)
                    file_exists = any(file_obj.get('name') == filename for file_obj in files)
                except Exception as e:
                    # If the directory doesn't exist, this will raise an exception
                    file_exists = False
                
                if file_exists:
                    if logger:
                        logger.info(f"Thumbnail already exists, skipping upload: {storage_path_with_file}")
                else:
                    # Upload the file to storage
                    upload_result = client.storage.from_('clips').upload(
                        path=storage_path_with_file,
                        file=file_content,
                        file_options={"content-type": content_type}
                    )
                    if logger:
                        logger.info(f"Uploaded thumbnail: {storage_path_with_file}")
                
                # Get the public URL in either case
                thumbnail_url = client.storage.from_('clips').get_public_url(storage_path_with_file)
                # Remove any trailing question mark
                thumbnail_url = thumbnail_url.rstrip('?')
                thumbnail_urls.append({
                    "url": thumbnail_url,
                    "filename": filename,
                    "is_ai_selected": False
                })
                
            except Exception as e:
                if "Duplicate" in str(e):
                    # File already exists, just get the URL
                    thumbnail_url = client.storage.from_('clips').get_public_url(storage_path_with_file)
                    # Remove any trailing question mark
                    thumbnail_url = thumbnail_url.rstrip('?')
                    thumbnail_urls.append({
                        "url": thumbnail_url,
                        "filename": filename,
                        "is_ai_selected": False
                    })
                    if logger:
                        logger.info(f"Using existing thumbnail: {thumbnail_url}")
                else:
                    # Real error occurred
                    if logger:
                        logger.error(f"Error uploading thumbnail {filename}: {str(e)}")
        
        # Upload AI thumbnails
        ai_thumbnail_urls = []
        
        # Create a mapping from path to metadata
        ai_thumbnail_map = {}
        for metadata in ai_thumbnail_metadata:
            if 'path' in metadata and 'rank' in metadata:
                ai_thumbnail_map[metadata['path']] = metadata
        
        for thumbnail_path in ai_thumbnail_paths:
            if not os.path.exists(thumbnail_path):
                if logger:
                    logger.warning(f"AI thumbnail file not found: {thumbnail_path}")
                continue
            
            # Get the filename from the path
            filename = os.path.basename(thumbnail_path)
            
            # Get metadata for this thumbnail
            metadata = ai_thumbnail_map.get(thumbnail_path, {})
            rank = metadata.get('rank')
            timestamp = metadata.get('timestamp')
            description = metadata.get('description', '')
            reason = metadata.get('reason', '')
            
            if not rank:
                if logger:
                    logger.warning(f"Missing rank for AI thumbnail: {thumbnail_path}")
                continue
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(thumbnail_path)
            if not content_type:
                content_type = "image/jpeg"
            
            # Read file content
            with open(thumbnail_path, 'rb') as file:
                file_content = file.read()
            
            # Upload file to Supabase Storage
            storage_path_with_file = f"{storage_path}/{filename}"
            
            try:
                # Check if the file already exists
                file_exists = False
                try:
                    files = client.storage.from_('clips').list(storage_path)
                    file_exists = any(file_obj.get('name') == filename for file_obj in files)
                except Exception:
                    file_exists = False
                
                if file_exists:
                    if logger:
                        logger.info(f"AI thumbnail already exists, skipping upload: {storage_path_with_file}")
                else:
                    # Upload the file to storage
                    upload_result = client.storage.from_('clips').upload(
                        path=storage_path_with_file,
                        file=file_content,
                        file_options={"content-type": content_type}
                    )
                    if logger:
                        logger.info(f"Uploaded AI thumbnail: {storage_path_with_file}")
                
                # Get the public URL
                thumbnail_url = client.storage.from_('clips').get_public_url(storage_path_with_file)
                # Remove any trailing question mark
                thumbnail_url = thumbnail_url.rstrip('?')
                
                # Add to AI thumbnail URLs list with metadata
                ai_thumbnail_urls.append({
                    "url": thumbnail_url,
                    "filename": filename,
                    "is_ai_selected": True,
                    "rank": rank,
                    "timestamp": timestamp,
                    "description": description,
                    "reason": reason
                })
                
            except Exception as e:
                if "Duplicate" in str(e):
                    # File already exists, just get the URL
                    thumbnail_url = client.storage.from_('clips').get_public_url(storage_path_with_file)
                    # Remove any trailing question mark
                    thumbnail_url = thumbnail_url.rstrip('?')
                    ai_thumbnail_urls.append({
                        "url": thumbnail_url,
                        "filename": filename,
                        "is_ai_selected": True,
                        "rank": rank,
                        "timestamp": timestamp,
                        "description": description,
                        "reason": reason
                    })
                    if logger:
                        logger.info(f"Using existing AI thumbnail: {thumbnail_url}")
                else:
                    # Real error occurred
                    if logger:
                        logger.error(f"Error uploading AI thumbnail {filename}: {str(e)}")
        
        # Update the clip record with the thumbnail URLs if any were uploaded or found
        update_data = {}
        
        # Regular thumbnails + AI thumbnails in one JSONB array
        combined_thumbnails = thumbnail_urls + ai_thumbnail_urls
        
        if combined_thumbnails:
            update_data["all_thumbnail_urls"] = combined_thumbnails
            
            # If AI thumbnails exist, use the highest ranked one (rank 1) as the main thumbnail
            # Otherwise fallback to the first regular thumbnail
            ai_primary = next((t for t in ai_thumbnail_urls if str(t.get("rank")) == "1"), None)
            if ai_primary:
                update_data["thumbnail_url"] = ai_primary["url"]
            elif thumbnail_urls:
                update_data["thumbnail_url"] = thumbnail_urls[0]["url"]
            
            # Ensure thumbnail_url doesn't have a trailing question mark
            if "thumbnail_url" in update_data:
                update_data["thumbnail_url"] = update_data["thumbnail_url"].rstrip('?')
        
        # Only update if we have data to update
        if update_data:
            try:
                # Update the clips table with the thumbnail URLs
                update_result = client.table('clips').update(update_data).eq('id', clip_id).execute()
                
                if logger:
                    logger.info(f"Updated clip record with thumbnail data: {clip_id}")
            except Exception as db_error:
                if logger:
                    logger.error(f"Failed to update clips table: {str(db_error)}")
                # Continue processing as thumbnails are still uploaded
        
        return {
            'thumbnail_upload_success': True,
            'thumbnail_urls': [t["url"] for t in thumbnail_urls],
            'ai_thumbnail_urls': [t["url"] for t in ai_thumbnail_urls]
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Thumbnail upload failed: {str(e)}")
        return {
            'thumbnail_upload_failed': True,
            'error': str(e)
        } 