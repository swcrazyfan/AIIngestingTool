#!/usr/bin/env python3
"""
Comparison: Gemini API vs Vertex AI approaches for video analysis
"""

# ============================================================================
# CURRENT APPROACH: Direct Gemini API
# ============================================================================

def gemini_api_approach():
    """Using direct Gemini API with API key"""
    from google import genai
    from google.genai import types
    
    # Authentication: API Key
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    
    # Load video
    video_bytes = open(video_file_path, 'rb').read()
    
    # Generate content
    response = client.models.generate_content(
        model='models/gemini-2.0-flash',
        contents=types.Content(
            parts=[
                types.Part(
                    inline_data=types.Blob(data=video_bytes, mime_type='video/mp4')
                ),
                types.Part(text='Summarize this video.')
            ]
        )
    )
    return response.text

# ============================================================================
# VERTEX AI APPROACH: Google Cloud Credentials
# ============================================================================

def vertex_ai_approach():
    """Using Vertex AI with Google Cloud credentials"""
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    
    # Authentication: Google Cloud credentials (no API key needed)
    PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
    LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    
    # Load video
    video_bytes = open(video_file_path, 'rb').read()
    
    # Create video part
    video_part = Part.from_data(
        mime_type="video/mp4",
        data=video_bytes
    )
    
    # Initialize model
    model = GenerativeModel('gemini-2.0-flash')
    
    # Generate content
    response = model.generate_content([
        video_part, 
        "Summarize this video."
    ])
    return response.text

# ============================================================================
# KEY DIFFERENCES
# ============================================================================

"""
AUTHENTICATION:
- Gemini API: Requires GEMINI_API_KEY
- Vertex AI: Uses Google Cloud credentials (gcloud auth)

MODELS:
- Gemini API: models/gemini-2.0-flash  (with 'models/' prefix)
- Vertex AI: gemini-2.0-flash          (without 'models/' prefix)

SETUP:
- Gemini API: Just need API key
- Vertex AI: Need Google Cloud project, authentication, permissions

BENEFITS OF VERTEX AI:
- Better enterprise integration
- More sophisticated billing/quotas
- Better monitoring and logging
- Access to additional Google Cloud services
- More robust authentication (no API keys to manage)

POTENTIAL ISSUES:
- Same underlying Gemini models (so same video processing issues)
- More complex setup
- Requires Google Cloud project
""" 