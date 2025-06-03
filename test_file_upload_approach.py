#!/usr/bin/env python3

import os
import time
from dotenv import load_dotenv
load_dotenv()

from google import genai

# Get API key from environment
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

# Use the actual video file from your system
video_file_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"

print(f"Uploading video file: {video_file_path}")

try:
    # Upload the file
    myfile = client.files.upload(file=video_file_path)
    print(f"File uploaded. Name: {myfile.name}, State: {myfile.state}")
    
    # Wait for processing with proper error handling
    max_attempts = 12  # 1 minute max wait
    attempts = 0
    
    while myfile.state == "PROCESSING" and attempts < max_attempts:
        print(f'Waiting for video to be processed... (attempt {attempts + 1})')
        time.sleep(5)
        attempts += 1
        
        try:
            myfile = client.files.get(name=myfile.name)
            print(f"Current state: {myfile.state}")
        except Exception as status_error:
            print(f"Error checking file status: {status_error}")
            print(f"Error type: {type(status_error)}")
            break
    
    if myfile.state == "ACTIVE":
        print("File is ready for processing!")
        
        # Try to generate content
        response = client.models.generate_content(
            model=os.getenv('VIDEO_MODEL'),
            contents=[myfile, "Summarize this video in 3 sentences."]
        )
        
        print("SUCCESS!")
        print(response.text)
        
    elif myfile.state == "PROCESSING":
        print("File is still processing after 1 minute - timing out")
    else:
        print(f"File processing failed. Final state: {myfile.state}")
        
except Exception as e:
    print(f"Upload error: {e}")
    print(f"Error type: {type(e)}")
    import traceback
    traceback.print_exc() 