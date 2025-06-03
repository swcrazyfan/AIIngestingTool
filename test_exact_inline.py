#!/usr/bin/env python3
"""
Test the exact inline method pattern specified by user.
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

def test_exact_inline_method():
    """Test using the exact inline method pattern provided by user."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Initialize client
    client = genai.Client(api_key=api_key)
    print("✓ Client initialized successfully")
    
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
        # Use the EXACT inline method pattern provided by user
        print("Loading video file...")
        video_bytes = open(video_path, 'rb').read()
        print(f"✓ Video loaded: {len(video_bytes)} bytes")
        
        print("Testing EXACT inline method pattern...")
        response = client.models.generate_content(
            model='models/gemini-2.0-flash',
            contents=types.Content(
                parts=[
                    types.Part(
                        inline_data=types.Blob(data=video_bytes, mime_type='video/mp4')
                    ),
                    types.Part(text='Please summarize the video in 3 sentences.')
                ]
            )
        )
        
        print("✅ EXACT inline method successful!")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ EXACT inline method failed: {e}")
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
    print("Testing the EXACT inline method pattern...")
    success = test_exact_inline_method()
    if success:
        print("🎉 The exact inline method works!")
    else:
        print("💔 The exact inline method is also failing!") 