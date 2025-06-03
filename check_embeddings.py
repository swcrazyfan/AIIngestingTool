import json

with open('clips_data.json', 'r') as f:
    data = json.load(f)

clips = data['data']['data']
print('Embeddings Summary:')
print('=' * 50)

for i, clip in enumerate(clips):
    clip_id = clip['id']
    filename = clip['file_name']
    
    keyword_emb = clip.get('keyword_embedding')
    summary_emb = clip.get('summary_embedding') 
    thumb1_emb = clip.get('thumbnail_1_embedding')
    thumb2_emb = clip.get('thumbnail_2_embedding')
    thumb3_emb = clip.get('thumbnail_3_embedding')
    
    has_keyword = keyword_emb is not None and len(keyword_emb) > 0
    has_summary = summary_emb is not None and len(summary_emb) > 0
    has_thumb1 = thumb1_emb is not None and len(thumb1_emb) > 0
    has_thumb2 = thumb2_emb is not None and len(thumb2_emb) > 0
    has_thumb3 = thumb3_emb is not None and len(thumb3_emb) > 0
    
    print(f'{i+1}. {filename[:30]:<30} (ID: {clip_id[:8]}...)')
    print(f'   Keyword:  {"✓" if has_keyword else "✗"} ({len(keyword_emb) if keyword_emb else 0} dims)')
    print(f'   Summary:  {"✓" if has_summary else "✗"} ({len(summary_emb) if summary_emb else 0} dims)')
    print(f'   Thumb1:   {"✓" if has_thumb1 else "✗"} ({len(thumb1_emb) if thumb1_emb else 0} dims)')
    print(f'   Thumb2:   {"✓" if has_thumb2 else "✗"} ({len(thumb2_emb) if thumb2_emb else 0} dims)')
    print(f'   Thumb3:   {"✓" if has_thumb3 else "✗"} ({len(thumb3_emb) if thumb3_emb else 0} dims)')
print()

print('Summary:')
total_clips = len(clips)
keyword_count = sum(1 for c in clips if c.get('keyword_embedding') and len(c.get('keyword_embedding', [])) > 0)
summary_count = sum(1 for c in clips if c.get('summary_embedding') and len(c.get('summary_embedding', [])) > 0)
thumb1_count = sum(1 for c in clips if c.get('thumbnail_1_embedding') and len(c.get('thumbnail_1_embedding', [])) > 0)

print(f'Total clips: {total_clips}')
print(f'Clips with keyword embeddings: {keyword_count}/{total_clips}')
print(f'Clips with summary embeddings: {summary_count}/{total_clips}')
print(f'Clips with thumbnail embeddings: {thumb1_count}/{total_clips}')

# Show specific clip IDs that have at least some embeddings
print('\nClips with thumbnail embeddings:')
for clip in clips:
    if clip.get('thumbnail_1_embedding') and len(clip.get('thumbnail_1_embedding', [])) > 0:
        print(f'  {clip["file_name"]} (ID: {clip["id"]})') 