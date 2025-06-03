#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.search_logic import find_similar_clips_duckdb

def test_cli_weights():
    with get_db_connection() as conn:
        print("🔍 Testing CLI weights vs Direct function weights")
        print("=" * 50)
        
        clip_id = '9204c6f0-f62b-4c0c-8786-333502d8ce07'
        
        # Test with direct function weights (what worked)
        print("📊 Direct function weights (0.4, 0.3, 0.3):")
        results1 = find_similar_clips_duckdb(
            source_clip_id=clip_id,
            conn=conn,
            mode='visual',
            match_count=5,
            visual_thumb1_weight=0.4,
            visual_thumb2_weight=0.3,
            visual_thumb3_weight=0.3,
            similarity_threshold=0.2
        )
        
        print(f"   Found {len(results1)} results")
        for r in results1:
            print(f"   - {r['file_name']}: {r['combined_similarity_score']:.4f}")
        
        print()
        print("📊 CLI weights (0.2, 0.15, 0.15) - 0.5 * [0.4, 0.3, 0.3]:")
        results2 = find_similar_clips_duckdb(
            source_clip_id=clip_id,
            conn=conn,
            mode='visual',
            match_count=5,
            visual_thumb1_weight=0.2,   # 0.5 * 0.4
            visual_thumb2_weight=0.15,  # 0.5 * 0.3
            visual_thumb3_weight=0.15,  # 0.5 * 0.3
            similarity_threshold=0.2
        )
        
        print(f"   Found {len(results2)} results")
        for r in results2:
            print(f"   - {r['file_name']}: {r['combined_similarity_score']:.4f}")
            
        if len(results1) != len(results2):
            print("\n❌ CONFIRMED: CLI weights are causing the issue!")
            print("The similarity scores are scaled down by ~50%, falling below threshold.")

if __name__ == "__main__":
    test_cli_weights() 