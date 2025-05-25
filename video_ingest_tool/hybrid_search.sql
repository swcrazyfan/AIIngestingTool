-- =====================================================
-- HYBRID SEARCH FUNCTIONS FOR VIDEO CATALOG
-- =====================================================

-- Function for basic semantic search using vector similarity
CREATE OR REPLACE FUNCTION semantic_search_clips(
  query_summary_embedding vector(1024),
  query_keyword_embedding vector(1024),
  user_id_filter UUID,
  match_count INT DEFAULT 10,
  summary_weight FLOAT DEFAULT 1.0,
  keyword_weight FLOAT DEFAULT 0.8,
  similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
  id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  content_tags TEXT[],
  duration_seconds NUMERIC,
  camera_make TEXT,
  camera_model TEXT,
  content_category TEXT,
  processed_at TIMESTAMPTZ,
  summary_similarity FLOAT,
  keyword_similarity FLOAT,
  combined_similarity FLOAT
)
LANGUAGE SQL
AS $$
WITH summary_search AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary, 
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at,
    (v.summary_vector <#> query_summary_embedding) * -1 as summary_similarity,
    ROW_NUMBER() OVER (ORDER BY v.summary_vector <#> query_summary_embedding) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.summary_vector IS NOT NULL
  ORDER BY v.summary_vector <#> query_summary_embedding
  LIMIT LEAST(match_count * 2, 50)
),
keyword_search AS (
  SELECT
    c.id,
    (v.keyword_vector <#> query_keyword_embedding) * -1 as keyword_similarity
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.keyword_vector IS NOT NULL
  ORDER BY v.keyword_vector <#> query_keyword_embedding
  LIMIT LEAST(match_count * 2, 50)
)
SELECT
  ss.id,
  ss.file_name,
  ss.local_path,
  ss.content_summary,
  ss.content_tags,
  ss.duration_seconds,
  ss.camera_make,
  ss.camera_model,
  ss.content_category,
  ss.processed_at,
  ss.summary_similarity,
  COALESCE(ks.keyword_similarity, 0.0) as keyword_similarity,
  (ss.summary_similarity * summary_weight + COALESCE(ks.keyword_similarity, 0.0) * keyword_weight) as combined_similarity
FROM summary_search ss
LEFT JOIN keyword_search ks ON ss.id = ks.id
WHERE ss.summary_similarity >= similarity_threshold
ORDER BY combined_similarity DESC
LIMIT match_count;
$$;

-- Function for hybrid search combining full-text and semantic search using RRF
CREATE OR REPLACE FUNCTION hybrid_search_clips(
  query_text TEXT,
  query_summary_embedding vector(1024),
  query_keyword_embedding vector(1024),
  user_id_filter UUID,
  match_count INT DEFAULT 10,
  fulltext_weight FLOAT DEFAULT 1.0,
  summary_weight FLOAT DEFAULT 1.0,
  keyword_weight FLOAT DEFAULT 0.8,
  rrf_k INT DEFAULT 50
)
RETURNS TABLE (
  id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  content_tags TEXT[],
  duration_seconds NUMERIC,
  camera_make TEXT,
  camera_model TEXT,
  content_category TEXT,
  processed_at TIMESTAMPTZ,
  transcript_preview TEXT,
  similarity_score FLOAT,
  search_rank FLOAT,
  match_type TEXT
)
LANGUAGE SQL
AS $$
WITH fulltext AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary, 
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at, c.transcript_preview,
    ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) as fts_score,
    ROW_NUMBER() OVER(ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC) as rank_ix
  FROM clips c
  WHERE c.user_id = user_id_filter
    AND c.fts @@ websearch_to_tsquery('english', query_text)
  ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC
  LIMIT LEAST(match_count * 2, 30)
),
summary_semantic AS (
  SELECT
    c.id, c.file_name, c.local_path, c.content_summary,
    c.content_tags, c.duration_seconds, c.camera_make, c.camera_model,
    c.content_category, c.processed_at, c.transcript_preview,
    (v.summary_vector <#> query_summary_embedding) * -1 as similarity_score,
    ROW_NUMBER() OVER (ORDER BY v.summary_vector <#> query_summary_embedding) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.summary_vector IS NOT NULL
  ORDER BY v.summary_vector <#> query_summary_embedding
  LIMIT LEAST(match_count * 2, 30)
),
keyword_semantic AS (
  SELECT
    c.id,
    (v.keyword_vector <#> query_keyword_embedding) * -1 as keyword_similarity,
    ROW_NUMBER() OVER (ORDER BY v.keyword_vector <#> query_keyword_embedding) as rank_ix
  FROM clips c
  JOIN vectors v ON c.id = v.clip_id
  WHERE c.user_id = user_id_filter
    AND v.embedding_type = 'full_clip'
    AND v.keyword_vector IS NOT NULL
  ORDER BY v.keyword_vector <#> query_keyword_embedding
  LIMIT LEAST(match_count * 2, 30)
)
SELECT
  COALESCE(ft.id, ss.id) as id,
  COALESCE(ft.file_name, ss.file_name) as file_name,
  COALESCE(ft.local_path, ss.local_path) as local_path,
  COALESCE(ft.content_summary, ss.content_summary) as content_summary,
  COALESCE(ft.content_tags, ss.content_tags) as content_tags,
  COALESCE(ft.duration_seconds, ss.duration_seconds) as duration_seconds,
  COALESCE(ft.camera_make, ss.camera_make) as camera_make,
  COALESCE(ft.camera_model, ss.camera_model) as camera_model,
  COALESCE(ft.content_category, ss.content_category) as content_category,
  COALESCE(ft.processed_at, ss.processed_at) as processed_at,
  COALESCE(ft.transcript_preview, ss.transcript_preview) as transcript_preview,
  COALESCE(ss.similarity_score, 0.0) as similarity_score,
  -- RRF SCORING WITH DUAL VECTORS AND FULL-TEXT
  COALESCE(1.0 / (rrf_k + ft.rank_ix), 0.0) * fulltext_weight +
  COALESCE(1.0 / (rrf_k + ss.rank_ix), 0.0) * summary_weight +
  COALESCE(1.0 / (rrf_k + ks.rank_ix), 0.0) * keyword_weight as search_rank,
  CASE 
    WHEN ft.id IS NOT NULL AND ss.id IS NOT NULL THEN 'hybrid'
    WHEN ft.id IS NOT NULL THEN 'fulltext'
    ELSE 'semantic'
  END as match_type
FROM fulltext ft
FULL OUTER JOIN summary_semantic ss ON ft.id = ss.id
FULL OUTER JOIN keyword_semantic ks ON COALESCE(ft.id, ss.id) = ks.id
ORDER BY search_rank DESC
LIMIT match_count;
$$;

-- Function for full-text search only
CREATE OR REPLACE FUNCTION fulltext_search_clips(
  query_text TEXT,
  user_id_filter UUID,
  match_count INT DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  content_tags TEXT[],
  duration_seconds NUMERIC,
  camera_make TEXT,
  camera_model TEXT,
  content_category TEXT,
  processed_at TIMESTAMPTZ,
  transcript_preview TEXT,
  fts_rank FLOAT
)
LANGUAGE SQL
AS $$
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
  ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) as fts_rank
FROM clips c
WHERE c.user_id = user_id_filter
  AND c.fts @@ websearch_to_tsquery('english', query_text)
ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC
LIMIT match_count;
$$;

-- Function to search transcripts specifically
CREATE OR REPLACE FUNCTION search_transcripts(
  query_text TEXT,
  user_id_filter UUID,
  match_count INT DEFAULT 10,
  min_content_length INT DEFAULT 50
)
RETURNS TABLE (
  clip_id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  full_text TEXT,
  transcript_preview TEXT,
  duration_seconds NUMERIC,
  processed_at TIMESTAMPTZ,
  fts_rank FLOAT
)
LANGUAGE SQL
AS $$
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
$$;

-- Function to find similar clips based on existing clip
CREATE OR REPLACE FUNCTION find_similar_clips(
  source_clip_id UUID,
  user_id_filter UUID,
  match_count INT DEFAULT 5,
  similarity_threshold FLOAT DEFAULT 0.5
)
RETURNS TABLE (
  id UUID,
  file_name TEXT,
  local_path TEXT,
  content_summary TEXT,
  content_tags TEXT[],
  duration_seconds NUMERIC,
  content_category TEXT,
  similarity_score FLOAT
)
LANGUAGE SQL
AS $$
WITH source_vector AS (
  SELECT v.summary_vector
  FROM vectors v
  WHERE v.clip_id = source_clip_id
    AND v.embedding_type = 'full_clip'
    AND v.summary_vector IS NOT NULL
  LIMIT 1
)
SELECT
  c.id,
  c.file_name,
  c.local_path,
  c.content_summary,
  c.content_tags,
  c.duration_seconds,
  c.content_category,
  (v.summary_vector <#> sv.summary_vector) * -1 as similarity_score
FROM clips c
JOIN vectors v ON c.id = v.clip_id
CROSS JOIN source_vector sv
WHERE c.user_id = user_id_filter
  AND c.id != source_clip_id
  AND v.embedding_type = 'full_clip'
  AND v.summary_vector IS NOT NULL
  AND (v.summary_vector <#> sv.summary_vector) * -1 >= similarity_threshold
ORDER BY v.summary_vector <#> sv.summary_vector
LIMIT match_count;
$$;