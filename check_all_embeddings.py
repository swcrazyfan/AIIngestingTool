import json
import subprocess

# Get clips data
result = subprocess.run(['curl', '-s', 'http://localhost:8001/api/clips?limit=20'], 
                       capture_output=True, text=True)

try:
    response = json.loads(result.stdout)
    clips = response['data']['data']
    
    print(f'📋 COMPLETE EMBEDDING STATUS (All {len(clips)} clips):')
    print()
    
    # Count embeddings
    summary_count = sum(1 for clip in clips if clip['summary_embedding'])
    keyword_count = sum(1 for clip in clips if clip['keyword_embedding'])
    thumb1_count = sum(1 for clip in clips if clip['thumbnail_1_embedding'])
    thumb2_count = sum(1 for clip in clips if clip['thumbnail_2_embedding'])
    thumb3_count = sum(1 for clip in clips if clip['thumbnail_3_embedding'])
    ai_thumbs_count = sum(1 for clip in clips if clip['ai_selected_thumbnails_json'])
    
    print(f'📊 FINAL STATISTICS:')
    print(f'   Total clips: {len(clips)}')
    print(f'   Summary embeddings: {summary_count}/{len(clips)} ({summary_count/len(clips)*100:.1f}%)')
    print(f'   Keyword embeddings: {keyword_count}/{len(clips)} ({keyword_count/len(clips)*100:.1f}%)')
    print(f'   Thumbnail 1 embeddings: {thumb1_count}/{len(clips)} ({thumb1_count/len(clips)*100:.1f}%)')
    print(f'   Thumbnail 2 embeddings: {thumb2_count}/{len(clips)} ({thumb2_count/len(clips)*100:.1f}%)')
    print(f'   Thumbnail 3 embeddings: {thumb3_count}/{len(clips)} ({thumb3_count/len(clips)*100:.1f}%)')
    print(f'   AI thumbnail selections: {ai_thumbs_count}/{len(clips)} ({ai_thumbs_count/len(clips)*100:.1f}%)')
    print()
    
    print('📋 DETAILED STATUS BY CLIP:')
    complete_count = 0
    partial_count = 0
    minimal_count = 0
    
    for i, clip in enumerate(clips, 1):
        summary_status = '✅' if clip['summary_embedding'] else '❌'
        keyword_status = '✅' if clip['keyword_embedding'] else '❌'
        thumb1_status = '✅' if clip['thumbnail_1_embedding'] else '❌'
        thumb2_status = '✅' if clip['thumbnail_2_embedding'] else '❌'
        thumb3_status = '✅' if clip['thumbnail_3_embedding'] else '❌'
        ai_thumbs_status = '✅' if clip['ai_selected_thumbnails_json'] else '❌'
        
        # Categorize completeness
        complete_embeddings = all([clip['summary_embedding'], clip['keyword_embedding'], 
                                 clip['thumbnail_1_embedding'], clip['thumbnail_2_embedding'], 
                                 clip['thumbnail_3_embedding']])
        has_ai_analysis = clip['ai_selected_thumbnails_json'] is not None
        
        if complete_embeddings:
            status_indicator = '🎯'  # Complete success
            complete_count += 1
        elif has_ai_analysis:
            status_indicator = '⚠️'   # Has AI analysis but missing embeddings
            partial_count += 1
        else:
            status_indicator = '❌'   # Minimal processing
            minimal_count += 1
        
        print(f'{i:2d}. {status_indicator} {clip["file_name"]:20s} | Sum:{summary_status} Key:{keyword_status} T1:{thumb1_status} T2:{thumb2_status} T3:{thumb3_status} | AI:{ai_thumbs_status}')
    
    print()
    print('📈 PROCESSING CATEGORIES:')
    print(f'🎯 Complete (All embeddings): {complete_count} clips')
    print(f'⚠️  Partial (Has AI, missing embeddings): {partial_count} clips') 
    print(f'❌ Minimal (Keywords only): {minimal_count} clips')
    
except Exception as e:
    print(f'Error: {e}')
    print('Raw response:')
    print(result.stdout) 