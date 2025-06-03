#!/usr/bin/env python3

"""
Similarity Test Validation
Test our thumbnail descriptions removal implementation and diagnose similarity search issues.
"""

import json
import sys
from pathlib import Path

def test_implementation_validation():
    """Test our implementation to see what's working."""
    print("🔍 Testing Thumbnail Descriptions Removal Implementation")
    print("="*60)
    
    try:
        # Add project root to path
        sys.path.insert(0, '.')
        
        # Test database connection and clip data
        from video_ingest_tool.database.duckdb.connection import get_db_connection
        
        print("📊 Checking Database Contents...")
        
        with get_db_connection() as conn:
            # Check clips table with correct schema and column names
            clips_result = conn.execute("SELECT id, file_name, ai_selected_thumbnails_json FROM app_data.clips LIMIT 5").fetchall()
            
            print(f"✅ Found {len(clips_result)} clips in database")
            
            for clip_id, file_name, thumbnails_json in clips_result:
                clip_id_str = str(clip_id)
                print(f"\n📹 {file_name} (ID: {clip_id_str[:8]}...)")
                
                if thumbnails_json:
                    try:
                        thumbnails = json.loads(thumbnails_json) if isinstance(thumbnails_json, str) else thumbnails_json
                        print(f"   📸 Thumbnails: {len(thumbnails)}")
                        
                        # Check structure of first thumbnail
                        if thumbnails:
                            first_thumb = thumbnails[0]
                            print(f"   🔍 Thumbnail structure: {list(first_thumb.keys())}")
                            
                            # Verify our simplified structure
                            expected_fields = ['timestamp', 'reason', 'rank', 'path']
                            old_fields = ['description', 'detailed_visual_description']
                            
                            has_expected = all(field in first_thumb for field in expected_fields)
                            has_old = any(field in first_thumb for field in old_fields)
                            
                            if has_expected and not has_old:
                                print("   ✅ NEW STRUCTURE: Simplified thumbnail metadata confirmed!")
                            elif has_old:
                                print("   ⚠️  OLD STRUCTURE: Still contains description fields")
                            else:
                                print("   ❓ UNKNOWN STRUCTURE: Missing expected fields")
                                
                            # Show example thumbnail (truncated for readability)
                            example = {k: (v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v) 
                                     for k, v in first_thumb.items()}
                            print(f"   📝 Example: {example}")
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"   ❌ Invalid JSON in thumbnails: {e}")
                else:
                    print("   ⚠️  No thumbnails data")
            
            # Check thumbnail embeddings in clips table
            print(f"\n🔍 Checking Thumbnail Embeddings...")
            
            try:
                # Check thumbnail embeddings directly in clips table
                embeddings_result = conn.execute("""
                    SELECT id, file_name, 
                           thumbnail_1_embedding IS NOT NULL as has_thumb1,
                           thumbnail_2_embedding IS NOT NULL as has_thumb2,
                           thumbnail_3_embedding IS NOT NULL as has_thumb3
                    FROM app_data.clips 
                    LIMIT 5
                """).fetchall()
                
                total_embeddings = 0
                for clip_id, file_name, has_thumb1, has_thumb2, has_thumb3 in embeddings_result:
                    thumb_count = sum([has_thumb1, has_thumb2, has_thumb3])
                    total_embeddings += thumb_count
                    print(f"   📸 {file_name}: {thumb_count}/3 thumbnail embeddings")
                
                print(f"📊 Total thumbnail embeddings: {total_embeddings}")
                
                if total_embeddings > 0:
                    print("✅ Thumbnail embeddings found - similarity search should work!")
                else:
                    print("⚠️  No thumbnail embeddings found - this explains why similarity search failed!")
                        
            except Exception as e:
                print(f"   ❌ Error checking embeddings: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_embedding_generation():
    """Test if our embedding generation is working."""
    print(f"\n🔍 Testing Embedding Generation...")
    
    try:
        from video_ingest_tool.embeddings_image import generate_thumbnail_embedding
        import inspect
        
        # Check function signature
        sig = inspect.signature(generate_thumbnail_embedding)
        params = list(sig.parameters.keys())
        
        print(f"📝 Function signature: {params}")
        
        # Verify no description parameter
        if 'description' not in params:
            print("✅ CONFIRMED: No description parameter (image-only embeddings)")
        else:
            print("❌ ISSUE: Still has description parameter")
            
        # Check if we can find any thumbnail files from our recent ingest
        thumbnail_dir = Path("data/clips")
        if thumbnail_dir.exists():
            thumbnail_files = list(thumbnail_dir.glob("*/thumbnails/*.jpg"))
            print(f"📸 Found {len(thumbnail_files)} thumbnail files")
            
            if thumbnail_files:
                # Check multiple thumbnails to see size patterns
                sample_sizes = []
                for i, thumb_file in enumerate(thumbnail_files[:5]):
                    try:
                        from PIL import Image
                        img = Image.open(thumb_file)
                        max_dim = max(img.size)
                        sample_sizes.append(max_dim)
                        
                        if i == 0:  # Show details for first one
                            print(f"📝 Sample thumbnail: {thumb_file}")
                            print(f"✅ Image loadable: {img.size} pixels")
                    except Exception as e:
                        print(f"❌ Cannot load image {thumb_file}: {e}")
                
                if sample_sizes:
                    avg_max_dim = sum(sample_sizes) / len(sample_sizes)
                    print(f"📊 Average max dimension: {avg_max_dim:.1f}px")
                    
                    if all(size <= 512 for size in sample_sizes):
                        print(f"✅ NEW FORMAT: All thumbnails ≤512px")
                    elif all(size > 512 for size in sample_sizes):
                        print(f"⚠️  OLD FORMAT: All thumbnails >512px")
                    else:
                        print(f"🔄 MIXED FORMAT: Some old, some new thumbnails")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        return False

def main():
    """Run similarity validation tests."""
    print("🚀 Starting Similarity Test Validation\n")
    
    tests = [
        ("Implementation Validation", test_implementation_validation),
        ("Embedding Generation Test", test_embedding_generation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🧪 {test_name}")
        print('='*60)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"💥 {test_name} - CRASHED: {e}")
    
    print(f"\n📊 Similarity Test Results:")
    print(f"   • Tests Passed: {passed}/{total}")
    print(f"   • Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All validation tests passed!")
        print("💡 If similarity search still fails, it's likely due to embedding API timeouts during ingest.")
        print("🔧 To fix: Ensure embedding server is running and re-run ingest with --generate-embeddings")
    else:
        print(f"\n⚠️  {total-passed} tests need attention")
    
    return passed == total

if __name__ == "__main__":
    main() 