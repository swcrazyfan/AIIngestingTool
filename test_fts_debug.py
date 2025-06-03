#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from video_ingest_tool.database.duckdb.connection import get_db_connection

def test_fts():
    """Test FTS functionality directly."""
    print("=== TESTING FTS FUNCTIONALITY ===")
    
    with get_db_connection() as conn:
        # Test 1: Check if FTS docs are indexed
        try:
            docs_count = conn.execute("SELECT COUNT(*) FROM fts_app_data_clips.docs").fetchone()[0]
            print(f"FTS docs count: {docs_count}")
        except Exception as e:
            print(f"FTS docs error: {e}")
        
        # Test 2: Get a clip ID for testing
        clip_result = conn.execute("SELECT id FROM app_data.clips WHERE transcript_preview LIKE '%curtain%' LIMIT 1").fetchone()
        if clip_result:
            clip_id = clip_result[0]
            print(f"Found clip with 'curtain': {clip_id}")
            
            # Test 3: Try direct FTS match
            try:
                fts_result = conn.execute("SELECT fts_app_data_clips.match_bm25(?, 'curtain')", [clip_id]).fetchone()
                print(f"Direct FTS match result: {fts_result}")
            except Exception as e:
                print(f"Direct FTS match error: {e}")
        else:
            print("No clip found with 'curtain' in transcript")
        
        # Test 4: Check what's actually in the FTS index
        try:
            sample_docs = conn.execute("SELECT * FROM fts_app_data_clips.docs LIMIT 3").fetchall()
            print(f"Sample FTS docs: {len(sample_docs)} found")
            for doc in sample_docs:
                print(f"  Doc: {doc}")
        except Exception as e:
            print(f"Sample docs error: {e}")
        
        # Test 5: Try different FTS query syntax
        try:
            alt_query = """
                SELECT c.id, c.file_name, fts_app_data_clips.match_bm25(c.id, 'curtain') as score
                FROM app_data.clips c
                WHERE fts_app_data_clips.match_bm25(c.id, 'curtain') > 0
                LIMIT 5
            """
            alt_results = conn.execute(alt_query).fetchall()
            print(f"Alternative FTS query results: {len(alt_results)} found")
            for result in alt_results:
                print(f"  {result}")
        except Exception as e:
            print(f"Alternative FTS query error: {e}")

if __name__ == "__main__":
    test_fts() 