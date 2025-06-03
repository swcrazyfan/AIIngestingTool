#!/usr/bin/env python3

import os
import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()

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
                }
            },
            "required": ["summary"]
        }

    def _create_comprehensive_analysis_prompt(self) -> str:
        """
        Create comprehensive analysis prompt for Gemini Flash 2.5.
        
        Returns:
            str: Prompt for the Gemini model
        """
        return """You are a professional filmmaker and producer. Analyze this video comprehensively and provide detailed information about what you see and hear. Focus on visual content, audio, activities, and overall summary."""

    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """Test with the exact old working version structure"""
        try:
            print(f"Testing OLD VERSION - Starting analysis of: {video_path}")
            
            # Check file size 
            file_size = os.path.getsize(video_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"Video file size: {file_size_mb:.1f}MB")

            # Read video bytes
            video_bytes = open(video_path, 'rb').read()
            
            # Use the old working API call structure
            schema = self._get_comprehensive_analysis_schema()
            prompt = self._create_comprehensive_analysis_prompt()
            
            response = self.client.models.generate_content(
                model="models/gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(
                        data=video_bytes,
                        mime_type="video/mp4"
                    ),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    generation_config=types.GenerationConfig(
                        response_schema=schema,
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
            )
            
            print("SUCCESS with old version!")
            return json.loads(response.text)
            
        except Exception as e:
            print(f"ERROR with old version: {e}")
            return {"error": str(e)}

# Test with the old version
if __name__ == "__main__":
    video_path = '/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4'
    
    api_key = os.getenv('GEMINI_API_KEY')
    print(f'API Key available: {bool(api_key)}')
    
    analyzer = VideoAnalyzer(api_key=api_key)
    result = analyzer.analyze_video(video_path) 