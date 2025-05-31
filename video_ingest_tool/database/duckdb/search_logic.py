import duckdb
from typing import List, Dict, Any, Optional, Tuple # Added Tuple for type hint
import structlog # Changed from logging
import duckdb # Ensure duckdb is imported if not already for type hints

logger = structlog.get_logger(__name__) # Changed to structlog

# According to test_schema.py and DuckDB FTS behavior for schema-qualified tables,
# the FTS function is called as fts_<schema_name>_<table_name>.match_bm25()
FTS_FUNCTION_PREFIX = "fts_app_data_clips"

def fulltext_search_clips_duckdb(
    query_text: str,
    conn: duckdb.DuckDBPyConnection,
    match_count: int = 10
) -> List[Dict[str, Any]]:
    """
    Performs a full-text search on the 'app_data.clips' table using DuckDB's FTS.

    Args:
        query_text: The text to search for.
        conn: Active DuckDB connection.
        match_count: The maximum number of matches to return.

    Returns:
        A list of dictionaries, where each dictionary represents a matching clip
        and includes selected clip details and the FTS score.
    """
    if not query_text:
        return []

    logger.info(f"Performing FTS for query: '{query_text}', limit: {match_count}")

    select_columns = [
        "c.id", "c.file_name", "c.file_checksum", "c.content_summary", "c.transcript_preview",
        "c.created_at", "c.duration_seconds", "c.primary_thumbnail_path"
    ]
    select_columns_str = ", ".join(select_columns)

    sql_query = f"""
    WITH scored_clips AS (
        SELECT
            c.id AS clip_id_for_join, 
            {FTS_FUNCTION_PREFIX}.match_bm25(c.id, ?) AS fts_score
        FROM
            app_data.clips AS c
    )
    SELECT
        {select_columns_str},
        sc.fts_score
    FROM
        app_data.clips AS c
    JOIN
        scored_clips sc ON c.id = sc.clip_id_for_join
    WHERE
        sc.fts_score IS NOT NULL AND sc.fts_score > 0 
    ORDER BY
        sc.fts_score DESC
    LIMIT
        ?;
    """

    try:
        results = conn.execute(sql_query, [query_text, match_count]).fetchall()
        
        if not results:
            logger.info(f"No FTS results found for query: '{query_text}'")
            return []

        column_names = [desc[0] for desc in conn.description]
        clips = [dict(zip(column_names, row)) for row in results]
        
        logger.info(f"Found {len(clips)} FTS results for query: '{query_text}'")
        return clips

    except Exception as e:
        logger.error(f"Error during fulltext_search_clips_duckdb for query '{query_text}': {e}", exc_info=True)
        return []

def semantic_search_clips_duckdb(
    conn: duckdb.DuckDBPyConnection,
    query_summary_embedding: Optional[List[float]] = None,
    query_keyword_embedding: Optional[List[float]] = None,
    match_count: int = 10,
    summary_weight: float = 0.5,
    keyword_weight: float = 0.5,
    similarity_threshold: float = 0.1 
) -> List[Dict[str, Any]]:
    """
    Performs a semantic search on the 'app_data.clips' table using cosine similarity
    on HNSW indexed embedding columns.
    """
    if not any([query_summary_embedding, query_keyword_embedding]): 
        logger.warning("No query embeddings provided for semantic search.")
        return []

    logger.info(f"Performing semantic search, match_count={match_count}, threshold={similarity_threshold}")

    select_columns = [
        "c.id", "c.file_name", "c.file_checksum", "c.content_summary",
        "c.transcript_preview", "c.created_at", "c.duration_seconds",
        "c.primary_thumbnail_path", "c.keyword_embedding" 
    ]
    select_columns_str = ", ".join(select_columns)
    
    base_params = [] 
    score_calculations = []
    
    if query_summary_embedding:
        score_calculations.append(f"{summary_weight} * array_cosine_similarity(c.summary_embedding, ?::FLOAT[1024])")
        base_params.append(query_summary_embedding)
        
    if query_keyword_embedding:
        score_calculations.append(f"{keyword_weight} * array_cosine_similarity(c.keyword_embedding, ?::FLOAT[1024])")
        base_params.append(query_keyword_embedding)

    if not score_calculations: 
        return []

    combined_score_expr = " + ".join(score_calculations)
    
    sql_query = f"""
    WITH semantic_scores AS (
        SELECT
            c.id as clip_id,
            ({combined_score_expr}) AS combined_similarity_score
        FROM
            app_data.clips AS c
        WHERE
            ({combined_score_expr}) IS NOT NULL
            AND ({combined_score_expr}) >= ?
    )
    SELECT
        {select_columns_str},
        ss.combined_similarity_score
    FROM
        app_data.clips AS c
    JOIN
        semantic_scores ss ON c.id = ss.clip_id
    ORDER BY
        ss.combined_similarity_score DESC
    LIMIT
        ?;
    """
    final_params = base_params * 3 
    final_params.append(similarity_threshold)
    final_params.append(match_count)

    try:
        results = conn.execute(sql_query, final_params).fetchall()
        
        if not results:
            logger.info("No semantic search results found.")
            return []

        column_names = [desc[0] for desc in conn.description]
        clips = [dict(zip(column_names, row)) for row in results]
        
        logger.info(f"Found {len(clips)} semantic search results.")
        return clips

    except Exception as e:
        logger.error(f"Error during semantic_search_clips_duckdb: {e}", exc_info=True)
        return []

def hybrid_search_clips_duckdb(
    query_text: str,
    query_summary_embedding: Optional[List[float]],
    query_keyword_embedding: Optional[List[float]],
    conn: duckdb.DuckDBPyConnection,
    match_count: int = 10,
    fts_weight: float = 0.4,
    summary_weight: float = 0.3,
    keyword_weight: float = 0.3,
    rrf_k: int = 60, 
    similarity_threshold: float = 0.1 
) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search combining FTS and semantic search results using RRF.
    """
    logger.info("Performing hybrid search.", query_text=query_text)

    # 1. Perform FTS
    fts_results = fulltext_search_clips_duckdb(query_text, conn, match_count=match_count * 2) 
    logger.info("Hybrid search: FTS results.", count=len(fts_results))
    if fts_results:
        logger.debug("Hybrid search: FTS top result.", id=fts_results[0].get('id'), score=fts_results[0].get('fts_score'))

    # 2. Perform Semantic Search (summary)
    semantic_summary_results = []
    if query_summary_embedding and summary_weight > 0:
        logger.debug("Hybrid search: Performing semantic summary search.")
        semantic_summary_results = semantic_search_clips_duckdb(
            conn=conn,
            query_summary_embedding=query_summary_embedding,
            match_count=match_count * 2, 
            summary_weight=1.0, 
            keyword_weight=0.0,
            similarity_threshold=similarity_threshold
        )
    logger.info("Hybrid search: Semantic summary results.", count=len(semantic_summary_results))
    if semantic_summary_results:
        logger.debug("Hybrid search: Semantic summary top result.", id=semantic_summary_results[0].get('id'), score=semantic_summary_results[0].get('combined_similarity_score'))

    # 3. Perform Semantic Search (keyword)
    semantic_keyword_results = []
    if query_keyword_embedding and keyword_weight > 0:
        logger.debug("Hybrid search: Performing semantic keyword search.")
        semantic_keyword_results = semantic_search_clips_duckdb(
            conn=conn,
            query_keyword_embedding=query_keyword_embedding,
            match_count=match_count * 2, 
            summary_weight=0.0,
            keyword_weight=1.0, 
            similarity_threshold=similarity_threshold
        )
    logger.info("Hybrid search: Semantic keyword results.", count=len(semantic_keyword_results))
    if semantic_keyword_results:
        logger.debug("Hybrid search: Semantic keyword top result.", id=semantic_keyword_results[0].get('id'), score=semantic_keyword_results[0].get('combined_similarity_score'))

    # 4. Combine results using Reciprocal Rank Fusion (RRF)
    
    ranked_lists: Dict[str, Dict[Any, Tuple[int, float]]] = {} 
    if fts_results:
        fts_results.sort(key=lambda x: x.get('fts_score', 0.0), reverse=True)
        ranked_lists['fts'] = {res['id']: (idx + 1, res.get('fts_score', 0.0)) for idx, res in enumerate(fts_results)}
        
    if semantic_summary_results:
        semantic_summary_results.sort(key=lambda x: x.get('combined_similarity_score', 0.0), reverse=True)
        ranked_lists['summary_semantic'] = {res['id']: (idx + 1, res.get('combined_similarity_score', 0.0)) for idx, res in enumerate(semantic_summary_results)}

    if semantic_keyword_results:
        semantic_keyword_results.sort(key=lambda x: x.get('combined_similarity_score', 0.0), reverse=True)
        ranked_lists['keyword_semantic'] = {res['id']: (idx + 1, res.get('combined_similarity_score', 0.0)) for idx, res in enumerate(semantic_keyword_results)}

    rrf_scores: Dict[Any, float] = {} 
    all_doc_ids: set[Any] = set() 
    if 'fts' in ranked_lists: all_doc_ids.update(ranked_lists['fts'].keys())
    if 'summary_semantic' in ranked_lists: all_doc_ids.update(ranked_lists['summary_semantic'].keys())
    if 'keyword_semantic' in ranked_lists: all_doc_ids.update(ranked_lists['keyword_semantic'].keys())

    for doc_id_uuid in all_doc_ids: 
        score = 0.0
        if 'fts' in ranked_lists and doc_id_uuid in ranked_lists['fts']:
            rank = ranked_lists['fts'][doc_id_uuid][0]
            score += fts_weight / (rrf_k + rank)
        
        if 'summary_semantic' in ranked_lists and doc_id_uuid in ranked_lists['summary_semantic']:
            rank = ranked_lists['summary_semantic'][doc_id_uuid][0]
            score += summary_weight / (rrf_k + rank)

        if 'keyword_semantic' in ranked_lists and doc_id_uuid in ranked_lists['keyword_semantic']:
            rank = ranked_lists['keyword_semantic'][doc_id_uuid][0]
            score += keyword_weight / (rrf_k + rank)
        
        if score > 0:
            rrf_scores[doc_id_uuid] = score 

    sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x_uuid: rrf_scores[x_uuid], reverse=True) 
    logger.info("Hybrid search: RRF scores calculated.", count=len(rrf_scores))
    if sorted_doc_ids:
        top_rrf_id = sorted_doc_ids[0]
        logger.debug("Hybrid search: Top RRF document.", id=top_rrf_id, score=rrf_scores[top_rrf_id])
    else:
        logger.info("Hybrid search: No documents after RRF scoring.")
        return [] 
    
    final_results = []
    ids_to_fetch = sorted_doc_ids[:match_count] 
    if not ids_to_fetch: 
        logger.info("Hybrid search: No IDs to fetch after RRF and match_count limit.")
        return []
        
    placeholders = ', '.join(['?'] * len(ids_to_fetch))
    
    select_columns_final = [
        "id", "file_name", "file_checksum", "content_summary", "transcript_preview",
        "created_at", "duration_seconds", "primary_thumbnail_path"
    ]
    select_str_final = ", ".join(select_columns_final)

    sql_final_fetch = f"""
    SELECT {select_str_final}
    FROM app_data.clips
    WHERE id IN ({placeholders})
    """
    
    try:
        db_results = conn.execute(sql_final_fetch, ids_to_fetch).fetchall()
        
        column_names = [desc[0] for desc in conn.description]
        results_map = {row_dict['id']: row_dict for row_dict in [dict(zip(column_names, row)) for row in db_results]}

        for doc_id_uuid in ids_to_fetch: 
            if doc_id_uuid in results_map: 
                clip_data = results_map[doc_id_uuid]
                clip_data['rrf_score'] = rrf_scores[doc_id_uuid] 
                
                if 'fts' in ranked_lists and doc_id_uuid in ranked_lists['fts']:
                    clip_data['fts_score_debug'] = ranked_lists['fts'][doc_id_uuid][1]
                if 'summary_semantic' in ranked_lists and doc_id_uuid in ranked_lists['summary_semantic']:
                    clip_data['summary_semantic_score_debug'] = ranked_lists['summary_semantic'][doc_id_uuid][1]
                if 'keyword_semantic' in ranked_lists and doc_id_uuid in ranked_lists['keyword_semantic']:
                    clip_data['keyword_semantic_score_debug'] = ranked_lists['keyword_semantic'][doc_id_uuid][1]
                final_results.append(clip_data)
            else: 
                 logger.warning("Document ID from RRF sort not found in DB results for final fetch.", doc_id=doc_id_uuid)

        logger.info("Hybrid search returned results.", count=len(final_results))
        return final_results

    except Exception as e:
        logger.error("Error during final fetch for hybrid search.", error=str(e), exc_info=True)
        return []


# Placeholder for search_transcripts_duckdb (will be similar to fulltext_search_clips_duckdb but might focus on transcript field or have different scoring)
def search_transcripts_duckdb(
    query_text: str,
    conn: duckdb.DuckDBPyConnection,
    match_count: int = 10
) -> List[Dict[str, Any]]:
    logger.warning("search_transcripts_duckdb is not yet implemented, using fulltext_search_clips_duckdb as a stand-in.")
    # For now, can alias or re-implement if specific transcript focus is needed.
    # The FTS index already includes transcript_preview and searchable_content (which includes full_transcript).
    return fulltext_search_clips_duckdb(query_text, conn, match_count)