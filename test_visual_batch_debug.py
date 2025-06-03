#!/usr/bin/env python3
"""
Debug script to test what visual batches determine about gender within the full pipeline context.
This helps identify where the gender assessment is going wrong.
"""

import os
import tempfile
import sys
from pathlib import Path
import base64
import requests

def encode_image(image_path: str) -> str:
    """Encode image to base64 for API usage."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_visual_batch_gender(video_path: str):
    """Test visual batch gender identification within full pipeline context."""
    
    print("🔍 VISUAL BATCH GENDER DEBUG")
    print("=" * 60)
    print(f"📹 Video: {os.path.basename(video_path)}")
    print(f"🎯 Goal: Debug gender assessment in visual batches")
    
    # Create temp directory for frames
    with tempfile.TemporaryDirectory() as temp_dir:
        keyframes_dir = os.path.join(temp_dir, "keyframes")
        os.makedirs(keyframes_dir, exist_ok=True)
        
        # Extract frames using our existing script
        print("\n🖼️  Extracting keyframes...")
        extract_cmd = f"python extract_best_10_frames.py \"{video_path}\" -n 6 -o \"{keyframes_dir}\""
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
        
        # Create mock audio transcript (to simulate full pipeline context)
        mock_audio_transcript = """## AUDIO TRANSCRIPTION
[00:00:00.0] - "Pay no attention to the man behind the curtain. Go before I lose my temper."
[00:00:02.2] - "The great and powerful Oz has spoken."
[00:00:03.2] - "Yeah."
[00:00:03.8] - "I think so."

## ACOUSTIC & VOCAL ANALYSIS
- Emotional tone: Intense, commanding, with urgency and frustration
- Speaking style: Forceful and theatrical delivery
- Number of speakers: Single speaker throughout
- Vocal dynamics: Rapid pace, high volume, dramatic emphasis
- Audio quality: Clear studio recording, minimal background noise
- Background/environment: Controlled studio acoustics

## TIMING & PERFORMANCE ASSESSMENT
- Overall pacing: Dramatic build-up with emotional intensity
- Delivery style: Scripted theatrical performance
- Notable vocal moments: Emphasis on "great and powerful Oz"

## EDITOR'S CONTENT ASSESSMENT
- Content type: Theatrical dialogue from "The Wizard of Oz"
- Production context: Studio recording/performance rehearsal
- Notable elements: Classic theatrical lines, dramatic delivery"""

        # Test first batch (frames 1-3)
        batch_1_frames = frame_files[:3]
        frame_batch = []
        
        for i, frame_file in enumerate(batch_1_frames, 1):
            frame_path = os.path.join(keyframes_dir, frame_file)
            timestamp = frame_file.split('_')[2].replace('s', '').replace('.jpg', '')
            frame_batch.append((frame_path, timestamp, i))
            print(f"📷 Batch 1 Frame {i}: {frame_file} (timestamp: {timestamp}s)")
        
        # Create the exact system prompt from the main script
        system_prompt = f"""You are a professional video editor reviewing footage from recent shoots. You're analyzing visual content to catalog and organize your clips.

WORKFLOW CONTEXT:
✅ STEP 1 COMPLETED: Audio transcription and speaker voice analysis from the editor
🔄 STEP 2 CURRENT: Visual analysis of keyframes (batch 1 of 2)
⏳ STEP 3 UPCOMING: Final content categorization and organization decision

EDITOR'S VISUAL ANALYSIS TASK:
As an experienced editor, you need to analyze these visual frames to understand what you're working with. This batch contains {len(frame_batch)} keyframes from different timestamps.

CRITICAL UNDERSTANDING - STILL FRAMES FROM VIDEO:
- These are STILL FRAMES extracted from a moving video, not photographs
- People may be speaking even if their mouth appears closed in the frame
- Don't assume someone isn't talking just because their mouth looks closed in a still frame
- However, also don't automatically assume the visible person IS the speaker

VISUAL GENDER IDENTIFICATION (PRIORITY):
- VISUAL gender identification is more reliable than voice-based assessment
- Based on what you can SEE, determine the person's apparent gender
- Consider: facial features, hair style, clothing, body structure, overall appearance
- If visual evidence clearly indicates gender, this should take priority over audio assessment
- Be confident in your visual assessment - you can see the person directly
- Note if there's any discrepancy between audio and visual gender assessment

CRITICAL: IGNORE AUDIO GENDER ASSESSMENT - TRUST YOUR EYES
- Audio-based gender identification can be unreliable
- Your visual assessment is more accurate - you can directly see the person
- If you see a male person, they are male regardless of voice characteristics
- If you see a female person, they are female regardless of voice characteristics
- Voice pitch and tone can be misleading - PRIORITIZE what you visually observe
- State your visual gender assessment clearly and confidently

ABSOLUTE RULE: VISUAL ANALYSIS IS THE ONLY SOURCE FOR GENDER
- Look at facial features: jawline, nose shape, brow structure, cheekbones
- Look at hair style and length
- Look at overall appearance and body structure
- DO NOT consider audio content, dialogue, or voice characteristics
- DO NOT let character voices or performance context influence gender assessment
- This person's PHYSICAL APPEARANCE determines their gender - nothing else
- If you see masculine facial features, the person is male
- If you see feminine facial features, the person is female
- The audio track is completely irrelevant to gender identification

COMPLETE AUDIO TRANSCRIPT:
{mock_audio_transcript}

Use this exact transcript to understand what's being said during these video timestamps. Match the visual timestamps with the audio timeline.

YOUR PROFESSIONAL ASSESSMENT SHOULD INCLUDE:

2. **VISUAL GENDER ASSESSMENT** (PRIORITY - override audio if needed):
   - Based on VISUAL EVIDENCE, what is the apparent gender of the person?
   - Consider facial features, hair, clothing, body structure, overall appearance
   - If your visual assessment differs from the audio assessment, note this
   - Visual gender identification takes priority - you can see the person directly
   - Use appropriate pronouns based on visual appearance

END WITH: Brief summary of what this batch adds to your understanding of the overall content, your visual gender assessment, and your assessment of who is speaking."""

        # Prepare images
        images = []
        for frame_path, timestamp, frame_num in frame_batch:
            frame_base64 = encode_image(frame_path)
            frame_name = os.path.basename(frame_path)
            
            images.append({
                "type": "text",
                "text": f"VISUAL FRAME {frame_num} - TIMESTAMP: {timestamp}s\n\nFrame file: {frame_name}\n\nDescribe EXACTLY what you see at {timestamp} seconds:\n- Person's physical appearance and clothing\n- Exact facial expression and body position\n- Background and setting details\n- Any objects, props, or equipment visible\n- What specific action is being performed\n\nBe completely factual and literal."
            })
            images.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{frame_base64}"
                }
            })

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": images
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"ANALYZE VISUAL BATCH 1 WITH COMPLETE FACTUAL ACCURACY:\n\n1. Describe exactly what you see in each frame at its timestamp (literal visual description)\n2. CRITICAL: What is the VISUAL GENDER of the person based on facial features, hair, and appearance?\n3. How does this batch continue the actual visual progression?\n4. What exact words from the audio transcript are being spoken during these moments?\n5. How do the literal visual and audio elements correlate?\n6. End with a brief factual summary of this batch for continuity.\n\nCRITICAL: Focus on literal, observable facts. Describe exactly what is visible and audible. This is for accurate video indexing, not creative interpretation."
                    }
                ]
            }
        ]
        
        # Make API call
        payload = {
            "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.1
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer 2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP"
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
            print("🔍 VISUAL BATCH 1 GENDER DEBUG RESULTS")
            print("=" * 60)
            print(analysis)
            print("=" * 60)
            
            # Save results
            report_path = f"{os.path.splitext(os.path.basename(video_path))[0]}_batch_debug.md"
            with open(report_path, 'w') as f:
                f.write(f"# Visual Batch Gender Debug\n\n")
                f.write(f"**Video:** {video_path}\n")
                f.write(f"**Batch:** 1 of 2\n")
                f.write(f"**Frames:** {len(frame_batch)}\n")
                f.write(f"**Test Focus:** Debug gender assessment in full pipeline context\n\n")
                f.write("## Results\n\n")
                f.write(analysis)
            
            print(f"📄 Results saved: {report_path}")
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_visual_batch_debug.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        sys.exit(1)
    
    test_visual_batch_gender(video_path) 