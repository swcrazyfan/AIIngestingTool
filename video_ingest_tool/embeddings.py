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
    Technical specs are handled by full-text search.
    
    Args:
        video_data: VideoIngestOutput model
        
    Returns:
        Tuple of (summary_content, keyword_content, metadata)
    """
    
    # SUMMARY EMBEDDING: Semantic narrative content
    summary_parts = []
    
    # Core content description
    if video_data.analysis and video_data.analysis.ai_analysis and video_data.analysis.ai_analysis.summary:
        summary = video_data.analysis.ai_analysis.summary
        
        # Content category as context
        if summary.content_category:
            summary_parts.append(f"{summary.content_category} content")
        
        # Main semantic description (the "what" and "why")
        if summary.overall:
            summary_parts.append(summary.overall)
        
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
    
    # KEYWORD EMBEDDING: Concept tags and semantic keywords
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
    
    # Combine all concept lists
    all_concepts = []
    if visual_concepts:
        all_concepts.append(" ".join(set(visual_concepts)))
    if activity_concepts:
        all_concepts.append(" ".join(set(activity_concepts)))
    if category_concepts:
        all_concepts.append(" ".join(set(category_concepts)))
    
    keyword_concepts.extend(all_concepts)
    keyword_content = " ".join(keyword_concepts)
    
    # Truncate both contents
    summary_content, summary_truncation = truncate_text(summary_content, 3500)
    keyword_content, keyword_truncation = truncate_text(keyword_content, 3500)
    
    metadata = {
        "summary_tokens": count_tokens(summary_content),
        "keyword_tokens": count_tokens(keyword_content),
        "summary_truncation": summary_truncation,
        "keyword_truncation": keyword_truncation,
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
    keyword_content: str,
    original_content: str,
    metadata: Dict[str, Any],
    logger=None
) -> bool:
    """Store embeddings in Supabase database following pgvector patterns."""
    from .auth import AuthManager
    
    auth_manager = AuthManager()
    client = auth_manager.get_authenticated_client()
    
    if not client:
        raise ValueError("Authentication required for storing embeddings")
    
    try:
        # Get user ID
        user_response = client.auth.get_user()
        user_id = user_response.user.id
        
        vector_data = {
            "clip_id": clip_id,
            "user_id": user_id,
            "embedding_type": "full_clip",
            "embedding_source": "combined",
            "summary_vector": summary_embedding,
            "keyword_vector": keyword_embedding,
            "embedded_content": f"Summary: {summary_content}\nKeywords: {keyword_content}",
            "original_content": original_content,
            "token_count": metadata["summary_tokens"] + metadata["keyword_tokens"],
            "original_token_count": count_tokens(original_content),
            "truncation_method": metadata["summary_truncation"]
        }
        
        result = client.table('vectors').insert(vector_data).execute()
        
        if logger:
            logger.info(f"Stored embeddings for clip: {clip_id}")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to store embeddings: {str(e)}")
        raise