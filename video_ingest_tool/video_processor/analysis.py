"""
AI video analysis for the video ingest tool.

This module provides AI-powered video analysis capabilities using Google's
Gemini Flash 2.5 model to extract comprehensive information from video content.
"""

import json
import os
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file (required for Prefect workers)
load_dotenv()

try:
    # Import the new unified Google GenAI SDK
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

import structlog
logger = structlog.get_logger(__name__)

def load_filmmaker_vocabulary() -> Dict[str, Any]:
    """
    Load filmmaker-focused vocabulary from JSON file.
    
    Returns:
        Dict[str, Any]: Vocabulary data with categories and terms
    """
    try:
        vocab_file_path = os.path.join(os.path.dirname(__file__), 'filmmaker_vocabulary.json')
        with open(vocab_file_path, 'r', encoding='utf-8') as f:
            vocab_data = json.load(f)
        return vocab_data
    except Exception as e:
        logger.warning(f"Could not load filmmaker vocabulary: {e}")
        # Return fallback minimal vocabulary
        return {
            "categories": {
                "people_and_roles": ["person", "subject", "presenter"],
                "actions_and_performance": ["speaking", "demonstrating", "showing"],
                "emotions_and_tone": ["professional", "engaged", "focused"],
                "settings_and_environments": ["studio", "office", "indoor"],
                "production_elements": ["interview", "presentation", "tutorial"],
                "visual_quality": ["clear", "well-lit", "professional-grade"]
            }
        }

def get_filmmaker_vocabulary_list() -> List[str]:
    """
    Get a flat list of all filmmaker vocabulary terms.
    
    Returns:
        List[str]: All vocabulary terms from all categories
    """
    vocab_data = load_filmmaker_vocabulary()
    all_terms = []
    
    for category_terms in vocab_data.get("categories", {}).values():
        all_terms.extend(category_terms)
    
    return all_terms

def get_vocabulary_section() -> str:
    """Generate vocabulary section for AI prompt including both standardized and filmmaker-focused terms."""
    vocab_data = load_filmmaker_vocabulary()
    categories = vocab_data.get("categories", {})
    
    filmmaker_vocab_text = """

**FILMMAKER-FOCUSED VOCABULARY FOR SUMMARY AND KEYWORDS**

In addition to the standardized vocabulary above, preferentially use these filmmaker-focused terms in your summary and keyword sections:

"""
    
    for category_name, terms in categories.items():
        category_display = category_name.replace('_', ' ').title()
        terms_text = ', '.join(terms)
        filmmaker_vocab_text += f"**{category_display}:** {terms_text}\n\n"
    
    filmmaker_vocab_text += """
**IMPORTANT:** These filmmaker terms should be used in summary, key_activities, and content descriptions. 
Do NOT use them in visual_analysis sections - keep existing shot types and technical quality terms unchanged.

"""

    vocab_text = """
**CRITICAL: STANDARDIZED VOCABULARY FOR CONSISTENCY**

To ensure consistency across all video analyses, you MUST use only these standardized terms when describing visual content:

**Person Descriptions:**
- Age: child, teenager, young adult, middle-aged person, older adult
- Gender: Use "person" or "individual" (neutral terms preferred)
- Hair colors: blonde, brown, black, red, gray, white, silver
- Hair styles: short hair, medium-length hair, long hair, curly hair, straight hair, wavy hair
- Clothing tops: t-shirt, shirt, blouse, sweater, jacket, hoodie, tank top
- Colors: black, white, blue, red, green, yellow, purple, orange, gray, pink
- Poses: standing, sitting, walking, gesturing, speaking, looking at camera, profile view
- Expressions: neutral expression, smiling, serious expression, speaking, listening, concentrated

**Settings & Backgrounds:**
- Indoor: studio, office, home, classroom, conference room, kitchen, living room
- Outdoor: park, street, garden, beach, forest, mountain, urban area
- Backgrounds: green screen, white background, natural background, indoor background, outdoor background

**Lighting & Camera:**
- Lighting: bright lighting, soft lighting, natural lighting, studio lighting, low lighting, backlighting
- Positions: centered, left side, right side, close-up view, medium view, wide view

**IMPORTANT CONSISTENCY RULES:**
1. Always use "person" instead of "man/woman" unless gender is critically relevant
2. Use exact color names from the list above
3. Use exact clothing terms from the list above
4. Describe hair using the standardized combinations (e.g., "curly brown hair" not "messy hair")
5. Use consistent lighting and position terms
6. When multiple people are present, describe them using consistent patterns

This vocabulary ensures that visually similar clips will receive similar descriptions and embeddings.
"""
    
    return vocab_text + filmmaker_vocab_text

class VideoAnalyzer:
    """AI-powered video analyzer using Gemini Flash 2.5."""
    
    def __init__(self, api_key: str, fps: int = 1, db_connection=None):
        """
        Initialize video analyzer.
        
        Args:
            api_key: Google Gemini API key
            fps: Frames per second for video analysis
            db_connection: Optional database connection for reference-based analysis
        """
        if not GENAI_AVAILABLE:
            raise ImportError("Google GenAI library not available. Install with: pip install google-genai")
        
        self.logger = logger
        self.fps = fps
        self.db_connection = db_connection
        
        # Initialize the client with the new unified SDK
        self.client = genai.Client(api_key=api_key)
        
        self.logger.info("VideoAnalyzer initialized with Gemini Flash 2.5")
        
    def _get_comprehensive_analysis_schema(self) -> types.Schema:
        """
        Define comprehensive analysis schema for video processing using modern genai.types.Schema.
        
        Returns:
            types.Schema: Properly typed schema for structured AI analysis
        """
        return types.Schema(
            type=types.Type.OBJECT,
            required=["summary", "visual_analysis", "audio_analysis", "content_analysis"],
            properties={
                "summary": types.Schema(
                    type=types.Type.OBJECT,
                    required=["overall", "key_activities", "content_category", "condensed_summary"],
                    properties={
                        "overall": types.Schema(
                            type=types.Type.STRING,
                            description="Detailed and accurate description of exactly what's seen and heard in the video. Include specific visual elements, subjects, actions, settings, and colors. Describe exactly what is happening in the frame with precision."
                        ),
                        "key_activities": types.Schema(
                            type=types.Type.ARRAY,
                            description="List of main activities or actions occurring in the video with specific visual details",
                            items=types.Schema(type=types.Type.STRING)
                        ),
                        "content_category": types.Schema(
                            type=types.Type.STRING,
                            description="Primary category of content (e.g., Interview, Tutorial, Event, Nature, etc.)"
                        ),
                        "condensed_summary": types.Schema(
                            type=types.Type.STRING,
                            description="Ultra-concise version of the overall description limited to 64 tokens max. Include only the most essential visual elements, subjects, and setting. This will be used for SigLIP embeddings."
                        )
                    }
                ),
                "visual_analysis": types.Schema(
                    type=types.Type.OBJECT,
                    required=["shot_types", "technical_quality"],
                    properties={
                        "shot_types": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                required=["timestamp", "shot_attributes_ordered", "description"],
                                properties={
                                    "timestamp": types.Schema(type=types.Type.STRING),
                                    "duration_seconds": types.Schema(type=types.Type.NUMBER),
                                    "shot_attributes_ordered": types.Schema(
                                        type=types.Type.ARRAY,
                                        description="A list of 2-5 descriptive attributes for the shot, ordered by prominence or accuracy (most prominent/defining attribute first). Attributes can describe framing, angle, movement, production techniques, or visual style. Use consistent terminology from the provided vocabulary.",
                                        items=types.Schema(type=types.Type.STRING)
                                    ),
                                    "description": types.Schema(type=types.Type.STRING),
                                    "confidence": types.Schema(type=types.Type.NUMBER)
                                }
                            )
                        ),
                        "technical_quality": types.Schema(
                            type=types.Type.OBJECT,
                            required=["overall_focus_quality", "stability_assessment", "usability_rating"],
                            properties={
                                "overall_focus_quality": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["Excellent", "Good", "Fair", "Poor", "Very Poor"]
                                ),
                                "stability_assessment": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["Very Stable", "Stable", "Moderately Shaky", "Very Shaky", "Unusable"]
                                ),
                                "detected_artifacts": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["type", "severity", "description"],
                                        properties={
                                            "type": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Blockiness", "Banding", "Dead Pixels", "Sensor Dust", "Compression Artifacts", "Motion Blur", "Other"]
                                            ),
                                            "severity": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Minor", "Moderate", "Severe"]
                                            ),
                                            "description": types.Schema(type=types.Type.STRING)
                                        }
                                    )
                                ),
                                "usability_rating": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["Excellent", "Good", "Acceptable", "Poor", "Unusable"]
                                )
                            }
                        ),
                        "text_and_graphics": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "detected_text": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["timestamp", "text_type", "readability"],
                                        properties={
                                            "timestamp": types.Schema(type=types.Type.STRING),
                                            "text_content": types.Schema(type=types.Type.STRING),
                                            "text_type": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Title/Heading", "Subtitle", "Caption", "UI Text", "Signage", "Other", "Unclear/Blurry"]
                                            ),
                                            "readability": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Clear", "Partially Clear", "Blurry", "Unreadable"]
                                            )
                                        }
                                    )
                                ),
                                "detected_logos_icons": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["timestamp", "description", "element_type"],
                                        properties={
                                            "timestamp": types.Schema(type=types.Type.STRING),
                                            "description": types.Schema(
                                                type=types.Type.STRING,
                                                description="Generic description without brand identification (e.g., 'Red circular icon', 'Blue rectangular logo')"
                                            ),
                                            "element_type": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Logo", "Icon", "Graphic Element", "UI Element"]
                                            ),
                                            "size": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Small", "Medium", "Large", "Prominent"]
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                        "keyframe_analysis": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "recommended_keyframes": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["timestamp", "reason", "visual_quality"],
                                        properties={
                                            "timestamp": types.Schema(type=types.Type.STRING),
                                            "reason": types.Schema(
                                                type=types.Type.STRING,
                                                description="Why this frame is recommended (e.g., 'Clear face visible', 'Good composition', 'Key action moment')"
                                            ),
                                            "visual_quality": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Excellent", "Good", "Fair", "Poor"]
                                            )
                                        }
                                    )
                                ),
                                "recommended_thumbnails": types.Schema(
                                    type=types.Type.ARRAY,
                                    description="Exactly 3 frames ranked by how well they represent the entire clip",
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["timestamp", "reason", "rank"],
                                        properties={
                                            "timestamp": types.Schema(type=types.Type.STRING),
                                            "reason": types.Schema(
                                                type=types.Type.STRING,
                                                description="Why this frame represents the video well"
                                            ),
                                            "rank": types.Schema(
                                                type=types.Type.STRING,
                                                description="Rank with 1 being best representative frame",
                                                enum=["1", "2", "3"]
                                            )
                                        }
                                    )
                                )
                            }
                        )
                    }
                ),
                "audio_analysis": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "transcript": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "full_text": types.Schema(type=types.Type.STRING),
                                "segments": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["timestamp", "text"],
                                        properties={
                                            "timestamp": types.Schema(type=types.Type.STRING),
                                            "speaker": types.Schema(type=types.Type.STRING),
                                            "text": types.Schema(type=types.Type.STRING),
                                            "confidence": types.Schema(type=types.Type.NUMBER)
                                        }
                                    )
                                )
                            }
                        ),
                        "speaker_analysis": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "speaker_count": types.Schema(type=types.Type.INTEGER),
                                "speakers": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["speaker_id", "speaking_time_seconds"],
                                        properties={
                                            "speaker_id": types.Schema(type=types.Type.STRING),
                                            "speaking_time_seconds": types.Schema(type=types.Type.NUMBER),
                                            "attributes": types.Schema(
                                                type=types.Type.ARRAY,
                                                items=types.Schema(type=types.Type.STRING)
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                        "sound_events": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                required=["timestamp", "event_type", "description"],
                                properties={
                                    "timestamp": types.Schema(type=types.Type.STRING),
                                    "event_type": types.Schema(type=types.Type.STRING),
                                    "description": types.Schema(type=types.Type.STRING),
                                    "duration_seconds": types.Schema(type=types.Type.NUMBER)
                                }
                            )
                        ),
                        "audio_quality": types.Schema(
                            type=types.Type.OBJECT,
                            required=["clarity", "background_noise_level", "dialogue_intelligibility"],
                            properties={
                                "clarity": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["Excellent", "Good", "Fair", "Poor", "Very Poor"]
                                ),
                                "background_noise_level": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["None", "Minimal", "Moderate", "Significant", "Overwhelming"]
                                ),
                                "dialogue_intelligibility": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["Excellent", "Good", "Fair", "Poor", "Very Poor", "No Dialogue"]
                                )
                            }
                        )
                    }
                ),
                "content_analysis": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "entities": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "people_count": types.Schema(type=types.Type.INTEGER),
                                "people_details": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["description"],
                                        properties={
                                            "description": types.Schema(type=types.Type.STRING),
                                            "role": types.Schema(type=types.Type.STRING),
                                            "appearances": types.Schema(
                                                type=types.Type.ARRAY,
                                                items=types.Schema(
                                                    type=types.Type.OBJECT,
                                                    required=["timestamp"],
                                                    properties={
                                                        "timestamp": types.Schema(type=types.Type.STRING),
                                                        "duration_seconds": types.Schema(type=types.Type.NUMBER)
                                                    }
                                                )
                                            )
                                        }
                                    )
                                ),
                                "locations": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["name", "type"],
                                        properties={
                                            "name": types.Schema(type=types.Type.STRING),
                                            "type": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Indoor", "Outdoor", "Urban", "Rural", "Studio", "Other"]
                                            ),
                                            "description": types.Schema(type=types.Type.STRING)
                                        }
                                    )
                                ),
                                "objects_of_interest": types.Schema(
                                    type=types.Type.ARRAY,
                                    items=types.Schema(
                                        type=types.Type.OBJECT,
                                        required=["object", "significance"],
                                        properties={
                                            "object": types.Schema(type=types.Type.STRING),
                                            "significance": types.Schema(
                                                type=types.Type.STRING,
                                                enum=["Primary Subject", "Secondary Element", "Background Element", "Prop"]
                                            ),
                                            "timestamps": types.Schema(
                                                type=types.Type.ARRAY,
                                                items=types.Schema(type=types.Type.STRING)
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                        "activity_summary": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                required=["timestamp", "activity", "importance"],
                                properties={
                                    "timestamp": types.Schema(type=types.Type.STRING),
                                    "activity": types.Schema(type=types.Type.STRING),
                                    "duration": types.Schema(type=types.Type.STRING),
                                    "importance": types.Schema(
                                        type=types.Type.STRING,
                                        enum=["High", "Medium", "Low"]
                                    )
                                }
                            )
                        ),
                        "content_warnings": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                required=["type", "description", "timestamp"],
                                properties={
                                    "type": types.Schema(
                                        type=types.Type.STRING,
                                        enum=["Violence", "Strong Language", "Nudity", "Sexual Content", "Drug Use", "Alcohol Use", "Disturbing Imagery", "Political Content", "Other"]
                                    ),
                                    "description": types.Schema(type=types.Type.STRING),
                                    "timestamp": types.Schema(type=types.Type.STRING)
                                }
                            )
                        )
                    }
                )
            }
        )
        
    def _create_comprehensive_analysis_prompt(self, reference_examples: str = "") -> str:
        """
        Create comprehensive analysis prompt for Gemini Flash 2.5.
        
        Args:
            reference_examples: Optional reference examples from existing analyses
        
        Returns:
            str: Prompt for the Gemini model
        """
        vocabulary_section = get_vocabulary_section()
        
        return f"""
You are a professional filmmaker and producer. Your job is to analyze this video so that you can accurately describe it to others and so it can be categorized and found later.

{vocabulary_section}

{reference_examples}

Please analyze this video comprehensively and provide detailed information in all of the following areas:
        
1. For the 'summary' object in the schema, provide the following details:
   - **For the 'overall' field:** Construct a detailed and accurate narrative description, **approximately 100-256 tokens long,** of what is seen and heard throughout the video. This description must:
     - Detail specific visual elements, subjects, key actions in sequence, settings, and dominant colors.
     - Describe precisely what happens with factual accuracy.
     - **USE ONLY THE STANDARDIZED VOCABULARY PROVIDED ABOVE for person descriptions, clothing, colors, settings, etc.**
     - **Crucially, from the video's discernible speech or transcript, integrate 1-2 impactful and concise key phrases, short sentences, or direct quotes that capture critical information or the essence of a key moment. These should be naturally woven into this overall description.**
   - **For the 'key_activities' field (array of strings):** List the main activities or actions occurring in the video. Each item in the array should be a string describing a distinct activity with specific visual details **using the standardized vocabulary.**
   - **For the 'content_category' field (string):** Identify and state the primary category of the content (e.g., Interview, Tutorial, Event, Nature, Product Demo, etc.).
   - **For the 'condensed_summary' field (string):** Generate an ultra-concise version, **strictly limited to a maximum of 64 tokens,** of the overall video description. This summary must include only the most essential and directly observable visual elements, subjects, and the immediate setting. **CRITICAL: Use ONLY standardized vocabulary terms for maximum embedding consistency.** This is critical for SigLIP embeddings and must be purely descriptive of visuals.

2. For the 'visual_analysis' object in the schema, provide the following details:
   - **For the 'shot_types' field (array of objects):** For each identified distinct shot segment in the video, you will populate an object. Instead of a single 'shot_type', you will now provide an ordered list of descriptive attributes for its 'shot_attributes_ordered' field.
     - **List between 2 to 5 attributes for each shot segment.**
     - **Order these attributes starting with the one you deem most defining, primary, or most accurate for that shot segment, followed by other relevant attributes in decreasing order of prominence or confidence.**
     - **You MUST ONLY use the following vocabulary for all shot attributes, unless a shot has a truly unique style not covered by these terms (in which case use 'Other Notable Style' and explain in the description). Do NOT invent new terms or use synonyms. Use only the above vocabulary for all shot attributes:**
         - Aerial / Drone Shot
         - Wide Shot / Establishing Shot
         - Medium Shot
         - Medium Close-Up (MCU)
         - Close-Up (CU)
         - Extreme Close-Up (ECU) / Detail Shot
         - Over-the-Shoulder Shot (OTS)
         - Low Angle Shot
         - High Angle Shot
         - Dutch Angle / Canted Shot
         - POV (Point of View) Shot
         - Tracking / Follow Shot
         - Static / Locked-Down Shot
         - Handheld Shot
         - Interview Setup
         - Screen Recording / Screencast
         - Graphic / Animation
         - Green Screen
         - Slow Motion
         - Time-Lapse
         - Rack Focus
         - Medium Close-Up
         - Other Notable Style (use this ONLY if a shot has a very distinct visual characteristic not covered, and elaborate in the shot's 'description' field)
     - **The 'description' field for this shot segment should then provide a brief (1-2 sentences) natural language summary that contextualizes these attributes for the specific shot, USING STANDARDIZED VOCABULARY.**
     - **The 'confidence' field for this shot segment should reflect your confidence in the primary (first) attribute listed or the overall set of attributes provided.**
     - 'timestamp' (string): Start time of the shot. **Use the format "5s600ms" (e.g., 5 seconds and 600 milliseconds) for all timestamps.**
     - 'duration_seconds' (number): Duration of the shot.
     - 'shot_attributes_ordered' (array of strings): The ordered list of attributes as described above.
     - 'description' (string): A brief description of the shot's content or composition.
     - 'confidence' (number, optional): If your model can provide it, include a confidence score (0-1) for the shot type classification.
   - **For the 'technical_quality' object:**
     - **For 'overall_focus_quality' (string):** Assess and select from the enum ["Excellent", "Good", "Fair", "Poor", "Very Poor"].
     - **For 'stability_assessment' (string):** Assess and select from the enum ["Very Stable", "Stable", "Moderately Shaky", "Very Shaky", "Unusable"].
     - **For 'detected_artifacts' (array of objects):** If any visual artifacts are detected, provide an array where each object details an artifact with 'type' (from enum), 'severity' (from enum), and 'description' (string).
     - **For 'usability_rating' (string):** Assess and select from the enum ["Excellent", "Good", "Acceptable", "Poor", "Unusable"].
   - **For the 'text_and_graphics' object:**
     - **For 'detected_text' (array of objects):** If any text is visible, provide an array where each object details detected text, including 'timestamp', 'text_content' (string), 'text_type' (from enum), and 'readability' (from enum). **Use the format "5s600ms" for all timestamps.**
     - **For 'detected_logos_icons' (array of objects):** If any logos or icons are visible, provide an array where each object details them, including 'timestamp', 'description' (string, generic without brand ID, e.g., 'Red circular icon'), 'element_type' (from enum), and 'size' (from enum). **Use the format "5s600ms" for all timestamps.**
   - **For the 'keyframe_analysis.recommended_keyframes' field (array of objects):** Beyond the three main thumbnails, if there are other notable keyframes, list them here. Each object should include 'timestamp', 'reason' (string, why this frame is recommended), and 'visual_quality' (from enum). **Use the format "5s600ms" for all timestamps.**
   - **For the 'keyframe_analysis.recommended_thumbnails' field (array of exactly 3 objects):** Select and provide details for exactly three (3) thumbnail frames, ranked by how well they represent the entire clip. These frames should be visually distinct, clear, well-composed, in-focus, and suitable as video thumbnails. For each of the 3 thumbnail objects, you must provide:
      a) 'timestamp' (string): The timestamp of the selected frame. **Use the format "5s600ms" (e.g., 5 seconds and 600 milliseconds).**
      b) 'reason' (string): A brief explanation of why this frame represents the video well and is suitable as a thumbnail.
      c) 'rank' (string): The rank ("1", "2", or "3"), with "1" being the most representative frame.
   - Prioritize: Frames that represent the video's main subject and content, are clear, well-composed, in-focus, and diverse in representing different aspects of the video.

3. For the 'audio_analysis' object in the schema, provide the following details:
   - **For the 'transcript' object:**
     - **For 'full_text' (string):** Provide the complete transcribed text of all speech in the video.
     - **For 'segments' (array of objects):** If segmentation is possible, provide an array where each object details a transcript segment, including 'timestamp', 'speaker' (string, if identifiable, e.g., "Speaker 1"), 'text' (string content of the segment), and 'confidence' (number, 0-1 for transcription accuracy of the segment). **Use the format "5s600ms" for all timestamps.**
   - **For the 'speaker_analysis' object:**
     - **For 'speaker_count' (integer):** Provide the total number of distinct speakers identified.
     - **For 'speakers' (array of objects):** If speaker identification is performed, provide an array where each object details a speaker, including 'speaker_id' (string), 'speaking_time_seconds' (number), and 'attributes' (array of strings, e.g., perceived gender, accent if discernible and relevant).
   - **For the 'sound_events' field (array of objects):** Identify significant non-speech sound events. Each object should include 'timestamp', 'event_type' (string, e.g., "music", "applause", "door slam"), 'description' (string), and 'duration_seconds' (number). **Use the format "5s600ms" for all timestamps.**
   - **For the 'audio_quality' object:**
     - **For 'clarity' (string):** Assess overall audio clarity and select from the enum.
     - **For 'background_noise_level' (string):** Assess background noise and select from the enum.
     - **For 'dialogue_intelligibility' (string):** Assess how well dialogue can be understood and select from the enum (or "No Dialogue").

4. For the 'content_analysis' object in the schema, provide the following details:
   - **For the 'entities' object:**
     - **For 'people_count' (integer):** State the total number of distinct people visually identified.
     - **For 'people_details' (array of objects):** For each distinct person identified, provide an object with 'description' (string using STANDARDIZED VOCABULARY, e.g., "person with red shirt"), 'role' (string, e.g., "interviewer," "main subject"), and 'appearances' (array of objects with 'timestamp' and 'duration_seconds' for each appearance). **Use the format "5s600ms" for all timestamps.**
     - **For 'locations' (array of objects):** Identify distinct locations using standardized vocabulary. Each object should include 'name' (string, e.g., "Central Park," "Office Meeting Room"), 'type' (from enum), and 'description' (string using standardized terms).
     - **For 'objects_of_interest' (array of objects):** Identify key objects using standardized vocabulary. Each object should include 'object' (string, e.g., "laptop," "red book"), 'significance' (from enum), and 'timestamps' (array of strings indicating when the object is visible). **Use the format "5s600ms" for all timestamps.**
   - **For the 'activity_summary' field (array of objects):** Summarize key activities segment by segment using standardized vocabulary. Each object should include 'timestamp', 'activity' (string description), 'duration' (string, e.g., "5 seconds"), and 'importance' (from enum). **Use the format "5s600ms" for all timestamps.**
   - **For the 'content_warnings' field (array of objects):** If any sensitive content is present, provide an array where each object details a warning, including 'type' (from enum like "Violence", "Strong Language"), 'description' (string, specific details), and 'timestamp'. If no warnings, this can be an empty array or omitted if allowed by schema. **Use the format "5s600ms" for all timestamps.**
        
MOST IMPORTANT: Your descriptions must be accurate and precise. Focus on exactly what is seen and heard, with specific details about visual elements and audio content. **ALWAYS USE THE STANDARDIZED VOCABULARY provided above to ensure consistency across all analyses - this is critical for accurate indexing and searchability of the video content.**
        
Please be thorough but concise in your descriptions. Organize the analysis according to the provided schema. Focus on information that would be valuable for video editors to quickly understand and organize footage.
        """
        
    def analyze_video(self, video_to_analyze: str) -> Dict[str, Any]:
        """
        Perform comprehensive video analysis using Gemini AI.
        
        Args:
            video_to_analyze: Path to video file to analyze
            
        Returns:
            Dict[str, Any]: Structured analysis results
        """
        try:
            self.logger.info(f"Starting comprehensive AI analysis of: {video_to_analyze}")
            
            # Detect content type for better reference matching
            content_hints = self._detect_content_type(video_to_analyze)
            self.logger.info(f"Detected content hints: {content_hints}")
            
            # Get reference examples for consistency
            reference_examples = self._get_reference_examples(content_hints)
            if reference_examples:
                self.logger.info("Using reference examples for consistency")
            
            # Get model from environment variable with fallback
            model_name = os.getenv('VIDEO_MODEL', 'models/gemini-2.5-flash-preview')
            self.logger.info(f"Using model: {model_name}")
            
            # Check file size 
            file_size = os.path.getsize(video_to_analyze)
            file_size_mb = file_size / (1024 * 1024)
            self.logger.info(f"Video file size: {file_size_mb:.1f}MB")
            
            # Check if file is small enough for inline data (recommended <20MB)
            if file_size_mb > 20:
                self.logger.warning(f"File size ({file_size_mb:.1f}MB) exceeds 20MB limit for inline data. Consider using file upload method.")
                return {
                    'error': f'File too large for inline data ({file_size_mb:.1f}MB > 20MB)',
                    'analysis_status': 'failed',
                    'analysis_timestamp': time.time()
                }
            
            # Read video file as bytes for inline data
            self.logger.info("Reading video file for inline data transmission...")
            with open(video_to_analyze, 'rb') as video_file:
                video_bytes = video_file.read()
            
            self.logger.info(f"Video loaded into memory: {len(video_bytes)} bytes")
            
            # Create the analysis prompt with reference examples
            prompt = self._create_comprehensive_analysis_prompt(reference_examples)
            
            # Get the schema for structured output
            schema = self._get_comprehensive_analysis_schema()
            
            # Structure content properly with roles
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=video_bytes, mime_type='video/mp4')
                    ]
                )
            ]
            
            # Configure generation with modern approach
            generate_content_config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=schema
            )
            
            # Generate content using modern structured approach
            self.logger.info("Sending video analysis request with structured content...")
            response = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=generate_content_config
            )
            
            self.logger.info("Video analysis completed successfully")
            
            # Parse the structured JSON response
            analysis_data = json.loads(response.text)
            self.logger.info(f"Received structured analysis with keys: {list(analysis_data.keys())}")
            
            return analysis_data
            
        except Exception as e:
            self.logger.error(f"Video analysis failed: {str(e)}")
            
            # Log detailed error information
            import traceback
            self.logger.error(f"Full error traceback: {traceback.format_exc()}")
            
            # Try to get more details from the exception
            if hasattr(e, 'response'):
                self.logger.error(f"Response object: {e.response}")
                if hasattr(e.response, 'text'):
                    self.logger.error(f"Response text: {e.response.text}")
                if hasattr(e.response, 'status_code'):
                    self.logger.error(f"Response status code: {e.response.status_code}")
                if hasattr(e.response, 'headers'):
                    self.logger.error(f"Response headers: {dict(e.response.headers)}")
            
            # Log Google API specific error attributes
            if hasattr(e, 'code'):
                self.logger.error(f"Google API error code: {e.code}")
            if hasattr(e, 'message'):
                self.logger.error(f"Google API error message: {e.message}")
            if hasattr(e, 'status'):
                self.logger.error(f"Google API error status: {e.status}")
            
            # Check if this is a Google server error (500) - if so, provide fallback
            is_server_error = (
                hasattr(e, 'code') and str(e.code) == "500" or
                hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 500 or
                "500 INTERNAL" in str(e)
            )
            
            if is_server_error:
                self.logger.warning("Google server error detected. Returning fallback analysis structure...")
                # Return a minimal valid analysis structure to keep pipeline working
                return {
                    'summary': {
                        'overall': 'AI analysis temporarily unavailable due to Google server issues. Basic metadata processing completed successfully.',
                        'key_activities': ['Video processing', 'Metadata extraction'],
                        'content_category': 'Unknown',
                        'condensed_summary': 'Video processed without AI analysis'
                    },
                    'visual_analysis': {
                        'shot_types': [],
                        'technical_quality': {
                            'overall_focus_quality': 'Unknown',
                            'stability_assessment': 'Unknown',
                            'detected_artifacts': [],
                            'usability_rating': 'Unknown'
                        }
                    },
                    'audio_analysis': {},
                    'content_analysis': {},
                    'analysis_status': 'fallback_due_to_server_error',
                    'analysis_timestamp': time.time(),
                    'server_error': str(e)
                }
            
            return {
                'error': str(e),
                'analysis_status': 'failed',
                'analysis_timestamp': time.time()
            } 

    def _get_reference_examples(self, video_content_hints: List[str] = None) -> str:
        """
        Get reference examples from existing analyses to maintain consistency.
        
        Args:
            video_content_hints: Optional hints about video content to find relevant examples
            
        Returns:
            str: Reference examples section for the prompt
        """
        if not self.db_connection:
            return ""
        
        try:
            # Get a few recent examples of good descriptions for reference
            query = """
            SELECT content_summary, ai_selected_thumbnails_json 
            FROM app_data.clips 
            WHERE content_summary IS NOT NULL 
            AND ai_selected_thumbnails_json IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 3
            """
            
            examples = self.db_connection.execute(query).fetchall()
            
            if not examples:
                return ""
            
            reference_text = """

**REFERENCE EXAMPLES FOR CONSISTENCY**

Here are examples of well-formatted descriptions from previous analyses. Use these as style and terminology guides:

"""
            
            import json
            for i, (summary, thumbnails_json) in enumerate(examples, 1):
                try:
                    thumbnails = json.loads(thumbnails_json)
                    if thumbnails and len(thumbnails) > 0:
                        sample_thumbnail = thumbnails[0]
                        reference_text += f"""
Example {i}:
- Summary: "{summary[:100]}..."
- Thumbnail timestamp: "{sample_thumbnail.get('timestamp', 'N/A')}"
- Thumbnail reason: "{sample_thumbnail.get('reason', 'N/A')[:80]}..."

"""
                except:
                    continue
            
            reference_text += """
Notice the consistent terminology, structure, and level of detail. Match this style in your analysis.

"""
            return reference_text
            
        except Exception as e:
            self.logger.warning(f"Could not fetch reference examples: {e}")
            return ""
    
    def _detect_content_type(self, video_path: str) -> List[str]:
        """
        Simple content type detection based on filename and basic analysis.
        This could be expanded with actual video preview analysis.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List[str]: Content hints for finding relevant reference examples
        """
        filename = os.path.basename(video_path).lower()
        hints = []
        
        # Basic filename-based detection
        if any(term in filename for term in ['interview', 'talk', 'conversation']):
            hints.append('interview')
        if any(term in filename for term in ['tutorial', 'demo', 'howto']):
            hints.append('tutorial')
        if any(term in filename for term in ['screen', 'record', 'capture']):
            hints.append('screen_recording')
        if any(term in filename for term in ['event', 'conference', 'meeting']):
            hints.append('event')
        
        return hints 