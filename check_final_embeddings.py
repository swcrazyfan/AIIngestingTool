import json
import subprocess

# Get clips data
result = subprocess.run(['curl', '-s', 'http://localhost:8001/api/clips?limit=16'], 
                       capture_output=True, text=True)
response = json.loads(result.stdout)
clips = response['data']['data']

print(f'📋 FINAL EMBEDDING STATUS (All {len(clips)} clips):')
print()

# Count embeddings
summary_count = sum(1 for clip in clips if clip['summary_embedding'])
keyword_count = sum(1 for clip in clips if clip['keyword_embedding'])
thumb1_count = sum(1 for clip in clips if clip['thumbnail_1_embedding'])
thumb2_count = sum(1 for clip in clips if clip['thumbnail_2_embedding'])
thumb3_count = sum(1 for clip in clips if clip['thumbnail_3_embedding'])
ai_thumbs_count = sum(1 for clip in clips if clip['ai_selected_thumbnails_json'])

print(f'📊 OVERALL STATISTICS:')
print(f'   Total clips: {len(clips)}')
print(f'   Summary embeddings: {summary_count}/{len(clips)} ({summary_count/len(clips)*100:.1f}%)')
print(f'   Keyword embeddings: {keyword_count}/{len(clips)} ({keyword_count/len(clips)*100:.1f}%)')
print(f'   Thumbnail 1 embeddings: {thumb1_count}/{len(clips)} ({thumb1_count/len(clips)*100:.1f}%)')
print(f'   Thumbnail 2 embeddings: {thumb2_count}/{len(clips)} ({thumb2_count/len(clips)*100:.1f}%)')
print(f'   Thumbnail 3 embeddings: {thumb3_count}/{len(clips)} ({thumb3_count/len(clips)*100:.1f}%)')
print(f'   AI thumbnail selections: {ai_thumbs_count}/{len(clips)} ({ai_thumbs_count/len(clips)*100:.1f}%)')
print()

print('📋 DETAILED CLIP STATUS:')
for i, clip in enumerate(clips, 1):
    summary_status = '✅' if clip['summary_embedding'] else '❌'
    keyword_status = '✅' if clip['keyword_embedding'] else '❌'
    thumb1_status = '✅' if clip['thumbnail_1_embedding'] else '❌'
    thumb2_status = '✅' if clip['thumbnail_2_embedding'] else '❌'
    thumb3_status = '✅' if clip['thumbnail_3_embedding'] else '❌'
    ai_thumbs_status = '✅' if clip['ai_selected_thumbnails_json'] else '❌'
    
    print(f'{i:2d}. {clip["file_name"]:20s} | Sum:{summary_status} Key:{keyword_status} T1:{thumb1_status} T2:{thumb2_status} T3:{thumb3_status} | AI:{ai_thumbs_status}') 