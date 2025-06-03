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
        "c.created_at", "c.duration_seconds", "c.primary_thumbnail_path", "c.content_category"
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
    summary_weight: float = 0.5, # Default weight for summary embedding
    keyword_weight: float = 0.5, # Default weight for keyword embedding
    similarity_threshold: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Performs a semantic search on the 'app_data.clips' table using cosine similarity
    on HNSW indexed TEXT embedding columns (summary_embedding, keyword_embedding).
    This function is intended for querying with externally generated text embeddings.
    """
    if not query_summary_embedding and not query_keyword_embedding:
        logger.warning("No query embeddings (summary or keyword) provided for semantic_search_clips_duckdb.")
        return []

    logger.info(
        "Performing text-based semantic search.",
        match_count=match_count,
        threshold=similarity_threshold,
        summary_weight=summary_weight,
        keyword_weight=keyword_weight
    )

    select_columns = [
        "c.id", "c.file_name", "c.file_checksum", "c.content_summary",
        "c.transcript_preview", "c.created_at", "c.duration_seconds",
        "c.primary_thumbnail_path"
    ]
    select_columns_str = ", ".join(select_columns)

    base_params = []
    score_calculations = []

    if query_summary_embedding and summary_weight > 0:
        score_calculations.append(f"{summary_weight} * array_cosine_similarity(c.summary_embedding, ?::FLOAT[1024])")
        base_params.append(query_summary_embedding)

    if query_keyword_embedding and keyword_weight > 0:
        score_calculations.append(f"{keyword_weight} * array_cosine_similarity(c.keyword_embedding, ?::FLOAT[1024])")
        base_params.append(query_keyword_embedding)

    if not score_calculations: # Should not happen if initial check passed, but good for safety
        logger.warning("No active score calculations for text semantic search.")
        return []

    combined_score_expr = " + ".join(score_calculations)
    
    params_for_score_expr = list(base_params)

    sql_query = f"""
    WITH semantic_scores AS (
        SELECT
            c.id as clip_id,
            ({combined_score_expr}) AS combined_similarity_score
        FROM
            app_data.clips AS c
        WHERE
            ({combined_score_expr}) IS NOT NULL AND ({combined_score_expr}) >= ?
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

    final_params = []
    final_params.extend(params_for_score_expr) # For SELECT in CTE
    final_params.extend(params_for_score_expr) # For IS NOT NULL in WHERE
    final_params.extend(params_for_score_expr) # For >= ? in WHERE
    final_params.append(similarity_threshold)
    final_params.append(match_count)

    try:
        results = conn.execute(sql_query, final_params).fetchall()
        
        if not results:
            logger.info("No text semantic search results found.")
            return []

        column_names = [desc[0] for desc in conn.description]
        clips = [dict(zip(column_names, row)) for row in results]
        
        logger.info(f"Found {len(clips)} text semantic search results.")
        return clips

    except Exception as e:
        logger.error(f"Error during text-only semantic_search_clips_duckdb: {e}", exc_info=True)
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


def find_similar_clips_duckdb(
    source_clip_id: str,
    conn: duckdb.DuckDBPyConnection,
    mode: str = "combined",
    match_count: int = 5,
    text_summary_weight: float = 0.5,    # Weight for summary_embedding in "text" or "combined"
    text_keyword_weight: float = 0.5,    # Weight for keyword_embedding in "text" or "combined"
    visual_thumb1_weight: float = 0.4,   # Weight for thumbnail_1_embedding in "visual" or "combined"
    visual_thumb2_weight: float = 0.3,   # Weight for thumbnail_2_embedding in "visual" or "combined"
    visual_thumb3_weight: float = 0.3,   # Weight for thumbnail_3_embedding in "visual" or "combined"
    combined_mode_text_factor: float = 0.6, # Overall factor for text features in "combined" mode
    combined_mode_visual_factor: float = 0.4, # Overall factor for visual features in "combined" mode
    similarity_threshold: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Finds clips similar to a given source clip ID based on their embeddings,
    supporting different modes: "text", "visual", or "combined".
    """
    logger.info("Finding similar clips.", source_clip_id=source_clip_id, mode=mode, match_count=match_count)

    if mode not in ["text", "visual", "combined"]:
        logger.error("Invalid mode for find_similar_clips_duckdb.", mode=mode)
        return []

    try:
        source_clip_query = """
        SELECT summary_embedding, keyword_embedding,
               thumbnail_1_embedding, thumbnail_2_embedding, thumbnail_3_embedding
        FROM app_data.clips WHERE id = ?;
        """
        source_embeddings_row = conn.execute(source_clip_query, [source_clip_id]).fetchone()

        if not source_embeddings_row:
            logger.warning("Source clip not found for similarity search.", source_clip_id=source_clip_id)
            return []

        source_summary_emb, source_keyword_emb, source_thumb1_emb, source_thumb2_emb, source_thumb3_emb = source_embeddings_row

        score_calculations = []
        base_params = []
        
        # --- Text Mode ---
        if mode == "text":
            if source_summary_emb:
                score_calculations.append(f"{text_summary_weight} * array_cosine_similarity(c.summary_embedding, ?::FLOAT[1024])")
                base_params.append(source_summary_emb)
            if source_keyword_emb:
                score_calculations.append(f"{text_keyword_weight} * array_cosine_similarity(c.keyword_embedding, ?::FLOAT[1024])")
                base_params.append(source_keyword_emb)
            if not score_calculations:
                logger.warning("Source clip has no text embeddings for 'text' mode similarity search.", source_clip_id=source_clip_id)
                return []

        # --- Visual Mode ---
        elif mode == "visual":
            # Improved cross-slot visual similarity comparison
            # Instead of only comparing same slots, we'll find the best match across all available slots
            source_visual_embeddings = []
            if source_thumb1_emb:
                source_visual_embeddings.append((source_thumb1_emb, visual_thumb1_weight, "thumbnail_1_embedding"))
            if source_thumb2_emb:
                source_visual_embeddings.append((source_thumb2_emb, visual_thumb2_weight, "thumbnail_2_embedding"))
            if source_thumb3_emb:
                source_visual_embeddings.append((source_thumb3_emb, visual_thumb3_weight, "thumbnail_3_embedding"))
            
            if not source_visual_embeddings:
                logger.warning("Source clip has no visual embeddings for 'visual' mode similarity search.", source_clip_id=source_clip_id)
                return []
            
            # Build cross-slot comparison: for each source embedding, compare against all target slots
            # Take the maximum similarity score across all combinations
            cross_slot_comparisons = []
            for source_emb, source_weight, source_slot in source_visual_embeddings:
                slot_comparisons = []
                
                # Compare this source embedding against all possible target slots
                slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_1_embedding, ?::FLOAT[1152]), 0)")
                base_params.append(source_emb)
                slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_2_embedding, ?::FLOAT[1152]), 0)")
                base_params.append(source_emb)
                slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_3_embedding, ?::FLOAT[1152]), 0)")
                base_params.append(source_emb)
                
                # Take the maximum similarity across all target slots for this source embedding
                max_similarity_expr = f"GREATEST({', '.join(slot_comparisons)})"
                cross_slot_comparisons.append(f"{source_weight} * {max_similarity_expr}")
            
            # Average the similarities from all source embeddings
            if len(cross_slot_comparisons) == 1:
                score_calculations.append(cross_slot_comparisons[0])
            else:
                score_calculations.append(f"({' + '.join(cross_slot_comparisons)}) / {len(cross_slot_comparisons)}")

        # --- Combined Mode ---
        elif mode == "combined":
            text_scores_parts = []
            visual_scores_parts = []
            
            # Text part
            if source_summary_emb:
                text_scores_parts.append(f"{text_summary_weight} * array_cosine_similarity(c.summary_embedding, ?::FLOAT[1024])")
                base_params.append(source_summary_emb)
            if source_keyword_emb:
                text_scores_parts.append(f"{text_keyword_weight} * array_cosine_similarity(c.keyword_embedding, ?::FLOAT[1024])")
                base_params.append(source_keyword_emb)
            
            # Visual part - use cross-slot comparison like in visual mode
            source_visual_embeddings = []
            if source_thumb1_emb:
                source_visual_embeddings.append((source_thumb1_emb, visual_thumb1_weight, "thumbnail_1_embedding"))
            if source_thumb2_emb:
                source_visual_embeddings.append((source_thumb2_emb, visual_thumb2_weight, "thumbnail_2_embedding"))
            if source_thumb3_emb:
                source_visual_embeddings.append((source_thumb3_emb, visual_thumb3_weight, "thumbnail_3_embedding"))
            
            if source_visual_embeddings:
                # Build cross-slot comparison for visual similarity in combined mode
                cross_slot_comparisons = []
                for source_emb, source_weight, source_slot in source_visual_embeddings:
                    slot_comparisons = []
                    
                    # Compare this source embedding against all possible target slots
                    slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_1_embedding, ?::FLOAT[1152]), 0)")
                    base_params.append(source_emb)
                    slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_2_embedding, ?::FLOAT[1152]), 0)")
                    base_params.append(source_emb)
                    slot_comparisons.append(f"COALESCE(array_cosine_similarity(c.thumbnail_3_embedding, ?::FLOAT[1152]), 0)")
                    base_params.append(source_emb)
                    
                    # Take the maximum similarity across all target slots for this source embedding
                    max_similarity_expr = f"GREATEST({', '.join(slot_comparisons)})"
                    cross_slot_comparisons.append(f"{source_weight} * {max_similarity_expr}")
                
                # Average the similarities from all source embeddings for visual component
                if len(cross_slot_comparisons) == 1:
                    visual_component = cross_slot_comparisons[0]
                else:
                    visual_component = f"({' + '.join(cross_slot_comparisons)}) / {len(cross_slot_comparisons)}"
                
                visual_scores_parts.append(visual_component)

            if text_scores_parts:
                score_calculations.append(f"{combined_mode_text_factor} * ({' + '.join(text_scores_parts)})")
            if visual_scores_parts:
                score_calculations.append(f"{combined_mode_visual_factor} * ({' + '.join(visual_scores_parts)})")
            
            if not score_calculations:
                logger.warning("Source clip has no text or visual embeddings for 'combined' mode similarity search.", source_clip_id=source_clip_id)
                return []
        
        # --- Build and Execute Query ---
        combined_score_expr = " + ".join(score_calculations)
        params_for_score_expr = list(base_params)

        select_columns_list = [
            "c.id", "c.file_name", "c.file_checksum", "c.content_summary",
            "c.transcript_preview", "c.created_at", "c.duration_seconds",
            "c.primary_thumbnail_path"
        ]
        select_columns_str = ", ".join(select_columns_list)

        sql_query = f"""
        WITH semantic_scores AS (
            SELECT
                c.id as clip_id,
                ({combined_score_expr}) AS combined_similarity_score
            FROM
                app_data.clips AS c
            WHERE
                c.id != ? AND -- Exclude source clip ID early
                ({combined_score_expr}) IS NOT NULL AND ({combined_score_expr}) >= ?
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
            ?; -- Limit to the desired match_count directly
        """
        
        final_params = []
        final_params.extend(params_for_score_expr)  # For SELECT in CTE
        final_params.append(source_clip_id)         # For c.id != ?
        final_params.extend(params_for_score_expr)  # For IS NOT NULL in WHERE
        final_params.extend(params_for_score_expr)  # For >= threshold in WHERE
        final_params.append(similarity_threshold)
        final_params.append(match_count)           # SQL LIMIT is now match_count

        results = conn.execute(sql_query, final_params).fetchall()
        
        if not results:
            logger.info("No similar clips found.", source_clip_id=source_clip_id, mode=mode)
            return []

        column_names = [desc[0] for desc in conn.description]
        similar_clips = [dict(zip(column_names, row)) for row in results] # No Python slicing needed
        
        logger.info("Found similar clips.", count=len(similar_clips), source_clip_id=source_clip_id, mode=mode)
        return similar_clips

    except Exception as e:
        logger.error("Error during find_similar_clips_duckdb.", source_clip_id=source_clip_id, mode=mode, error=str(e), exc_info=True)
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