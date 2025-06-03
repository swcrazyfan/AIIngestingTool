#!/usr/bin/env python3

import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Test with the most basic old version structure
def test_old_basic_structure():
    video_path = '/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4'
    
    api_key = os.getenv('GEMINI_API_KEY')
    print(f'API Key available: {bool(api_key)}')
    
    client = genai.Client(api_key=api_key)
    
    # Check file size 
    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)
    print(f"Video file size: {file_size_mb:.1f}MB")

    # Read video bytes
    video_bytes = open(video_path, 'rb').read()
    
    try:
        print("Testing OLD BASIC structure...")
        
        # Use the simplest old structure: separate content items, no complex config
        response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=video_bytes,
                    mime_type="video/mp4"
                ),
                "Briefly describe what you see in this video."
            ]
        )
        
        print("SUCCESS with old basic structure!")
        print("Response:", response.text[:200] + "...")
        return True
        
    except Exception as e:
        print(f"ERROR with old basic structure: {e}")
        return False

if __name__ == "__main__":
    test_old_basic_structure() 
 