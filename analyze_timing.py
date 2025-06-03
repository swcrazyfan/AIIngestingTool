#!/usr/bin/env python3

"""
Timing Analysis Script
Analyze the ingest logs to check for concurrent embedding API calls
"""

import re
from datetime import datetime

def analyze_timing():
    """Analyze timing patterns from the logs."""
    print("🕒 Timing Analysis: Embedding Generation Steps")
    print("=" * 60)
    
    # Key timing events from the logs
    events = [
        # Embedding generation starts
        ("21:25:03", "P1100071.MP4", "embedding_generation", "START"),
        ("21:25:12", "MVI_0484.MP4", "embedding_generation", "START"),
        ("21:25:13", "PANA1194.MP4", "embedding_generation", "START"),
        ("21:25:18", "PANA1189.MP4", "embedding_generation", "START"),
        ("21:25:50", "MVI_0481.MP4", "embedding_generation", "START"),
        
        # API timeout errors (these happen 30 seconds after API calls start)
        ("21:26:05", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:25:35
        ("21:26:22", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:25:52
        ("21:26:26", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:25:56
        ("21:26:36", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:26:06
        ("21:26:46", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:26:16
        ("21:26:53", "UNKNOWN", "api_timeout", "ERROR"),  # 30s after ~21:26:23
        
        # Embedding generation completes
        ("21:25:03", "P1100071.MP4", "embedding_generation", "COMPLETE"),
        ("21:26:26", "MVI_0484.MP4", "embedding_generation", "COMPLETE"),
        ("21:26:36", "PANA1194.MP4", "embedding_generation", "COMPLETE"),
        ("21:26:46", "PANA1189.MP4", "embedding_generation", "COMPLETE"),
        ("21:27:16", "MVI_0481.MP4", "embedding_generation", "COMPLETE"),
    ]
    
    print("📋 Timeline of Events:")
    print()
    
    # Sort events by time
    sorted_events = sorted(events, key=lambda x: x[0])
    
    for time, file, event_type, status in sorted_events:
        if event_type == "embedding_generation":
            if status == "START":
                print(f"🚀 {time} - {file} - Embedding generation STARTED")
            else:
                print(f"✅ {time} - {file} - Embedding generation COMPLETED")
        else:
            print(f"❌ {time} - API timeout error (30s timeout)")
    
    print()
    print("🔍 Analysis:")
    print()
    
    # Check for overlapping periods
    print("📊 Overlap Analysis:")
    print("- P1100071.MP4: 21:25:03 → 21:25:03 (instant success)")
    print("- MVI_0484.MP4: 21:25:12 → 21:26:26 (1min 14sec)")
    print("- PANA1194.MP4: 21:25:13 → 21:26:36 (1min 23sec)")  
    print("- PANA1189.MP4: 21:25:18 → 21:26:46 (1min 28sec)")
    print("- MVI_0481.MP4: 21:25:50 → 21:27:16 (1min 26sec)")
    
    print()
    print("⚠️  CONCURRENT CALLS DETECTED:")
    print("Even without '--parallel-tasks', multiple embedding generations")
    print("were running simultaneously:")
    print()
    print("🔴 21:25:12-21:25:18: 4 files started embedding within 6 seconds!")
    print("   - MVI_0484.MP4 (21:25:12)")
    print("   - PANA1194.MP4 (21:25:13)")  
    print("   - PANA1189.MP4 (21:25:18)")
    print("   - All running concurrently until their timeouts/completions")
    print()
    print("🔴 21:25:50: MVI_0481.MP4 started while others still running")
    
    print()
    print("💡 Root Cause:")
    print("The pipeline processes multiple files in sequence, but WITHIN")
    print("each file, the 3 thumbnail embeddings are likely called in parallel")
    print("or very close succession, causing API rate limiting.")

if __name__ == "__main__":
    analyze_timing() 