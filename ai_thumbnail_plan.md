# AI Thumbnail Selection and Embedding Implementation Plan

## Current Status
**Progress:** 0/12 components implemented (0% complete)  
**Testing Status:** No components tested yet

## High-level Plan
1. ⬜ Update analysis schema to include best thumbnail recommendations
2. ⬜ Update analysis prompt to request concise frame descriptions
3. ⬜ Create new thumbnail selection module
4. ⬜ Implement image processing for embedding preparation
5. ⬜ Update database schema via Supabase migrations
6. ⬜ Create embedding generation for thumbnails
7. ⬜ Update storage step to save selected thumbnails
8. ⬜ Integrate with vector database
9. ⬜ Update UI to display AI-selected thumbnails
10. ⬜ Update search to include thumbnail embeddings

## Implementation Phases

> **Status Legend**:  
> ⬜ = Waiting / Not Started  
> 🔄 = In Progress  
> ✅ = Completed

### Phase 1: Schema and Model Updates

- ⬜ Update AI analysis schema in `video_processor/analysis.py`
  - Add `recommended_thumbnails` array with exactly 3 items (ranked by quality)
  - Each thumbnail should include:
    - `timestamp`: When this frame appears
    - `description`: Concise description (10-20 tokens max)
    - `reason`: Why this frame was selected
    - `rank`: Explicit ranking (1=best, 2=second, 3=third)

- ⬜ Update AI prompt in `video_processor/analysis.py`
  - Request the model to select exactly 3 representative frames
  - Provide clear instructions for concise descriptions using the token structure:
    - Primary Subject (1-2 tokens)
    - Action/Type (1-2 tokens)
    - Key Details (2-4 tokens)
    - Context (1-2 tokens)
  - Emphasize rank ordering (best first, followed by two alternatives)

### Phase 2: Thumbnail Processing

- ⬜ Create `steps/analysis/ai_thumbnail_selection.py`
  - Implement function to extract timestamps from AI analysis
  - Add capability to extract the specific frames at those timestamps
  - Process each extracted frame to standard dimensions (256x256)
  - Generate filenames with "AI_" prefix using the same timestamp format: `AI_{filename}_{timestamp}_{rank}.jpg`
    - Example: `AI_video.mp4_10s500ms_1.jpg` (for rank 1 thumbnail at 10.5 seconds)
  - Save thumbnails in the same directory as regular thumbnails
  - Return paths and metadata for storage step

### Phase 3: Database Updates

- ⬜ Create Supabase migration for database schema updates
  - Create migration script for `clips` table:
    ```sql
    -- Add to clips table
    ALTER TABLE clips ADD COLUMN ai_thumbnail_1_path TEXT;
    ALTER TABLE clips ADD COLUMN ai_thumbnail_2_path TEXT;
    ALTER TABLE clips ADD COLUMN ai_thumbnail_3_path TEXT;
    ALTER TABLE clips ADD COLUMN ai_thumbnail_1_timestamp TEXT;
    ALTER TABLE clips ADD COLUMN ai_thumbnail_2_timestamp TEXT;
    ALTER TABLE clips ADD COLUMN ai_thumbnail_3_timestamp TEXT;
    ```

  - Create migration script for `vectors` table:
    ```sql
    -- Add to vectors table
    ALTER TABLE vectors ADD COLUMN thumbnail_1_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN thumbnail_2_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN thumbnail_3_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN thumbnail_1_description TEXT;
    ALTER TABLE vectors ADD COLUMN thumbnail_2_description TEXT;
    ALTER TABLE vectors ADD COLUMN thumbnail_3_description TEXT;
    ALTER TABLE vectors ADD COLUMN thumbnail_1_reason TEXT;
    ALTER TABLE vectors ADD COLUMN thumbnail_2_reason TEXT;
    ALTER TABLE vectors ADD COLUMN thumbnail_3_reason TEXT;
    ```

- ⬜ Apply migrations using Supabase MCP
  - Use `mcp_supabase_apply_migration` to run the migration scripts
  - Verify schema changes in Supabase dashboard

### Phase 4: Embedding Generation

- ⬜ Create `video_ingest_tool/embeddings_image.py`
  - Implement function to convert image to base64
  - Implement function to resize/compress images to 256x256
  - Implement function to create combined image+text payload
  - Implement function to call LiteLLM endpoint with proper format
  - Return embedding vectors for storage
  - Configuration:
    - LITELLM_BASE_URL: https://litellm.joshhost.com
    - MODEL: siglip-base-patch16-256-multilingual-onnx
    - LITELLM_KEY: From environment variable

- ⬜ Update `steps/storage/embeddings.py`
  - Add capability to process thumbnails for embedding
  - Generate text+image combined embeddings
  - Store in vectors table alongside existing text embeddings

### Phase 5: Integration

- ⬜ Update `steps/storage/thumbnail_upload.py`
  - Extend upload functionality to handle AI-selected thumbnails
  - Upload AI thumbnails to the same Supabase storage path
  - Store their URLs in the database with appropriate prefixes

- ⬜ Update `steps/storage/database_storage.py`
  - Add code to store AI-selected thumbnail paths and timestamps
  - Link to clip record

- ⬜ Update pipeline in main processor
  - Ensure AI thumbnail selection runs after video analysis but before storage
  - Pass thumbnail data to embedding generation step

### Phase 6: UI and Search Updates

- ⬜ Update frontend components to display AI-selected thumbnails
- ⬜ Update search functionality to leverage thumbnail embeddings
- ⬜ Add option to prioritize searches by visual similarity

## Detailed Component Structure

### AI Analysis Schema Update

```json
"keyframe_analysis": {
  "type": "OBJECT",
  "properties": {
    "recommended_keyframes": {
      // existing schema
    },
    "recommended_thumbnails": {
      "type": "ARRAY",
      "description": "Exactly 3 frames ranked by how well they represent the entire clip",
      "minItems": 3,
      "maxItems": 3,
      "items": {
        "type": "OBJECT",
        "properties": {
          "timestamp": {"type": "STRING"},
          "description": {
            "type": "STRING",
            "description": "Concise 10-20 token description using format: Subject Action/Type Key-Details Context"
          },
          "reason": {
            "type": "STRING",
            "description": "Why this frame represents the video well"
          },
          "rank": {
            "type": "INTEGER",
            "enum": [1, 2, 3],
            "description": "Rank with 1 being best representative frame"
          }
        },
        "required": ["timestamp", "description", "reason", "rank"]
      }
    }
  }
}
```

### Embedding Generation API Structure

```python
def generate_thumbnail_embedding(image_path, description):
    """
    Generate embedding for image+text combination using SigLIP model.
    
    Args:
        image_path: Path to the thumbnail image
        description: Short text description of the thumbnail
        
    Returns:
        List[float]: 768-dimensional embedding vector
    """
    # 1. Resize image to 256x256 (maintaining aspect ratio with padding)
    image = resize_image(image_path, 256, 256)
    
    # 2. Convert to base64
    base64_image = image_to_base64(image)
    
    # 3. Format payload for LiteLLM
    payload = {
        "model": "siglip-base-patch16-256-multilingual-onnx",
        "input": {"image": base64_image, "text": description}
    }
    
    # 4. Call LiteLLM endpoint
    response = requests.post(
        os.getenv("LITELLM_BASE_URL"),
        headers={
            "Authorization": f"Bearer {os.getenv('LITELLM_KEY')}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    
    # 5. Return embedding
    return response.json()["data"][0]["embedding"]
```

### Supabase Migration Implementation

```python
def apply_ai_thumbnail_migrations(project_id):
    """Apply migrations for AI thumbnail features using Supabase MCP."""
    
    # Migration for clips table
    clips_migration = """
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_1_path TEXT;
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_2_path TEXT;
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_3_path TEXT;
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_1_timestamp TEXT;
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_2_timestamp TEXT;
    ALTER TABLE clips ADD COLUMN IF NOT EXISTS ai_thumbnail_3_timestamp TEXT;
    """
    
    # Migration for vectors table
    vectors_migration = """
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_1_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_2_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_3_embedding vector(768);
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_1_description TEXT;
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_2_description TEXT;
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_3_description TEXT;
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_1_reason TEXT;
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_2_reason TEXT;
    ALTER TABLE vectors ADD COLUMN IF NOT EXISTS thumbnail_3_reason TEXT;
    """
    
    # Apply migrations using Supabase MCP
    mcp_supabase_apply_migration(
        project_id=project_id,
        name="add_ai_thumbnail_fields_to_clips",
        query=clips_migration
    )
    
    mcp_supabase_apply_migration(
        project_id=project_id,
        name="add_ai_thumbnail_fields_to_vectors",
        query=vectors_migration
    )
```

### Thumbnail Processing Logic Flow

1. Extract timestamps from AI analysis
2. Use ffmpeg to extract frames at exact timestamps
3. Process each frame to 256x256 square format
4. Save with "AI_" prefix and formatted timestamp: `AI_{filename}_{timestamp}_{rank}.jpg`
   - Example: `AI_video.mp4_5s600ms_1.jpg` (for the best frame at 5.6 seconds)
5. Generate base64 encoding of each image
6. Combine with text description in required format
7. Send to embedding endpoint
8. Store embeddings and paths

### Thumbnail Upload Integration

```python
def upload_ai_thumbnails(data, supabase_client, user_id, clip_id, logger=None):
    """
    Upload AI-selected thumbnails to Supabase storage.
    
    Args:
        data: Pipeline data containing AI thumbnail paths
        supabase_client: Authenticated Supabase client
        user_id: User ID for storage path
        clip_id: Clip ID for storage path
        logger: Optional logger
        
    Returns:
        Dict: URLs of uploaded AI thumbnails
    """
    ai_thumbnail_paths = data.get('ai_thumbnail_paths', [])
    if not ai_thumbnail_paths:
        if logger:
            logger.warning("No AI thumbnails available for upload")
        return {}
        
    # Create storage path structure: users/{user_id}/videos/{clip_id}/thumbnails/
    storage_path = f"users/{user_id}/videos/{clip_id}/thumbnails"
    
    # Upload each AI thumbnail
    ai_thumbnail_urls = {}
    for rank, thumbnail_path in enumerate(ai_thumbnail_paths, 1):
        if not os.path.exists(thumbnail_path):
            continue
            
        # Get the filename from the path (already has AI_ prefix)
        filename = os.path.basename(thumbnail_path)
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(thumbnail_path)
        if not content_type:
            content_type = "image/jpeg"
            
        # Read file content
        with open(thumbnail_path, 'rb') as file:
            file_content = file.read()
            
        # Upload file to Supabase Storage
        storage_path_with_file = f"{storage_path}/{filename}"
        
        # Upload the file to storage
        upload_result = supabase_client.storage.from_('videos').upload(
            path=storage_path_with_file,
            file=file_content,
            file_options={"content-type": content_type}
        )
        
        # Get the public URL
        thumbnail_url = supabase_client.storage.from_('videos').get_public_url(storage_path_with_file)
        ai_thumbnail_urls[f'ai_thumbnail_{rank}_url'] = thumbnail_url
        
    return ai_thumbnail_urls
```

## Implementation Guidelines

### Thumbnail Description Format

Enforce this structure for all thumbnail descriptions:
- Primary Subject (1-2 tokens): e.g., "basketball", "cooking", "meeting"
- Action/Type (1-2 tokens): e.g., "highlights", "tutorial", "presentation"
- Key Details (2-4 tokens): e.g., "slam dunk", "pasta recipe", "quarterly results"
- Context (1-2 tokens): e.g., "professional", "beginner", "championship"

Example: "basketball championship highlights incredible shots" (5 tokens)

### AI Thumbnail Naming Convention

- Format: `AI_{original_filename}_{timestamp}_{rank}.jpg`
- Examples:
  - `AI_MVI_0484.MP4_2s800ms_1.jpg` (rank 1 thumbnail at 2.8 seconds)
  - `AI_P1000011.MOV_5s600ms_2.jpg` (rank 2 thumbnail at 5.6 seconds)
  - `AI_video.mp4_14s000ms_3.jpg` (rank 3 thumbnail at 14.0 seconds)

### Integration Testing

After implementing each component:
1. Verify AI correctly selects 3 frames with proper descriptions
2. Verify frames are extracted and processed correctly
3. Verify AI thumbnails are saved with correct naming convention and in the same directory
4. Verify thumbnails are uploaded to Supabase with proper paths
5. Verify embeddings are generated and stored correctly
6. Test search functionality using the new embeddings 