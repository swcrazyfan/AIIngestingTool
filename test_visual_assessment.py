#!/usr/bin/env python3
import base64
import requests
import json

def test_visual_analysis():
    """Test visual gender identification on a single frame"""
    
    # Read one of the frames
    with open('MVI_0484_best_3_frames/frame_01_0.000s_START_m0.000_s76.jpg', 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Simple visual assessment prompt
    messages = [
        {
            'role': 'system',
            'content': 'You are examining a frame from a video. Based ONLY on visual appearance, describe what you see. Focus on: apparent age, physical appearance, clothing, hair, and any visual cues about the person. Be factual and descriptive.'
        },
        {
            'role': 'user',
            'content': [
                {
                    'type': 'text',
                    'text': 'Look at this person and describe their visual appearance. What do you see in terms of physical characteristics, age, hair, clothing, etc.? Be specific and factual.'
                },
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:image/jpeg;base64,{image_data}'
                    }
                }
            ]
        }
    ]
    
    payload = {
        'model': 'meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8',
        'messages': messages,
        'max_tokens': 500,
        'temperature': 0.1
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer 2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP'
    }
    
    response = requests.post('https://api.deepinfra.com/v1/openai/chat/completions', 
                           headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print('VISUAL ASSESSMENT:')
        print(result['choices'][0]['message']['content'])
        print()
        print('TOKEN USAGE:', result.get('usage', {}))
    else:
        print(f'Error: {response.status_code} - {response.text}')

if __name__ == "__main__":
    test_visual_analysis() 