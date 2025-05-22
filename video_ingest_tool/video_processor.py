"""
Video processing module for compressing and analyzing videos using Gemini Flash 2.5.
"""

import os
import sys
import json
import logging
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Import the Config class directly
from video_ingest_tool.config import Config

# Load environment variables from .env file
# Look for .env file in the project root directory
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# Default compression configuration - single source of truth
DEFAULT_COMPRESSION_CONFIG = {
    'max_dimension': 1280,  # Scale longest dimension to this size
    'fps': 5,
    'video_bitrate': '1000k',
    'audio_bitrate': '32k',
    'audio_channels': 1,
    'use_hardware_accel': True,
    'codec_priority': ['hevc_videotoolbox', 'h264_videotoolbox', 'libx265', 'libx264'],
    'crf_value': '25',
}

class VideoCompressor:
    """Handles video compression using ffmpeg with hardware acceleration when available."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            **DEFAULT_COMPRESSION_CONFIG,
            **(config or {})
        }
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _check_videotoolbox_availability(self) -> Dict[str, bool]:
        """
        Check if VideoToolbox hardware acceleration is available on macOS.
        
        Returns:
            Dict[str, bool]: Dictionary with availability of h264 and hevc encoders
        """
        result = {
            'h264_videotoolbox': False,
            'hevc_videotoolbox': False
        }
        
        if sys.platform != 'darwin':
            return result
            
        try:
            # Check if VideoToolbox encoders are available in ffmpeg
            proc = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"], 
                check=True, capture_output=True, text=True
            )
            result['h264_videotoolbox'] = 'h264_videotoolbox' in proc.stdout
            result['hevc_videotoolbox'] = 'hevc_videotoolbox' in proc.stdout
            
            if result['h264_videotoolbox']:
                self.logger.info("H.264 VideoToolbox encoder is available")
            if result['hevc_videotoolbox']:
                self.logger.info("HEVC VideoToolbox encoder is available")
                
            return result
        except Exception as e:
            self.logger.warning(f"Error checking for VideoToolbox: {str(e)}")
            return result
    
    def _select_best_codec(self) -> str:
        """
        Select the best available codec based on priorities and system capabilities.
        
        Returns:
            str: The best available codec to use
        """
        available_codecs = {
            'libx264': True,  # Assume libx264 is always available
            'libx265': False,  # Will be checked below
            'h264_videotoolbox': False,
            'hevc_videotoolbox': False
        }
        
        # Check if h265/HEVC is available
        try:
            hevc_check = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"], 
                check=True, capture_output=True, text=True
            )
            available_codecs['libx265'] = 'libx265' in hevc_check.stdout
        except Exception:
            pass
            
        # If hardware acceleration is enabled and we're on macOS, check for VideoToolbox
        if self.config['use_hardware_accel'] and sys.platform == 'darwin':
            vt_availability = self._check_videotoolbox_availability()
            available_codecs['h264_videotoolbox'] = vt_availability['h264_videotoolbox']
            available_codecs['hevc_videotoolbox'] = vt_availability['hevc_videotoolbox']
        
        # Select the best codec based on priority list
        for codec in self.config['codec_priority']:
            if codec in available_codecs and available_codecs[codec]:
                self.logger.info(f"Selected codec: {codec}")
                return codec
                
        # Default to libx264 as fallback
        self.logger.info("Falling back to libx264 codec")
        return 'libx264'

    def _get_video_resolution(self, input_path: str) -> tuple:
        """
        Get the resolution of the input video.
        
        Args:
            input_path: Path to input video file
            
        Returns:
            tuple: (width, height) or (None, None) if detection fails
        """
        try:
            # Use ffprobe to get video resolution
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", 
                "-show_streams", "-select_streams", "v:0", input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            probe_data = json.loads(result.stdout)
            
            if probe_data.get('streams'):
                video_stream = probe_data['streams'][0]
                width = video_stream.get('width')
                height = video_stream.get('height')
                
                if width and height:
                    self.logger.info(f"Detected video resolution: {width}x{height}")
                    return (int(width), int(height))
            
            self.logger.warning("Could not detect video resolution")
            return (None, None)
            
        except Exception as e:
            self.logger.warning(f"Failed to detect video resolution: {str(e)}")
            return (None, None)

    def compress(self, input_path: str, output_dir: str = None) -> str:
        """
        Compress video using ffmpeg with the best available codec.
        
        Args:
            input_path: Path to input video file
            output_dir: Directory to save compressed file (defaults to compressed/ next to input)
            
        Returns:
            str: Path to compressed output video
            
        Raises:
            RuntimeError: If compression fails
        """
        try:
            # Create output directory - use provided directory or create compressed/ next to input
            if output_dir:
                compressed_dir = os.path.join(output_dir, "compressed")
            else:
                input_dir = os.path.dirname(input_path)
                compressed_dir = os.path.join(input_dir, "compressed")
            
            os.makedirs(compressed_dir, exist_ok=True)
            
            # Use just the filename for the output, not the full path
            input_basename = os.path.basename(input_path)
            output_basename = f"{os.path.splitext(input_basename)[0]}_compressed.mp4"
            output_path = os.path.join(compressed_dir, output_basename)
            
            self.logger.info(f"Compressing {input_path} to {output_path}")
            
            # Check if input file exists
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
                
            # Check for ffmpeg
            try:
                subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")
                
            # Detect input video resolution
            input_width, input_height = self._get_video_resolution(input_path)
            
            # Determine if we need to scale down
            needs_scaling = False
            scale_filter = None
            max_dimension = self.config['max_dimension']
            
            if input_width and input_height:
                # Find the longest dimension
                longest_dimension = max(input_width, input_height)
                
                # Check if longest dimension exceeds our target
                if longest_dimension > max_dimension:
                    needs_scaling = True
                    
                    # Calculate scaling to fit longest dimension
                    scale_factor = max_dimension / longest_dimension
                    target_width = int(input_width * scale_factor)
                    target_height = int(input_height * scale_factor)
                    
                    # Make sure dimensions are even (required for many codecs)
                    target_width = target_width if target_width % 2 == 0 else target_width - 1
                    target_height = target_height if target_height % 2 == 0 else target_height - 1
                    
                    scale_filter = f"scale={target_width}:{target_height}"
                    self.logger.info(f"Scaling down from {input_width}x{input_height} to {target_width}x{target_height} (longest dimension: {longest_dimension} → {max_dimension})")
                else:
                    self.logger.info(f"Resolution {input_width}x{input_height} fits within {max_dimension}px, compressing without scaling")
            else:
                # If we can't detect resolution, use default scaling as fallback
                needs_scaling = True
                scale_filter = f"scale={max_dimension}:{max_dimension}"
                self.logger.warning(f"Could not detect resolution, using default scaling to {max_dimension}px")
            
            # Select the best available codec
            video_codec = self._select_best_codec()
            
            # Base ffmpeg command
            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", video_codec
            ]
            
            # Add codec-specific parameters
            if video_codec == 'libx264' or video_codec == 'libx265':
                # For software encoding, use CRF (Constant Rate Factor) for quality-based encoding
                cmd.extend(["-crf", str(self.config['crf_value'])])  # Use configurable CRF
            elif 'videotoolbox' in video_codec:
                # For hardware encoding, use bitrate-based encoding
                cmd.extend(["-b:v", self.config['video_bitrate']])
                
                # Add specific VideoToolbox parameters for better quality
                cmd.extend(["-allow_sw", "1"])  # Allow software encoding as fallback
                
                # Add ProRes options for better quality with VideoToolbox
                if video_codec == 'hevc_videotoolbox':
                    cmd.extend(["-profile:v", "main"])
            
            # Add scaling filter if needed
            if needs_scaling:
                cmd.extend(["-vf", scale_filter])
            
            # Add other common parameters
            cmd.extend([
                "-r", str(self.config['fps']),     # Frame rate
                "-c:a", "aac", "-b:a", self.config['audio_bitrate'],  # Audio codec and bitrate
                "-ac", str(self.config['audio_channels']),  # Audio channels
                "-y",                              # Overwrite output
                output_path
            ])
            
            self.logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
            
            # Execute ffmpeg command
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Check if output file was created and has a reasonable size
            if os.path.exists(output_path):
                input_size = os.path.getsize(input_path)
                output_size = os.path.getsize(output_path)
                compression_ratio = input_size / output_size if output_size > 0 else 0
                
                self.logger.info(f"Compression successful!")
                self.logger.info(f"Input size: {input_size/1024/1024:.2f} MB")
                self.logger.info(f"Output size: {output_size/1024/1024:.2f} MB")
                self.logger.info(f"Compression ratio: {compression_ratio:.2f}x")
            else:
                self.logger.warning(f"Output file not found: {output_path}")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg error: {e.stderr}")
            raise RuntimeError(f"Compression failed: ffmpeg error: {e.stderr}")
        except Exception as e:
            self.logger.error(f"Compression failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Compression failed: {str(e)}")

class VideoAnalyzer:
    """Handles comprehensive video analysis using Gemini Flash 2.5."""
    
    def __init__(self, api_key: str, fps: int = 1):
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
                        "overall": {"type": "STRING"},
                        "key_activities": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of main activities or actions occurring in the video"
                        },
                        "content_category": {
                            "type": "STRING",
                            "description": "Primary category of content (e.g., Interview, Tutorial, Event, Nature, etc.)"
                        }
                    },
                    "required": ["overall", "key_activities", "content_category"]
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
                                            "segments_count": {"type": "INTEGER"}
                                        },
                                        "required": ["speaker_id", "speaking_time_seconds"]
                                    }
                                }
                            },
                            "required": ["speaker_count"]
                        },
                        "sound_events": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "timestamp": {"type": "STRING"},
                                    "event_type": {
                                        "type": "STRING",
                                        "enum": [
                                            "Applause", "Laughter", "Music", "Door Slam", "Phone Ringing",
                                            "Footsteps", "Crowd Noise", "Vehicle Sounds", "Nature Sounds",
                                            "Mechanical Sounds", "Electronic Beeps", "Wind", "Rain",
                                            "Background Music", "Other"
                                        ]
                                    },
                                    "description": {"type": "STRING"},
                                    "duration_seconds": {"type": "NUMBER"},
                                    "prominence": {
                                        "type": "STRING",
                                        "enum": ["Background", "Moderate", "Prominent", "Dominant"]
                                    }
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
                                    "enum": ["Minimal", "Low", "Moderate", "High", "Excessive"]
                                },
                                "dialogue_intelligibility": {
                                    "type": "STRING",
                                    "enum": ["Very Clear", "Clear", "Mostly Clear", "Difficult", "Unintelligible"]
                                }
                            }
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
                                            "role": {"type": "STRING", "description": "Role in the video (e.g., 'Speaker', 'Interviewer', 'Subject', 'Background')"},
                                            "visibility_duration": {"type": "STRING", "description": "How long they appear (e.g., 'Throughout', 'Brief', 'Intermittent')"}
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
                                                "enum": ["Indoor", "Outdoor", "Studio", "Office", "Home", "Public Space", "Natural Setting", "Other"]
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
                                            "significance": {"type": "STRING", "description": "Why this object is notable"},
                                            "timestamp": {"type": "STRING"}
                                        },
                                        "required": ["object", "significance"]
                                    }
                                }
                            },
                            "required": ["people_count"]
                        },
                        "activity_summary": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "activity": {"type": "STRING"},
                                    "timestamp": {"type": "STRING"},
                                    "duration": {"type": "STRING"},
                                    "importance": {
                                        "type": "STRING",
                                        "enum": ["High", "Medium", "Low"]
                                    }
                                },
                                "required": ["activity", "timestamp", "importance"]
                            }
                        },
                        "content_warnings": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {
                                        "type": "STRING",
                                        "enum": ["Violence", "Strong Language", "Adult Content", "Flashing Lights", "Loud Sounds", "Other"]
                                    },
                                    "description": {"type": "STRING"},
                                    "timestamp": {"type": "STRING"}
                                },
                                "required": ["type", "description"]
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
            str: Detailed prompt for video analysis
        """
        return """
        Analyze this video comprehensively for video editing purposes. Provide detailed analysis in the following areas:

        1. SUMMARY & OVERVIEW:
        - Overall content summary
        - Key activities and actions occurring
        - Primary content category

        2. VISUAL ANALYSIS:
        - Shot type classification for each significant segment using these categories:
          * Drone Shot, Scenic Wide/Exterior, Interview Setup, Talking Head
          * Close-Up, Extreme Close-Up/Detail Shot, Wide Shot, POV Shot
          * Tracking/Follow Shot, Static/Locked-Down Shot, Handheld Shot
          * Slow Motion, Time-Lapse, Screen Recording, Graphic/Animation
          * Dutch Angle, Rack Focus, Over-the-Shoulder, Low/High Angle
        - Technical quality assessment (focus, stability, artifacts)
        - Text and logo/icon detection with readability assessment
        - Recommended keyframes for thumbnails based on visual quality and content

        3. AUDIO ANALYSIS:
        - Full speech transcription with speaker identification
        - Speaker diarization (distinguish different speakers)
        - Non-speech sound event detection (applause, music, ambient sounds, etc.)
        - Audio quality assessment

        4. CONTENT ANALYSIS:
        - People count and role identification
        - Location and setting identification
        - Significant objects or elements
        - Activity timeline with importance ratings
        - Content warnings if applicable

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
            return response.text
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {str(e)}")
            raise


class VideoProcessor(object): # Changed inheritance
    """Pipeline processor for video analysis."""

    def __init__(self, config: Config, compression_config: Dict[str, Any] = None):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store compression configuration for VideoCompressor
        self.compression_config = compression_config or {}
        
        # Get API key from environment variables (now loaded from .env file)
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not found. Check your .env file in the project root.")
            
        self.logger.info("VideoProcessor initialized successfully")
        
    def _display_analysis_summary(self, analysis_json: Dict[str, Any]) -> None:
        """
        Display a comprehensive summary of the analysis results.
        
        Args:
            analysis_json: The complete analysis results dictionary
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("COMPREHENSIVE AI ANALYSIS SUMMARY")
        self.logger.info("="*80)
        
        # Summary section
        summary = analysis_json.get('summary', {})
        self.logger.info(f"\n📝 OVERALL SUMMARY:")
        self.logger.info(f"   Content: {summary.get('overall', 'No summary available')}")
        self.logger.info(f"   Category: {summary.get('content_category', 'Unknown')}")
        
        key_activities = summary.get('key_activities', [])
        if key_activities:
            self.logger.info(f"   Key Activities: {', '.join(key_activities)}")
        
        # Visual Analysis section
        visual = analysis_json.get('visual_analysis', {})
        self.logger.info(f"\n🎬 VISUAL ANALYSIS:")
        
        shot_types = visual.get('shot_types', [])
        if shot_types:
            self.logger.info(f"   Shot Types Detected: {len(shot_types)} different shots")
            for shot in shot_types[:3]:  # Show first 3 shots
                self.logger.info(f"     • {shot['timestamp']}: {shot['shot_type']} - {shot['description']}")
            if len(shot_types) > 3:
                self.logger.info(f"     ... and {len(shot_types) - 3} more shots")
        
        # Technical quality
        tech_quality = visual.get('technical_quality', {})
        if tech_quality:
            self.logger.info(f"   Technical Quality:")
            self.logger.info(f"     • Focus: {tech_quality.get('overall_focus_quality', 'Unknown')}")
            self.logger.info(f"     • Stability: {tech_quality.get('stability_assessment', 'Unknown')}")
            self.logger.info(f"     • Usability: {tech_quality.get('usability_rating', 'Unknown')}")
            
            artifacts = tech_quality.get('detected_artifacts', [])
            if artifacts:
                self.logger.info(f"     • Artifacts Detected: {len(artifacts)} issues found")
                for artifact in artifacts:
                    self.logger.info(f"       - {artifact['type']}: {artifact['severity']} - {artifact['description']}")
        
        # Text and graphics
        text_graphics = visual.get('text_and_graphics', {})
        detected_text = text_graphics.get('detected_text', [])
        detected_logos = text_graphics.get('detected_logos_icons', [])
        
        if detected_text or detected_logos:
            self.logger.info(f"   Text & Graphics:")
            if detected_text:
                self.logger.info(f"     • Text Elements: {len(detected_text)} detected")
                for text in detected_text[:2]:  # Show first 2
                    self.logger.info(f"       - {text['timestamp']}: {text['text_type']} ({text['readability']})")
                    if text.get('text_content'):
                        self.logger.info(f"         Content: \"{text['text_content']}\"")
            
            if detected_logos:
                self.logger.info(f"     • Logos/Icons: {len(detected_logos)} detected")
                for logo in detected_logos[:2]:  # Show first 2
                    self.logger.info(f"       - {logo['timestamp']}: {logo['element_type']} - {logo['description']}")
        
        # Audio Analysis section
        audio = analysis_json.get('audio_analysis', {})
        self.logger.info(f"\n🔊 AUDIO ANALYSIS:")
        
        # Transcript
        transcript = audio.get('transcript', {})
        if transcript and transcript.get('full_text'):
            full_text = transcript['full_text']
            preview_text = full_text[:100] + "..." if len(full_text) > 100 else full_text
            self.logger.info(f"   Transcript Preview: \"{preview_text}\"")
        
        # Speakers
        speaker_analysis = audio.get('speaker_analysis', {})
        speaker_count = speaker_analysis.get('speaker_count', 0)
        if speaker_count > 0:
            self.logger.info(f"   Speakers: {speaker_count} detected")
            speakers = speaker_analysis.get('speakers', [])
            for speaker in speakers:
                self.logger.info(f"     • {speaker['speaker_id']}: {speaker['speaking_time_seconds']:.1f}s speaking time")
        
        # Sound events
        sound_events = audio.get('sound_events', [])
        if sound_events:
            self.logger.info(f"   Sound Events: {len(sound_events)} detected")
            for event in sound_events[:3]:  # Show first 3
                self.logger.info(f"     • {event['timestamp']}: {event['event_type']} - {event['description']}")
        
        # Audio quality
        audio_quality = audio.get('audio_quality', {})
        if audio_quality:
            self.logger.info(f"   Audio Quality:")
            self.logger.info(f"     • Clarity: {audio_quality.get('clarity', 'Unknown')}")
            self.logger.info(f"     • Background Noise: {audio_quality.get('background_noise_level', 'Unknown')}")
            self.logger.info(f"     • Dialogue Intelligibility: {audio_quality.get('dialogue_intelligibility', 'Unknown')}")
        
        # Content Analysis section
        content = analysis_json.get('content_analysis', {})
        self.logger.info(f"\n👥 CONTENT ANALYSIS:")
        
        # Entities
        entities = content.get('entities', {})
        people_count = entities.get('people_count', 0)
        if people_count > 0:
            self.logger.info(f"   People: {people_count} detected")
            people_details = entities.get('people_details', [])
            for person in people_details[:3]:  # Show first 3
                self.logger.info(f"     • {person['description']} ({person.get('role', 'Unknown role')})")
        
        locations = entities.get('locations', [])
        if locations:
            self.logger.info(f"   Locations:")
            for location in locations:
                self.logger.info(f"     • {location['name']} ({location['type']}): {location.get('description', '')}")
        
        objects = entities.get('objects_of_interest', [])
        if objects:
            self.logger.info(f"   Objects of Interest: {len(objects)} detected")
            for obj in objects[:3]:  # Show first 3
                self.logger.info(f"     • {obj['object']}: {obj['significance']}")
        
        # Activity summary
        activities = content.get('activity_summary', [])
        if activities:
            self.logger.info(f"   Key Activities:")
            for activity in activities[:5]:  # Show first 5
                importance_emoji = "🔴" if activity['importance'] == "High" else "🟡" if activity['importance'] == "Medium" else "🟢"
                self.logger.info(f"     {importance_emoji} {activity['timestamp']}: {activity['activity']} ({activity.get('duration', 'Unknown duration')})")
        
        # Content warnings
        warnings = content.get('content_warnings', [])
        if warnings:
            self.logger.info(f"\n⚠️  CONTENT WARNINGS:")
            for warning in warnings:
                self.logger.info(f"   • {warning['type']}: {warning['description']} (at {warning['timestamp']})")
        
        # Keyframe recommendations
        keyframes = visual.get('keyframe_analysis', {}).get('recommended_keyframes', [])
        if keyframes:
            self.logger.info(f"\n🖼️  RECOMMENDED KEYFRAMES:")
            for keyframe in keyframes[:3]:  # Show first 3
                self.logger.info(f"   • {keyframe['timestamp']}: {keyframe['reason']} (Quality: {keyframe['visual_quality']})")
        
        self.logger.info("\n" + "="*80)
        self.logger.info("END OF ANALYSIS SUMMARY")
        self.logger.info("="*80)

    def process(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Process a video file through compression and AI analysis.
        
        Args:
            file_path: Path to video file
            output_dir: Directory to save processed files (optional)
            
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            # Verify file exists
            if not os.path.exists(file_path):
                self.logger.error(f"File not found: {file_path}")
                return {
                    'success': False,
                    'error': f"File not found: {file_path}"
                }
                
            self.logger.info(f"Starting compression for: {file_path}")
            
            # Compress video
            compressor = VideoCompressor(self.compression_config)
            compressed_path = compressor.compress(file_path, output_dir)
            
            self.logger.info(f"Compression successful. Output: {compressed_path}")
            self.logger.info(f"Starting AI analysis...")
            
            # Analyze video
            # Get FPS from compression config, with fallback to default
            fps_for_analysis = self.compression_config.get('fps', 5)
            analyzer = VideoAnalyzer(api_key=self.api_key, fps=fps_for_analysis)
            analysis_results = analyzer.analyze_video(compressed_path)
            
            # Parse analysis results
            analysis_json = json.loads(analysis_results)
            
            self.logger.info(f"AI analysis completed successfully")
            
            # Display comprehensive analysis summary
            try:
                self._display_analysis_summary(analysis_json)
            except Exception as e:
                self.logger.error(f"Error displaying analysis summary: {str(e)}")
                
            return {
                'success': True,
                'compressed_path': compressed_path,
                'analysis_json': analysis_json
            }
        
        except Exception as e:
            self.logger.error(f"Video processing failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }