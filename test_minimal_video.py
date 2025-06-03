#!/usr/bin/env python3
"""
Absolutely minimal video test.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Minimal setup
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

# Use a simple, widely supported model
model = "models/gemini-1.5-flash"

# Load video
video_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0033_4731487b-717d-44a7-9100-ef36a8fab0de/compressed/PANA0033_compressed.mp4"
with open(video_path, 'rb') as f:
    video_data = f.read()

print(f"Testing with minimal args: {model}")
print(f"Video size: {len(video_data)} bytes")

try:
    # Absolutely minimal call
    response = client.models.generate_content(
        model=model,
        contents=[
            "Describe this video",
            types.Part.from_bytes(data=video_data, mime_type='video/mp4')
        ]
    )
    print("✅ SUCCESS!")
    print(response.text)
except Exception as e:
    print(f"❌ FAILED: {e}") 