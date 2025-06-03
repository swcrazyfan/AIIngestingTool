#!/usr/bin/env python3

import os
import time
from dotenv import load_dotenv
load_dotenv()

import vertexai
from vertexai.generative_models import GenerativeModel, Part
import vertexai.preview.generative_models as generative_models

# Setup Vertex AI
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', 'your-project-id')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

print(f"Using Vertex AI with Project: {PROJECT_ID}, Location: {LOCATION}")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Use the actual video file from your system
video_file_path = "/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"

print(f"Testing video file: {video_file_path}")

try:
    # Load video file
    with open(video_file_path, 'rb') as video_file:
        video_data = video_file.read()
    
    print(f"Video loaded: {len(video_data)} bytes")
    
    # Create video part
    video_part = Part.from_data(
        mime_type="video/mp4",
        data=video_data
    )
    
    # Initialize model
    model_name = os.getenv('VIDEO_MODEL', 'gemini-2.0-flash')
    print(f"Using model: {model_name}")
    
    model = GenerativeModel(model_name)
    
    # Generate content
    print("Generating content...")
    response = model.generate_content(
        [video_part, "Summarize this video in 3 sentences."],
        generation_config=generative_models.GenerationConfig(
            max_output_tokens=1000,
            temperature=0.1,
        ),
    )
    
    print("SUCCESS!")
    print(response.text)
    
except Exception as e:
    print(f"Error: {e}")
    print(f"Error type: {type(e)}")
    import traceback
    traceback.print_exc() 