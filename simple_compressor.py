import os
import logging
import sys
import subprocess

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleCompressor:
    """A simpler video compressor using ffmpeg command line."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def compress(self, input_path):
        """Compress video using ffmpeg directly."""
        try:
            self.logger.info(f"Compressing video: {input_path}")
            output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
            
            # Check for ffmpeg
            try:
                subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.logger.error("ffmpeg not found in PATH. Please install ffmpeg.")
                return None
                
            # Compress video using ffmpeg
            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264", "-crf", "28",  # Video codec and quality
                "-vf", "scale=1280:720",           # Resolution
                "-r", "1",                         # 1 FPS
                "-c:a", "aac", "-b:a", "16k",      # Audio codec and bitrate
                "-ac", "1",                        # Mono audio
                "-y",                              # Overwrite output
                output_path
            ]
            
            self.logger.info(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.logger.info(f"Compression successful. Output: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Compression failed: {str(e)}")
            if hasattr(e, 'stderr'):
                self.logger.error(f"FFMPEG error: {e.stderr}")
            return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_compressor.py <video_path>")
        return
        
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        logger.error(f"Input video file not found: {video_path}")
        return
        
    logger.info(f"Testing simple video compression for: {video_path}")
    
    try:
        # Test the simple compressor
        compressor = SimpleCompressor()
        compressed_path = compressor.compress(video_path)
        
        if compressed_path:
            logger.info(f"Compression successful! Output: {compressed_path}")
            # Check if file exists and get its size
            if os.path.exists(compressed_path):
                size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                logger.info(f"Compressed file size: {size_mb:.2f} MB")
            else:
                logger.error(f"Expected output file not found: {compressed_path}")
        else:
            logger.error("Compression failed.")
            
    except Exception as e:
        logger.error(f"Compression process failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
