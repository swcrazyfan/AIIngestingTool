#!/usr/bin/env python3
"""
Test simple prompt to Gemini model.
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

def test_simple_prompt():
    """Test a very simple prompt to the model."""
    
    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("✗ No GEMINI_API_KEY found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Get model from environment
    model_name = os.getenv('VIDEO_MODEL', 'models/gemini-2.5-flash-preview-05-20')
    print(f"✓ Using model: {model_name}")
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        print("✓ Client initialized successfully")
        
        # Send a very simple prompt
        print("Sending simple prompt...")
        response = client.models.generate_content(
            model=model_name,
            contents="Hello! Can you say hello back?"
        )
        
        print("✅ Simple prompt successful!")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Simple prompt failed: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response}")
            if hasattr(e.response, 'text'):
                print(f"  Response text: {e.response.text}")
            if hasattr(e.response, 'status_code'):
                print(f"  Status code: {e.response.status_code}")
        return False

if __name__ == "__main__":
    print("Testing simple prompt to Gemini model...")
    success = test_simple_prompt()
    if success:
        print("🎉 Basic text prompts are working!")
    else:
        print("💔 Even simple prompts are failing!") 