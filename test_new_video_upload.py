#!/usr/bin/env python3
"""
Test video analysis with file upload using a different video file.
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

def test_new_video_upload():
    """Test video analysis using file upload with the user's video file."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Use the user's video file
    video_path = "/Users/developer/Downloads/IMG_7564.MOV"
    
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
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
        
        # Check file status
        print("Checking file processing status...")
        file_status = client.files.get(name=myfile.name)
        print(f"✓ File status: {file_status.state}")
        
        if file_status.state == "PROCESSING":
            print("Waiting for file processing to complete...")
            while file_status.state == "PROCESSING":
                time.sleep(5)
                file_status = client.files.get(name=myfile.name)
                print(f"  File status: {file_status.state}")
        
        if file_status.state == "FAILED":
            print(f"❌ File processing failed: {file_status}")
            return False
            
        print(f"✓ File processing completed with status: {file_status.state}")
        
        # Test with different models
        models_to_test = [
            "models/gemini-1.5-flash",
            "models/gemini-2.0-flash"
        ]
        
        for model_name in models_to_test:
            print(f"\n--- Testing with {model_name} ---")
            try:
                # Send a very simple video prompt with uploaded file
                print("Sending simple video prompt with uploaded file...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[myfile, "What do you see in this video? Please describe it in 2-3 sentences."]
                )
                
                print(f"✅ Video analysis with {model_name} successful!")
                print(f"Response: {response.text}")
                return True
                
            except Exception as e:
                print(f"❌ Video analysis with {model_name} failed: {e}")
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
                continue
        
        return False
        
    except Exception as e:
        print(f"❌ File upload failed: {e}")
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
    print("Testing video analysis with file upload using user's video...")
    success = test_new_video_upload()
    if success:
        print("🎉 Video analysis with new file upload is working!")
    else:
        print("💔 Video upload with new file also failing!") 