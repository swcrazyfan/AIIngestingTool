# Supabase Schema and Functions for AI Ingesting Tool

This document outlines the public schema structure and SQL functions for the AI Ingesting Tool Supabase project. This information can be used to recreate the database schema and functionality on another database instance.

## Table of Contents
1.  [Schema Overview](#schema-overview)
2.  [Table Definitions](#table-definitions)
    *   [`user_profiles`](#user_profiles)
    *   [`clips`](#clips)
    *   [`segments`](#segments)
    *   [`analysis`](#analysis)
    *   [`vectors`](#vectors)
    *   [`transcripts`](#transcripts)
3.  [Vector Embeddings](#vector-embeddings)
4.  [SQL Function Definitions](#sql-function-definitions)
    *   [`fulltext_search_clips`](#fulltext_search_clips)
    *   [`hybrid_search_clips`](#hybrid_search_clips)
    *   [`search_transcripts`](#search_transcripts)
    *   [`semantic_search_clips`](#semantic_search_clips)

## Schema Overview

The database schema is designed to store information about users, video clips, their segments, analysis results (including AI-generated insights), vector embeddings for semantic search, and full-text transcripts.

*   **`user_profiles`**: Stores user profile information, linking to the `auth.users` table.
*   **`clips`**: The central table storing metadata for each ingested video clip. It includes file information, technical details, content summaries, tags, and links to other related tables. It features a `fts` column for full-text search.
*   **`segments`**: Stores information about individual segments within a video clip, such as start/end times, descriptions, and speaker IDs.
*   **`analysis`**: Contains results from various analysis processes performed on clips or segments, including AI model used, content categorization, and detailed visual/audio/content analysis data.
*   **`vectors`**: Stores vector embeddings generated from clip content (summaries, keywords, thumbnails) to enable semantic search capabilities. The `vector` data type is used, typically provided by the `pgvector` extension.
*   **`transcripts`**: Holds the full-text transcripts for clips, including segmented text and speaker information. It also has an `fts` column for searching within transcripts.

Relationships are established using foreign keys, primarily linking back to `clips` and `user_profiles` (via `auth.users`).

## Table Definitions

Below are the `CREATE TABLE` statements derived from the schema information. Note that default values, checks, and relationships are included. You will need the `pgvector` extension enabled in your PostgreSQL instance for the `vector` type to work.

### `user_profiles`

```sql
CREATE TABLE public.user_profiles (
    id uuid NOT NULL,
    profile_type text NULL DEFAULT 'user'::text,
    display_name text NULL,
    created_at timestamptz NULL DEFAULT now(),
    updated_at timestamptz NULL DEFAULT now(),
    CONSTRAINT user_profiles_pkey PRIMARY KEY (id),
    CONSTRAINT user_profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id),
    CHECK ((profile_type = ANY (ARRAY['admin'::text, 'user'::text])))
);
```

### `clips`

```sql
CREATE TABLE public.clips (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    file_path text NOT NULL,
    local_path text NOT NULL,
    file_name text NOT NULL,
    file_checksum text NOT NULL,
    file_size_bytes int8 NOT NULL,
    duration_seconds numeric NULL,
    created_at timestamptz NULL DEFAULT now(),
    processed_at timestamptz NULL DEFAULT now(),
    width int4 NULL,
    height int4 NULL,
    frame_rate numeric NULL,
    codec text NULL,
    camera_make text NULL,
    camera_model text NULL,
    container text NULL,
    content_category text NULL,
    content_summary text NULL,
    content_tags _text NULL,
    full_transcript text NULL,
    transcript_preview text NULL,
    searchable_content text NULL,
    technical_metadata jsonb NULL,
    camera_details jsonb NULL,
    audio_tracks jsonb NULL,
    subtitle_tracks jsonb NULL,
    thumbnails _text NULL,
    all_thumbnail_urls jsonb NULL DEFAULT '[]'::jsonb,
    thumbnail_url text NULL,
    updated_at timestamptz NULL DEFAULT now(),
    fts tsvector NULL GENERATED ALWAYS AS (generate_clip_fts(file_name, content_summary, transcript_preview, content_tags, searchable_content)) STORED, -- Definition of generate_clip_fts not provided, assuming it exists
    CONSTRAINT clips_pkey PRIMARY KEY (id),
    CONSTRAINT clips_file_checksum_key UNIQUE (file_checksum),
    CONSTRAINT clips_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

-- Note: The 'generate_clip_fts' function used in the 'fts' generated column is not defined here.
-- You would need to define it based on its original implementation.
-- Example placeholder for generate_clip_fts:
-- CREATE OR REPLACE FUNCTION generate_clip_fts(
--     p_file_name text,
--     p_content_summary text,
--     p_transcript_preview text,
--     p_content_tags text[],
--     p_searchable_content text
-- ) RETURNS tsvector
-- LANGUAGE plpgsql IMMUTABLE
-- AS $$
-- BEGIN
--     RETURN to_tsvector('english',
--         COALESCE(p_file_name, '') || ' ' ||
--         COALESCE(p_content_summary, '') || ' ' ||
--         COALESCE(p_transcript_preview, '') || ' ' ||
--         COALESCE(array_to_string(p_content_tags, ' '), '') || ' ' ||
--         COALESCE(p_searchable_content, '')
--     );
-- END;
-- $$;

-- It's also recommended to create an index on the fts column for performance:
CREATE INDEX clips_fts_idx ON public.clips USING GIN (fts);
```

### `segments`

```sql
CREATE TABLE public.segments (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    clip_id uuid NULL,
    user_id uuid NOT NULL,
    segment_index int4 NOT NULL,
    start_time_seconds numeric NOT NULL,
    end_time_seconds numeric NOT NULL,
    duration_seconds numeric NULL,
    segment_type text NULL DEFAULT 'auto'::text,
    speaker_id text NULL,
    segment_description text NULL,
    keyframe_timestamp numeric NULL,
    segment_content text NULL,
    fts tsvector NULL, -- Assuming this might be populated by a trigger or application logic
    created_at timestamptz NULL DEFAULT now(),
    CONSTRAINT segments_pkey PRIMARY KEY (id),
    CONSTRAINT segments_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(id),
    CONSTRAINT segments_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
    CHECK ((segment_index >= 0))
);

-- If 'fts' column in 'segments' is used for search, an index is recommended:
-- CREATE INDEX segments_fts_idx ON public.segments USING GIN (fts);
```

### `analysis`

```sql
CREATE TABLE public.analysis (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    clip_id uuid NULL,
    segment_id uuid NULL,
    user_id uuid NOT NULL,
    analysis_type text NOT NULL,
    analysis_scope text NOT NULL,
    ai_model text NULL DEFAULT 'gemini-flash-2.5'::text,
    content_category text NULL,
    usability_rating text NULL,
    speaker_count int4 NULL,
    visual_analysis jsonb NULL,
    audio_analysis jsonb NULL,
    content_analysis jsonb NULL,
    analysis_summary jsonb NULL,
    analysis_file_path text NULL,
    created_at timestamptz NULL DEFAULT now(),
    ai_analysis jsonb NULL,
    CONSTRAINT analysis_pkey PRIMARY KEY (id),
    CONSTRAINT analysis_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(id),
    CONSTRAINT analysis_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.segments(id),
    CONSTRAINT analysis_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
    CHECK ((analysis_scope = ANY (ARRAY['full_clip'::text, 'segment'::text])))
);
```

### `vectors`

```sql
CREATE TABLE public.vectors (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    clip_id uuid NULL,
    segment_id uuid NULL,
    user_id uuid NOT NULL,
    embedding_type text NOT NULL,
    embedding_source text NOT NULL,
    summary_embedding public.vector(1024) NULL, -- BAAI/bge-m3 embeddings
    keyword_embedding public.vector(1024) NULL, -- BAAI/bge-m3 embeddings
    embedded_content text NOT NULL,
    original_content text NULL,
    created_at timestamptz NULL DEFAULT now(),
    thumbnail_embeddings jsonb NULL DEFAULT '{}'::jsonb,
    metadata jsonb NULL,
    thumbnail_1_embedding public.vector(768) NULL, -- Thumbnail embeddings
    thumbnail_2_embedding public.vector(768) NULL, -- Thumbnail embeddings
    thumbnail_3_embedding public.vector(768) NULL, -- Thumbnail embeddings
    CONSTRAINT vectors_pkey PRIMARY KEY (id),
    CONSTRAINT vectors_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(id),
    CONSTRAINT vectors_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.segments(id),
    CONSTRAINT vectors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
    CHECK ((embedding_type = ANY (ARRAY['full_clip'::text, 'segment'::text, 'keyframe'::text])))
);

-- Example for specifying vector dimensions:
-- ALTER TABLE public.vectors ALTER COLUMN summary_embedding TYPE public.vector(1024);
-- ALTER TABLE public.vectors ALTER COLUMN keyword_embedding TYPE public.vector(1024);
-- ALTER TABLE public.vectors ALTER COLUMN thumbnail_1_embedding TYPE public.vector(768);
-- ALTER TABLE public.vectors ALTER COLUMN thumbnail_2_embedding TYPE public.vector(768);
-- ALTER TABLE public.vectors ALTER COLUMN thumbnail_3_embedding TYPE public.vector(768);

-- Indexes for vector columns are crucial for performance (using HNSW or IVFFlat with pgvector):
-- CREATE INDEX ON public.vectors USING hnsw (summary_embedding public.vector_l2_ops);
-- CREATE INDEX ON public.vectors USING hnsw (keyword_embedding public.vector_l2_ops);
-- CREATE INDEX ON public.vectors USING hnsw (thumbnail_1_embedding public.vector_l2_ops);
-- CREATE INDEX ON public.vectors USING hnsw (thumbnail_2_embedding public.vector_l2_ops);
-- CREATE INDEX ON public.vectors USING hnsw (thumbnail_3_embedding public.vector_l2_ops);
```

### `transcripts`

```sql
CREATE TABLE public.transcripts (
    clip_id uuid NOT NULL,
    user_id uuid NOT NULL,
    full_text text NOT NULL,
    segments jsonb NOT NULL,
    speakers jsonb NULL,
    non_speech_events jsonb NULL,
    fts tsvector NULL, -- Assuming this is populated by a trigger or application logic
    created_at timestamptz NULL DEFAULT now(),
    CONSTRAINT transcripts_pkey PRIMARY KEY (clip_id),
    CONSTRAINT transcripts_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(id),
    CONSTRAINT transcripts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

-- If 'fts' column in 'transcripts' is used for search, an index is recommended:
-- CREATE INDEX transcripts_fts_idx ON public.transcripts USING GIN (fts);
-- A function would also be needed to populate this fts field, e.g., from 'full_text'.
```

## Vector Embeddings

The `vectors` table uses the `public.vector` data type, which is provided by the `pgvector` PostgreSQL extension. The dimensions for the embeddings are:
*   `summary_embedding` (BAAI/bge-m3): 1024 dimensions
*   `keyword_embedding` (BAAI/bge-m3): 1024 dimensions
*   `thumbnail_1_embedding`, `thumbnail_2_embedding`, `thumbnail_3_embedding`: 768 dimensions (model not specified here, but dimensions confirmed)

**Important:** The `CREATE TABLE` statement for `vectors` above has been updated to include these dimensions directly (e.g., `public.vector(1024)` and `public.vector(768)`). If you were to create the table without dimensions first, you would use `ALTER TABLE` commands like these:

```sql
-- For BAAI/bge-m3 embeddings:
ALTER TABLE public.vectors ALTER COLUMN summary_embedding TYPE public.vector(1024);
ALTER TABLE public.vectors ALTER COLUMN keyword_embedding TYPE public.vector(1024);

-- For thumbnail embeddings:
ALTER TABLE public.vectors ALTER COLUMN thumbnail_1_embedding TYPE public.vector(768);
ALTER TABLE public.vectors ALTER COLUMN thumbnail_2_embedding TYPE public.vector(768);
ALTER TABLE public.vectors ALTER COLUMN thumbnail_3_embedding TYPE public.vector(768);
```

For efficient similarity searches, you should also create indexes on your vector columns. `pgvector` supports different index types like HNSW and IVFFlat. Example using HNSW with L2 distance:

```sql
CREATE INDEX ON public.vectors USING hnsw (summary_embedding public.vector_l2_ops);
CREATE INDEX ON public.vectors USING hnsw (keyword_embedding public.vector_l2_ops);
-- Add similar indexes for thumbnail_X_embedding columns if they are used in similarity searches.
```

## SQL Function Definitions

The following are the SQL functions used for searching within the database.

### `fulltext_search_clips`

```sql
CREATE OR REPLACE FUNCTION public.fulltext_search_clips(p_query_text text, p_user_id_filter uuid, p_match_count integer DEFAULT 10)
 RETURNS TABLE(id uuid, file_name text, local_path text, content_summary text, content_tags text[], duration_seconds numeric, camera_make text, camera_model text, content_category text, processed_at timestamp with time zone, transcript_preview text, fts_rank double precision)
 LANGUAGE sql
 STABLE
AS $function$
SELECT
    c.id,
    c.file_name,
    c.local_path,
    c.content_summary,
    c.content_tags,
    c.duration_seconds,
    c.camera_make,
    c.camera_model,
    c.content_category,
    c.processed_at,
    c.transcript_preview,
    ts_rank_cd(c.fts, websearch_to_tsquery('english', p_query_text)) AS fts_rank
FROM
    clips c
WHERE
    c.user_id = p_user_id_filter
    AND c.fts @@ websearch_to_tsquery('english', p_query_text)
ORDER BY
    fts_rank DESC
LIMIT
    p_match_count;
$function$
```

### `hybrid_search_clips`

```sql
CREATE OR REPLACE FUNCTION public.hybrid_search_clips(p_query_text text, p_query_summary_embedding vector, p_query_keyword_embedding vector, p_user_id_filter uuid, p_match_count integer DEFAULT 10, p_fulltext_weight double precision DEFAULT 2.5, p_summary_weight double precision DEFAULT 1.0, p_keyword_weight double precision DEFAULT 0.8, p_rrf_k integer DEFAULT 50, p_summary_threshold double precision DEFAULT 0.4, p_keyword_threshold double precision DEFAULT 0.4)
 RETURNS TABLE(id uuid, file_name text, local_path text, content_summary text, content_tags text[], duration_seconds numeric, camera_make text, camera_model text, content_category text, processed_at timestamp with time zone, transcript_preview text, similarity_score double precision, search_rank bigint, match_type text)
 LANGUAGE sql
 STABLE
AS $function$
WITH fulltext_cte AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary,
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at, c.transcript_preview,
    ts_rank_cd(c.fts, websearch_to_tsquery('english', p_query_text)) as score,
    ROW_NUMBER() OVER(ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', p_query_text)) DESC) as rank_ix
  FROM clips c
  WHERE c.user_id = p_user_id_filter
    AND c.fts @@ websearch_to_tsquery('english', p_query_text)
  ORDER BY score DESC
  LIMIT LEAST(p_match_count * 3, 60)
),
summary_semantic_cte AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary,
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at, c.transcript_preview,
    (1 - (v.summary_embedding <=> p_query_summary_embedding)) as score, -- Cosine similarity
    ROW_NUMBER() OVER (ORDER BY (1 - (v.summary_embedding <=> p_query_summary_embedding)) DESC) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = p_user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.summary_embedding IS NOT NULL
    AND (1 - (v.summary_embedding <=> p_query_summary_embedding)) >= p_summary_threshold
  ORDER BY score DESC
  LIMIT LEAST(p_match_count * 3, 60)
),
keyword_semantic_cte AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary,
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at, c.transcript_preview,
    (1 - (v.keyword_embedding <=> p_query_keyword_embedding)) as score, -- Cosine similarity
    ROW_NUMBER() OVER (ORDER BY (1 - (v.keyword_embedding <=> p_query_keyword_embedding)) DESC) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = p_user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.keyword_embedding IS NOT NULL
    AND (1 - (v.keyword_embedding <=> p_query_keyword_embedding)) >= p_keyword_threshold
  ORDER BY score DESC
  LIMIT LEAST(p_match_count * 3, 60)
)
SELECT
  COALESCE(ft.id, ss.id, ks.id) as id,
  COALESCE(ft.file_name, ss.file_name, ks.file_name) as file_name,
  COALESCE(ft.local_path, ss.local_path, ks.local_path) as local_path,
  COALESCE(ft.content_summary, ss.content_summary, ks.content_summary) as content_summary,
  COALESCE(ft.content_tags, ss.content_tags, ks.content_tags) as content_tags,
  COALESCE(ft.duration_seconds, ss.duration_seconds, ks.duration_seconds) as duration_seconds,
  COALESCE(ft.camera_make, ss.camera_make, ks.camera_make) as camera_make,
  COALESCE(ft.camera_model, ss.camera_model, ks.camera_model) as camera_model,
  COALESCE(ft.content_category, ss.content_category, ks.content_category) as content_category,
  COALESCE(ft.processed_at, ss.processed_at, ks.processed_at) as processed_at,
  COALESCE(ft.transcript_preview, ss.transcript_preview, ks.transcript_preview) as transcript_preview,
  (COALESCE(1.0 / (p_rrf_k + ft.rank_ix), 0.0) * p_fulltext_weight) +
  (COALESCE(1.0 / (p_rrf_k + ss.rank_ix), 0.0) * p_summary_weight) +
  (COALESCE(1.0 / (p_rrf_k + ks.rank_ix), 0.0) * p_keyword_weight) as similarity_score,
  ROW_NUMBER() OVER (ORDER BY
    (COALESCE(1.0 / (p_rrf_k + ft.rank_ix), 0.0) * p_fulltext_weight) +
    (COALESCE(1.0 / (p_rrf_k + ss.rank_ix), 0.0) * p_summary_weight) +
    (COALESCE(1.0 / (p_rrf_k + ks.rank_ix), 0.0) * p_keyword_weight) DESC
  ) as search_rank,
  CASE
    WHEN ft.id IS NOT NULL AND (ss.id IS NOT NULL OR ks.id IS NOT NULL) THEN 'hybrid'
    WHEN ft.id IS NOT NULL THEN 'fulltext'
    WHEN ss.id IS NOT NULL OR ks.id IS NOT NULL THEN 'semantic'
    ELSE 'unknown'
  END as match_type
FROM fulltext_cte ft
FULL OUTER JOIN summary_semantic_cte ss ON ft.id = ss.id
FULL OUTER JOIN keyword_semantic_cte ks ON COALESCE(ft.id, ss.id) = ks.id
WHERE COALESCE(ft.id, ss.id, ks.id) IS NOT NULL
ORDER BY similarity_score DESC
LIMIT p_match_count;
$function$
```

### `search_transcripts`

```sql
CREATE OR REPLACE FUNCTION public.search_transcripts(query_text text, user_id_filter uuid, match_count integer DEFAULT 10, min_content_length integer DEFAULT 50)
 RETURNS TABLE(clip_id uuid, file_name text, local_path text, content_summary text, full_text text, transcript_preview text, duration_seconds numeric, processed_at timestamp with time zone, fts_rank double precision)
 LANGUAGE sql
AS $function$
SELECT
  t.clip_id,
  c.file_name,
  c.local_path,
  c.content_summary,
  t.full_text,
  c.transcript_preview,
  c.duration_seconds,
  c.processed_at,
  ts_rank_cd(t.fts, websearch_to_tsquery('english', query_text)) as fts_rank
FROM transcripts t
JOIN clips c ON t.clip_id = c.id
WHERE t.user_id = user_id_filter
  AND LENGTH(t.full_text) >= min_content_length
  AND t.fts @@ websearch_to_tsquery('english', query_text)
ORDER BY ts_rank_cd(t.fts, websearch_to_tsquery('english', query_text)) DESC
LIMIT match_count;
$function$
```

### `semantic_search_clips`

```sql
CREATE OR REPLACE FUNCTION public.semantic_search_clips(p_query_summary_embedding vector, p_query_keyword_embedding vector, p_user_id_filter uuid, p_match_count integer DEFAULT 10, p_summary_weight double precision DEFAULT 1.0, p_keyword_weight double precision DEFAULT 0.8, p_similarity_threshold double precision DEFAULT 0.4)
 RETURNS TABLE(id uuid, file_name text, local_path text, content_summary text, content_tags text[], duration_seconds numeric, camera_make text, camera_model text, content_category text, processed_at timestamp with time zone, transcript_preview text, summary_similarity double precision, keyword_similarity double precision, combined_similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
SELECT
    c.id,
    c.file_name,
    c.local_path,
    c.content_summary,
    c.content_tags,
    c.duration_seconds,
    c.camera_make,
    c.camera_model,
    c.content_category,
    c.processed_at,
    c.transcript_preview,
    (1 - (v.summary_embedding <=> p_query_summary_embedding)) AS summary_similarity,
    COALESCE((1 - (v.keyword_embedding <=> p_query_keyword_embedding)), 0.0) AS keyword_similarity,
    ((1 - (v.summary_embedding <=> p_query_summary_embedding)) * p_summary_weight) +
    (COALESCE((1 - (v.keyword_embedding <=> p_query_keyword_embedding)), 0.0) * p_keyword_weight) AS combined_similarity
FROM
    clips c
JOIN
    vectors v ON c.id = v.clip_id
WHERE
    c.user_id = p_user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.summary_embedding IS NOT NULL
    AND (1 - (v.summary_embedding <=> p_query_summary_embedding)) >= p_similarity_threshold
ORDER BY
    combined_similarity DESC
LIMIT
    p_match_count;
$function$