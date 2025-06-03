#!/usr/bin/env python3

import os
import json
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Get API key from environment
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

def simple_schema():
    """Simple schema for testing structured output"""
    return {
        "type": "OBJECT",
        "properties": {
            "summary": {
                "type": "STRING",
                "description": "A brief summary of the content"
            },
            "key_points": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of 2-3 main points"
            },
            "category": {
                "type": "STRING",
                "enum": ["Tutorial", "Interview", "Demo", "Other"],
                "description": "Content category"
            }
        },
        "required": ["summary", "key_points", "category"]
    }

# Test 1: Text-only structured output
def test_text_structured_output():
    """Test structured output with text only"""
    print("=== Testing Text-Only Structured Output ===")
    
    try:
        schema = simple_schema()
        
        response = client.models.generate_content(
            model="models/gemini-2.5-flash-preview-05-20",
            contents=["Analyze this text: 'This is a video about cooking pasta. First, you boil water. Then add salt. Finally, cook the pasta for 8-10 minutes.'"],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
        )
        
        print("SUCCESS - Text structured output!")
        result = json.loads(response.text)
        print(json.dumps(result, indent=2))
        return True
        
    except Exception as e:
        print(f"FAILED - Text structured output: {e}")
        return False

# Test 2: Video structured output (using your working pattern)
def test_video_structured_output():
    """Test structured output with video using the old working pattern"""
    print("\n=== Testing Video Structured Output (Old Pattern) ===")
    
    try:
        # Use your actual video file
        video_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"
        
        # Load video bytes (same as your working code)
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
        
        print(f"Video loaded: {len(video_bytes)} bytes")
        
        # Create video part (same as your working code)
        video_blob = types.Blob(
            data=video_bytes,
            mime_type="video/mp4"
        )
        video_part = types.Part(
            inline_data=video_blob,
            video_metadata=types.VideoMetadata(
                fps=1  # Same as your working code
            )
        )
        
        schema = simple_schema()
        prompt = "Analyze this video and provide a structured response with summary, key points, and category."
        
        # Use exact same pattern as your working code
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[prompt, video_part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                mediaResolution=types.MediaResolution.MEDIA_RESOLUTION_LOW
            )
        )
        
        print("SUCCESS - Video structured output!")
        result = json.loads(response.text)
        print(json.dumps(result, indent=2))
        return True
        
    except Exception as e:
        print(f"FAILED - Video structured output: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

# Test 3: Video without structured output (basic response)
def test_video_basic_output():
    """Test video analysis without structured output"""
    print("\n=== Testing Video Basic Output (No JSON Schema) ===")
    
    try:
        video_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"
        
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
        
        video_blob = types.Blob(
            data=video_bytes,
            mime_type="video/mp4"
        )
        video_part = types.Part(
            inline_data=video_blob,
            video_metadata=types.VideoMetadata(fps=1)
        )
        
        # No structured output config - just basic text response
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=["Summarize this video in 2-3 sentences.", video_part]
        )
        
        print("SUCCESS - Video basic output!")
        print(response.text)
        return True
        
    except Exception as e:
        print(f"FAILED - Video basic output: {e}")
        print(f"Error type: {type(e)}")
        return False

if __name__ == "__main__":
    print("Testing structured output functionality...")
    
    # Run all tests
    text_result = test_text_structured_output()
    video_structured_result = test_video_structured_output()
    video_basic_result = test_video_basic_output()
    
    print("\n=== SUMMARY ===")
    print(f"Text structured output: {'✅ PASS' if text_result else '❌ FAIL'}")
    print(f"Video structured output: {'✅ PASS' if video_structured_result else '❌ FAIL'}")
    print(f"Video basic output: {'✅ PASS' if video_basic_result else '❌ FAIL'}")
    
    if text_result and not video_structured_result:
        print("\n📊 DIAGNOSIS: Structured output works with text but fails with video")
    elif not text_result and not video_structured_result:
        print("\n📊 DIAGNOSIS: Structured output is broken for both text and video")
    elif video_basic_result and not video_structured_result:
        print("\n📊 DIAGNOSIS: Video processing works but structured output with video fails")
    elif not video_basic_result:
        print("\n📊 DIAGNOSIS: Video processing is completely broken") 