#!/usr/bin/env python3

import os
import sys
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Test with the single compressed file
video_path = '/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4'

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
video_bytes = open(video_path, 'rb').read()

print(f'Testing video analysis with {len(video_bytes)/1024/1024:.1f}MB file...')
print(f'API Key available: {bool(os.getenv("GEMINI_API_KEY"))}')

# Test different models
models_to_test = [
    'models/gemini-1.5-flash',
    'models/gemini-1.5-pro', 
    'models/gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
    'gemini-2.0-flash'
]

for model in models_to_test:
    print(f'\n--- Testing with model: {model} ---')
    try:
        response = client.models.generate_content(
            model=model,
            contents=types.Content(
                parts=[
                    types.Part(
                        inline_data=types.Blob(data=video_bytes, mime_type='video/mp4')
                    ),
                    types.Part(text='Briefly describe what you see in this video.')
                ]
            )
        )
        print(f'SUCCESS with {model}:', response.text[:100] + '...')
        break  # Stop on first success
    except Exception as e:
        print(f'ERROR with {model}:', str(e)) 