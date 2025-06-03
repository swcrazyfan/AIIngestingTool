#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

from video_ingest_tool.search import VideoSearcher, format_search_results
from video_ingest_tool.cli_commands.search import SearchCommand
# from video_ingest_tool.config.search_config import get_search_config # Not directly used in test logic

def run_search_test(search_type: str, query: str = "Green Screen", limit: int = 3):
    """Runs the full search pipeline test for a given search type."""
    print(f"\n=== TESTING FULL SEARCH PIPELINE FOR TYPE: {search_type.upper()} ===")
    print(f"Testing query: '{query}', type: {search_type}, limit: {limit}")
    
    # Step 1: Test VideoSearcher directly
    print("\n1. Testing VideoSearcher.search() directly:")
    searcher = VideoSearcher()
    raw_results = [] # Initialize raw_results
    try:
        raw_results = searcher.search(query=query, search_type=search_type, match_count=limit)
        print(f"   VideoSearcher returned: {len(raw_results)} results")
        if raw_results:
            print(f"   First result keys: {list(raw_results[0].keys())}")
            # Display score based on search type
            first_result_score = "N/A"
            if search_type == "semantic" and 'combined_similarity_score' in raw_results[0]:
                first_result_score = raw_results[0]['combined_similarity_score']
            elif search_type == "hybrid" and 'rrf_score' in raw_results[0]: # Corrected: was 'similarity_score'
                first_result_score = raw_results[0]['rrf_score']
            elif search_type == "fulltext" and 'fts_rank' in raw_results[0]:
                first_result_score = raw_results[0]['fts_rank']
            print(f"   First result sample: {raw_results[0].get('file_name')} -> score/rank: {first_result_score}")
    except Exception as e:
        print(f"   VideoSearcher failed: {e}")
        # Don't return here, allow other steps to be attempted if desired, or they will fail gracefully
    
    # Step 2: Test format_search_results
    print("\n2. Testing format_search_results():")
    formatted_results = [] # Initialize formatted_results
    if not raw_results: # Skip if previous step failed to produce results
        print("   Skipping format_search_results as no raw results were obtained.")
    else:
        try:
            formatted_results = format_search_results(raw_results, search_type, show_scores=True)
            print(f"   format_search_results returned: {len(formatted_results)} results")
            if formatted_results:
                print(f"   First formatted result keys: {list(formatted_results[0].keys())}")
                # Display score from formatted results based on search type
                first_formatted_score = "N/A"
                if search_type == "semantic" and 'combined_similarity' in formatted_results[0]:
                    first_formatted_score = formatted_results[0]['combined_similarity']
                elif search_type == "hybrid" and 'relevance_score' in formatted_results[0]: # formatted name
                    first_formatted_score = formatted_results[0]['relevance_score']
                elif search_type == "fulltext" and 'fts_rank' in formatted_results[0]:
                    first_formatted_score = formatted_results[0]['fts_rank']
                print(f"   First formatted result: {formatted_results[0].get('file_name')} -> score/rank: {first_formatted_score}")
        except Exception as e:
            print(f"   format_search_results failed: {e}")
    
    # Step 3: Test SearchCommand
    print("\n3. Testing SearchCommand.search():")
    command = SearchCommand()
    try:
        # Note: SearchCommand.execute uses 'search_type' as string, consistent with CLI
        command_result = command.search(query=query, search_type=search_type, limit=limit) # search_type is 'action' in SearchCommand.execute
        
        # The SearchCommand().search() method is a convenience wrapper.
        # Its internal 'action' parameter for execute() is 'search'.
        # The 'search_type' param here is passed to the underlying VideoSearcher.
        
        print(f"   SearchCommand success: {command_result.get('success')}")
        if command_result.get('success'):
            data = command_result.get('data', {})
            results_from_command = data.get('results', []) # results are already formatted by SearchCommand
            print(f"   SearchCommand returned: {len(results_from_command)} results")
            print(f"   Data keys: {list(data.keys())}")
            if results_from_command:
                # Display score from command results based on search type
                first_command_score = "N/A"
                if search_type == "semantic" and 'combined_similarity' in results_from_command[0]:
                    first_command_score = results_from_command[0]['combined_similarity']
                elif search_type == "hybrid" and 'relevance_score' in results_from_command[0]: # formatted name
                    first_command_score = results_from_command[0]['relevance_score']
                elif search_type == "fulltext" and 'fts_rank' in results_from_command[0]:
                    first_command_score = results_from_command[0]['fts_rank']
                print(f"   First command result: {results_from_command[0].get('file_name')} -> score/rank: {first_command_score}")
        else:
            print(f"   SearchCommand error: {command_result.get('error')}")
    except Exception as e:
        print(f"   SearchCommand failed: {e}")
    
    # Step 4: Check if results have required fields (using raw_results for original field names)
    print("\n4. Checking raw result field mapping (if available):")
    if raw_results:
        first_result = raw_results[0]
        print(f"   Raw result fields: {list(first_result.keys())}")
        print("   Field values:")
        for key, value in first_result.items():
            # Only print easily displayable values
            if isinstance(value, (int, float, str)) and len(str(value)) < 100:
                print(f"     {key}: {value}")
            elif isinstance(value, list) and not value: # empty list
                 print(f"     {key}: []")
            elif value is None:
                 print(f"     {key}: None")

if __name__ == "__main__":
    run_search_test(search_type="semantic")
    run_search_test(search_type="hybrid")
    run_search_test(search_type="fulltext", query="curtain") # Use a different query for fulltext to get results
    # Example for transcript search (if you want to add it)
    # run_search_test(search_type="transcripts", query="specific transcript phrase") 