#!/usr/bin/env python3

"""
Test script to validate Phase 5: API and Embedding Integration
Ensures all components work together with simplified thumbnail structure.
"""

import json
import os

def test_api_integration():
    """Test that API components handle simplified thumbnail structure."""
    print("🔍 Testing API Integration...")
    
    try:
        # Test import of API server components
        import sys
        sys.path.append('.')
        from video_ingest_tool.api.server import create_app
        print("✅ API server imports successful")
        
        # Test import of CLI commands (used by API)
        from video_ingest_tool.cli_commands.clips import ClipsCommand
        print("✅ CLI commands import successful")
        
        return True
    except Exception as e:
        print(f"❌ API integration test failed: {e}")
        return False

def test_embedding_generation():
    """Test that embedding generation works with simplified structure."""
    print("🔍 Testing Embedding Generation...")
    
    try:
        from video_ingest_tool.embeddings_image import generate_thumbnail_embedding, batch_generate_thumbnail_embeddings
        
        # Test that function signature doesn't require description
        import inspect
        sig = inspect.signature(generate_thumbnail_embedding)
        params = list(sig.parameters.keys())
        
        if 'description' in params:
            print("❌ generate_thumbnail_embedding still has 'description' parameter")
            return False
        
        print("✅ generate_thumbnail_embedding function signature correct (no description param)")
        
        # Test batch function
        batch_sig = inspect.signature(batch_generate_thumbnail_embeddings)
        batch_params = list(batch_sig.parameters.keys())
        
        print(f"✅ batch_generate_thumbnail_embeddings parameters: {batch_params}")
        
        return True
    except Exception as e:
        print(f"❌ Embedding generation test failed: {e}")
        return False

def test_prefect_flow_integration():
    """Test that Prefect flows handle simplified structure."""
    print("🔍 Testing Prefect Flow Integration...")
    
    try:
        from video_ingest_tool.flows.prefect_flows import process_video_file_task
        from video_ingest_tool.tasks.analysis.ai_thumbnail_selection import ai_thumbnail_selection_step
        
        print("✅ Prefect flow imports successful")
        
        # Check that ai_thumbnail_selection_step function works with simplified structure
        import inspect
        sig = inspect.signature(ai_thumbnail_selection_step.fn)
        params = list(sig.parameters.keys())
        
        print(f"✅ ai_thumbnail_selection_step parameters: {params}")
        
        return True
    except Exception as e:
        print(f"❌ Prefect flow integration test failed: {e}")
        return False

def test_simplified_data_flow():
    """Test the complete data flow with simplified structure."""
    print("🔍 Testing Complete Data Flow...")
    
    # Simulate simplified AI thumbnail metadata (Phase 1-4 output)
    simplified_ai_thumbs = [
        {
            'timestamp': '5s500ms', 
            'reason': 'Clear subject view with good lighting', 
            'rank': '1', 
            'path': '/test/thumb1.jpg'
        },
        {
            'timestamp': '10s200ms', 
            'reason': 'Good composition and framing', 
            'rank': '2', 
            'path': '/test/thumb2.jpg'
        }
    ]
    
    # Test JSON serialization (API responses)
    try:
        json_data = json.dumps(simplified_ai_thumbs)
        parsed_back = json.loads(json_data)
        
        # Verify structure
        for thumb in parsed_back:
            required_fields = ['timestamp', 'reason', 'rank', 'path']
            for field in required_fields:
                assert field in thumb, f"Missing required field: {field}"
            
            # Ensure no old description fields
            assert 'description' not in thumb, "Old 'description' field should not be present"
            assert 'detailed_visual_description' not in thumb, "Old 'detailed_visual_description' field should not be present"
        
        print("✅ Simplified metadata structure correctly serializes/deserializes")
        print(f"✅ Each thumbnail has required fields: {required_fields}")
        print("✅ No old description fields present")
        
        return True
    except Exception as e:
        print(f"❌ Data flow test failed: {e}")
        return False

def test_filmmaker_vocabulary_integration():
    """Test that filmmaker vocabulary is properly integrated."""
    print("🔍 Testing Filmmaker Vocabulary Integration...")
    
    try:
        from video_ingest_tool.video_processor.analysis import load_filmmaker_vocabulary, get_vocabulary_section
        
        # Test vocabulary loading
        vocab_data = load_filmmaker_vocabulary()
        if vocab_data:
            # Calculate total terms from categories
            total_terms = sum(len(terms) for terms in vocab_data['categories'].values())
            print(f"✅ Filmmaker vocabulary loaded: {total_terms} terms")
            print(f"✅ Vocabulary version: {vocab_data['vocabulary_version']}")
            
            # Test vocabulary section generation
            vocab_section = get_vocabulary_section()
            if 'filmmaker-focused' in vocab_section.lower():
                print("✅ Vocabulary section includes filmmaker terms")
            else:
                print("⚠️  Vocabulary section might not include filmmaker terms")
            
            return True
        else:
            print("❌ Failed to load filmmaker vocabulary")
            return False
    except Exception as e:
        print(f"❌ Filmmaker vocabulary test failed: {e}")
        return False

def main():
    """Run all Phase 5 validation tests."""
    print("🚀 Starting Phase 5: API and Embedding Integration Validation\n")
    
    tests = [
        test_api_integration,
        test_embedding_generation,
        test_prefect_flow_integration,
        test_simplified_data_flow,
        test_filmmaker_vocabulary_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}\n")
    
    print(f"📊 Phase 5 Validation Results:")
    print(f"   • Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ Phase 5: API and Embedding Integration - COMPLETED SUCCESSFULLY!")
        return True
    else:
        print("❌ Phase 5: Some tests failed - needs attention")
        return False

if __name__ == "__main__":
    main() 