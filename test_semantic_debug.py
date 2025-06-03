#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.search_logic import semantic_search_clips_duckdb
from video_ingest_tool.embeddings import generate_embeddings

def test_semantic_search():
    """Test semantic search functionality directly."""
    print("=== TESTING SEMANTIC SEARCH ===")
    
    # Test with "green screen" which we know is in the content
    summary_content = "Video content about: green screen"
    keyword_content = "green screen"
    
    print(f"Generating embeddings for: '{summary_content}' and '{keyword_content}'")
    query_summary_embedding, query_keyword_embedding = generate_embeddings(summary_content, keyword_content)
    
    print(f"Summary embedding length: {len(query_summary_embedding) if query_summary_embedding else 'None'}")
    print(f"Keyword embedding length: {len(query_keyword_embedding) if query_keyword_embedding else 'None'}")
    
    with get_db_connection() as conn:
        # Check if embeddings exist in the database
        embed_check = conn.execute("""
            SELECT file_name, 
                   CASE WHEN summary_embedding IS NOT NULL THEN LENGTH(summary_embedding) ELSE 0 END as sum_len,
                   CASE WHEN keyword_embedding IS NOT NULL THEN LENGTH(keyword_embedding) ELSE 0 END as key_len
            FROM app_data.clips 
            ORDER BY file_name
        """).fetchall()
        
        print("\\nEmbedding status in database:")
        for file_name, sum_len, key_len in embed_check:
            print(f"  {file_name}: summary={sum_len}, keyword={key_len}")
        
        # Test semantic search with very low threshold
        print("\\nTesting semantic search with threshold 0.01:")
        results = semantic_search_clips_duckdb(
            conn=conn,
            query_summary_embedding=query_summary_embedding,
            query_keyword_embedding=query_keyword_embedding,
            match_count=5,
            summary_weight=1.0,
            keyword_weight=0.8,
            similarity_threshold=0.01
        )
        
        print(f"Semantic search results: {len(results)} found")
        for r in results:
            print(f"  {r.get('file_name')}: score={r.get('combined_similarity_score')}")
            print(f"    Summary: {r.get('content_summary', '')[:80]}...")

if __name__ == "__main__":
    test_semantic_search() 