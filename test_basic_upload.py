#!/usr/bin/env python3

import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Get API key from environment
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

# Only for videos of size <20Mb
video_file_name = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"
video_bytes = open(video_file_name, 'rb').read()

print(f"Video loaded: {len(video_bytes)} bytes")

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

print(response.text) 