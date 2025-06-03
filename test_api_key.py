#!/usr/bin/env python3
"""
Test Gemini API key authentication.
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

def test_api_key():
    """Test if the API key works with basic authentication."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        print("✓ Client initialized successfully")
        
        # Try to list models (basic API test)
        print("Testing basic API call...")
        models = client.models.list()
        
        # Print available models
        print("✓ API authentication successful!")
        print("Available models:")
        for model in models:
            if hasattr(model, 'name'):
                print(f"  - {model.name}")
            else:
                print(f"  - {model}")
        
        return True
        
    except Exception as e:
        print(f"✗ API authentication failed: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response}")
            if hasattr(e.response, 'text'):
                print(f"  Response text: {e.response.text}")
        return False

if __name__ == "__main__":
    print("Testing Gemini API key authentication...")
    success = test_api_key()
    if success:
        print("✅ API key is working!")
    else:
        print("❌ API key test failed!") 