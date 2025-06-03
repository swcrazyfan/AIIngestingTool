#!/usr/bin/env python3
"""
Test simple video analysis with inline data.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from google import genai
    from google.genai import types
    print("✓ Google GenAI library available")
except ImportError:
    print("✗ Google GenAI library not available")
    exit(1)

def test_video_simple():
    """Test a very simple video prompt with inline data."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Get model from environment
    model_name = os.getenv('VIDEO_MODEL', 'models/gemini-2.5-flash-preview-05-20')
    print(f"✓ Using model: {model_name}")
    
    # Find the compressed video file from our previous run
    video_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4"
    
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
        print("Run the ingest first to create the compressed video")
        return False
    
    # Check file size
    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)
    print(f"✓ Video file found: {file_size_mb:.1f}MB")
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        print("✓ Client initialized successfully")
        
        # Read video file
        print("Loading video into memory...")
        with open(video_path, 'rb') as video_file:
            video_bytes = video_file.read()
        print(f"✓ Video loaded: {len(video_bytes)} bytes")
        
        # Send a very simple video prompt
        print("Sending simple video prompt...")
        response = client.models.generate_content(
            model=model_name,
            contents=[
                "What do you see in this video?",
                types.Part.from_bytes(data=video_bytes, mime_type='video/mp4')
            ]
        )
        
        print("✅ Simple video prompt successful!")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Simple video prompt failed: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response}")
            if hasattr(e.response, 'text'):
                print(f"  Response text: {e.response.text}")
            if hasattr(e.response, 'status_code'):
                print(f"  Status code: {e.response.status_code}")
        if hasattr(e, 'code'):
            print(f"  Error code: {e.code}")
        if hasattr(e, 'message'):
            print(f"  Error message: {e.message}")
        return False

if __name__ == "__main__":
    print("Testing simple video prompt with inline data...")
    success = test_video_simple()
    if success:
        print("🎉 Basic video analysis is working!")
    else:
        print("💔 Even simple video prompts are failing!") 