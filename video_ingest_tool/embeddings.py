"""
Vector embeddings generation using BAAI/bge-m3 via DeepInfra.
Following Supabase best practices for hybrid search.
"""

import os
import openai
import tiktoken
from typing import List, Dict, Any, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)

def get_embedding_client():
    """Get OpenAI client configured for DeepInfra API."""
    return openai.OpenAI(
        api_key=os.getenv("DEEPINFRA_API_KEY"),
        base_url="https://api.deepinfra.com/v1/openai"
    )

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens: {str(e)}")
        return len(text) // 4  # Rough estimate

def truncate_text(text: str, max_tokens: int = 3500) -> Tuple[str, str]:
    """Intelligently truncate text to fit token limit with sentence boundaries."""
    token_count = count_tokens(text)
    
    if token_count <= max_tokens:
        return text, "none"
    
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        
        # First, try token-based truncation
        truncated_tokens = tokens[:max_tokens]
        truncated_text = encoding.decode(truncated_tokens)
        
        # Try to cut at sentence boundary to preserve meaning
        # Look for sentence endings near the cut point
        sentences = text.split('. ')
        if len(sentences) > 1:
            # Rebuild text sentence by sentence until we exceed token limit
            rebuilt_text = ""
            for i, sentence in enumerate(sentences):
                test_text = rebuilt_text + sentence
                if i < len(sentences) - 1:  # Add period back except for last sentence
                    test_text += ". "
                
                if count_tokens(test_text) > max_tokens:
                    # This sentence would exceed limit, stop at previous sentence
                    if rebuilt_text:  # We have at least one complete sentence
                        return rebuilt_text.rstrip() + "...", "sentence_boundary"
                    else:
                        # Even first sentence is too long, fall back to token truncation
                        break
                rebuilt_text = test_text
        
    # Fallback to token-based truncation with ellipsis
        return truncated_text + "...", "token_boundary"
        
    except Exception as e:
        logger.warning(f"Failed to truncate with tiktoken: {str(e)}")
        # Fallback: character-based truncation with sentence awareness
        char_limit = max_tokens * 4  # Rough estimate
        if len(text) <= char_limit:
            return text, "none"
        
        truncated = text[:char_limit]
        # Try to cut at last sentence boundary
        last_period = truncated.rfind('. ')
        if last_period > char_limit * 0.7:  # Only if we keep at least 70% of content
            return truncated[:last_period + 1] + "...", "char_sentence_boundary"
        else:
            return truncated + "...", "char_estimate"

def prepare_embedding_content(video_data) -> Tuple[str, str, Dict[str, Any]]:
    """
    Prepare semantic content for embedding generation optimized for hybrid search.
    Technical specs are handled by full-text search, but now also included in keyword embeddings.
    
    Args:
        video_data: VideoIngestOutput model
        
    Returns:
        Tuple of (summary_content, keyword_content, metadata)
    """
    
    # SUMMARY EMBEDDING: Semantic narrative content
    summary_parts = []
    
    # Initialize siglip_summary at the top level
    siglip_summary = None
    
    # Core content description
    if video_data.analysis and video_data.analysis.ai_analysis and video_data.analysis.ai_analysis.summary:
        summary = video_data.analysis.ai_analysis.summary
        
        # Content category as context
        if summary.content_category:
            summary_parts.append(f"{summary.content_category} content")
        
        # Main semantic description (the "what" and "why")
        if summary.overall:
            summary_parts.append(summary.overall)
        
        # Condensed summary for SigLIP
        if hasattr(summary, 'condensed_summary') and summary.condensed_summary:
            siglip_summary = summary.condensed_summary
        
        # Key activities in natural language
        if summary.key_activities:
            activities_text = ", ".join(summary.key_activities)
            summary_parts.append(f"Activities include {activities_text}")
    
    # Location and setting context
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.content_analysis and
        video_data.analysis.ai_analysis.content_analysis.entities and
        video_data.analysis.ai_analysis.content_analysis.entities.locations):
        locations = []
        for loc in video_data.analysis.ai_analysis.content_analysis.entities.locations:
            if loc.name and loc.type:
                locations.append(f"{loc.name} ({loc.type.lower()})")
            elif loc.name:
                locations.append(loc.name)
        if locations:
            summary_parts.append(f"Filmed in {', '.join(locations)}")
    
    # Visual style and cinematography
    shot_style_parts = []
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.visual_analysis and
        video_data.analysis.ai_analysis.visual_analysis.shot_types):
        # Extract shot types and convert to natural language
        for shot in video_data.analysis.ai_analysis.visual_analysis.shot_types:
            if shot.shot_type:
                # Convert technical terms to searchable concepts
                shot_type = shot.shot_type.lower()
                if "static" in shot_type or "locked" in shot_type:
                    shot_style_parts.append("stationary camera work")
                elif "wide" in shot_type:
                    shot_style_parts.append("wide angle cinematography")
                elif "close" in shot_type:
                    shot_style_parts.append("close-up footage")
                else:
                    shot_style_parts.append(f"{shot_type} cinematography")
    
    if shot_style_parts:
        summary_parts.append(f"Features {', '.join(set(shot_style_parts))}")
    
    # Content purpose and educational value
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.content_analysis and
        video_data.analysis.ai_analysis.content_analysis.activity_summary):
        purposes = []
        for activity in video_data.analysis.ai_analysis.content_analysis.activity_summary:
            activity_text = activity.activity.lower()
            if "technical" in activity_text or "commentary" in activity_text:
                purposes.append("educational technical demonstration")
            elif "landscape" in activity_text or "scenic" in activity_text:
                purposes.append("scenic documentation")
            elif "demonstration" in activity_text:
                purposes.append("instructional content")
        
        if purposes:
            summary_parts.append(f"Serves as {', '.join(set(purposes))}")
    
    summary_content = ". ".join(summary_parts)
    
    # KEYWORD EMBEDDING: Concept tags, semantic keywords, and ALL technical metadata
    keyword_concepts = []
    
    # Core semantic concepts from transcript
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.audio_analysis and 
        video_data.analysis.ai_analysis.audio_analysis.transcript and
        video_data.analysis.ai_analysis.audio_analysis.transcript.full_text):
        # Include transcript for semantic concept extraction
        transcript = video_data.analysis.ai_analysis.audio_analysis.transcript.full_text
        keyword_concepts.append(transcript)
    
    # Visual and environmental concepts
    visual_concepts = []
    
    # Location concepts
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.content_analysis and
        video_data.analysis.ai_analysis.content_analysis.entities):
        entities = video_data.analysis.ai_analysis.content_analysis.entities
        
        # Location-based concepts
        if entities.locations:
            for loc in entities.locations:
                if loc.name:
                    visual_concepts.append(loc.name.lower())
                if loc.type:
                    visual_concepts.append(loc.type.lower())
        
        # Object-based concepts
        if entities.objects_of_interest:
            for obj in entities.objects_of_interest:
                if obj.object:
                    visual_concepts.append(obj.object.lower())
    
    # Shot style concepts
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.visual_analysis and
        video_data.analysis.ai_analysis.visual_analysis.shot_types):
        for shot in video_data.analysis.ai_analysis.visual_analysis.shot_types:
            if shot.shot_type:
                # Extract key concepts from shot types
                shot_words = shot.shot_type.lower().replace("/", " ").replace("-", " ").split()
                visual_concepts.extend([word for word in shot_words if len(word) > 2])
    
    # Activity and purpose concepts
    activity_concepts = []
    if (video_data.analysis and video_data.analysis.ai_analysis and 
        video_data.analysis.ai_analysis.content_analysis and
        video_data.analysis.ai_analysis.content_analysis.activity_summary):
        for activity in video_data.analysis.ai_analysis.content_analysis.activity_summary:
            if activity.activity:
                # Extract key concepts from activities
                activity_words = activity.activity.lower().split()
                activity_concepts.extend([word for word in activity_words if len(word) > 3])
    
    # Content category concepts
    category_concepts = []
    if video_data.analysis and video_data.analysis.ai_analysis and video_data.analysis.ai_analysis.summary:
        if video_data.analysis.ai_analysis.summary.content_category:
            category_concepts.append(video_data.analysis.ai_analysis.summary.content_category.lower())
    
    # --- Camera and EXIF ---
    if hasattr(video_data, 'camera') and video_data.camera:
        if video_data.camera.make:
            keyword_concepts.append(video_data.camera.make)
        if video_data.camera.model:
            keyword_concepts.append(video_data.camera.model)
        if video_data.camera.lens_model:
            keyword_concepts.append(video_data.camera.lens_model)
        if video_data.camera.focal_length:
            if video_data.camera.focal_length.value_mm:
                keyword_concepts.append(f"focal length {video_data.camera.focal_length.value_mm}mm")
            if video_data.camera.focal_length.category:
                category = video_data.camera.focal_length.category.lower()
                keyword_concepts.append(category)
                keyword_concepts.append(f"{category} shot")
        if video_data.camera.settings:
            if video_data.camera.settings.iso:
                keyword_concepts.append(f"ISO {video_data.camera.settings.iso}")
            if video_data.camera.settings.shutter_speed:
                keyword_concepts.append(f"shutter speed {video_data.camera.settings.shutter_speed}")
            if video_data.camera.settings.f_stop:
                keyword_concepts.append(f"f/{video_data.camera.settings.f_stop}")
            if video_data.camera.settings.exposure_mode:
                keyword_concepts.append(f"{video_data.camera.settings.exposure_mode} exposure")
            if video_data.camera.settings.white_balance:
                keyword_concepts.append(f"{video_data.camera.settings.white_balance} white balance")
        if video_data.camera.location:
            if video_data.camera.location.location_name:
                keyword_concepts.append(video_data.camera.location.location_name)
            if video_data.camera.location.gps_latitude and video_data.camera.location.gps_longitude:
                keyword_concepts.append(f"gps {video_data.camera.location.gps_latitude},{video_data.camera.location.gps_longitude}")

    # --- Video Codec/Container ---
    if hasattr(video_data, 'video') and video_data.video:
        if video_data.video.codec:
            if video_data.video.codec.name:
                keyword_concepts.append(video_data.video.codec.name)
            if video_data.video.codec.profile:
                keyword_concepts.append(video_data.video.codec.profile)
            if video_data.video.codec.level:
                keyword_concepts.append(f"level {video_data.video.codec.level}")
            if video_data.video.codec.bitrate_kbps:
                keyword_concepts.append(f"{video_data.video.codec.bitrate_kbps} kbps")
            if video_data.video.codec.bit_depth:
                keyword_concepts.append(f"{video_data.video.codec.bit_depth}-bit")
            if video_data.video.codec.chroma_subsampling:
                keyword_concepts.append(f"chroma {video_data.video.codec.chroma_subsampling}")
            if video_data.video.codec.pixel_format:
                keyword_concepts.append(video_data.video.codec.pixel_format)
            if video_data.video.codec.bitrate_mode:
                keyword_concepts.append(video_data.video.codec.bitrate_mode)
            if video_data.video.codec.cabac is not None:
                keyword_concepts.append(f"cabac {video_data.video.codec.cabac}")
            if video_data.video.codec.ref_frames:
                keyword_concepts.append(f"{video_data.video.codec.ref_frames} ref frames")
            if video_data.video.codec.gop_size:
                keyword_concepts.append(f"gop size {video_data.video.codec.gop_size}")
            if video_data.video.codec.scan_type:
                keyword_concepts.append(video_data.video.codec.scan_type)
            if video_data.video.codec.field_order:
                keyword_concepts.append(video_data.video.codec.field_order)
        if video_data.video.container:
            keyword_concepts.append(video_data.video.container)
        if video_data.video.resolution:
            if video_data.video.resolution.width and video_data.video.resolution.height:
                keyword_concepts.append(f"{video_data.video.resolution.width}x{video_data.video.resolution.height}")
            if hasattr(video_data.video.resolution, 'aspect_ratio') and video_data.video.resolution.aspect_ratio:
                keyword_concepts.append(f"aspect ratio {video_data.video.resolution.aspect_ratio}")
        if video_data.video.frame_rate:
            keyword_concepts.append(f"{video_data.video.frame_rate} fps")
        # --- HDR/Color ---
        if video_data.video.color:
            if video_data.video.color.color_space:
                keyword_concepts.append(video_data.video.color.color_space)
            if video_data.video.color.color_primaries:
                keyword_concepts.append(video_data.video.color.color_primaries)
            if video_data.video.color.transfer_characteristics:
                keyword_concepts.append(video_data.video.color.transfer_characteristics)
            if video_data.video.color.matrix_coefficients:
                keyword_concepts.append(video_data.video.color.matrix_coefficients)
            if video_data.video.color.color_range:
                keyword_concepts.append(video_data.video.color.color_range)
            if video_data.video.color.hdr:
                if video_data.video.color.hdr.format:
                    keyword_concepts.append(f"HDR {video_data.video.color.hdr.format}")
                if video_data.video.color.hdr.master_display:
                    keyword_concepts.append(f"master display {video_data.video.color.hdr.master_display}")
                if video_data.video.color.hdr.max_cll:
                    keyword_concepts.append(f"max CLL {video_data.video.color.hdr.max_cll}")
                if video_data.video.color.hdr.max_fall:
                    keyword_concepts.append(f"max FALL {video_data.video.color.hdr.max_fall}")
        # --- Exposure ---
        if video_data.video.exposure:
            if video_data.video.exposure.warning:
                keyword_concepts.append(f"exposure warning: {video_data.video.exposure.warning}")
            if video_data.video.exposure.stops:
                keyword_concepts.append(f"{video_data.video.exposure.stops} stops")
            if video_data.video.exposure.overexposed_percentage is not None:
                keyword_concepts.append(f"overexposed {video_data.video.exposure.overexposed_percentage}%")
            if video_data.video.exposure.underexposed_percentage is not None:
                keyword_concepts.append(f"underexposed {video_data.video.exposure.underexposed_percentage}%")

    # --- Audio/Subtitle Tracks ---
    if hasattr(video_data, 'audio_tracks') and video_data.audio_tracks:
        for track in video_data.audio_tracks:
            if hasattr(track, 'language') and track.language:
                keyword_concepts.append(f"audio language {track.language}")
            if hasattr(track, 'codec') and track.codec:
                keyword_concepts.append(f"audio codec {track.codec}")
    if hasattr(video_data, 'subtitle_tracks') and video_data.subtitle_tracks:
        for track in video_data.subtitle_tracks:
            if hasattr(track, 'language') and track.language:
                keyword_concepts.append(f"subtitle language {track.language}")
            if hasattr(track, 'codec') and track.codec:
                keyword_concepts.append(f"subtitle codec {track.codec}")

    # Combine all concept lists
    all_concepts = []
    if visual_concepts:
        all_concepts.append(" ".join(set(visual_concepts)))
    if activity_concepts:
        all_concepts.append(" ".join(set(activity_concepts)))
    if category_concepts:
        all_concepts.append(" ".join(set(category_concepts)))
    
    keyword_concepts.extend(all_concepts)
    keyword_content = " ".join([str(k) for k in keyword_concepts if k])
    
    # Truncate both contents
    summary_content, summary_truncation = truncate_text(summary_content, 3500)
    keyword_content, keyword_truncation = truncate_text(keyword_content, 3500)
    
    # Add SigLIP condensed summary to metadata
    metadata = {
        "summary_tokens": count_tokens(summary_content),
        "keyword_tokens": count_tokens(keyword_content),
        "summary_truncation": summary_truncation,
        "keyword_truncation": keyword_truncation,
        "siglip_summary": siglip_summary,
        "original_transcript_length": len(video_data.analysis.ai_analysis.audio_analysis.transcript.full_text) if (
            video_data.analysis and video_data.analysis.ai_analysis and 
            video_data.analysis.ai_analysis.audio_analysis and 
            video_data.analysis.ai_analysis.audio_analysis.transcript and
            video_data.analysis.ai_analysis.audio_analysis.transcript.full_text
        ) else 0
    }
    
    return summary_content, keyword_content, metadata

def generate_embeddings(
    summary_content: str,
    keyword_content: str,
    logger=None
) -> Tuple[List[float], List[float]]:
    """Generate embeddings using BAAI/bge-m3 via DeepInfra."""
    try:
        client = get_embedding_client()
        
        # Generate summary embedding
        summary_response = client.embeddings.create(
            input=summary_content,
            model="BAAI/bge-m3",
            encoding_format="float"
        )
        summary_embedding = summary_response.data[0].embedding
        
        # Generate keyword embedding
        keyword_response = client.embeddings.create(
            input=keyword_content,
            model="BAAI/bge-m3",
            encoding_format="float"
        )
        keyword_embedding = keyword_response.data[0].embedding
        
        if logger:
            logger.info(f"Generated embeddings - Summary: {len(summary_embedding)}D, Keywords: {len(keyword_embedding)}D")
        
        return summary_embedding, keyword_embedding
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to generate embeddings: {str(e)}")
        raise

def store_embeddings(
    clip_id: str,
    summary_embedding: List[float],
    keyword_embedding: List[float],
    summary_content: str,
    original_content: str,
    metadata: Dict[str, Any],
    thumbnail_embeddings: Optional[Dict[int, List[float]]] = None,
    thumbnail_descriptions: Optional[Dict[int, str]] = None,
    thumbnail_reasons: Optional[Dict[int, str]] = None,
    logger=None
) -> bool:
    """
    Store embeddings in Supabase database.
    
    Args:
        clip_id: ID of the clip the embeddings are for
        summary_embedding: Vector embedding of the summary content
        keyword_embedding: Vector embedding for keyword search
        summary_content: The content that was embedded (used as primary matching content)
        original_content: The original unprocessed content
        metadata: Additional metadata about the embeddings
        thumbnail_embeddings: Optional dictionary mapping thumbnail ranks to embeddings
        thumbnail_descriptions: Optional dictionary mapping thumbnail ranks to descriptions
        thumbnail_reasons: Optional dictionary mapping thumbnail ranks to selection reasons
        logger: Optional logger
        
    Returns:
        bool: True if embeddings were stored successfully, False otherwise
    """
    from .auth import AuthManager
    
    # Check authentication
    auth_manager = AuthManager()
    client = auth_manager.get_authenticated_client()
    
    if not client:
        if logger:
            logger.error("Authentication required for storing embeddings")
        return False
    
    try:
        # Get user_id from auth manager
        user_id = auth_manager.get_user_id()
        if not user_id:
            if logger:
                logger.error("Cannot store embeddings: No authenticated user")
            return False
        
        # First, delete any existing vectors for this clip
        if logger:
            logger.info(f"Deleting existing vector records for clip: {clip_id}")
            
        client.table('vectors').delete().eq('clip_id', clip_id).execute()
        
        # Create base vector data
        vector_data = {
            "clip_id": clip_id,
            "user_id": user_id,
            "embedding_type": "full_clip",  # Must be 'full_clip' when segment_id is NULL
            "embedding_source": "BAAI/bge-m3",
            "summary_embedding": summary_embedding,
            "keyword_embedding": keyword_embedding,
            "embedded_content": summary_content,  # Primary content for matching
            "original_content": original_content, # Original content before processing
            "metadata": metadata,
            # Add thumbnails metadata as JSONB (without the actual embeddings)
            "thumbnail_embeddings": {}
        }
        
        # Add thumbnail embeddings if available
        if thumbnail_embeddings and thumbnail_descriptions:
            # Store thumbnail embeddings in dedicated vector columns
            # and store metadata in the JSONB structure
            thumbnail_data = {}
            
            for rank, embedding in thumbnail_embeddings.items():
                if embedding is not None:
                    # Store embedding in the dedicated vector column
                    if str(rank) == "1":
                        vector_data["thumbnail_1_embedding"] = embedding
                    elif str(rank) == "2":
                        vector_data["thumbnail_2_embedding"] = embedding
                    elif str(rank) == "3":
                        vector_data["thumbnail_3_embedding"] = embedding
                    
                    # Store metadata in the JSONB field (without the embedding)
                    thumbnail_info = {
                        "rank": str(rank)  # Ensure rank is stored as string
                    }
                    
                    # Add description if available
                    if thumbnail_descriptions and rank in thumbnail_descriptions:
                        thumbnail_info["description"] = thumbnail_descriptions[rank]
                    
                    # Add reason if available
                    if thumbnail_reasons and rank in thumbnail_reasons:
                        thumbnail_info["reason"] = thumbnail_reasons[rank]
                    
                    # Use rank as the key in the JSONB
                    thumbnail_data[str(rank)] = thumbnail_info
            
            vector_data["thumbnail_embeddings"] = thumbnail_data
        
        result = client.table('vectors').insert(vector_data).execute()
        
        if logger:
            logger.info(f"Stored embeddings for clip: {clip_id}")
            if thumbnail_embeddings:
                thumbnail_count = sum(1 for rank in thumbnail_embeddings if thumbnail_embeddings[rank] is not None)
                logger.info(f"Stored {thumbnail_count} thumbnail embeddings")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to store embeddings: {str(e)}")
        return False