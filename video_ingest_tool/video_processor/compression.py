"""
Video compression module for compressing video files using ffmpeg.

This module provides the VideoCompressor class for hardware-accelerated video compression.
"""

import os
import sys
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple

from ..config import DEFAULT_COMPRESSION_CONFIG


class VideoCompressor:
    """Handles video compression using ffmpeg with hardware acceleration when available."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the VideoCompressor with configuration.
        
        Args:
            config: Optional configuration to override default settings
        """
        self.config = {
            **DEFAULT_COMPRESSION_CONFIG,
            **(config or {})
        }
        self.logger = logging.getLogger(self.__class__.__name__)
    
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

    def _get_video_resolution(self, input_path: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Get the resolution of the input video.
        
        Args:
            input_path: Path to input video file
            
        Returns:
            Tuple[Optional[int], Optional[int]]: (width, height) or (None, None) if detection fails
        """
        try:
            # Use ffprobe to get video resolution
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json", 
                "-show_streams", "-select_streams", "v:0", input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            probe_data = json.loads(result.stdout)
            
            if probe_data.get('streams'):
                video_stream = probe_data['streams'][0]
                width = video_stream.get('width')
                height = video_stream.get('height')
                
                if width and height:
                    self.logger.info(f"Detected video resolution: {width}x{height}")
                    return (int(width), int(height))
            
            self.logger.warning("Could not detect video resolution")
            return (None, None)
            
        except Exception as e:
            self.logger.warning(f"Failed to detect video resolution: {str(e)}")
            return (None, None)

    def compress(self, input_path: str, output_dir: str = None) -> str:
        """
        Compress video using ffmpeg with the best available codec.
        
        Args:
            input_path: Path to input video file
            output_dir: Directory to save compressed file (defaults to ../compressed relative to input)
            
        Returns:
            str: Path to compressed output video
            
        Raises:
            RuntimeError: If compression fails
        """
        try:
            # Create output directory - use provided directory or create parallel compressed/ directory
            if output_dir:
                compressed_dir = output_dir
            else:
                # Get the parent directory of the input file's directory
                input_dir = os.path.dirname(input_path)
                parent_dir = os.path.dirname(input_dir)
                
                # Create a 'compressed' directory at the same level as the input directory
                input_dir_name = os.path.basename(input_dir)
                compressed_dir = os.path.join(parent_dir, "compressed", input_dir_name)
            
            os.makedirs(compressed_dir, exist_ok=True)
            
            # Use just the filename for the output, not the full path
            input_basename = os.path.basename(input_path)
            output_basename = f"{os.path.splitext(input_basename)[0]}_compressed.mp4"
            output_path = os.path.join(compressed_dir, output_basename)
            
            self.logger.info(f"Compressing {input_path} to {output_path}")
            
            # Check if input file exists
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
                
            # Check for ffmpeg
            try:
                subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")
                
            # Detect input video resolution
            input_width, input_height = self._get_video_resolution(input_path)
            
            # Determine if we need to scale down
            needs_scaling = False
            scale_filter = None
            max_dimension = self.config['max_dimension']
            
            if input_width and input_height:
                # Find the longest dimension
                longest_dimension = max(input_width, input_height)
                
                # Check if longest dimension exceeds our target
                if longest_dimension > max_dimension:
                    needs_scaling = True
                    
                    # Calculate scaling to fit longest dimension
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
                scale_filter = f"scale={max_dimension}:{max_dimension}"
                self.logger.warning(f"Could not detect resolution, using default scaling to {max_dimension}px")
            
            # Select the best available codec
            video_codec = self._select_best_codec()
            
            # Base ffmpeg command
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-c:v", video_codec
            ]
            
            # Add codec-specific parameters
            if video_codec == 'libx264' or video_codec == 'libx265':
                # For software encoding, use CRF (Constant Rate Factor) for quality-based encoding
                cmd.extend(["-crf", str(self.config['crf_value'])])  # Use configurable CRF
            elif 'videotoolbox' in video_codec:
                # For hardware encoding, use bitrate-based encoding
                cmd.extend(["-b:v", self.config['video_bitrate']])
                
                # Add specific VideoToolbox parameters for better quality
                cmd.extend(["-allow_sw", "1"])  # Allow software encoding as fallback
                
                # Add ProRes options for better quality with VideoToolbox
                if video_codec == 'hevc_videotoolbox':
                    cmd.extend(["-profile:v", "main"])
            else:
                # Default to bitrate for other encoders
                cmd.extend(["-b:v", self.config['video_bitrate']])
            
            # Set video filters if needed
            if needs_scaling:
                cmd.extend(["-vf", scale_filter])
            
            # Set frame rate
            cmd.extend(["-r", str(self.config['fps'])])
            
            # Set audio settings
            cmd.extend([
                "-c:a", "aac",
                "-b:a", self.config['audio_bitrate'],
                "-ac", str(self.config['audio_channels'])
            ])
            
            # Add output path
            cmd.append(output_path)
            
            # Execute ffmpeg
            self.logger.info(f"Running compression command: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Check if output file was created and has a reasonable size
            if os.path.exists(output_path):
                input_size = os.path.getsize(input_path)
                output_size = os.path.getsize(output_path)
                compression_ratio = input_size / output_size if output_size > 0 else 0
                
                self.logger.info(f"Compression successful!")
                self.logger.info(f"Input size: {input_size/1024/1024:.2f} MB")
                self.logger.info(f"Output size: {output_size/1024/1024:.2f} MB")
                self.logger.info(f"Compression ratio: {compression_ratio:.2f}x")
                return output_path
            else:
                raise RuntimeError(f"Output file not created: {output_path}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg error: {e.stderr}")
            raise RuntimeError(f"Compression failed: ffmpeg error: {e.stderr}")
        except Exception as e:
            self.logger.error(f"Compression failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Compression failed: {str(e)}") 