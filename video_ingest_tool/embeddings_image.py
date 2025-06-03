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

def resize_image(image_path: str, target_width: int = 512, target_height: int = 512) -> Image.Image:
    """
    Resize an image while maintaining aspect ratio with padding.
    
    Args:
        image_path: Path to the image file
        target_width: Target width (default: 256)
        target_height: Target height (default: 256)
        
    Returns:
        PIL.Image.Image: Resized image
    """
    # Open the image
    img = Image.open(image_path)
    
    # Calculate the resize dimensions to maintain aspect ratio
    width, height = img.size
    
    if width > height:
        new_width = target_width
        new_height = int(height * target_width / width)
    else:
        new_height = target_height
        new_width = int(width * target_height / height)
    
    # Resize the image
    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Create a new image with white background for padding
    padded_img = Image.new("RGB", (target_width, target_height), (255, 255, 255))
    
    # Paste the resized image centered on the padded image
    paste_x = (target_width - new_width) // 2
    paste_y = (target_height - new_height) // 2
    padded_img.paste(resized_img, (paste_x, paste_y))
    
    return padded_img

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
    description: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None, # api_key is not used by this server
    logger=None
) -> Optional[List[float]]:
    """
    Generate embedding for image using the SigLIP model via local API.
    
    Args:
        image_path: Path to the thumbnail image
        description: Short text description of the thumbnail
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

        logger.info(f"Generating joint image+text embedding for: {image_path}")
        logger.info(f"With description: {description}")
        logger.info(f"Using API endpoint: {api_base}/v1/embeddings")

        # Send both image and text as joint input using JointInputItem format
        # The API expects input to be a list, even for a single item
        payload = {
            "input": [{
                "image": data_uri,
                "text": description
            }]
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
                        logger.info(f"Successfully generated joint embedding of dimension {len(embedding)}")
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
    Generate joint image+text embeddings for multiple thumbnails.
    
    Args:
        thumbnails: List of dictionaries with 'path', 'description', 'detailed_visual_description', and 'rank' keys
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
        description = thumbnail.get('description')
        detailed_visual_description = thumbnail.get('detailed_visual_description')
        rank = thumbnail.get('rank')
        
        if not path or rank is None:
            logger.warning(f"Missing required fields in thumbnail: {thumbnail}")
            continue
            
        # Prefer detailed_visual_description over basic description for better SigLIP embeddings
        embedding_description = detailed_visual_description if detailed_visual_description else description
        
        if not embedding_description:
            logger.warning(f"No description available for thumbnail rank {rank}, skipping")
            continue
        
        # Convert rank to int if it's a string
        rank_int = int(rank) if isinstance(rank, str) else rank
        
        logger.info(f"Processing thumbnail with rank {rank}")
        logger.info(f"Using {'detailed' if detailed_visual_description else 'basic'} description: {embedding_description[:100]}...")
        
        embedding = generate_thumbnail_embedding(
            image_path=path,
            description=embedding_description,
            api_base=api_base,
            api_key=api_key,
            logger=logger
        )
        
        embeddings[rank_int] = embedding
    
    return embeddings