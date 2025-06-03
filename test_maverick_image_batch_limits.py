#!/usr/bin/env python3
"""
Test script to determine the maximum number of images the Maverick API can handle in a single batch.
Tests with 5, 10, 15, and 20 images to find the optimal batch size.
"""

import os
import sys
import json
import base64
import time
import tempfile
import requests
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

# Import frame extraction to get test images
from extract_best_10_frames import extract_best_frames_from_video

class MaverickBatchTester:
    """Test the Maverick API with different image batch sizes."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
        self.api_url = "https://api.deepinfra.com/v1/openai/chat/completions"
        
    def encode_image_base64(self, image_path: str) -> str:
        """Encode image to base64 string."""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to encode {image_path}: {e}")
    
    def extract_test_images(self, video_path: str, num_images: int) -> List[str]:
        """Extract test images from a video file."""
        print(f"📹 Extracting {num_images} test images from video...")
        
        temp_dir = tempfile.mkdtemp(prefix="maverick_batch_test_")
        frames_dir = os.path.join(temp_dir, "test_frames")
        
        try:
            # Extract frames using our frame extractor
            frame_candidates = extract_best_frames_from_video(video_path, num_images, frames_dir)
            
            if not frame_candidates:
                raise RuntimeError("Failed to extract test frames")
            
            # Get frame files
            frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])
            frame_paths = [os.path.join(frames_dir, f) for f in frame_files[:num_images]]
            
            print(f"✅ Extracted {len(frame_paths)} test images")
            return frame_paths
            
        except Exception as e:
            print(f"❌ Failed to extract test images: {e}")
            return []
    
    def test_batch_size(self, image_paths: List[str], batch_size: int) -> Tuple[bool, dict]:
        """Test a specific batch size with the Maverick API."""
        
        print(f"\n🧪 Testing batch size: {batch_size} images")
        print(f"📁 Using images: {[os.path.basename(p) for p in image_paths[:batch_size]]}")
        
        start_time = time.time()
        
        # Calculate total image data size
        total_size = sum(os.path.getsize(path) for path in image_paths[:batch_size])
        total_size_mb = total_size / (1024 * 1024)
        
        print(f"📊 Total image data: {total_size_mb:.2f} MB")
        
        messages = [{
            "role": "system",
            "content": f"""You are testing image batch processing capabilities. 
            
You will receive {batch_size} images in this request. Your task is to:
1. Confirm you can see all {batch_size} images
2. Briefly describe what you see in each image (1-2 sentences per image)
3. Provide a summary of the overall content

Keep your response concise but demonstrate you can process all images successfully."""
        }]
        
        # Create user message with all images
        user_content = [{
            "type": "text",
            "text": f"BATCH TEST: Process these {batch_size} images and confirm you can see all of them. Briefly describe each image and provide a summary."
        }]
        
        # Add all images to the request
        for i, image_path in enumerate(image_paths[:batch_size], 1):
            try:
                image_base64 = self.encode_image_base64(image_path)
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                })
                print(f"  ✓ Added image {i}: {os.path.basename(image_path)}")
            except Exception as e:
                print(f"  ❌ Failed to encode image {i}: {e}")
                return False, {"error": f"Failed to encode image {i}: {e}"}
        
        messages.append({"role": "user", "content": user_content})
        
        # Make API call
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            print(f"🚀 Sending request to Maverick API...")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=300)  # 5 min timeout
            
            request_time = time.time() - start_time
            
            if response.status_code != 200:
                error_msg = f"API Error {response.status_code}: {response.text}"
                print(f"❌ {error_msg}")
                return False, {
                    "error": error_msg,
                    "status_code": response.status_code,
                    "request_time": request_time,
                    "total_size_mb": total_size_mb
                }
            
            result = response.json()
            
            if 'error' in result:
                error_msg = f"API Error: {result['error']}"
                print(f"❌ {error_msg}")
                return False, {
                    "error": error_msg,
                    "request_time": request_time,
                    "total_size_mb": total_size_mb
                }
            
            # Success!
            usage = result.get('usage', {})
            content = result['choices'][0]['message']['content']
            
            print(f"✅ SUCCESS! Batch size {batch_size} completed")
            print(f"⏱️  Request time: {request_time:.2f}s")
            print(f"🔢 Token usage: {usage}")
            print(f"📝 Response preview: {content[:200]}...")
            
            return True, {
                "success": True,
                "request_time": request_time,
                "total_size_mb": total_size_mb,
                "token_usage": usage,
                "response_length": len(content),
                "content_preview": content[:500]
            }
            
        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after 5 minutes"
            print(f"⏰ {error_msg}")
            return False, {
                "error": error_msg,
                "request_time": time.time() - start_time,
                "total_size_mb": total_size_mb
            }
        except Exception as e:
            error_msg = f"Request failed: {e}"
            print(f"❌ {error_msg}")
            return False, {
                "error": error_msg,
                "request_time": time.time() - start_time,
                "total_size_mb": total_size_mb
            }
    
    def run_batch_tests(self, video_path: str, test_sizes: List[int] = [5, 10, 15, 20]) -> dict:
        """Run batch tests with different sizes."""
        
        print("🧪 MAVERICK API BATCH SIZE TESTING")
        print("=" * 60)
        print(f"🤖 Model: {self.model}")
        print(f"📹 Test video: {os.path.basename(video_path)}")
        print(f"📊 Testing batch sizes: {test_sizes}")
        print()
        
        # Extract enough test images for the largest batch
        max_images = max(test_sizes)
        test_images = self.extract_test_images(video_path, max_images)
        
        if len(test_images) < max_images:
            print(f"❌ Could only extract {len(test_images)} images, need {max_images}")
            return {"error": "Insufficient test images"}
        
        results = {}
        
        for batch_size in test_sizes:
            try:
                success, result_data = self.test_batch_size(test_images, batch_size)
                results[batch_size] = result_data
                
                if success:
                    print(f"✅ Batch size {batch_size}: SUCCESS")
                else:
                    print(f"❌ Batch size {batch_size}: FAILED")
                    # Stop testing larger sizes if this one failed
                    print(f"⚠️  Stopping tests - {batch_size} images failed, larger batches likely won't work")
                    break
                
                # Brief pause between tests
                if batch_size != test_sizes[-1]:
                    print("⏱️  Brief pause between tests...")
                    time.sleep(3)
                    
            except Exception as e:
                print(f"❌ Batch size {batch_size}: Exception - {e}")
                results[batch_size] = {"error": str(e)}
                break
        
        # Cleanup test images
        if test_images:
            try:
                import shutil
                temp_dir = os.path.dirname(os.path.dirname(test_images[0]))
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"\n🧹 Cleaned up test images")
            except:
                pass
        
        return results
    
    def print_summary(self, results: dict):
        """Print a summary of the test results."""
        
        print("\n" + "=" * 60)
        print("📊 BATCH TEST SUMMARY")
        print("=" * 60)
        
        successful_batches = []
        failed_batches = []
        
        for batch_size, result in results.items():
            if result.get("success", False):
                successful_batches.append(batch_size)
                print(f"✅ {batch_size:2d} images: SUCCESS ({result['request_time']:.1f}s, {result['total_size_mb']:.1f}MB)")
            else:
                failed_batches.append(batch_size)
                error = result.get("error", "Unknown error")[:50]
                print(f"❌ {batch_size:2d} images: FAILED - {error}")
        
        print("\n📈 RECOMMENDATIONS:")
        
        if successful_batches:
            max_successful = max(successful_batches)
            print(f"✅ Maximum batch size: {max_successful} images")
            print(f"🎯 Recommended batch size: {max_successful} images")
            
            # Performance analysis
            if len(successful_batches) > 1:
                times = [results[size]['request_time'] for size in successful_batches]
                sizes = [results[size]['total_size_mb'] for size in successful_batches]
                
                fastest_idx = times.index(min(times))
                fastest_size = successful_batches[fastest_idx]
                
                print(f"⚡ Fastest batch size: {fastest_size} images ({times[fastest_idx]:.1f}s)")
                print(f"📊 Performance scaling: {min(times):.1f}s - {max(times):.1f}s")
        else:
            print("❌ No batch sizes succeeded - API may have strict limits or other issues")
        
        print("\n🔧 OPTIMIZATION SUGGESTIONS:")
        if successful_batches and max(successful_batches) >= 15:
            print("✅ Large batches (15+) work - can use high batch sizes for efficiency")
        elif successful_batches and max(successful_batches) >= 10:
            print("⚠️  Medium batches (10-14) work - use moderate batch sizes")
        elif successful_batches and max(successful_batches) >= 5:
            print("⚠️  Only small batches (5-9) work - use conservative batch sizes")
        else:
            print("❌ Very limited batching capability - may need individual image processing")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test Maverick API image batch processing limits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python test_maverick_image_batch_limits.py video.mp4                    # Test default sizes (5,10,15,20)
  python test_maverick_image_batch_limits.py video.mp4 --sizes 3 6 9 12  # Test custom sizes
  python test_maverick_image_batch_limits.py video.mp4 --max-size 25     # Test up to 25 images
        ''')
    
    parser.add_argument('video_path', help='Path to test video file')
    parser.add_argument('--sizes', nargs='+', type=int, default=[5, 10, 15, 20],
                        help='Batch sizes to test (default: 5 10 15 20)')
    parser.add_argument('--max-size', type=int,
                        help='Test sizes 5, 10, 15, 20, 25, ... up to this max')
    parser.add_argument('--api-key', default="2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP",
                        help='DeepInfra API key')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.video_path):
        print(f"❌ Video file not found: {args.video_path}")
        return 1
    
    # Determine test sizes
    if args.max_size:
        test_sizes = list(range(5, args.max_size + 1, 5))
    else:
        test_sizes = args.sizes
    
    print(f"🎯 Will test batch sizes: {test_sizes}")
    
    try:
        # Create tester
        tester = MaverickBatchTester(args.api_key)
        
        # Run tests
        results = tester.run_batch_tests(args.video_path, test_sizes)
        
        # Print summary
        tester.print_summary(results)
        
        # Save results to file
        results_file = f"maverick_batch_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "test_info": {
                    "video_path": args.video_path,
                    "test_sizes": test_sizes,
                    "model": tester.model,
                    "timestamp": datetime.now().isoformat()
                },
                "results": results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 