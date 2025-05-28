"""
Video analysis module for AI-powered video content analysis using Gemini Flash 2.5.

This module provides the VideoAnalyzer class for handling Gemini AI integration.
"""

import json
import logging
from typing import Dict, Any

from google import genai
from google.genai import types


class VideoAnalyzer:
    """Handles comprehensive video analysis using Gemini Flash 2.5."""
    
    def __init__(self, api_key: str, fps: int = 1):
        """
        Initialize the VideoAnalyzer with API key and frame rate.
        
        Args:
            api_key: Gemini API key
            fps: Frame rate for video analysis (default: 1)
        """
        self.client = genai.Client(api_key=api_key)
        self.api_key = api_key
        self.fps = fps
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _get_comprehensive_analysis_schema(self) -> Dict[str, Any]:
        """
        Define comprehensive analysis schema for video processing.
        
        Returns:
            Dict[str, Any]: JSON schema for structured AI analysis
        """
        return {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "OBJECT",
                    "properties": {
                        "overall": {
                            "type": "STRING",
                            "description": "Detailed and accurate description of exactly what's seen and heard in the video. Include specific visual elements, subjects, actions, settings, and colors. Describe exactly what is happening in the frame with precision."
                        },
                        "key_activities": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of main activities or actions occurring in the video with specific visual details"
                        },
                        "content_category": {
                            "type": "STRING",
                            "description": "Primary category of content (e.g., Interview, Tutorial, Event, Nature, etc.)"
                        },
                        "condensed_summary": {
                            "type": "STRING",
                            "description": "Ultra-concise version of the overall description limited to 64 tokens max. Include only the most essential visual elements, subjects, and setting. This will be used for SigLIP embeddings."
                        }
                    },
                    "required": ["overall", "key_activities", "content_category", "condensed_summary"]
                },
                "visual_analysis": {
                    "type": "OBJECT",
                    "properties": {
                        "shot_types": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "timestamp": {"type": "STRING"},
                                    "duration_seconds": {"type": "NUMBER"},
                                    "shot_attributes_ordered": {
                                        "type": "ARRAY",
                                        "items": {"type": "STRING"},
                                        "description": "A list of 2-5 descriptive attributes for the shot, ordered by prominence or accuracy (most prominent/defining attribute first). Attributes can describe framing, angle, movement, production techniques, or visual style. Use consistent terminology from the provided vocabulary."
                                    },
                                    "description": {"type": "STRING"},
                                    "confidence": {"type": "NUMBER", "minimum": 0, "maximum": 1}
                                },
                                "required": ["timestamp", "shot_attributes_ordered", "description"]
                            }
                        },
                        "technical_quality": {
                            "type": "OBJECT",
                            "properties": {
                                "overall_focus_quality": {
                                    "type": "STRING",
                                    "enum": ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
                                },
                                "stability_assessment": {
                                    "type": "STRING",
                                    "enum": ["Very Stable", "Stable", "Moderately Shaky", "Very Shaky", "Unusable"]
                                },
                                "detected_artifacts": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "type": {
                                                "type": "STRING",
                                                "enum": ["Blockiness", "Banding", "Dead Pixels", "Sensor Dust", "Compression Artifacts", "Motion Blur", "Other"]
                                            },
                                            "severity": {
                                                "type": "STRING",
                                                "enum": ["Minor", "Moderate", "Severe"]
                                            },
                                            "description": {"type": "STRING"}
                                        },
                                        "required": ["type", "severity", "description"]
                                    }
                                },
                                "usability_rating": {
                                    "type": "STRING",
                                    "enum": ["Excellent", "Good", "Acceptable", "Poor", "Unusable"]
                                }
                            },
                            "required": ["overall_focus_quality", "stability_assessment", "usability_rating"]
                        },
                        "text_and_graphics": {
                            "type": "OBJECT",
                            "properties": {
                                "detected_text": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "timestamp": {"type": "STRING"},
                                            "text_content": {"type": "STRING"},
                                            "text_type": {
                                                "type": "STRING",
                                                "enum": ["Title/Heading", "Subtitle", "Caption", "UI Text", "Signage", "Other", "Unclear/Blurry"]
                                            },
                                            "readability": {
                                                "type": "STRING",
                                                "enum": ["Clear", "Partially Clear", "Blurry", "Unreadable"]
                                            }
                                        },
                                        "required": ["timestamp", "text_type", "readability"]
                                    }
                                },
                                "detected_logos_icons": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "timestamp": {"type": "STRING"},
                                            "description": {
                                                "type": "STRING",
                                                "description": "Generic description without brand identification (e.g., 'Red circular icon', 'Blue rectangular logo')"
                                            },
                                            "element_type": {
                                                "type": "STRING",
                                                "enum": ["Logo", "Icon", "Graphic Element", "UI Element"]
                                            },
                                            "size": {
                                                "type": "STRING",
                                                "enum": ["Small", "Medium", "Large", "Prominent"]
                                            }
                                        },
                                        "required": ["timestamp", "description", "element_type"]
                                    }
                                }
                            }
                        },
                        "keyframe_analysis": {
                            "type": "OBJECT",
                            "properties": {
                                "recommended_keyframes": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "timestamp": {"type": "STRING"},
                                            "reason": {
                                                "type": "STRING",
                                                "description": "Why this frame is recommended (e.g., 'Clear face visible', 'Good composition', 'Key action moment')"
                                            },
                                            "visual_quality": {
                                                "type": "STRING",
                                                "enum": ["Excellent", "Good", "Fair", "Poor"]
                                            }
                                        },
                                        "required": ["timestamp", "reason", "visual_quality"]
                                    }
                                },
                                "recommended_thumbnails": {
                                    "type": "ARRAY",
                                    "description": "Exactly 3 frames ranked by how well they represent the entire clip",
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "timestamp": {"type": "STRING"},
                                            "description": {
                                                "type": "STRING",
                                                "description": "Concise 10-20 token description using format: Subject Action/Type Key-Details Context"
                                            },
                                            "reason": {
                                                "type": "STRING",
                                                "description": "Why this frame represents the video well"
                                            },
                                            "rank": {
                                                "type": "STRING",
                                                "enum": ["1", "2", "3"],
                                                "description": "Rank with 1 being best representative frame"
                                            }
                                        },
                                        "required": ["timestamp", "description", "reason", "rank"]
                                    }
                                }
                            }
                        }
                    },
                    "required": ["shot_types", "technical_quality"]
                },
                "audio_analysis": {
                    "type": "OBJECT",
                    "properties": {
                        "transcript": {
                            "type": "OBJECT",
                            "properties": {
                                "full_text": {"type": "STRING"},
                                "segments": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "timestamp": {"type": "STRING"},
                                            "speaker": {"type": "STRING"},
                                            "text": {"type": "STRING"},
                                            "confidence": {"type": "NUMBER", "minimum": 0, "maximum": 1}
                                        },
                                        "required": ["timestamp", "text"]
                                    }
                                }
                            }
                        },
                        "speaker_analysis": {
                            "type": "OBJECT",
                            "properties": {
                                "speaker_count": {"type": "INTEGER"},
                                "speakers": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "speaker_id": {"type": "STRING"},
                                            "speaking_time_seconds": {"type": "NUMBER"},
                                            "attributes": {
                                                "type": "ARRAY",
                                                "items": {"type": "STRING"}
                                            }
                                        },
                                        "required": ["speaker_id", "speaking_time_seconds"]
                                    }
                                }
                            }
                        },
                        "sound_events": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "timestamp": {"type": "STRING"},
                                    "event_type": {"type": "STRING"},
                                    "description": {"type": "STRING"},
                                    "duration_seconds": {"type": "NUMBER"}
                                },
                                "required": ["timestamp", "event_type", "description"]
                            }
                        },
                        "audio_quality": {
                            "type": "OBJECT",
                            "properties": {
                                "clarity": {
                                    "type": "STRING",
                                    "enum": ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
                                },
                                "background_noise_level": {
                                    "type": "STRING",
                                    "enum": ["None", "Minimal", "Moderate", "Significant", "Overwhelming"]
                                },
                                "dialogue_intelligibility": {
                                    "type": "STRING",
                                    "enum": ["Excellent", "Good", "Fair", "Poor", "Very Poor", "No Dialogue"]
                                }
                            },
                            "required": ["clarity", "background_noise_level", "dialogue_intelligibility"]
                        }
                    }
                },
                "content_analysis": {
                    "type": "OBJECT",
                    "properties": {
                        "entities": {
                            "type": "OBJECT",
                            "properties": {
                                "people_count": {"type": "INTEGER"},
                                "people_details": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "description": {"type": "STRING"},
                                            "role": {"type": "STRING"},
                                            "appearances": {
                                                "type": "ARRAY",
                                                "items": {
                                                    "type": "OBJECT",
                                                    "properties": {
                                                        "timestamp": {"type": "STRING"},
                                                        "duration_seconds": {"type": "NUMBER"}
                                                    },
                                                    "required": ["timestamp"]
                                                }
                                            }
                                        },
                                        "required": ["description"]
                                    }
                                },
                                "locations": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "name": {"type": "STRING"},
                                            "type": {
                                                "type": "STRING",
                                                "enum": ["Indoor", "Outdoor", "Urban", "Rural", "Studio", "Other"]
                                            },
                                            "description": {"type": "STRING"}
                                        },
                                        "required": ["name", "type"]
                                    }
                                },
                                "objects_of_interest": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "object": {"type": "STRING"},
                                            "significance": {
                                                "type": "STRING",
                                                "enum": ["Primary Subject", "Secondary Element", "Background Element", "Prop"]
                                            },
                                            "timestamps": {
                                                "type": "ARRAY",
                                                "items": {"type": "STRING"}
                                            }
                                        },
                                        "required": ["object", "significance"]
                                    }
                                }
                            }
                        },
                        "activity_summary": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "timestamp": {"type": "STRING"},
                                    "activity": {"type": "STRING"},
                                    "duration": {"type": "STRING"},
                                    "importance": {
                                        "type": "STRING",
                                        "enum": ["High", "Medium", "Low"]
                                    }
                                },
                                "required": ["timestamp", "activity", "importance"]
                            }
                        },
                        "content_warnings": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {
                                        "type": "STRING",
                                        "enum": ["Violence", "Strong Language", "Nudity", "Sexual Content", "Drug Use", "Alcohol Use", "Disturbing Imagery", "Political Content", "Other"]
                                    },
                                    "description": {"type": "STRING"},
                                    "timestamp": {"type": "STRING"}
                                },
                                "required": ["type", "description", "timestamp"]
                            }
                        }
                    }
                }
            },
            "required": ["summary", "visual_analysis", "audio_analysis", "content_analysis"]
        }
        
    def _create_analysis_prompt(self) -> str:
        """
        Create comprehensive analysis prompt for Gemini Flash 2.5.
        
        Returns:
            str: Prompt for the Gemini model
        """
        return """
You are a professional filmmaker and producer. Your job is to analyze this video so that you can accurately describe it to others and so it can be categorized and found later. Please analyze this video comprehensively and provide detailed information in all of the following areas:
        
1. For the 'summary' object in the schema, provide the following details:
   - **For the 'overall' field:** Construct a detailed and accurate narrative description, **approximately 100-256 tokens long,** of what is seen and heard throughout the video. This description must:
     - Detail specific visual elements, subjects, key actions in sequence, settings, and dominant colors.
     - Describe precisely what happens with factual accuracy.
     - **Crucially, from the video's discernible speech or transcript, integrate 1-2 impactful and concise key phrases, short sentences, or direct quotes that capture critical information or the essence of a key moment. These should be naturally woven into this overall description.**
   - **For the 'key_activities' field (array of strings):** List the main activities or actions occurring in the video. Each item in the array should be a string describing a distinct activity with specific visual details.
   - **For the 'content_category' field (string):** Identify and state the primary category of the content (e.g., Interview, Tutorial, Event, Nature, Product Demo, etc.).
   - **For the 'condensed_summary' field (string):** Generate an ultra-concise version, **strictly limited to a maximum of 64 tokens,** of the overall video description. This summary must include only the most essential and directly observable visual elements, subjects, and the immediate setting. This is critical for SigLIP embeddings and must be purely descriptive of visuals.

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
     - **The 'description' field for this shot segment should then provide a brief (1-2 sentences) natural language summary that contextualizes these attributes for the specific shot.**
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
      b) 'description' (string): **A concise, literal description of exactly what is visible in this specific frame, 10-20 tokens long, using the format: Subject Action/Type Key-Details Context. Focus only on the visual content of this single frame.**
      c) 'reason' (string): A brief explanation of why this frame represents the video well and is suitable as a thumbnail.
      d) 'rank' (string): The rank ("1", "2", or "3"), with "1" being the most representative frame.
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
     - **For 'people_details' (array of objects):** For each distinct person identified, provide an object with 'description' (string, e.g., "person with red hat"), 'role' (string, e.g., "interviewer," "main subject"), and 'appearances' (array of objects with 'timestamp' and 'duration_seconds' for each appearance). **Use the format "5s600ms" for all timestamps.**
     - **For 'locations' (array of objects):** Identify distinct locations. Each object should include 'name' (string, e.g., "Central Park," "Office Meeting Room"), 'type' (from enum), and 'description' (string).
     - **For 'objects_of_interest' (array of objects):** Identify key objects. Each object should include 'object' (string, e.g., "laptop," "red book"), 'significance' (from enum), and 'timestamps' (array of strings indicating when the object is visible). **Use the format "5s600ms" for all timestamps.**
   - **For the 'activity_summary' field (array of objects):** Summarize key activities segment by segment. Each object should include 'timestamp', 'activity' (string description), 'duration' (string, e.g., "5 seconds"), and 'importance' (from enum). **Use the format "5s600ms" for all timestamps.**
   - **For the 'content_warnings' field (array of objects):** If any sensitive content is present, provide an array where each object details a warning, including 'type' (from enum like "Violence", "Strong Language"), 'description' (string, specific details), and 'timestamp'. If no warnings, this can be an empty array or omitted if allowed by schema. **Use the format "5s600ms" for all timestamps.**
        
MOST IMPORTANT: Your descriptions must be accurate and precise. Focus on exactly what is seen and heard, with specific details about visual elements and audio content. This is critical for accurate indexing and searchability of the video content.
        
Please be thorough but concise in your descriptions. Organize the analysis according to the provided schema. Focus on information that would be valuable for video editors to quickly understand and organize footage.
        """
        
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """
        Perform comprehensive video analysis using Gemini Flash 2.5.
        
        Args:
            video_path: Path to video file to analyze
            
        Returns:
            Dict[str, Any]: Structured analysis results
        """
        try:
            self.logger.info(f"Starting comprehensive AI analysis of: {video_path}")
            
            # Load video bytes
            with open(video_path, 'rb') as f:
                video_bytes = f.read()
            
            # Create video part for Gemini API
            video_blob = types.Blob(
                data=video_bytes,
                mime_type="video/mp4"
            )
            video_part = types.Part(
                inline_data=video_blob,
                video_metadata=types.VideoMetadata(
                    fps=self.fps  # Use actual FPS setting from compression config
                )
            )
            
            # Get comprehensive analysis schema
            schema = self._get_comprehensive_analysis_schema()
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt()
            
            self.logger.info("Sending video to Gemini Flash 2.5 for analysis...")
            
            # Request comprehensive analysis
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt, video_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    mediaResolution=types.MediaResolution.MEDIA_RESOLUTION_LOW
                )
            )
            
            self.logger.info("AI analysis completed successfully")
            return json.loads(response.text)
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {str(e)}")
            raise 