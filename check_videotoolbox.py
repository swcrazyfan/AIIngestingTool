import os
import sys
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_videotoolbox():
    """Check if VideoToolbox is available on this system"""
    logger.info("Checking VideoToolbox availability...")
    
    try:
        # Check for macOS
        if sys.platform != 'darwin':
            logger.info(f"Not running on macOS (platform: {sys.platform}), VideoToolbox not available")
            return False
            
        # Check if ffmpeg is installed
        try:
            subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
            logger.info("ffmpeg is installed")
        except subprocess.CalledProcessError:
            logger.error("ffmpeg is not installed")
            return False
            
        # Check available encoders
        encoders = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"], 
            check=True, capture_output=True, text=True
        )
        
        # Check for VideoToolbox encoders
        h264_vt = 'h264_videotoolbox' in encoders.stdout
        hevc_vt = 'hevc_videotoolbox' in encoders.stdout
        
        if h264_vt:
            logger.info("✅ h264_videotoolbox encoder is available")
        else:
            logger.info("❌ h264_videotoolbox encoder is NOT available")
            
        if hevc_vt:
            logger.info("✅ hevc_videotoolbox encoder is available")
        else:
            logger.info("❌ hevc_videotoolbox encoder is NOT available")
            
        # Check if we can run a simple encoding test with VideoToolbox
        if h264_vt or hevc_vt:
            logger.info("Running a simple VideoToolbox encoding test...")
            
            # Create a simple test video (5 seconds)
            test_video = "/tmp/videotoolbox_test.mp4"
            test_output = "/tmp/videotoolbox_test_out.mp4"
            
            # Create test video if it doesn't exist
            if not os.path.exists(test_video):
                logger.info("Creating test video...")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", test_video
                ], check=True)
                
            # Try to encode with VideoToolbox
            codec = "h264_videotoolbox" if h264_vt else "hevc_videotoolbox"
            logger.info(f"Testing encoding with {codec}...")
            try:
                result = subprocess.run([
                    "ffmpeg", "-y", "-i", test_video, 
                    "-c:v", codec, "-b:v", "2000k",
                    "-vf", "scale=640:360",
                    test_output
                ], check=True, capture_output=True, text=True)
                
                logger.info("✅ VideoToolbox encoding test successful!")
                if os.path.exists(test_output):
                    size = os.path.getsize(test_output)
                    logger.info(f"Output file size: {size/1024:.1f} KB")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ VideoToolbox encoding test failed: {e.stderr}")
                return False
        else:
            logger.info("No VideoToolbox encoders available")
            return False
            
    except Exception as e:
        logger.error(f"Error checking VideoToolbox: {str(e)}")
        return False

if __name__ == "__main__":
    result = check_videotoolbox()
    print(f"\nVideoToolbox is {'AVAILABLE' if result else 'NOT AVAILABLE'} on this system")
