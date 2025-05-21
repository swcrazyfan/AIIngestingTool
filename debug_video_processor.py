import os
import logging
import sys
from video_ingest_tool.config import Config
from video_ingest_tool.video_processor import VideoCompressor

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_video_processor.py <video_path>")
        return
        
    video_path = sys.argv[1]
    if not os.path.exists(video_path):
        logger.error(f"Input video file not found: {video_path}")
        return
        
    logger.info(f"Testing video compression for: {video_path}")
    
    try:
        # Just test the VideoCompressor component
        compressor = VideoCompressor()
        logger.info("VideoCompressor initialized")
        
        compressed_path = compressor.compress(video_path)
        logger.info(f"Compression successful! Output: {compressed_path}")
        
    except Exception as e:
        logger.error(f"Compression failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
