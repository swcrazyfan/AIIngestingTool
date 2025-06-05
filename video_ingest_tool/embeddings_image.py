"""
Image embedding preparation module for the video ingest tool.

This module handles image preparation for embedding generation using the SigLIP model.
"""

import os
import base64
import logging
import requests
from typing import List, Dict, Any, Optional, Union
from io import BytesIO
from PIL import Image
import asyncio
import aiohttp
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file (required for Prefect workers)
load_dotenv()

def resize_image(image_path: str, max_dimension: int = 512) -> Image.Image:
    """
    Resize an image to fit within max dimension while preserving aspect ratio.
    No padding is applied - the image maintains its original aspect ratio.
    
    Args:
        image_path: Path to the image file
        max_dimension: Maximum dimension (width or height) for the resized image (default: 512)
        
    Returns:
        PIL.Image.Image: Resized image with preserved aspect ratio
    """
    # Open the image
    img = Image.open(image_path)
    
    # Get current dimensions
    width, height = img.size
    
    # Calculate scaling factor to fit within max dimension
    scale_factor = min(max_dimension / width, max_dimension / height)
    
    # Only resize if the image is larger than max dimension
    if scale_factor < 1.0:
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Convert to RGB if it has an alpha channel for consistency
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    return img

def image_to_base64(image: Union[str, Image.Image]) -> str:
    """
    Convert an image to base64 string.
    
    Args:
        image: Path to the image file or PIL Image object
        
    Returns:
        str: Base64 encoded image string
    """
    if isinstance(image, str):
        # It's a file path
        img = Image.open(image)
    else:
        # It's already a PIL Image
        img = image
    
    # Convert to RGB if it has an alpha channel
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    # Save to a BytesIO object
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=95)
    
    # Encode to base64
    base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return base64_image

def generate_thumbnail_embedding(
    image_path: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None, # api_key is not used by this server
    logger=None
) -> Optional[List[float]]:
    """
    Generate embedding for image using the SigLIP model via local API.
    Now generates image-only embeddings instead of joint image+text embeddings.
    
    Args:
        image_path: Path to the thumbnail image
        api_base: API base URL (default: http://localhost:8001)
        api_key: API key (not required for local server)
        logger: Optional logger
        
    Returns:
        Optional[List[float]]: 1152-dimensional embedding vector or None on failure
    """
    if logger is None:
        logger = logging.getLogger("image_embeddings")

    try:
        if not api_base:
            api_base = "http://localhost:9005"  # Embedding service endpoint

        # Convert original image to base64 with data URI format.
        # The server will handle resizing and preprocessing.
        with open(image_path, "rb") as image_file:
            img_bytes = image_file.read()
            # Determine image format for data URI
            if image_path.lower().endswith((".jpg", ".jpeg")):
                img_format = "jpeg"
            elif image_path.lower().endswith(".png"):
                img_format = "png"
            else:
                img_format = "jpeg"  # Default fallback
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            data_uri = f"data:image/{img_format};base64,{base64_image}"

        logger.info(f"Generating image-only embedding for: {image_path}")
        logger.info(f"Using API endpoint: {api_base}/v1/embeddings")

        # Send image-only input for SigLIP image embeddings
        # Updated payload format for image-only embeddings
        payload = {
            "input": data_uri
        }

        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(f"{api_base}/v1/embeddings", json=payload, headers=headers, timeout=30)
            
            logger.info(f"Response status code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                
                if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
                    embedding_data = result["data"][0]
                    if "embedding" in embedding_data:
                        embedding = embedding_data["embedding"]
                        logger.info(f"Successfully generated image-only embedding of dimension {len(embedding)}")
                        return embedding
                    else:
                        logger.error(f"'embedding' key missing in data item: {embedding_data}")
                else:
                    logger.error(f"Unexpected response structure or empty data: {result}")
            else:
                logger.error(f"API request failed: Status {response.status_code}, Response: {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error("API request timed out after 30 seconds")
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating image embedding: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Error generating image embedding: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def generate_thumbnail_embedding_async(
    image_path: str,
    session: aiohttp.ClientSession,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    logger=None
) -> Optional[List[float]]:
    """
    Generate embedding for image using the SigLIP model via local API (async version).
    
    Args:
        image_path: Path to the thumbnail image
        session: aiohttp ClientSession for making requests
        api_base: API base URL (default: http://localhost:9005)
        api_key: API key (not required for local server)
        logger: Optional logger
        
    Returns:
        Optional[List[float]]: 1152-dimensional embedding vector or None on failure
    """
    if logger is None:
        logger = logging.getLogger("image_embeddings")

    try:
        if not api_base:
            api_base = "http://localhost:9005"  # Embedding service endpoint

        # Convert original image to base64 with data URI format
        with open(image_path, "rb") as image_file:
            img_bytes = image_file.read()
            # Determine image format for data URI
            if image_path.lower().endswith((".jpg", ".jpeg")):
                img_format = "jpeg"
            elif image_path.lower().endswith(".png"):
                img_format = "png"
            else:
                img_format = "jpeg"  # Default fallback
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            data_uri = f"data:image/{img_format};base64,{base64_image}"

        logger.info(f"Generating image-only embedding for: {image_path}")

        # Send image-only input for SigLIP image embeddings
        payload = {
            "input": data_uri
        }

        headers = {"Content-Type": "application/json"}
        
        async with session.post(f"{api_base}/v1/embeddings", json=payload, headers=headers, timeout=30) as response:
            logger.info(f"Response status code: {response.status}")

            if response.status == 200:
                result = await response.json()
                
                if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
                    embedding_data = result["data"][0]
                    if "embedding" in embedding_data:
                        embedding = embedding_data["embedding"]
                        logger.info(f"Successfully generated image-only embedding of dimension {len(embedding)}")
                        return embedding
                    else:
                        logger.error(f"'embedding' key missing in data item: {embedding_data}")
                else:
                    logger.error(f"Unexpected response structure or empty data: {result}")
            else:
                response_text = await response.text()
                logger.error(f"API request failed: Status {response.status}, Response: {response_text}")
                
        return None

    except asyncio.TimeoutError:
        logger.error("API request timed out after 30 seconds")
        return None
    except Exception as e:
        logger.error(f"Error generating image embedding: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def batch_generate_thumbnail_embeddings_async(
    thumbnails: List[Dict], 
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    logger=None
) -> Dict[int, Optional[List[float]]]:
    """
    Generate image-only embeddings for multiple thumbnails concurrently.
    
    Args:
        thumbnails: List of dictionaries with 'path', 'timestamp', 'reason', and 'rank' keys
        api_base: API base URL (default: http://localhost:8005)
        api_key: API key (not required for local server)
        logger: Optional logger
        
    Returns:
        Dict[int, Optional[List[float]]]: Dictionary mapping thumbnail ranks to embeddings
    """
    if logger is None:
        logger = logging.getLogger("image_embeddings")
        
    embeddings = {}
    
    if not thumbnails:
        return embeddings
    
    # Create async tasks for all thumbnails
    async with aiohttp.ClientSession() as session:
        tasks = []
        thumbnail_ranks = []
        
        for thumbnail in thumbnails:
            path = thumbnail.get('path')
            rank = thumbnail.get('rank')
            timestamp = thumbnail.get('timestamp', 'unknown')
            reason = thumbnail.get('reason', 'no reason provided')
            
            if not path or rank is None:
                logger.warning(f"Missing required fields in thumbnail: {thumbnail}")
                continue
            
            # Convert rank to int if it's a string
            rank_int = int(rank) if isinstance(rank, str) else rank
            
            logger.info(f"Queuing thumbnail with rank {rank} at {timestamp}")
            logger.info(f"Reason for selection: {reason}")
            
            # Create async task for this thumbnail
            task = generate_thumbnail_embedding_async(
                image_path=path,
                session=session,
                api_base=api_base,
                api_key=api_key,
                logger=logger
            )
            tasks.append(task)
            thumbnail_ranks.append(rank_int)
        
        if tasks:
            logger.info(f"Sending {len(tasks)} image embedding requests concurrently...")
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for rank, result in zip(thumbnail_ranks, results):
                if isinstance(result, Exception):
                    logger.error(f"Error generating embedding for rank {rank}: {result}")
                    embeddings[rank] = None
                else:
                    embeddings[rank] = result
            
            successful_count = sum(1 for result in results if not isinstance(result, Exception) and result is not None)
            logger.info(f"Completed concurrent embedding generation: {successful_count}/{len(tasks)} successful")
    
    return embeddings

def batch_generate_thumbnail_embeddings(
    thumbnails: List[Dict], 
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    logger=None
) -> Dict[int, Optional[List[float]]]:
    """
    Generate image-only embeddings for multiple thumbnails.
    Now uses concurrent requests for better performance.
    
    Args:
        thumbnails: List of dictionaries with 'path', 'timestamp', 'reason', and 'rank' keys.
                   No longer requires 'description' or 'detailed_visual_description' fields.
        api_base: API base URL (default: http://localhost:8005)
        api_key: API key (not required for direct server)
        logger: Optional logger
        
    Returns:
        Dict[int, Optional[List[float]]]: Dictionary mapping thumbnail ranks to embeddings
    """
    try:
        # Use the async version but run it in sync context
        return asyncio.run(batch_generate_thumbnail_embeddings_async(
            thumbnails, api_base, api_key, logger
        ))
    except Exception as e:
        if logger:
            logger.error(f"Failed to generate batch thumbnail embeddings: {str(e)}")
        return {}