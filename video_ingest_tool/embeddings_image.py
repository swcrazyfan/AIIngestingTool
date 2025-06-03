"""
Image embedding preparation module for the video ingest tool.

This module handles image preparation for embedding generation using the SigLIP model.
"""

import os
import base64
from io import BytesIO
import requests
from typing import Dict, List, Optional, Union
import logging
from PIL import Image
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
            api_base = "http://100.121.182.8:8001"  # Embedding service endpoint

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


def batch_generate_thumbnail_embeddings(
    thumbnails: List[Dict], 
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    logger=None
) -> Dict[int, Optional[List[float]]]:
    """
    Generate image-only embeddings for multiple thumbnails.
    Updated to work with simplified thumbnail metadata (no description fields).
    
    Args:
        thumbnails: List of dictionaries with 'path', 'timestamp', 'reason', and 'rank' keys.
                   No longer requires 'description' or 'detailed_visual_description' fields.
        api_base: API base URL (default: http://100.121.182.8:8001)
        api_key: API key (not required for direct server)
        logger: Optional logger
        
    Returns:
        Dict[int, Optional[List[float]]]: Dictionary mapping thumbnail ranks to embeddings
    """
    if logger is None:
        logger = logging.getLogger("image_embeddings")
        
    embeddings = {}
    
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
        
        logger.info(f"Processing thumbnail with rank {rank} at {timestamp}")
        logger.info(f"Reason for selection: {reason}")
        logger.info(f"Generating image-only embedding (no text description)")
        
        embedding = generate_thumbnail_embedding(
            image_path=path,
            api_base=api_base,
            api_key=api_key,
            logger=logger
        )
        
        embeddings[rank_int] = embedding
    
    return embeddings