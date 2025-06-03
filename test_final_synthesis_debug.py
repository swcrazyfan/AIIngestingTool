#!/usr/bin/env python3
"""
Debug script to test final synthesis with explicit male visual assessment.
This tests if the final synthesis properly respects visual batch conclusions.
"""

import requests

def test_final_synthesis_with_male_visual():
    """Test final synthesis with explicit male visual identification."""
    
    print("🔍 FINAL SYNTHESIS GENDER DEBUG")
    print("=" * 60)
    print("🎯 Goal: Test if final synthesis respects explicit male visual assessment")
    
    # Mock audio analysis (without gender assessment)
    audio_analysis = """## AUDIO TRANSCRIPTION
[00:00:00.0] - "Pay no attention to the man behind the curtain. Go before I lose my temper."
[00:00:02.2] - "The great and powerful Oz has spoken."
[00:00:03.2] - "Yeah."
[00:00:03.8] - "I think so."

## ACOUSTIC & VOCAL ANALYSIS
- Emotional tone: Intense, commanding, with urgency and frustration
- Speaking style: Forceful and theatrical delivery
- Number of speakers: Single speaker throughout
- Vocal dynamics: Rapid pace, high volume, dramatic emphasis
- Audio quality: Clear studio recording, minimal background noise
- Background/environment: Controlled studio acoustics"""

    # Visual analysis that explicitly identifies MALE (from our debug test)
    visual_analysis = """=== VISUAL BATCH 1 ANALYSIS ===
Based on the facial features, hair, and overall appearance, the person appears to be male. The assessment is made considering the following:
- Facial structure: The jawline and facial contours appear masculine.
- Hair: The person has medium-length, dark hair that is styled in a way that is commonly associated with males.
- Overall appearance: The clothing and body structure are consistent with a male presentation.

The visual gender assessment confirms the person is male based on observable facial features and overall appearance.

=== VISUAL BATCH 2 ANALYSIS ===
The person continues to display the same masculine characteristics observed in the first batch. The facial features, including the angular jawline and masculine bone structure, remain consistent across all frames. Based on visual evidence, this is clearly a male individual performing in front of the green screen."""

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""CRITICAL TEST: You are given visual analysis that clearly states a person is MALE. Your job is to create a final report that respects this assessment.

=== AUDIO ANALYSIS ===
{audio_analysis}

=== VISUAL ANALYSIS ===
{visual_analysis}

INSTRUCTIONS: The visual analysis clearly states the person is MALE multiple times. Create a final report that correctly identifies the person as male based on this visual evidence.

QUESTION: What is the gender of the person in this video based on the visual analysis provided?"""
                }
            ]
        }
    ]

    payload = {
        "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer 2bpYzmxkqymkFBmkqmeCERgeoKKV3WtP"
    }
    
    try:
        response = requests.post("https://api.deepinfra.com/v1/openai/chat/completions", 
                               headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'error' in result:
            raise RuntimeError(f"API error: {result['error']}")
        
        analysis = result["choices"][0]["message"]["content"]
        
        print("\n" + "=" * 60)
        print("🔍 FINAL SYNTHESIS WITH EXPLICIT MALE ASSESSMENT")
        print("=" * 60)
        print(analysis)
        print("=" * 60)
        
        # Check if it properly identifies as male
        if "male" in analysis.lower() and "female" not in analysis.lower():
            print("\n✅ SUCCESS: Final synthesis correctly identified as MALE")
        elif "female" in analysis.lower():
            print("\n❌ FAILURE: Final synthesis incorrectly identified as FEMALE despite explicit male visual assessment")
        else:
            print("\n⚠️  UNCLEAR: Gender identification unclear in final synthesis")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")

if __name__ == "__main__":
    test_final_synthesis_with_male_visual() 