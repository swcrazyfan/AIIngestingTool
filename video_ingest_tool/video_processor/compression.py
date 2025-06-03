"""
Video compression module for compressing video files using ffmpeg.

This module provides the VideoCompressor class for hardware-accelerated video compression.
"""

import os
import sys
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple, Callable
import re # For parsing ffmpeg progress

from ..config import DEFAULT_COMPRESSION_CONFIG


class VideoCompressor:
    """Handles video compression using ffmpeg with hardware acceleration when available."""
    
    def __init__(self,
                 config: Optional[Dict[str, Any]] = None,
                 progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Initialize the VideoCompressor with configuration.
        
        Args:
            config: Optional configuration to override default settings
            progress_callback: Optional function to call with progress updates
        """
        self.config = {
            **DEFAULT_COMPRESSION_CONFIG,
            **(config or {})
        }
        self.logger = logging.getLogger(self.__class__.__name__)
        self.progress_callback = progress_callback
    
    def _check_videotoolbox_availability(self) -> Dict[str, bool]:
        """
        Check if VideoToolbox hardware acceleration is available on macOS.
        
        Returns:
            Dict[str, bool]: Dictionary with availability of h264 and hevc encoders
        """
        result = {
            'h264_videotoolbox': False,
            'hevc_videotoolbox': False
        }
        
        if sys.platform != 'darwin':
            return result
            
        try:
            # Check if VideoToolbox encoders are available in ffmpeg
            proc = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"], 
                check=True, capture_output=True, text=True
            )
            result['h264_videotoolbox'] = 'h264_videotoolbox' in proc.stdout
            result['hevc_videotoolbox'] = 'hevc_videotoolbox' in proc.stdout
            
            if result['h264_videotoolbox']:
                self.logger.info("H.264 VideoToolbox encoder is available")
            if result['hevc_videotoolbox']:
                self.logger.info("HEVC VideoToolbox encoder is available")
                
            return result
        except Exception as e:
            self.logger.warning(f"Error checking for VideoToolbox: {str(e)}")
            return result
    
    def _select_best_codec(self) -> str:
        """
        Select the best available codec based on priorities and system capabilities.
        
        Returns:
            str: The best available codec to use
        """
        available_codecs = {
            'libx264': True,  # Assume libx264 is always available
            'libx265': False,  # Will be checked below
            'h264_videotoolbox': False,
            'hevc_videotoolbox': False
        }
        
        # Check if h265/HEVC is available
        try:
            hevc_check = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"], 
                check=True, capture_output=True, text=True
            )
            available_codecs['libx265'] = 'libx265' in hevc_check.stdout
        except Exception:
            pass
            
        # If hardware acceleration is enabled and we're on macOS, check for VideoToolbox
        if self.config['use_hardware_accel'] and sys.platform == 'darwin':
            vt_availability = self._check_videotoolbox_availability()
            available_codecs['h264_videotoolbox'] = vt_availability['h264_videotoolbox']
            available_codecs['hevc_videotoolbox'] = vt_availability['hevc_videotoolbox']
        
        # Select the best codec based on priority list
        for codec in self.config['codec_priority']:
            if codec in available_codecs and available_codecs[codec]:
                self.logger.info(f"Selected codec: {codec}")
                return codec
                
        # Default to libx264 as fallback
        self.logger.info("Falling back to libx264 codec")
        return 'libx264'

    def _get_video_metadata(self, input_path: str) -> Dict[str, Any]:
        """
        Get metadata of the input video using ffprobe.
        
        Args:
            input_path: Path to input video file
            
        Returns:
            Dict[str, Any]: Dictionary containing 'width', 'height', 'duration', 'total_frames', 'avg_frame_rate'
                           Returns empty dict if detection fails.
        """
        metadata = {}
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-select_streams", "v:0", input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            probe_data = json.loads(result.stdout)

            if probe_data.get('streams'):
                video_stream = probe_data['streams'][0]
                metadata['width'] = int(video_stream.get('width', 0))
                metadata['height'] = int(video_stream.get('height', 0))
                
                duration_str = video_stream.get('duration')
                if duration_str:
                    metadata['duration'] = float(duration_str)
                
                # nb_frames might not always be accurate for all formats, calculate if possible
                total_frames_str = video_stream.get('nb_frames')
                avg_frame_rate_str = video_stream.get('avg_frame_rate')

                if total_frames_str and total_frames_str != "N/A":
                    metadata['total_frames'] = int(total_frames_str)
                elif duration_str and avg_frame_rate_str and avg_frame_rate_str != "0/0":
                    num, den = map(int, avg_frame_rate_str.split('/'))
                    if den > 0:
                        avg_fps = num / den
                        metadata['total_frames'] = int(float(duration_str) * avg_fps)
                
                if avg_frame_rate_str and avg_frame_rate_str != "0/0":
                     num, den = map(int, avg_frame_rate_str.split('/'))
                     if den > 0:
                         metadata['avg_frame_rate'] = num / den

                self.logger.info(f"Detected video metadata for {input_path}: {metadata}")
            else:
                self.logger.warning(f"Could not detect video stream for {input_path}")
        except Exception as e:
            self.logger.warning(f"Failed to detect video metadata for {input_path}: {str(e)}")
        return metadata

    def compress_video(self, input_path: str, output_dir: str = None,
                       flow_run_id: Optional[str] = None, file_path_for_tracker: Optional[str] = None) -> str:
        """
        Compress video using ffmpeg with the best available codec and report progress.
        
        Args:
            input_path: Path to input video file (actual source file)
            output_dir: Directory to save compressed file (defaults to ../compressed relative to input)
            flow_run_id: Optional Prefect flow run ID for progress tracking.
            file_path_for_tracker: Optional file path to use for progress tracker (if different from input_path, e.g. original path)

        Returns:
            str: Path to compressed output video
            
        Raises:
            RuntimeError: If compression fails
        """
        tracker_file_path = file_path_for_tracker or input_path
        try:
            if output_dir:
                compressed_dir = output_dir
            else:
                input_file_dir = os.path.dirname(input_path)
                parent_dir = os.path.dirname(input_file_dir)
                input_dir_name = os.path.basename(input_file_dir)
                compressed_dir = os.path.join(parent_dir, "compressed", input_dir_name)
            
            os.makedirs(compressed_dir, exist_ok=True)
            
            input_basename = os.path.basename(input_path)
            output_basename = f"{os.path.splitext(input_basename)[0]}_compressed.mp4"
            output_path = os.path.join(compressed_dir, output_basename)
            
            self.logger.info(f"Compressing {input_path} to {output_path}")
            
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
                
            try:
                subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")
                
            video_meta = self._get_video_metadata(input_path)
            input_width = video_meta.get('width')
            input_height = video_meta.get('height')
            total_frames = video_meta.get('total_frames')

            needs_scaling = False
            scale_filter = None
            max_dimension = self.config['max_dimension']
            
            if input_width and input_height:
                # Find the longest dimension
                longest_dimension = max(input_width, input_height)
                
                # Check if longest dimension exceeds our target
                if longest_dimension > max_dimension:
                    needs_scaling = True
                    
                    if self.config.get('use_conditional_scaling', False):
                        # Use conditional scaling filter like: scale='if(gte(iw,ih),854,-2)':'if(gte(ih,iw),854,-2)'
                        scale_filter = f"scale='if(gte(iw,ih),{max_dimension},-2)':'if(gte(ih,iw),{max_dimension},-2)'"
                        self.logger.info(f"Using conditional scaling from {input_width}x{input_height} with max dimension {max_dimension}px")
                    else:
                        # Calculate scaling to fit longest dimension (original method)
                        scale_factor = max_dimension / longest_dimension
                        target_width = int(input_width * scale_factor)
                        target_height = int(input_height * scale_factor)
                        
                        # Make sure dimensions are even (required for many codecs)
                        target_width = target_width if target_width % 2 == 0 else target_width - 1
                        target_height = target_height if target_height % 2 == 0 else target_height - 1
                        
                        scale_filter = f"scale={target_width}:{target_height}"
                        self.logger.info(f"Scaling down from {input_width}x{input_height} to {target_width}x{target_height} (longest dimension: {longest_dimension} → {max_dimension})")
                else:
                    self.logger.info(f"Resolution {input_width}x{input_height} fits within {max_dimension}px, compressing without scaling")
            else:
                # If we can't detect resolution, use default scaling as fallback
                needs_scaling = True
                if self.config.get('use_conditional_scaling', False):
                    scale_filter = f"scale='if(gte(iw,ih),{max_dimension},-2)':'if(gte(ih,iw),{max_dimension},-2)'"
                else:
                    scale_filter = f"scale={max_dimension}:{max_dimension}"
                self.logger.warning(f"Could not detect resolution, using default scaling to {max_dimension}px")
            
            # Select the best available codec
            video_codec = self._select_best_codec()
            
            # Base ffmpeg command
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-progress", "pipe:1",  # Output progress to stdout
                "-nostats",             # Don't output verbose stats to stderr
                "-c:v", video_codec
            ]
            
            if 'preset' in self.config and self.config['preset']:
                cmd.extend(["-preset", self.config['preset']])
 
            if video_codec == 'libx264' or video_codec == 'libx265':
                cmd.extend(["-crf", str(self.config['crf_value'])])
            elif 'videotoolbox' in video_codec:
                cmd.extend(["-b:v", self.config['video_bitrate']])
                cmd.extend(["-allow_sw", "1"])
                if video_codec == 'hevc_videotoolbox':
                    cmd.extend(["-profile:v", "main"])
            else:
                cmd.extend(["-b:v", self.config['video_bitrate']])
            
            if needs_scaling:
                cmd.extend(["-vf", scale_filter])
            
            cmd.extend(["-r", str(self.config['fps'])])
            
            # Ensure faststart for web playback (move moov atom to beginning)
            cmd.extend(["-movflags", "+faststart"])
            
            # Ensure universally compatible pixel format
            cmd.extend(["-pix_fmt", "yuv420p"])
            
            if self.config.get('audio_copy', False):
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend([
                    "-c:a", "aac", "-b:a", self.config['audio_bitrate'],
                    "-ac", str(self.config['audio_channels'])
                ])
            
            cmd.append(output_path)
            
            self.logger.info(f"Running compression command: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            
            progress_data = {}
            stderr_output = []

            if self.progress_callback and flow_run_id and total_frames:
                 # Initial progress update
                self.progress_callback({
                    'flow_run_id': flow_run_id,
                    'file_path': tracker_file_path,
                    'step_name': "video_compression",
                    'step_progress': 0,
                    'step_status': "processing",
                    'compression_update': {
                        'total_frames': total_frames,
                        'processed_frames': 0,
                        'current_rate': 0,
                        'speed': "0x"
                    }
                })

            # Read stdout for progress
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        progress_data[key.strip()] = value.strip()

                        if key == 'progress' and value == 'end':
                            break
                        
                        if self.progress_callback and flow_run_id and total_frames and \
                           ('frame' in progress_data or 'fps' in progress_data or 'speed' in progress_data):
                            processed_frames = int(progress_data.get('frame', 0))
                            current_fps = float(progress_data.get('fps', 0))
                            current_speed = progress_data.get('speed', "0x")
                            
                            step_prog = int((processed_frames / total_frames) * 100) if total_frames > 0 else 0
                            
                            self.progress_callback({
                                'flow_run_id': flow_run_id,
                                'file_path': tracker_file_path,
                                'step_name': "video_compression",
                                'step_progress': step_prog,
                                'step_status': "processing",
                                'compression_update': {
                                    'total_frames': total_frames,
                                    'processed_frames': processed_frames,
                                    'current_rate': current_fps,
                                    'speed': current_speed
                                }
                            })
                process.stdout.close()

            # Read stderr for errors
            if process.stderr:
                for line in iter(process.stderr.readline, ''):
                    stderr_output.append(line.strip())
                process.stderr.close()

            return_code = process.wait()

            if return_code == 0 and os.path.exists(output_path):
                input_size = os.path.getsize(input_path)
                output_size = os.path.getsize(output_path)
                compression_ratio = input_size / output_size if output_size > 0 else 0
                
                self.logger.info(f"Compression successful!")
                self.logger.info(f"Input size: {input_size/1024/1024:.2f} MB, Output size: {output_size/1024/1024:.2f} MB, Ratio: {compression_ratio:.2f}x")
                
                if self.progress_callback and flow_run_id:
                    self.progress_callback({
                        'flow_run_id': flow_run_id,
                        'file_path': tracker_file_path,
                        'step_name': "video_compression",
                        'step_progress': 100,
                        'step_status': "completed",
                        'compression_update': { 'processed_frames': total_frames } if total_frames else {}
                    })
                return output_path
            else:
                err_msg = f"ffmpeg process failed with code {return_code}."
                if stderr_output:
                    err_msg += f" Stderr: {' '.join(stderr_output)}"
                self.logger.error(err_msg)
                if self.progress_callback and flow_run_id:
                     self.progress_callback({
                        'flow_run_id': flow_run_id,
                        'file_path': tracker_file_path,
                        'step_name': "video_compression",
                        'step_status': "failed",
                        'compression_update': { 'error_detail': err_msg }
                    })
                raise RuntimeError(err_msg)
            
        except Exception as e:
            self.logger.error(f"Compression failed for {input_path}: {str(e)}", exc_info=True)
            if self.progress_callback and flow_run_id:
                self.progress_callback({
                    'flow_run_id': flow_run_id,
                    'file_path': tracker_file_path,
                    'step_name': "video_compression",
                    'step_status': "failed",
                    'compression_update': { 'error_detail': str(e) }
                })
            raise RuntimeError(f"Compression failed for {input_path}: {str(e)}")