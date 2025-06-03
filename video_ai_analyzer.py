#!/usr/bin/env python3
"""
Video AI Analyzer - Multimodal Analysis with Keyframes and Audio
Extracts keyframes and audio from video, sends to AI for comprehensive analysis.
"""

import os
import sys
import json
import base64
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple
import requests
from datetime import datetime
import cv2
import numpy as np

# Import our frame extraction function
from extract_best_10_frames import extract_best_frames_from_video

class VideoAIAnalyzer:
    """Comprehensive video analysis using multimodal AI."""
    
    def __init__(self, api_key: str, audio_model: str = "microsoft/Phi-4-multimodal-instruct", 
                 visual_model: str = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"):
        self.api_key = api_key
        self.audio_model = audio_model  # For audio transcription
        self.visual_model = visual_model  # For visual analysis and synthesis
        self.api_url = "https://api.deepinfra.com/v1/openai/chat/completions"
        
    def extract_audio(self, video_path: str, output_path: str = None) -> str:
        """Extract audio from video and compress to low bitrate MP3."""
        
        if output_path is None:
            output_path = f"temp_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            
        print(f"🎵 Extracting audio from {os.path.basename(video_path)}...")
        
        # Extract and compress audio using FFmpeg - MP3 for smaller file size
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'mp3',  # MP3 codec
            '-ar', '16000',  # 16kHz sample rate
            '-ab', '16k',  # 16kbps bitrate (ultra-compressed for API efficiency)
            '-ac', '1',  # Mono audio
            '-y',  # Overwrite output file
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            audio_size = os.path.getsize(output_path) / 1024  # KB
            print(f"✅ Audio extracted: {audio_size:.1f} KB (16kHz mono MP3)")
            
            # Check if audio file is too large
            if audio_size > 1000:  # More than 1MB
                print(f"⚠️  Audio file is large ({audio_size:.1f} KB) - may cause API issues")
            
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to extract audio: {e}")
    
    def encode_file_base64(self, file_path: str) -> str:
        """Encode file to base64 string."""
        try:
            with open(file_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to encode {file_path}: {e}")
    
    def select_best_3_frames(self, frame_files: List[str], frames_dir: str) -> List[Tuple[str, str, int]]:
        """Select the 3 most representative frames from all extracted frames."""
        
        print("🎯 Selecting 3 most representative frames...")
        
        # For now, select evenly distributed frames: first, middle, last
        if len(frame_files) >= 3:
            indices = [0, len(frame_files)//2, len(frame_files)-1]
            selected = []
            for i, idx in enumerate(indices, 1):
                frame_file = frame_files[idx]
                frame_path = os.path.join(frames_dir, frame_file)
                timestamp = frame_file.split('_')[2].replace('s', '')
                selected.append((frame_path, timestamp, i))
            
            print(f"✅ Selected frames: {[f[1] for f in selected]}")
            return selected
        else:
            # Use all available frames if less than 3
            selected = []
            for i, frame_file in enumerate(frame_files, 1):
                frame_path = os.path.join(frames_dir, frame_file)
                timestamp = frame_file.split('_')[2].replace('s', '')
                selected.append((frame_path, timestamp, i))
            return selected

    def analyze_audio_only(self, audio_path: str) -> str:
        """Analyze audio track separately to get transcript and audio content."""
        
        print("🎵 Analyzing audio track...")
        
        audio_base64 = self.encode_file_base64(audio_path)
        audio_size = os.path.getsize(audio_path) / 1024
        
        messages = [
            {
                "role": "system",
                "content": """You are a professional video editor organizing footage from recent shoots. You're going through raw clips to catalog and understand the content.

As an experienced editor, you have two main tasks:
1. TRANSCRIBE the audio exactly as spoken (your bread and butter skill)
2. Make EDUCATED GUESSES about what type of content this might be based on the dialogue

TRANSCRIPTION GUIDELINES:
- Listen carefully and write down exact spoken words
- Include precise timestamps
- This is literal transcription - word for word accuracy
- Note audio quality and speaker characteristics

CONTENT ANALYSIS (as an editor):
- Based on the dialogue style, delivery, and content, what might this be?
- Is this theatrical dialogue, documentary narration, casual conversation, rehearsal, etc.?
- Are there any recognizable phrases or speaking patterns that suggest the source?
- What production context does this seem to fit? (theater, film, practice, etc.)

FORMAT YOUR RESPONSE AS:
## AUDIO TRANSCRIPTION
[Timestamp] - "[Exact words spoken]"
[Timestamp] - "[Exact words spoken]"

## AUDIO CHARACTERISTICS
- Speaker: [demographics, accent, delivery style]
- Audio quality: [technical assessment]
- Background: [any ambient sounds]

## EDITOR'S CONTENT ASSESSMENT
- Content type: [educated guess based on dialogue]
- Production context: [likely scenario - rehearsal, performance, etc.]
- Notable elements: [anything that helps identify the source or purpose]

As a professional editor, make educated guesses but acknowledge when you're uncertain."""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""FOOTAGE REVIEW - AUDIO TRACK ({audio_size:.1f} KB)

You're reviewing this audio clip to catalog it for editing. Listen carefully and:

1. **TRANSCRIBE**: Write down every spoken word with timestamps
2. **ASSESS**: As an editor, what do you think this content is?

The dialogue style, delivery, and specific phrases should give you clues about:
- Is this from a known work or original content?
- What's the production context?
- What type of performance or recording is this?

Be thorough with transcription but also use your editing experience to make educated guesses about the content."""
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_base64,
                            "format": "mp3"
                        }
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """TRANSCRIBE AND ANALYZE:

1. Listen and transcribe every word spoken with timestamps
2. As a video editor, what do you think this footage contains?
   - Any recognizable dialogue or content?
   - What type of production does this seem like?
   - Performance, rehearsal, casual recording, etc.?

Format:
[Time] - "[Exact words spoken]"

Then give your professional assessment of what this content might be."""
                    }
                ]
            }
        ]
        
        payload = {
            "model": self.audio_model,
            "messages": messages,
            "max_tokens": 2000,  # Increased for detailed transcript
            "temperature": 0.05  # Even lower temperature for accurate transcription
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            raise RuntimeError(f"Audio analysis failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'error' in result:
            raise RuntimeError(f"Audio analysis error: {result['error']}")
        
        analysis = result['choices'][0]['message']['content']
        print(f"✅ Audio analysis complete ({result.get('usage', {}).get('total_tokens', 'unknown')} tokens)")
        
        return analysis

    def analyze_image_batch(self, frame_batch: List[Tuple[str, str, int]], 
                           batch_num: int, total_batches: int, 
                           audio_transcript: str = None, 
                           previous_summaries: List[str] = None) -> str:
        """Analyze a batch of up to 3 images with context from previous batches."""
        
        print(f"🖼️  Analyzing image batch {batch_num}/{total_batches} ({len(frame_batch)} frames)...")
        
        messages = []
        
        # Build context string from previous summaries
        context_info = ""
        if previous_summaries:
            context_info = "\n\nPREVIOUS VISUAL CONTEXT:\n"
            for i, summary in enumerate(previous_summaries, 1):
                context_info += f"Visual Batch {i} Summary: {summary}\n\n"
            context_info += "Use this context to understand the visual progression so far.\n"
        
        # Add audio context if available
        audio_context = ""
        if audio_transcript:
            audio_context = f"\n\nCOMPLETE AUDIO TRANSCRIPT:\n{audio_transcript}\n"
            audio_context += "\nUse this exact transcript to understand what's being said during these video timestamps. Match the visual timestamps with the audio timeline.\n"
        
        # System message for image batch analysis with factual emphasis
        messages.append({
            "role": "system",
            "content": f"""You are a professional video editor reviewing footage from recent shoots. You're analyzing visual content to catalog and organize your clips.

WORKFLOW CONTEXT:
✅ STEP 1 COMPLETED: Audio transcription and content assessment from the editor
🔄 STEP 2 CURRENT: Visual analysis of keyframes (batch {batch_num} of {total_batches})
⏳ STEP 3 UPCOMING: Final content categorization and organization decision

EDITOR'S VISUAL ANALYSIS TASK:
As an experienced editor, you need to analyze these visual frames to understand what you're working with. This batch contains {len(frame_batch)} keyframes from different timestamps.

{context_info}{audio_context}

YOUR PROFESSIONAL ASSESSMENT SHOULD INCLUDE:

1. **VISUAL INVENTORY** (your core skill):
   - Describe exactly what you see in each frame
   - Technical setup: lighting, equipment, green screen, microphones, etc.
   - Subject details: appearance, clothing, expressions, actions
   - Production quality and setup assessment

2. **CONTENT CORRELATION** (editor's experience):
   - How do these visuals match with the audio you've already reviewed?
   - What type of production does this look like based on setup and performance?
   - Is this a rehearsal, performance, casual recording, scripted content?

3. **EDITORIAL NOTES**:
   - Any technical issues or notable production elements
   - Performance style and delivery that matches the audio
   - How these frames help tell the story or content you're organizing

4. **CONTINUITY ASSESSMENT**:
   - How does this batch connect to previous visual content?
   - What's the narrative or performance progression?

CRITICAL FOR ORGANIZATION: Provide literal, factual descriptions that will help you catalog this footage properly. As an editor, you need accurate details for indexing and future reference.

END WITH: Brief summary of what this batch adds to your understanding of the overall content."""
        })
        
        # Add frame messages with clear timestamp emphasis
        for frame_path, timestamp, frame_num in frame_batch:
            frame_base64 = self.encode_file_base64(frame_path)
            frame_name = os.path.basename(frame_path)
            
            # Check if this is a consolidated frame with time range
            time_range_info = ""
            if len(frame_batch) <= 10 and "-" in timestamp:  # Likely consolidated
                time_range_info = "\n\n⚠️  IMPORTANT: This frame is REPRESENTATIVE of a time range. The visual content may have remained similar throughout this period, so this single frame represents the general visual state during the entire range."
            
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"VISUAL FRAME {frame_num} - TIMESTAMP: {timestamp}s\n\nFrame file: {frame_name}\n\nDescribe EXACTLY what you see at this timestamp:\n- Person's physical appearance and clothing\n- Exact facial expression and body position\n- Background and setting details\n- Any objects, props, or equipment visible\n- What specific action is being performed\n\nBe completely factual and literal.{time_range_info}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_base64}"
                        }
                    }
                ]
            })
        
        # Analysis request with clear factual emphasis
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"ANALYZE VISUAL BATCH {batch_num} WITH COMPLETE FACTUAL ACCURACY:\n\n1. Describe exactly what you see in each frame at its timestamp (literal visual description)\n2. How does this batch continue the actual visual progression from previous batches?\n3. What exact words from the audio transcript are being spoken during these moments?\n4. How do the literal visual and audio elements correlate?\n5. End with a brief factual summary of this batch for continuity.\n\nCRITICAL: Focus on literal, observable facts. Describe exactly what is visible and audible. This is for accurate video indexing, not creative interpretation."
                }
            ]
        })
        
        # Make API call
        payload = {
            "model": self.visual_model,
            "messages": messages,
            "max_tokens": 2000,  # Increased for detailed factual analysis
            "temperature": 0.1  # Lower temperature for more factual output
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            raise RuntimeError(f"Image batch {batch_num} failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'error' in result:
            raise RuntimeError(f"Image batch {batch_num} error: {result['error']}")
        
        analysis = result['choices'][0]['message']['content']
        print(f"✅ Image batch {batch_num} complete ({result.get('usage', {}).get('total_tokens', 'unknown')} tokens)")
        
        return analysis

    def extract_batch_summary(self, batch_analysis: str) -> str:
        """Extract the summary from a batch analysis for use as context."""
        
        # Look for the summary at the end of the analysis
        lines = batch_analysis.strip().split('\n')
        
        # Find lines that might contain the summary (usually the last few lines)
        summary_lines = []
        for line in reversed(lines):
            if line.strip() and not line.startswith('#'):
                summary_lines.insert(0, line.strip())
                if len(summary_lines) >= 3:  # Get last 3 non-empty lines
                    break
        
        if summary_lines:
            return ' '.join(summary_lines)
        else:
            # Fallback: first few sentences
            sentences = batch_analysis.split('.')[:3]
            return '. '.join(sentences) + '.'

    def synthesize_final_analysis(self, audio_analysis: str, image_analyses: List[str], 
                                 video_path: str, total_frames: int, custom_prompt: str = None) -> Dict:
        """Create final comprehensive analysis from separate audio and visual analyses."""
        
        print("\n🧠 Synthesizing final comprehensive analysis...")
        
        # Combine all image analyses
        combined_visual = "\n\n".join([f"=== VISUAL BATCH {i+1} ANALYSIS ===\n{analysis}" 
                                      for i, analysis in enumerate(image_analyses)])
        
        messages = []
        
        # System message for final synthesis with factual emphasis
        messages.append({
            "role": "system", 
            "content": f"""You are a professional video editor completing your footage review and making final organizational decisions.

WORKFLOW COMPLETED:
✅ STEP 1: Audio transcription and initial content assessment 
✅ STEP 2: Visual analysis of {len(image_analyses)} batches covering {total_frames} keyframes
🔄 STEP 3: FINAL ORGANIZATION - Catalog this footage and determine what you're working with

EDITOR'S FINAL ASSESSMENT TASK:
You've now reviewed both the complete audio transcript and visual content from "{os.path.basename(video_path)}". 
As an experienced editor, it's time to make your professional assessment and properly catalog this clip.

YOUR EDITORIAL EXPERTISE SHOULD DETERMINE:

1. **CONTENT IDENTIFICATION**: Based on the dialogue, delivery style, and visual setup, what do you think this footage contains?
   - Are there recognizable phrases or quotes that suggest the source material?
   - What type of content does the performance style indicate?
   - Is this from established material or original content?

2. **PRODUCTION CONTEXT**: What kind of shoot or recording session was this?
   - Rehearsal, performance, practice, audition, demo, etc.?
   - Professional production or casual recording?
   - What was the likely purpose of this footage?

3. **EDITORIAL CATEGORIZATION**: How would you file and organize this clip?
   - What tags or keywords would help you find this later?
   - What project or content type does this belong to?
   - How would you describe this to other team members?

4. **PROFESSIONAL RECOMMENDATIONS**: 
   - What would you do with this footage in post-production?
   - Any technical considerations for editing?
   - How could this content be used effectively?

CRITICAL GUIDELINES:
- Make EDUCATED GUESSES based on evidence from audio and visual content
- Use your professional experience to assess what you're seeing/hearing
- Be confident in your assessment but acknowledge uncertainty when appropriate
- Focus on practical, useful categorization for production workflow
- Include key phrases and recognizable content that would help identify this clip

Create a comprehensive editor's report that combines factual analysis with professional content assessment."""
        })
        
        # Provide the comprehensive analysis data
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""STEP 3: FINAL ORGANIZATION

Here is all the analysis data from the video "{os.path.basename(video_path)}" ({total_frames} keyframes analyzed):

=== COMPLETE AUDIO ANALYSIS ===
{audio_analysis}

=== COMPLETE VISUAL ANALYSIS ===
{combined_visual}

SYNTHESIZE THESE INTO A COMPLETE EDITOR'S REPORT:

{custom_prompt if custom_prompt else "Create a comprehensive editor's report that combines factual analysis with professional content assessment. Focus on exactly what is seen and heard. Include specific visual details, exact spoken content, and literal descriptions of actions. Correlate the word-for-word audio transcript with the visual progression to document exactly what happens in this video."}

CRITICAL: Be factual and literal. This is for video indexing - describe exactly what the video contains, not interpretations or metaphors."""
                }
            ]
        })
        
        # Make final API call
        payload = {
            "model": self.visual_model,
            "messages": messages,
            "max_tokens": 3000,  # Increased for comprehensive factual analysis
            "temperature": 0.1  # Lower temperature for more factual output
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            raise RuntimeError(f"Final synthesis failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'error' in result:
            raise RuntimeError(f"Final synthesis error: {result['error']}")
        
        print(f"✅ Final analysis complete ({result.get('usage', {}).get('total_tokens', 'unknown')} tokens)")
        
        return {
            'final_analysis': result['choices'][0]['message']['content'],
            'audio_analysis': audio_analysis,
            'image_analyses': image_analyses,
            'final_usage': result.get('usage', {}),
            'total_batches': len(image_analyses)
        }

    def analyze_video(self, video_path: str, num_frames: int = None, 
                     custom_prompt: str = None, temp_dir: str = None, consolidate: bool = False) -> Dict:
        """Complete video analysis workflow with separated audio and visual analysis."""
        
        print("🎬 VIDEO AI ANALYZER (Separated Audio/Visual)")
        print("=" * 60)
        print(f"📹 Video: {os.path.basename(video_path)}")
        print(f"🖼️  Frames: {num_frames if num_frames else 'intelligent auto-selection'} (single batch)")
        if consolidate:
            print("🔍 Consolidation: ENABLED (will group similar frames)")
        print(f"🤖 Models: {self.audio_model} + {self.visual_model}")
        print()
        
        # Create temporary directory
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="video_analysis_")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Step 1: Extract keyframes - let intelligent defaults decide if num_frames is None
            print("🖼️  Extracting keyframes...")
            frames_dir = os.path.join(temp_dir, "keyframes")
            frame_candidates = extract_best_frames_from_video(video_path, num_frames, frames_dir)
            
            if not frame_candidates:
                raise RuntimeError("Failed to extract frames")
            
            # Get frame files
            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            actual_frame_count = len(frame_files)
            
            # Prepare frame info for analysis
            frame_info = []
            for frame_file in frame_files:
                frame_path = os.path.join(frames_dir, frame_file)
                timestamp = frame_file.split('_')[2].replace('s', '')
                frame_info.append((frame_path, timestamp, len(frame_info) + 1))
            
            # Apply consolidation if requested
            if consolidate:
                consolidated_frames = self.consolidate_similar_frames(frame_info)
                # Convert back to frame_info format for analysis
                frame_info = [(path, timestamp, frame_num) for path, timestamp, frame_num, time_range in consolidated_frames]
                actual_frame_count = len(frame_info)
                print(f"📦 Using {actual_frame_count} consolidated frames for analysis")
            
            # Cap at 30 frames for optimal API performance
            if actual_frame_count > 30:
                print(f"⚠️  Frame count ({actual_frame_count}) exceeds optimal batch size, using first 30 frames")
                frame_info = frame_info[:30]
                actual_frame_count = 30
            
            print(f"✅ Analyzing {actual_frame_count} keyframes (single optimized batch)")
            
            # Step 2: Extract audio
            print("\n🎵 Extracting audio...")
            audio_path = os.path.join(temp_dir, "audio.mp3")
            self.extract_audio(video_path, audio_path)
            
            # Step 3: Analyze audio separately
            print(f"\n🚀 Step 1: Audio Analysis")
            audio_analysis = self.analyze_audio_only(audio_path)
            
            # Display audio transcription immediately
            print("\n" + "="*60)
            print("🎵 AUDIO TRANSCRIPTION RESULTS")
            print("="*60)
            print(audio_analysis)
            print("="*60)
            
            # Brief pause between requests
            print("⏱️  Brief pause...")
            import time
            time.sleep(3)
            
            # Step 4: Analyze ALL frames in a single batch (OPTIMIZED!)
            print(f"\n🚀 Step 2: Visual Analysis")
            print(f"📦 Processing all {actual_frame_count} frames in single optimized batch...")
            
            # Single batch analysis with all frames
            visual_analysis = self.analyze_image_batch(
                frame_info, 1, 1,  # batch_num=1, total_batches=1
                audio_transcript=audio_analysis
            )
            
            print(f"✅ Single batch visual analysis complete!")
            
            # Step 5: Synthesize final analysis
            print(f"\n🚀 Step 3: Final Synthesis")
            synthesis_result = self.synthesize_final_analysis(
                audio_analysis, [visual_analysis], video_path, actual_frame_count, custom_prompt
            )
            
            print("✅ Complete optimized analysis workflow finished!")
            
            return {
                'analysis': synthesis_result['final_analysis'],
                'audio_analysis': synthesis_result['audio_analysis'],
                'image_analyses': synthesis_result['image_analyses'],
                'usage': synthesis_result['final_usage'],
                'total_batches': 1,  # Always 1 now
                'frame_count': actual_frame_count,
                'frame_files': [os.path.basename(info[0]) for info in frame_info],
                'video_path': video_path,
                'consolidation_applied': consolidate
            }
            
        finally:
            # Cleanup temporary files
            print(f"\n🧹 Cleaning up temporary files in {temp_dir}...")
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def save_analysis_report(self, analysis_result: Dict, output_file: str = None):
        """Save the analysis to a formatted report file."""
        
        if output_file is None:
            video_name = Path(analysis_result['video_path']).stem
            output_file = f"{video_name}_analysis_report.md"
        
        with open(output_file, 'w') as f:
            f.write(f"# Video Analysis Report\n\n")
            f.write(f"**Video:** {analysis_result['video_path']}\n")
            f.write(f"**Frames Analyzed:** {analysis_result['frame_count']}\n")
            f.write(f"**Analysis Method:** Single batch ({analysis_result.get('total_batches', 1)} batch)\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            # Main analysis
            f.write("# COMPREHENSIVE ANALYSIS\n\n")
            f.write(analysis_result['analysis'])
            
            # Batch analyses if available
            if 'batch_analyses' in analysis_result:
                f.write(f"\n\n---\n\n# DETAILED BATCH ANALYSES\n\n")
                for i, batch_analysis in enumerate(analysis_result['batch_analyses'], 1):
                    f.write(f"## Batch {i} Analysis\n\n")
                    f.write(batch_analysis)
                    f.write(f"\n\n")
            
            f.write(f"\n\n---\n\n")
            f.write(f"**API Usage:** {analysis_result['usage']}\n")
            f.write(f"**Frames:** {', '.join(analysis_result['frame_files'])}\n")
        
        print(f"📄 Report saved: {output_file}")

    def frames_are_similar(self, frame1: np.ndarray, frame2: np.ndarray, threshold: float = 0.95) -> bool:
        """Check if two frames are visually similar using histogram comparison."""
        
        # Resize frames to same size for fair comparison
        if frame1.shape != frame2.shape:
            height, width = min(frame1.shape[0], frame2.shape[0]), min(frame1.shape[1], frame2.shape[1])
            frame1 = cv2.resize(frame1, (width, height))
            frame2 = cv2.resize(frame2, (width, height))
        
        # Method 1: Quick pixel difference check (fast filter)
        pixel_diff = np.mean(np.abs(frame1.astype(float) - frame2.astype(float)))
        if pixel_diff > 20:  # Frames are clearly different
            return False
        
        # Method 2: Histogram comparison (more precise)
        # Calculate histograms for each channel
        hist1_b = cv2.calcHist([frame1], [0], None, [256], [0, 256])
        hist1_g = cv2.calcHist([frame1], [1], None, [256], [0, 256])
        hist1_r = cv2.calcHist([frame1], [2], None, [256], [0, 256])
        
        hist2_b = cv2.calcHist([frame2], [0], None, [256], [0, 256])
        hist2_g = cv2.calcHist([frame2], [1], None, [256], [0, 256])
        hist2_r = cv2.calcHist([frame2], [2], None, [256], [0, 256])
        
        # Compare histograms using correlation
        corr_b = cv2.compareHist(hist1_b, hist2_b, cv2.HISTCMP_CORREL)
        corr_g = cv2.compareHist(hist1_g, hist2_g, cv2.HISTCMP_CORREL)
        corr_r = cv2.compareHist(hist1_r, hist2_r, cv2.HISTCMP_CORREL)
        
        # Average correlation across channels
        avg_correlation = (corr_b + corr_g + corr_r) / 3
        
        return avg_correlation > threshold

    def consolidate_similar_frames(self, frame_info: List[Tuple[str, str, int]], 
                                 similarity_threshold: float = 0.95) -> List[Tuple[str, str, int, str]]:
        """Group similar consecutive frames and return representatives with time ranges.
        Ensures minimum temporal coverage: first, last, and distributed middle frames."""
        
        if len(frame_info) <= 5:
            # If 5 or fewer frames, keep them all with individual timestamps
            return [(path, timestamp, frame_num, f"{timestamp}s") for path, timestamp, frame_num in frame_info]
        
        print(f"🔍 Consolidating similar frames (threshold: {similarity_threshold:.0%})...")
        
        # Always keep first and last frames for temporal coverage
        first_frame = frame_info[0]
        last_frame = frame_info[-1]
        middle_frames = frame_info[1:-1]
        
        if not middle_frames:
            return [(first_frame[0], first_frame[1], first_frame[2], f"{first_frame[1]}s"),
                    (last_frame[0], last_frame[1], last_frame[2], f"{last_frame[1]}s")]
        
        # Load frames for similarity comparison
        def load_frame(frame_path):
            frame = cv2.imread(frame_path)
            return frame if frame is not None else None
        
        # Group similar consecutive middle frames
        groups = []
        current_group = [middle_frames[0]]
        
        for i in range(1, len(middle_frames)):
            current_frame_path = middle_frames[i][0]
            previous_frame_path = current_group[-1][0]
            
            current_frame = load_frame(current_frame_path)
            previous_frame = load_frame(previous_frame_path)
            
            if (current_frame is not None and previous_frame is not None and 
                self.frames_are_similar(previous_frame, current_frame, similarity_threshold)):
                # Add to current group
                current_group.append(middle_frames[i])
            else:
                # Start new group
                groups.append(current_group)
                current_group = [middle_frames[i]]
        
        # Add the last group
        groups.append(current_group)
        
        # Select representatives and ensure minimum 3 middle frames
        middle_representatives = []
        
        if len(groups) < 3:
            # If we have fewer than 3 groups, distribute the available groups
            for group in groups:
                # Select best quality frame from each group
                best_frame = None
                best_sharpness = 0
                
                for frame_info_item in group:
                    frame = load_frame(frame_info_item[0])
                    if frame is not None:
                        sharpness = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                        if sharpness > best_sharpness:
                            best_sharpness = sharpness
                            best_frame = frame_info_item
                
                if best_frame:
                    # Create time range
                    start_time = group[0][1]
                    end_time = group[-1][1]
                    time_range = f"{start_time}s-{end_time}s ({len(group)} frames)" if len(group) > 1 else f"{start_time}s"
                    middle_representatives.append((best_frame[0], best_frame[1], best_frame[2], time_range))
            
            # Ensure we have at least 3 middle representatives by adding individual frames if needed
            while len(middle_representatives) < 3 and len(middle_frames) >= 3:
                # Distribute remaining frames evenly
                remaining_indices = []
                step = len(middle_frames) // (3 - len(middle_representatives))
                for i in range(len(middle_representatives), 3):
                    idx = min(i * step, len(middle_frames) - 1)
                    remaining_indices.append(idx)
                
                for idx in remaining_indices:
                    if idx < len(middle_frames):
                        frame_item = middle_frames[idx]
                        middle_representatives.append((frame_item[0], frame_item[1], frame_item[2], f"{frame_item[1]}s"))
                break
        
        else:
            # Select representatives from each group
            for group in groups:
                best_frame = None
                best_sharpness = 0
                
                for frame_info_item in group:
                    frame = load_frame(frame_info_item[0])
                    if frame is not None:
                        sharpness = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                        if sharpness > best_sharpness:
                            best_sharpness = sharpness
                            best_frame = frame_info_item
                
                if best_frame:
                    start_time = group[0][1]
                    end_time = group[-1][1]
                    time_range = f"{start_time}s-{end_time}s ({len(group)} frames)" if len(group) > 1 else f"{start_time}s"
                    middle_representatives.append((best_frame[0], best_frame[1], best_frame[2], time_range))
        
        # Combine all representatives: first + middle + last
        consolidated = []
        
        # Add first frame
        consolidated.append((first_frame[0], first_frame[1], first_frame[2], f"{first_frame[1]}s (START)"))
        
        # Add middle representatives (limit to reasonable number for API efficiency)
        max_middle = min(len(middle_representatives), 25)  # Leave room for first/last
        consolidated.extend(middle_representatives[:max_middle])
        
        # Add last frame (if different from first)
        if last_frame != first_frame:
            consolidated.append((last_frame[0], last_frame[1], last_frame[2], f"{last_frame[1]}s (END)"))
        
        original_count = len(frame_info)
        consolidated_count = len(consolidated)
        reduction = (1 - consolidated_count / original_count) * 100
        
        print(f"✅ Consolidated {original_count} → {consolidated_count} frames ({reduction:.1f}% reduction)")
        print(f"📊 Coverage: START + {len(middle_representatives)} middle sections + END")
        
        return consolidated

def main():
    parser = argparse.ArgumentParser(
        description='Analyze video using multimodal AI - extracts keyframes and audio for comprehensive analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python video_ai_analyzer.py video.mp4                                   # Default 9 frames (3 batches)
  python video_ai_analyzer.py video.mp4 -n 6                             # 6 keyframes (2 batches)
  python video_ai_analyzer.py video.mp4 -n 12                            # 12 keyframes (4 batches)
  python video_ai_analyzer.py video.mp4 -p "Focus on the technical aspects" # Custom prompt
  python video_ai_analyzer.py video.mp4 -o analysis.md                   # Custom output file
        ''')
    
    parser.add_argument('video_path', help='Path to the input video file')
    parser.add_argument('-n', '--num-frames', type=int, default=None,
                        help='Number of keyframes to extract (default: intelligent auto-selection based on video length)')
    parser.add_argument('-p', '--prompt', default=None,
                        help='Custom analysis prompt (optional)')
    parser.add_argument('-o', '--output', default=None,
                        help='Output file for analysis report (default: auto-generated)')
    parser.add_argument('--consolidate', action='store_true',
                        help='Consolidate visually similar consecutive frames to reduce redundancy (useful for static videos)')
    parser.add_argument('--api-key', default="2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP",
                        help='DeepInfra API key (default: provided key)')
    parser.add_argument('--audio-model', default="microsoft/Phi-4-multimodal-instruct",
                        help='AI model for audio analysis (default: Phi-4-multimodal-instruct)')
    parser.add_argument('--visual-model', default="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
                        help='AI model for visual analysis and synthesis (default: Llama-4-Maverick-17B-128E-Instruct-FP8)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.video_path):
        print(f"❌ Video file not found: {args.video_path}")
        return 1
    
    if args.num_frames is not None and args.num_frames < 1:
        print("❌ Must extract at least 1 frame when specifying frame count")
        return 1
    
    try:
        # Create analyzer
        analyzer = VideoAIAnalyzer(args.api_key, args.audio_model, args.visual_model)
        
        # Analyze video
        result = analyzer.analyze_video(
            args.video_path, 
            args.num_frames, 
            args.prompt,
            temp_dir=None,
            consolidate=args.consolidate
        )
        
        # Display results
        print("\n" + "="*60)
        print("🤖 AI ANALYSIS RESULTS")
        print("="*60)
        print(result['analysis'])
        print("\n" + "="*60)
        
        # Save report
        analyzer.save_analysis_report(result, args.output)
        
        print(f"\n🎉 Analysis complete! Token usage: {result['usage']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 