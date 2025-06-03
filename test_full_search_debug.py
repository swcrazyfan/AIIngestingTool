#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from video_ingest_tool.search import VideoSearcher, format_search_results
from video_ingest_tool.cli_commands.search import SearchCommand
from video_ingest_tool.config.search_config import get_search_config

def test_full_search_pipeline():
    """Test the complete search pipeline to find where results get lost."""
    print("=== TESTING FULL SEARCH PIPELINE ===")
    
    query = "Green Screen"
    search_type = "semantic"
    limit = 3
    
    print(f"Testing query: '{query}', type: {search_type}, limit: {limit}")
    
    # Step 1: Test VideoSearcher directly
    print("\\n1. Testing VideoSearcher.search() directly:")
    searcher = VideoSearcher()
    try:
        raw_results = searcher.search(query=query, search_type=search_type, match_count=limit)
        print(f"   VideoSearcher returned: {len(raw_results)} results")
        if raw_results:
            print(f"   First result keys: {list(raw_results[0].keys())}")
            print(f"   First result sample: {raw_results[0].get('file_name')} -> score: {raw_results[0].get('combined_similarity_score')}")
    except Exception as e:
        print(f"   VideoSearcher failed: {e}")
        return
    
    # Step 2: Test format_search_results
    print("\\n2. Testing format_search_results():")
    try:
        formatted_results = format_search_results(raw_results, search_type, show_scores=True)
        print(f"   format_search_results returned: {len(formatted_results)} results")
        if formatted_results:
            print(f"   First formatted result keys: {list(formatted_results[0].keys())}")
            print(f"   First formatted result: {formatted_results[0].get('file_name')} -> score: {formatted_results[0].get('combined_similarity')}")
    except Exception as e:
        print(f"   format_search_results failed: {e}")
        return
    
    # Step 3: Test SearchCommand
    print("\\n3. Testing SearchCommand.search():")
    command = SearchCommand()
    try:
        command_result = command.search(query=query, search_type=search_type, limit=limit)
        print(f"   SearchCommand success: {command_result.get('success')}")
        if command_result.get('success'):
            data = command_result.get('data', {})
            results = data.get('results', [])
            print(f"   SearchCommand returned: {len(results)} results")
            print(f"   Data keys: {list(data.keys())}")
            if results:
                print(f"   First command result: {results[0].get('file_name')} -> score: {results[0].get('combined_similarity')}")
        else:
            print(f"   SearchCommand error: {command_result.get('error')}")
    except Exception as e:
        print(f"   SearchCommand failed: {e}")
    
    # Step 4: Check if results have required fields
    print("\\n4. Checking result field mapping:")
    if raw_results:
        first_result = raw_results[0]
        print(f"   Raw result fields: {list(first_result.keys())}")
        print("   Field values:")
        for key, value in first_result.items():
            if isinstance(value, (int, float, str)) and len(str(value)) < 100:
                print(f"     {key}: {value}")

if __name__ == "__main__":
    test_full_search_pipeline() 