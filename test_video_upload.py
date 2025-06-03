#!/usr/bin/env python3
"""
Test video analysis with file upload using gemini-2.0-flash.
"""

import os
import time
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

def test_video_upload():
    """Test video analysis using file upload with gemini-2.0-flash."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Use model from environment
    model_name = os.getenv('VIDEO_MODEL', 'models/gemini-1.5-flash')
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
        
        # Upload video file
        print("Uploading video file...")
        myfile = client.files.upload(file=video_path)
        print(f"✓ Video uploaded successfully. File URI: {myfile.uri}")
        
        # Simple wait instead of checking status (to avoid the JSON parsing issues)
        print("Waiting for file processing...")
        time.sleep(30)  # Wait 30 seconds for processing
        
        # Send a very simple video prompt with uploaded file
        print("Sending simple video prompt with uploaded file...")
        response = client.models.generate_content(
            model=model_name,
            contents=[myfile, "What do you see in this video?"]
        )
        
        print("✅ Video analysis with file upload successful!")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Video analysis with file upload failed: {e}")
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
    print("Testing video analysis with file upload using gemini-2.0-flash...")
    success = test_video_upload()
    if success:
        print("🎉 Video analysis with file upload is working!")
    else:
        print("💔 Video upload approach also failing!") 