#!/usr/bin/env python3

"""
Visual Similarity Search Debug Test
Test visual similarity search with different thresholds to find the optimal setting.
"""

import sys
sys.path.insert(0, '.')

from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.search_logic import find_similar_clips_duckdb

def test_visual_similarity_with_thresholds():
    """Test visual similarity with different thresholds to debug the issue."""
    
    print("🔍 Visual Similarity Search Debug Test")
    print("=" * 50)
    
    # Test with a clip that has embeddings - use MVI clip to find other MVI clip
    test_clip_id = "9204c6f0-f62b-4c0c-8786-333502d8ce07"  # MVI_0484.MP4
    expected_similar_id = "2f4d22e4-879c-48a8-a226-b18d23ce4af1"  # MVI_0481.MP4
    
    # Test with different thresholds
    thresholds_to_test = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    
    with get_db_connection() as conn:
        print(f"🎯 Testing visual similarity for clip: {test_clip_id}")
        print()
        
        # First, check what embeddings this clip has
        source_query = """
        SELECT 
            file_name,
            CASE WHEN thumbnail_1_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_thumb1,
            CASE WHEN thumbnail_2_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_thumb2,
            CASE WHEN thumbnail_3_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_thumb3
        FROM app_data.clips WHERE id = ?
        """
        
        source_info = conn.execute(source_query, [test_clip_id]).fetchone()
        if source_info:
            print(f"📹 Source clip: {source_info[0]}")
            print(f"   Thumbnail 1 embedding: {source_info[1]}")
            print(f"   Thumbnail 2 embedding: {source_info[2]}")
            print(f"   Thumbnail 3 embedding: {source_info[3]}")
            print()
        
        # Test each threshold
        for threshold in thresholds_to_test:
            print(f"🔍 Testing threshold: {threshold}")
            
            try:
                results = find_similar_clips_duckdb(
                    source_clip_id=test_clip_id,
                    conn=conn,
                    mode="visual",
                    match_count=5,
                    similarity_threshold=threshold
                )
                
                if results:
                    print(f"   ✅ Found {len(results)} results")
                    found_expected = False
                    for i, result in enumerate(results[:3]):  # Show top 3
                        score = result.get('combined_similarity_score', 0)
                        file_name = result.get('file_name', 'Unknown')
                        clip_id = result.get('id', '')
                        if clip_id == expected_similar_id:
                            found_expected = True
                            print(f"      {i+1}. {file_name} (score: {score:.4f}) ⭐ EXPECTED MATCH!")
                        else:
                            print(f"      {i+1}. {file_name} (score: {score:.4f})")
                    if found_expected:
                        print(f"   🎯 SUCCESS: Found expected similar clip MVI_0481.MP4!")
                else:
                    print(f"   ❌ No results found")
                    
            except Exception as e:
                print(f"   💥 Error: {e}")
            
            print()
        
        # Also test what the actual similarity scores are between clips (raw calculation)
        print("🧮 Raw similarity score analysis:")
        print("=" * 30)
        
        # Get all clips with embeddings
        all_clips_query = """
        SELECT id, file_name, thumbnail_1_embedding, thumbnail_2_embedding, thumbnail_3_embedding
        FROM app_data.clips 
        WHERE (thumbnail_1_embedding IS NOT NULL OR thumbnail_2_embedding IS NOT NULL OR thumbnail_3_embedding IS NOT NULL)
        AND id != ?
        """
        
        other_clips = conn.execute(all_clips_query, [test_clip_id]).fetchall()
        source_embeddings = conn.execute("""
        SELECT thumbnail_1_embedding, thumbnail_2_embedding, thumbnail_3_embedding
        FROM app_data.clips WHERE id = ?
        """, [test_clip_id]).fetchone()
        
        if source_embeddings and other_clips:
            print(f"Comparing against {len(other_clips)} other clips:")
            
            for clip_id, file_name, thumb1, thumb2, thumb3 in other_clips[:3]:  # Test first 3
                print(f"\n📹 vs {file_name}:")
                
                # Calculate raw cosine similarities
                for i, source_emb in enumerate(source_embeddings, 1):
                    if source_emb:
                        target_embeddings = [thumb1, thumb2, thumb3]
                        for j, target_emb in enumerate(target_embeddings, 1):
                            if target_emb:
                                similarity_query = """
                                SELECT array_cosine_similarity(?::FLOAT[1152], ?::FLOAT[1152]) as similarity
                                """
                                sim_result = conn.execute(similarity_query, [source_emb, target_emb]).fetchone()
                                if sim_result:
                                    similarity = sim_result[0]
                                    print(f"   Thumb{i} -> Thumb{j}: {similarity:.4f}")

if __name__ == "__main__":
    test_visual_similarity_with_thresholds() 