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

def capture_detailed_error():
    """Capture detailed error information for the 500 error"""
    print("=== Capturing Detailed 500 Error Information ===")
    
    try:
        # Use your actual video file
        video_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"
        
        # Load video bytes
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
        
        print(f"Video loaded: {len(video_bytes)} bytes")
        
        # Create video part
        video_blob = types.Blob(
            data=video_bytes,
            mime_type="video/mp4"
        )
        video_part = types.Part(
            inline_data=video_blob,
            video_metadata=types.VideoMetadata(fps=1)
        )
        
        # Simple request - no structured output to eliminate that as a variable
        response = client.models.generate_content(
            model="models/gemini-2.5-flash-preview-05-20",
            contents=["Describe this video briefly.", video_part]
        )
        
        print("SUCCESS - This shouldn't happen based on previous tests")
        print(response.text)
        
    except Exception as e:
        print(f"\n=== ERROR DETAILS ===")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Module: {type(e).__module__}")
        print(f"Error Message: {str(e)}")
        
        # Try to get more details from the exception
        if hasattr(e, 'status_code'):
            print(f"Status Code: {e.status_code}")
        
        if hasattr(e, 'response'):
            print(f"Response Object: {e.response}")
            if hasattr(e.response, 'status_code'):
                print(f"Response Status Code: {e.response.status_code}")
            if hasattr(e.response, 'headers'):
                print(f"Response Headers: {dict(e.response.headers)}")
            if hasattr(e.response, 'text'):
                print(f"Response Text: {e.response.text}")
            if hasattr(e.response, 'content'):
                print(f"Response Content: {e.response.content}")
        
        if hasattr(e, 'details'):
            print(f"Error Details: {e.details}")
            
        if hasattr(e, 'args'):
            print(f"Error Args: {e.args}")
            
        # Try to get the raw response if available
        if hasattr(e, '_response'):
            print(f"Raw Response: {e._response}")
            
        # Print full traceback for debugging
        print(f"\n=== FULL TRACEBACK ===")
        import traceback
        traceback.print_exc()
        
        # Try to extract more from the error string if it contains JSON
        error_str = str(e)
        if '{' in error_str and '}' in error_str:
            try:
                # Extract JSON part
                start = error_str.find('{')
                end = error_str.rfind('}') + 1
                json_part = error_str[start:end]
                parsed_error = json.loads(json_part)
                print(f"\n=== PARSED ERROR JSON ===")
                print(json.dumps(parsed_error, indent=2))
            except:
                print("Could not parse JSON from error string")

if __name__ == "__main__":
    capture_detailed_error() 