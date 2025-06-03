#!/usr/bin/env python3

import os
import sys
import time
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Test with the single compressed file using upload method
video_path = '/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4'

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

print(f'Testing video analysis with upload method...')
print(f'API Key available: {bool(os.getenv("GEMINI_API_KEY"))}')
print(f'Video file size: {os.path.getsize(video_path)/1024/1024:.1f}MB')

try:
    # Upload the file first
    print("Uploading video file...")
    uploaded_file = client.files.upload(file=video_path)
    print(f"Video uploaded successfully. File URI: {uploaded_file.uri}")
    
    # Wait for file to become ACTIVE
    print("Waiting for file to become ACTIVE...")
    max_wait_time = 60
    wait_interval = 2
    elapsed_time = 0
    
    while elapsed_time < max_wait_time:
        file_info = client.files.get(name=uploaded_file.name)
        print(f"File status: {file_info.state}, elapsed time: {elapsed_time}s")
        
        if file_info.state == "ACTIVE":
            print("File is now ACTIVE and ready for analysis")
            break
        elif file_info.state == "FAILED":
            raise Exception(f"File upload failed. File state: {file_info.state}")
        
        time.sleep(wait_interval)
        elapsed_time += wait_interval
    else:
        raise Exception(f"File did not become ACTIVE within {max_wait_time} seconds")
    
    # Now try analysis
    print("Sending analysis request...")
    response = client.models.generate_content(
        model='models/gemini-2.0-flash',
        contents=[uploaded_file, "Briefly describe what you see in this video."]
    )
    
    print('SUCCESS:', response.text[:200] + '...')
    
    # Cleanup
    try:
        client.files.delete(name=uploaded_file.name)
        print("Uploaded file cleaned up")
    except Exception as cleanup_error:
        print(f"Failed to cleanup: {cleanup_error}")
        
except Exception as e:
    print('ERROR:', str(e)) 