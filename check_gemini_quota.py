#!/usr/bin/env python3
"""
Check Google Gemini API file upload quota and storage usage.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from google import genai
    print("✓ Google GenAI library available")
except ImportError:
    print("✗ Google GenAI library not available")
    exit(1)

def check_quota_and_files():
    """Check current file upload quota and list uploaded files."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return
    
    print(f"✓ Using API key: {api_key[:10]}...")
    
    # Initialize client
    try:
        client = genai.Client(api_key=api_key)
        print("✓ Successfully initialized Gemini client")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return
    
    # List all uploaded files
    try:
        print("\n📁 Checking uploaded files...")
        files = list(client.files.list())
        
        if not files:
            print("✓ No files currently uploaded - quota should be clear")
            return
        
        print(f"📊 Found {len(files)} uploaded files:")
        
        total_size = 0
        for i, file in enumerate(files, 1):
            # Get file details
            try:
                file_details = client.files.get(name=file.name)
                size_mb = getattr(file_details, 'size_bytes', 0) / (1024 * 1024) if hasattr(file_details, 'size_bytes') else 0
                total_size += size_mb
                
                print(f"  {i}. {file.name}")
                print(f"     URI: {file.uri}")
                print(f"     State: {getattr(file, 'state', 'Unknown')}")
                print(f"     Size: {size_mb:.2f} MB")
                print(f"     Created: {getattr(file, 'create_time', 'Unknown')}")
                print()
                
            except Exception as e:
                print(f"  {i}. {file.name} - Error getting details: {e}")
        
        print(f"📈 Total storage used: {total_size:.2f} MB")
        
        # Check if we should clean up old files
        if len(files) > 10 or total_size > 100:
            print("\n⚠️  You have many files or large storage usage.")
            print("   This could be causing quota issues.")
            
            response = input("\n🗑️  Delete all uploaded files to clear quota? (y/N): ")
            if response.lower() in ['y', 'yes']:
                delete_all_files(client, files)
        
    except Exception as e:
        print(f"✗ Error listing files: {e}")
        print(f"   This might indicate quota or permission issues")

def delete_all_files(client, files):
    """Delete all uploaded files to clear quota."""
    print("\n🗑️  Deleting uploaded files...")
    
    for file in files:
        try:
            client.files.delete(name=file.name)
            print(f"✓ Deleted: {file.name}")
        except Exception as e:
            print(f"✗ Failed to delete {file.name}: {e}")
    
    print("✅ File cleanup completed!")

if __name__ == "__main__":
    print("🔍 Checking Google Gemini API quota and file usage...\n")
    check_quota_and_files() 