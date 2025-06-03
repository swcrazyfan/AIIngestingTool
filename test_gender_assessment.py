#!/usr/bin/env python3
"""
Test script to isolate gender identification from visual analysis only.
This helps determine if the visual AI is correctly identifying gender without audio influence.
"""

import os
import tempfile
import sys
from pathlib import Path
import base64
import openai
import requests

def encode_image(image_path: str) -> str:
    """Encode image to base64 for API usage."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_gender_identification(video_path: str):
    """Test visual gender identification using keyframes from video."""
    
    print("🧪 GENDER IDENTIFICATION TEST")
    print("=" * 60)
    print(f"📹 Video: {os.path.basename(video_path)}")
    print(f"🎯 Goal: Test visual gender identification in isolation")
    
    # Create temp directory for frames
    with tempfile.TemporaryDirectory() as temp_dir:
        keyframes_dir = os.path.join(temp_dir, "keyframes")
        os.makedirs(keyframes_dir, exist_ok=True)
        
        # Extract frames using our existing script
        print("\n🖼️  Extracting keyframes...")
        extract_cmd = f"python extract_best_10_frames.py \"{video_path}\" -n 3 -o \"{keyframes_dir}\""
        result = os.system(extract_cmd)
        
        if result != 0:
            print("❌ Failed to extract frames")
            return
            
        # Get the extracted frames
        frame_files = sorted([f for f in os.listdir(keyframes_dir) if f.endswith('.jpg')])
        
        if not frame_files:
            print("❌ No frames extracted")
            return
            
        print(f"✅ Extracted {len(frame_files)} frames")
        
        # Prepare images for analysis
        images = []
        for frame_file in frame_files:
            frame_path = os.path.join(keyframes_dir, frame_file)
            timestamp = frame_file.split('_')[2].replace('s', '').replace('.jpg', '')
            base64_image = encode_image(frame_path)
            
            images.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            print(f"📷 Frame: {frame_file} (timestamp: {timestamp}s)")
        
        # Create focused gender assessment prompt
        messages = [
            {
                "role": "system",
                "content": """You are a professional casting director reviewing audition footage. Your job is to accurately identify the apparent gender of performers for casting purposes.

CRITICAL TASK: VISUAL GENDER IDENTIFICATION

You are looking at still frames from a video recording. Based SOLELY on what you can SEE in these images, determine:

1. **PRIMARY GENDER ASSESSMENT**: 
   - What is the apparent gender of the person in these frames?
   - Base this on: facial features, hair style, clothing, body structure, overall appearance
   - Be confident in your visual assessment
   - Use clear, direct language: "This appears to be a [male/female] person"

2. **VISUAL EVIDENCE**:
   - What specific visual cues support your gender assessment?
   - Describe the person's appearance in detail
   - Note hair style, facial structure, clothing, etc.

3. **CONFIDENCE LEVEL**:
   - How confident are you in this assessment? (High/Medium/Low)
   - What makes you confident or uncertain?

4. **CASTING NOTES**:
   - How would you describe this person to a casting team?
   - What role types might they be suitable for based on appearance?

FOCUS ONLY ON VISUAL EVIDENCE. Do not make assumptions based on voice, content, or other factors - only what you can directly observe in the images.

Be direct and professional in your assessment."""
            },
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text",
                        "text": f"Please analyze these {len(frame_files)} frames and provide your professional gender identification assessment:"
                    }
                ] + images
            }
        ]
        
        # Get visual-only gender assessment
        print("\n🤖 Analyzing gender identification...")
        
        payload = {
            "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "messages": messages,
            "max_tokens": 1500,
            "temperature": 0.1
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer 2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP"  # Same API key as main script
        }
        
        try:
            response = requests.post("https://api.deepinfra.com/v1/openai/chat/completions", 
                                   headers=headers, json=payload, timeout=120)
            
            if response.status_code != 200:
                raise RuntimeError(f"API request failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if 'error' in result:
                raise RuntimeError(f"API error: {result['error']}")
            
            analysis = result["choices"][0]["message"]["content"]
            
            print("\n" + "=" * 60)
            print("🎯 VISUAL GENDER IDENTIFICATION RESULTS")
            print("=" * 60)
            print(analysis)
            print("=" * 60)
            
            # Save results
            report_path = f"{os.path.splitext(os.path.basename(video_path))[0]}_gender_test.md"
            with open(report_path, 'w') as f:
                f.write(f"# Gender Identification Test\n\n")
                f.write(f"**Video:** {video_path}\n")
                f.write(f"**Frames:** {len(frame_files)}\n")
                f.write(f"**Test Focus:** Visual gender identification only\n\n")
                f.write("## Results\n\n")
                f.write(analysis)
            
            print(f"📄 Results saved: {report_path}")
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_gender_assessment.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        sys.exit(1)
    
    test_gender_identification(video_path) 