import argparse
import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from video_ingest_tool.video_processor import VideoProcessor
from video_ingest_tool.config import Config

# Load environment variables from .env file
project_root = Path(__file__).parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# Configure basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Test script for VideoProcessor.")
    parser.add_argument("video_path", help="Path to the input video file.")
    args = parser.parse_args()

    if not os.path.exists(args.video_path):
        logger.error(f"Input video file not found: {args.video_path}")
        return

    # Ensure GEMINI_API_KEY is set in your environment
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("GEMINI_API_KEY environment variable is not set in the .env file. Please add it to the .env file in the project root.")
        return

    try:
        # Create a default/mock Config object for testing
        # You might need to adjust this based on your actual Config class requirements
        mock_config_data = {
            "output_dir": "./test_output", # Example output directory
            "processors": {
                "video": {
                    "enabled": True,
                    # Add any other video-specific config VideoProcessor might need from Config
                }
            }
            # Add other necessary config fields if your Config class requires them
        }
        config = Config(config_data=mock_config_data)
        
        # Create the output directory if it doesn't exist
        os.makedirs(config.get_setting('output_dir', './test_output'), exist_ok=True)

        logger.info(f"Initializing VideoProcessor...")
        video_processor = VideoProcessor(config=config)

        logger.info(f"Processing video: {args.video_path}")
        result = video_processor.process(args.video_path)

        if result.get('success'):
            logger.info("Video processing successful!")
            logger.info(f"Compressed video saved at: {result.get('compressed_path')}")
            logger.info(f"Analysis JSON saved at: {result.get('analysis_path')}")
            
            # Print the AI analysis output directly from the result
            analysis_json = result.get('analysis_json', {})
            if analysis_json:
                # Print the formatted analysis results
                logger.info("\n========== AI ANALYSIS RESULTS ==========")
                
                # Summary section
                summary = analysis_json.get('summary', {})
                logger.info("\n----- SUMMARY -----")
                logger.info(f"Overall: {summary.get('overall', 'N/A')}")
                logger.info(f"Audio Key Points: {summary.get('audio_key_points', 'N/A')}")
                
                # Scenes section
                scenes = analysis_json.get('scenes', [])
                logger.info(f"\n----- SCENES ({len(scenes)}) -----")
                for i, scene in enumerate(scenes[:3], 1):  # Show first 3 scenes
                    logger.info(f"Scene {i}:")
                    logger.info(f"  Timestamp: {scene.get('timestamp', 'N/A')}")
                    logger.info(f"  Type: {scene.get('type', 'N/A')}")
                    logger.info(f"  Description: {scene.get('description', 'N/A')}")
                    logger.info(f"  People Count: {scene.get('people_count', 'N/A')}")
                if len(scenes) > 3:
                    logger.info(f"...and {len(scenes) - 3} more scenes. See full analysis in the JSON file.")
                
                # Audio section
                audio = analysis_json.get('audio', {})
                logger.info("\n----- AUDIO -----")
                logger.info(f"Has Dialogue: {audio.get('has_dialogue', 'N/A')}")
                key_phrases = audio.get('key_phrases', [])
                if key_phrases:
                    logger.info(f"Key Phrases: {', '.join(key_phrases)}")
                
                # Entities section
                entities = analysis_json.get('entities', {})
                logger.info("\n----- ENTITIES -----")
                logger.info(f"Total People: {entities.get('total_people', 'N/A')}")
                locations = entities.get('locations', [])
                if locations:
                    logger.info(f"Locations: {', '.join(locations)}")
                animals = entities.get('animals', [])
                if animals:
                    logger.info(f"Animals: {', '.join(animals)}")
                
                logger.info("\n=========================================")
        else:
            logger.error(f"Video processing failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        logger.error(f"An error occurred during the test: {e}", exc_info=True)

if __name__ == "__main__":
    main()
