#!/usr/bin/env python3
import sys
import os
import json
import requests
sys.path.append('/Users/developer/Development/GitHub/AIIngestingTool')

from video_ingest_tool.embeddings_image import batch_generate_thumbnail_embeddings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')

# Get AI thumbnail data from the API
print('Fetching AI thumbnail data from API...')
try:
    response = requests.get('http://localhost:8001/api/clips?limit=1')
    if response.status_code == 200:
        data = response.json()
        clips = data.get('data', {}).get('data', [])
        if clips:
            clip = clips[0]
            ai_thumbs_json = clip.get('ai_selected_thumbnails_json', '[]')
            ai_thumbnails = json.loads(ai_thumbs_json)
            
            print(f'Found {len(ai_thumbnails)} AI thumbnails')
            for thumb in ai_thumbnails:
                print(f'  Rank {thumb.get("rank")}: {thumb.get("path")}')
                print(f'    Description: {thumb.get("description")}')
                print(f'    File exists: {os.path.exists(thumb.get("path", ""))}')
            
            if ai_thumbnails:
                print('\nTesting batch thumbnail embedding generation...')
                print('===========================================')
                
                embeddings = batch_generate_thumbnail_embeddings(
                    ai_thumbnails,
                    logger=logger
                )
                
                print(f'\nResults:')
                print(f'Generated embeddings for {len(embeddings)} thumbnails')
                for rank, embedding in embeddings.items():
                    if embedding:
                        print(f'  Rank {rank}: {len(embedding)}D embedding - First 3 values: {embedding[:3]}')
                    else:
                        print(f'  Rank {rank}: FAILED to generate embedding')
            else:
                print('No AI thumbnails found to test with')
        else:
            print('No clips found in database')
    else:
        print(f'Failed to fetch clips: {response.status_code}')
        
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc() 