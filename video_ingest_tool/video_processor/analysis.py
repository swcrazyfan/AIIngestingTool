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
                                    "shot_type": {
                                        "type": "STRING",
                                        "enum": [
                                            "Drone Shot", "Scenic Wide / Exterior", "Interview Setup",
                                            "Talking Head", "Close-Up", "Extreme Close-Up / Detail Shot",
                                            "Wide Shot (General Context)", "POV (Point of View) Shot",
                                            "Tracking / Follow Shot", "Static / Locked-Down Shot",
                                            "Handheld Shot", "Slow Motion Visuals", "Time-Lapse Visuals",
                                            "Screen Recording / Screencast", "Graphic / Animation",
                                            "Dutch Angle / Canted Shot", "Rack Focus",
                                            "Over-the-Shoulder Shot (OTS)", "Low Angle Shot",
                                            "High Angle Shot", "Other"
                                        ]
                                    },
                                    "description": {"type": "STRING"},
                                    "confidence": {"type": "NUMBER", "minimum": 0, "maximum": 1}
                                },
                                "required": ["timestamp", "shot_type", "description"]
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
        Please analyze this video comprehensively and provide detailed information in all of the following areas:
        
        1. Overall summary and content categorization
           - Provide a HIGHLY ACCURATE and detailed description of exactly what's in the video
           - Focus on precision: describe specific subjects, actions, settings, colors, movements
           - Be factual about what is visible and audible, with exact details about what appears in frame
           - Also include a condensed version (64 tokens max) that captures essential visual elements
        
        2. Visual analysis including shot types, technical quality, text elements
           - Select exactly 3 representative thumbnail frames ranked by quality (1=best)
           - For each thumbnail, provide:
              a) A concise description (10-20 tokens) using format: Subject Action/Type Key-Details Context
              b) A reason why this frame best represents the video
              c) A clear ranking (1, 2, or 3) with 1 being the most representative frame
        
        3. Audio analysis including transcript, speaker identification, sound events
        4. Content analysis identifying people, locations, objects, and activities
        
        For technical quality assessment, evaluate focus quality, stability, artifacts, and overall usability.
        For audio quality, assess clarity, background noise, and dialogue intelligibility.
        
        For thumbnail selection, prioritize:
         - Frames that represent the video's main subject and content
         - Clear, well-composed, and in-focus frames
         - Frames that would work well as a video thumbnail
         - Diversity in your three choices to represent different aspects of the video
        
        MOST IMPORTANT: Your descriptions must be accurate and precise. Focus on exactly what is seen and heard,
        with specific details about visual elements and audio content. This is critical for accurate indexing
        and searchability of the video content.
        
        Please be thorough but concise in your descriptions. Organize the analysis according to the provided schema.
        Focus on information that would be valuable for video editors to quickly understand and organize footage.
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