#!/usr/bin/env python3
"""
Extract N best motion frames from any video with temporal progression.
Uses intelligent defaults with hybrid (motion analysis) or fast (temporal) extraction.
"""

import cv2
import numpy as np
import os
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

class FrameCandidate:
    """Represents a potential frame with quality metrics."""
    
    def __init__(self, frame_num: int, timestamp: float, frame: np.ndarray, 
                 motion_score: float, sharpness: float):
        self.frame_num = frame_num
        self.timestamp = timestamp
        self.frame = frame
        self.motion_score = motion_score
        self.sharpness = sharpness
        self.composite_score = 0.0
        
    def calculate_composite_score(self, motion_weight=0.7, sharpness_weight=0.3):
        """Calculate a composite quality score."""
        # Normalize scores (assuming motion_score 0-1, sharpness 0-1000+)
        norm_motion = min(self.motion_score * 10, 1.0)  # Scale motion to 0-1
        norm_sharpness = min(self.sharpness / 100.0, 1.0)  # Scale sharpness to 0-1
        
        self.composite_score = (motion_weight * norm_motion + 
                               sharpness_weight * norm_sharpness)
        return self.composite_score

def save_temporal_progression_frames(selected_frames: List[FrameCandidate], video_path: str, 
                                   output_dir: str, video_duration: float, num_frames: int):
    """Save frames with temporal progression naming."""
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nSaving {num_frames} temporal progression frames to: {output_dir}/")
    print("=" * 80)
    
    segment_duration = video_duration / num_frames
    
    for i, frame in enumerate(selected_frames):
        # Determine which segment this frame represents
        if i == 0:
            segment_info = "START"
        elif i == len(selected_frames) - 1:
            segment_info = "END"
        else:
            segment_num = int(frame.timestamp / segment_duration) + 1
            progress_pct = (frame.timestamp / video_duration) * 100
            segment_info = f"SEG{segment_num:02d}_{progress_pct:04.1f}%"
        
        # Create descriptive filename with temporal info
        filename = f"frame_{i+1:02d}_{frame.timestamp:.3f}s_{segment_info}_m{frame.motion_score:.3f}_s{frame.sharpness:.0f}.jpg"
        filepath = os.path.join(output_dir, filename)
        
        # Save frame with high quality
        cv2.imwrite(filepath, frame.frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        progress_pct = (frame.timestamp / video_duration) * 100
        print(f"Frame {i+1:2d}: {frame.timestamp:6.3f}s ({progress_pct:5.1f}%) | "
              f"Motion: {frame.motion_score:.3f} | Sharpness: {frame.sharpness:6.0f} | "
              f"Segment: {segment_info}")
    
    print(f"\n✓ Saved {len(selected_frames)} frames representing video timeline progression")
    print("✓ Each frame represents a different time segment for complete temporal coverage")

def extract_frames_fast_temporal(video_path: str, num_frames: int) -> List[FrameCandidate]:
    """Fast temporal sampling - just extract evenly spaced frames without motion analysis."""
    
    print(f"🚀 Fast temporal extraction mode (no motion analysis)")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"Video: {duration:.1f}s, {total_frames} frames at {fps:.1f} FPS")
    
    candidates = []
    
    # Calculate frame positions for even temporal distribution
    if num_frames == 1:
        frame_positions = [total_frames // 2]  # Middle frame
    else:
        frame_positions = []
        for i in range(num_frames):
            # Evenly distribute frames across the video
            position = int((i * total_frames) / (num_frames - 1))
            if position >= total_frames:
                position = total_frames - 1
            frame_positions.append(position)
    
    print(f"📊 Extracting {len(frame_positions)} evenly spaced frames")
    
    for i, frame_num in enumerate(frame_positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        
        if ret:
            # Resize frame
            frame = cv2.resize(frame, (854, 480))
            timestamp = frame_num / fps
            
            # Calculate sharpness only
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
            
            candidate = FrameCandidate(frame_num, timestamp, frame, 0.0, sharpness)
            candidates.append(candidate)
            
            print(f"  Frame {i+1}/{len(frame_positions)}: {timestamp:.3f}s (sharpness: {sharpness:.0f})")
        else:
            print(f"  Frame {i+1}/{len(frame_positions)}: Failed to extract frame at {frame_num}")
    
    cap.release()
    
    print(f"✓ Fast extraction complete: {len(candidates)} frames")
    return candidates

def extract_frames_hybrid_mode(video_path: str, num_frames: int, local_window: int = 4) -> List[FrameCandidate]:
    """Hybrid mode: Fast temporal sampling + local OpenCV optimization within small windows."""
    
    print(f"🚀 Hybrid extraction mode (temporal + local optimization)")
    print(f"📊 Local window: {local_window} frames around each target timestamp")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"Video: {duration:.1f}s, {total_frames} frames at {fps:.1f} FPS")
    
    candidates = []
    
    # Calculate target frame positions for even temporal distribution
    if num_frames == 1:
        target_positions = [total_frames // 2]
    else:
        target_positions = []
        for i in range(num_frames):
            position = int((i * total_frames) / (num_frames - 1))
            if position >= total_frames:
                position = total_frames - 1
            target_positions.append(position)
    
    print(f"📊 Analyzing {len(target_positions)} target positions with {local_window}-frame windows")
    
    for i, target_frame in enumerate(target_positions):
        print(f"  Target {i+1}/{len(target_positions)}: {target_frame/fps:.3f}s")
        
        # Define window around target frame
        window_start = max(0, target_frame - local_window // 2)
        window_end = min(total_frames - 1, target_frame + local_window // 2)
        window_frames = list(range(window_start, window_end + 1))
        
        print(f"    Analyzing frames {window_start}-{window_end} ({len(window_frames)} frames)")
        
        # Extract and analyze frames in this window
        window_candidates = []
        prev_frame = None
        
        for frame_num in window_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if ret:
                # Resize frame
                frame = cv2.resize(frame, (854, 480))
                timestamp = frame_num / fps
                
                # Calculate sharpness
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
                
                # Calculate motion if we have a previous frame
                motion_score = 0.0
                if prev_frame is not None:
                    gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                    gray2 = gray_frame
                    
                    # Box filter for speed
                    gray1 = cv2.boxFilter(gray1, -1, (5, 5))
                    gray2 = cv2.boxFilter(gray2, -1, (5, 5))
                    
                    # Calculate motion
                    diff = cv2.absdiff(gray1, gray2)
                    _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
                    
                    # Motion score
                    motion_score = cv2.countNonZero(thresh) / (thresh.shape[0] * thresh.shape[1])
                
                candidate = FrameCandidate(frame_num, timestamp, frame, motion_score, sharpness)
                candidate.calculate_composite_score()
                window_candidates.append(candidate)
                
                prev_frame = frame
        
        # Select best frame from this window
        if window_candidates:
            # Prioritize sharpness for quality, but consider motion too
            best_candidate = max(window_candidates, key=lambda x: x.sharpness)
            candidates.append(best_candidate)
            
            print(f"    ✓ Selected: {best_candidate.timestamp:.3f}s "
                  f"(motion: {best_candidate.motion_score:.3f}, sharpness: {best_candidate.sharpness:.0f})")
        else:
            print(f"    ❌ No frames extracted from window")
    
    cap.release()
    
    print(f"✓ Hybrid extraction complete: {len(candidates)} frames")
    return candidates

def calculate_intelligent_frame_count(duration: float, max_frames: int = 30) -> int:
    """Calculate optimal frame count based on video duration."""
    
    if duration <= 30:
        # Short videos: 1 frame per second (up to 30 frames)
        frame_count = min(int(duration), max_frames)
        print(f"📊 Short video ({duration:.1f}s): Using 1 FPS = {frame_count} frames")
    elif duration <= 60:
        # Medium videos: 1 frame every 2 seconds (15-30 frames)
        frame_count = min(int(duration / 2), max_frames)
        print(f"📊 Medium video ({duration:.1f}s): Using 1 frame every 2s = {frame_count} frames")
    elif duration <= 300:  # 5 minutes
        # Long videos: 1 frame every 10-15 seconds (20-30 frames)
        frame_count = min(max(int(duration / 10), 20), max_frames)
        print(f"📊 Long video ({duration:.1f}s): Using 1 frame every {duration/frame_count:.1f}s = {frame_count} frames")
    else:
        # Very long videos: Cap at max_frames with even distribution
        frame_count = max_frames
        interval = duration / frame_count
        print(f"📊 Very long video ({duration:.1f}s): Capped at {frame_count} frames (1 every {interval:.1f}s)")
    
    return frame_count

def extract_best_frames_from_video(video_path: str, num_frames: int = None, output_dir: str = None,
                                   fast_mode: bool = False, hybrid_mode: bool = False):
    """Main function to extract N best frames from a video with intelligent defaults."""
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    # Get video properties first to determine intelligent defaults
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    cap.release()
    
    # Use intelligent frame count if not specified
    if num_frames is None:
        num_frames = calculate_intelligent_frame_count(duration)
        print(f"🧠 Intelligent mode: auto-selected {num_frames} frames")
    
    # Intelligent mode selection if no explicit mode chosen
    if not (fast_mode or hybrid_mode):
        # Default to hybrid mode for better quality (motion analysis + local optimization)
        # Only use fast mode for extremely long videos where speed is critical
        if duration > 600:  # 10+ minutes - use fast mode for very long videos
            fast_mode = True
            print(f"🧠 Intelligent mode: using fast extraction for very long video")
        else:
            hybrid_mode = True  # Default to hybrid for all other videos
            if duration <= 30:
                print(f"🧠 Intelligent mode: using hybrid extraction for short video")
            elif duration <= 60:
                print(f"🧠 Intelligent mode: using hybrid extraction for medium video")
            else:
                print(f"🧠 Intelligent mode: using hybrid extraction for long video")
    
    if num_frames < 1:
        raise ValueError("Must extract at least 1 frame")
    
    # Create output directory
    if output_dir is None:
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_dir = f"{video_name}_best_{num_frames}_frames"
    
    print(f"BEST {num_frames} FRAMES EXTRACTOR")
    print("=" * 80)
    print(f"Input: {video_path}")
    print(f"Output: {output_dir}/")
    print(f"Video: {duration:.1f}s ({total_frames} frames at {fps:.1f} FPS)")
    
    start_time = time.time()
    
    try:
        # Determine extraction method
        if hybrid_mode:
            print(f"Strategy: Hybrid mode (temporal + local optimization)")
            print()
            all_selected = extract_frames_hybrid_mode(video_path, num_frames)
        else:  # fast_mode
            print(f"Strategy: Fast temporal sampling")
            print()
            all_selected = extract_frames_fast_temporal(video_path, num_frames)
        
        # Sort by timestamp to ensure proper order
        all_selected.sort(key=lambda x: x.timestamp)
        
        # Save frames with temporal progression info
        save_temporal_progression_frames(all_selected, video_path, output_dir, duration, num_frames)
        
        processing_time = time.time() - start_time
        
        # Calculate comprehensive performance metrics
        overall_fps = total_frames / processing_time
        
        print(f"\n✓ Successfully extracted {num_frames} frames in {processing_time:.2f}s")
        print(f"📊 PERFORMANCE METRICS:")
        print(f"   • Total video frames: {total_frames:,}")
        print(f"   • Overall processing: {overall_fps:.1f} FPS")
        
        if hybrid_mode:
            frames_analyzed = num_frames * 4  # Approximate frames analyzed in hybrid mode (4-frame windows)
            analysis_fps = frames_analyzed / processing_time
            efficiency = (frames_analyzed / total_frames) * 100
            print(f"   • Frames analyzed: ~{frames_analyzed} ({efficiency:.2f}% of total)")
            print(f"   • Analysis rate: {analysis_fps:.1f} FPS")
            print(f"✓ Hybrid mode: {efficiency:.2f}% selective analysis at {analysis_fps:.1f} FPS")
        else:  # fast_mode
            frames_processed = num_frames  # Fast mode only processes exact target frames
            efficiency = (frames_processed / total_frames) * 100
            print(f"   • Frames processed: {frames_processed} ({efficiency:.3f}% of total)")
            print(f"✓ Fast mode: {num_frames/processing_time:.1f} frames/second extraction")
        
        return all_selected
        
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description='Extract N best motion frames from any video with intelligent defaults',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python extract_best_10_frames.py video.mp4                    # Intelligent mode (auto frame count & method)
  python extract_best_10_frames.py video.mp4 -n 5              # Force 5 frames with intelligent method selection
  python extract_best_10_frames.py video.mp4 -n 20 --fast      # Force 20 frames with fast mode
  python extract_best_10_frames.py video.mp4 -n 10 --hybrid    # Force 10 frames with hybrid mode

Intelligent Mode (default):
  • Videos ≤30s: ~1 FPS with hybrid extraction (1 frame per second, best quality from 4-frame windows)
  • Videos 30-60s: ~0.5 FPS with hybrid extraction (1 frame per 2 seconds, motion analysis)  
  • Videos 60s-10m: ~20-30 frames with hybrid extraction (motion analysis + local optimization)
  • Videos >10m: 30 frames max with fast extraction (speed priority for very long videos)
        ''')
    
    parser.add_argument('video_path', help='Path to the input video file')
    parser.add_argument('-n', '--num-frames', type=int, default=None, 
                        help='Number of frames to extract (default: intelligent auto-selection)')
    parser.add_argument('-o', '--output-dir', default=None,
                        help='Output directory (default: auto-generated based on video name and frame count)')
    parser.add_argument('--fast', action='store_true',
                        help='Force fast mode (no motion analysis, just evenly spaced frames)')
    parser.add_argument('--hybrid', action='store_true',
                        help='Force hybrid mode (temporal + local optimization)')
    
    args = parser.parse_args()
    
    if args.num_frames is not None and args.num_frames < 1:
        print("Error: Must extract at least 1 frame")
        return
    
    extract_best_frames_from_video(args.video_path, args.num_frames, args.output_dir, 
                                   args.fast, args.hybrid)

if __name__ == "__main__":
    main() 