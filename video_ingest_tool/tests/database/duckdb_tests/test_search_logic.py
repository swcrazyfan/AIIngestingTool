import pytest
import duckdb
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock # For mocking

from video_ingest_tool.database.duckdb.crud import upsert_clip_data
from video_ingest_tool.database.duckdb.search_logic import fulltext_search_clips_duckdb, semantic_search_clips_duckdb
from video_ingest_tool.database.duckdb.schema import initialize_schema
from video_ingest_tool.database.duckdb.mappers import prepare_clip_data_for_db
from video_ingest_tool.database.duckdb.connection import get_db_connection
import openai # To allow mocking its structure if needed, though direct function mock is better
# Import the actual function that uses the openai client
from video_ingest_tool.embeddings import generate_embeddings # Removed prepare_embedding_content as it's not directly used in test logic after refactor

from video_ingest_tool.models import (
    VideoIngestOutput, FileInfo, VideoDetails, AnalysisDetails,
    VideoCodecDetails, VideoResolution, VideoColorDetails, VideoHDRDetails, VideoExposureDetails,
    CameraDetails, CameraFocalLength, CameraSettings, CameraLocation,
    ComprehensiveAIAnalysis, AIAnalysisSummary, AudioAnalysis, Transcript, Embeddings
)

# Re-using a simplified version of the helper from test_crud.py
def get_search_sample_vio(
    checksum_val: str,
    id_val: uuid.UUID,
    content_summary: str,
    file_name_override: Optional[str] = None,
    transcript_text: Optional[str] = None,
    summary_embedding_list: Optional[List[float]] = None,
    keyword_embedding_list: Optional[List[float]] = None
) -> VideoIngestOutput:
    now = datetime.now(timezone.utc)
    file_name = file_name_override or f"{checksum_val}.mp4"
    
    ai_summary = AIAnalysisSummary(overall=f"Overall summary for {file_name}", content_category="Test Search Category")
    audio_analysis = None
    if transcript_text:
        transcript = Transcript(full_text=transcript_text, segments=[])
        audio_analysis = AudioAnalysis(transcript=transcript)

    ai_analysis_obj = ComprehensiveAIAnalysis(summary=ai_summary, audio_analysis=audio_analysis)
    
    return VideoIngestOutput(
        id=str(id_val),
        file_info=FileInfo(
            local_path=f"/search/path/{file_name}",
            file_name=file_name,
            file_checksum=checksum_val,
            file_size_bytes=1024000,
            created_at=now,
            processed_at=now
        ),
        video=VideoDetails(
            duration_seconds=60.5, container="mp4",
            codec=VideoCodecDetails(name="h264", profile="High", level="4.1", bit_depth=8, chroma_subsampling="4:2:0", pixel_format="yuv420p"),
            resolution=VideoResolution(width=1920, height=1080, aspect_ratio="16:9"),
            color=VideoColorDetails(color_space="bt709", color_primaries="bt709", transfer_characteristics="bt709", matrix_coefficients="bt709", hdr=VideoHDRDetails(is_hdr=False)),
            exposure=VideoExposureDetails(warning=False, stops=0.0)
        ),
        camera=CameraDetails(
            make="SearchCam", model="S1", lens_model="LensX",
            focal_length=CameraFocalLength(), settings=CameraSettings(), location=CameraLocation()
        ),
        analysis=AnalysisDetails(
            content_summary=content_summary,
            content_tags=["search_test", content_summary.split(" ")[0].lower() if content_summary else "generic"],
            ai_analysis=ai_analysis_obj
        ),
        thumbnails=[],
        embeddings=Embeddings(
            summary_embedding=summary_embedding_list,
            keyword_embedding=keyword_embedding_list
        ) if summary_embedding_list or keyword_embedding_list else None
    )

@pytest.fixture(scope="function")
def db_conn_search():
    conn = get_db_connection(db_path=':memory:')
    try:
        conn.execute("SET TimeZone = 'UTC';")
        initialize_schema(conn, create_fts=False)
        yield conn
    finally:
        conn.close()

@pytest.fixture(scope="function")
def setup_search_data(db_conn_search: duckdb.DuckDBPyConnection, mocker: MagicMock) -> Dict[str, Any]:
    conn = db_conn_search
    inserted_data_info = {"ids": [], "embeddings_map": {}}
    embedding_dim = 1024

    # Create more distinct base vectors
    base_vectors = {
        "s_dogs":    [0.1, 0.11, 0.12, 0.13, 0.14],
        "k_dogs":    [0.15, 0.16, 0.17, 0.18, 0.19],
        "s_pasta":   [0.2, 0.21, 0.22, 0.23, 0.24],
        "k_pasta":   [0.25, 0.26, 0.27, 0.28, 0.29], # Target for pasta_query_keyword_text
        "s_mount":   [0.3, 0.31, 0.32, 0.33, 0.34],
        "k_mount":   [0.35, 0.36, 0.37, 0.38, 0.39],
        "s_duckdb":  [0.4, 0.41, 0.42, 0.43, 0.44],
        "k_duckdb":  [0.45, 0.46, 0.47, 0.48, 0.49],
        "s_cats":    [0.5, 0.51, 0.52, 0.53, 0.54], # Target for cats_query_summary_text
        "k_cats":    [0.55, 0.56, 0.57, 0.58, 0.59],
        "default":   [0.0, -0.1, 0.05, -0.05, 0.0]
    }

    # Pad vectors to embedding_dim
    for key in base_vectors:
        base_vec = base_vectors[key]
        padding_value = base_vec[-1] # Pad with the last value of the distinct part
        if len(base_vec) < embedding_dim:
            base_vectors[key].extend([padding_value] * (embedding_dim - len(base_vec)))
        elif len(base_vec) > embedding_dim: # Should not happen with embedding_dim=1024
             base_vectors[key] = base_vectors[key][:embedding_dim]


    mock_vector_map = {
        # search_001 ("dogs")
        "summary_for_dogs_video": base_vectors["s_dogs"],    # Target for dogs_query_summary_text
        "keywords_for_dogs_video": base_vectors["k_dogs"],

        # search_002 ("pasta")
        "summary_for_pasta_video": base_vectors["s_pasta"],
        "keywords_for_pasta_video": base_vectors["k_pasta"],  # Target for pasta_query_keyword_text

        # search_003 ("mountains")
        "summary_for_mountains_video": base_vectors["s_mount"],
        "keywords_for_mountains_video": base_vectors["k_mount"],

        # search_004 ("duckdb")
        "summary_for_duckdb_video": base_vectors["s_duckdb"],
        "keywords_for_duckdb_video": base_vectors["k_duckdb"],

        # search_005 ("cats")
        "summary_for_cats_video": base_vectors["s_cats"],     # Target for cats_query_summary_text
        "keywords_for_cats_video": base_vectors["k_cats"],
        
        # Query texts mapping to target vectors for exact matches in tests
        "pasta_query_summary_text": base_vectors["s_pasta"],   # Matches search_002 summary
        "pasta_query_keyword_text": base_vectors["k_pasta"],   # Matches search_002 keyword
        "dogs_query_summary_text": base_vectors["s_dogs"],    # Matches search_001 summary
        "cats_query_summary_text": base_vectors["s_cats"],     # Matches search_005 summary
        
        "default_mismatched_query_text": base_vectors["default"]
    }

    # Mock the response structure of openai.OpenAI().embeddings.create
    class MockEmbeddingData:
        def __init__(self, vector):
            self.embedding = vector

    class MockEmbeddingResponse:
        def __init__(self, vector):
            self.data = [MockEmbeddingData(vector)]

    # This side_effect function will be called by the actual generate_embeddings function
    # when client.embeddings.create is invoked.
    def mock_openai_embeddings_create_side_effect(input, model, encoding_format="float"):
        # 'input' here is the text content for embedding (e.g., "summary_for_dogs_video")
        vector = mock_vector_map.get(input, mock_vector_map["default_mismatched_query_text"])
        return MockEmbeddingResponse(vector)

    mock_openai_client = mocker.MagicMock(spec=openai.OpenAI) # Use spec for better mocking
    mock_openai_client.embeddings.create.side_effect = mock_openai_embeddings_create_side_effect
    mocker.patch('video_ingest_tool.embeddings.get_embedding_client', return_value=mock_openai_client)

    sample_data_defs = [
        {"id": uuid.uuid4(), "checksum": "search_001", "summary_text_key": "summary_for_dogs_video", "keyword_text_key": "keywords_for_dogs_video", "content_summary": "A video about happy dogs playing fetch.", "transcript": "The quick brown fox jumps over the lazy dog."},
        {"id": uuid.uuid4(), "checksum": "search_002", "summary_text_key": "summary_for_pasta_video", "keyword_text_key": "keywords_for_pasta_video", "content_summary": "Cooking tutorial for delicious pasta.", "transcript": "First, boil the water. Then add salt and pasta. Dogs are not involved."},
        {"id": uuid.uuid4(), "checksum": "search_003", "summary_text_key": "summary_for_mountains_video", "keyword_text_key": "keywords_for_mountains_video", "content_summary": "Exploring scenic mountains and happy trails.", "transcript": "The trail was long and winding, a beautiful dog accompanied us."},
        {"id": uuid.uuid4(), "checksum": "search_004", "summary_text_key": "summary_for_duckdb_video", "keyword_text_key": "keywords_for_duckdb_video", "content_summary": "Advanced DuckDB FTS features explained.", "transcript": "Full-text search in DuckDB is powerful for text analysis."},
        {"id": uuid.uuid4(), "checksum": "search_005", "summary_text_key": "summary_for_cats_video", "keyword_text_key": "keywords_for_cats_video", "content_summary": "A documentary about cats, not dogs.", "transcript": "Cats are independent creatures, unlike some other pets."}
    ]

    for data_def in sample_data_defs:
        summary_content_for_embedding = data_def["summary_text_key"]
        keyword_content_for_embedding = data_def["keyword_text_key"]

        # Call the actual generate_embeddings function from video_ingest_tool.embeddings
        # This function will internally use the mocked get_embedding_client -> mocked client.embeddings.create
        summary_emb, keyword_emb = generate_embeddings(
            summary_content=summary_content_for_embedding, 
            keyword_content=keyword_content_for_embedding
        )
        
        inserted_data_info["embeddings_map"][data_def["checksum"]] = {
            "summary_emb": summary_emb,
            "keyword_emb": keyword_emb
        }

        vio = get_search_sample_vio(
            checksum_val=data_def["checksum"],
            id_val=data_def["id"],
            content_summary=data_def["content_summary"],
            transcript_text=data_def["transcript"],
            summary_embedding_list=summary_emb,
            keyword_embedding_list=keyword_emb
        )
        
        prepared_data = prepare_clip_data_for_db(vio, None)
        assert prepared_data is not None, f"Failed to prepare data for {data_def['checksum']}"
        
        upsert_id = upsert_clip_data(prepared_data, conn)
        assert upsert_id == str(data_def["id"]), f"Upsert failed for {data_def['checksum']}"
        inserted_data_info["ids"].append(str(data_def["id"]))
        
    conn.commit()
    
    from video_ingest_tool.database.duckdb.schema import create_fts_index_for_clips
    create_fts_index_for_clips(conn)
    conn.commit()

    return inserted_data_info


def test_fulltext_search_clips_exact_match_summary(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results = fulltext_search_clips_duckdb("pasta", conn)
    assert len(results) >= 1
    assert any(r["file_checksum"] == "search_002" for r in results) 
    assert "fts_score" in results[0]
    assert results[0]["fts_score"] > 0

def test_fulltext_search_clips_match_transcript(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results = fulltext_search_clips_duckdb("brown fox", conn) 
    assert len(results) >= 1
    assert any(r["file_checksum"] == "search_001" for r in results)

def test_fulltext_search_clips_multiple_matches_and_ordering(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results = fulltext_search_clips_duckdb("happy", conn) 
    assert len(results) >= 2
    assert "fts_score" in results[0]
    if len(results) > 1:
        assert results[0]["fts_score"] >= results[1]["fts_score"]
    
    found_checksums = [r["file_checksum"] for r in results]
    assert "search_001" in found_checksums
    assert "search_003" in found_checksums

def test_fulltext_search_clips_limit_results(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results_limited = fulltext_search_clips_duckdb("happy", conn, match_count=1)
    assert len(results_limited) == 1
    
    results_more = fulltext_search_clips_duckdb("happy", conn, match_count=5)
    assert len(results_more) >= 2

def test_fulltext_search_no_results(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results = fulltext_search_clips_duckdb("nonexistenttermxyz", conn)
    assert len(results) == 0

def test_fulltext_search_empty_query(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    results = fulltext_search_clips_duckdb("", conn)
    assert len(results) == 0

def test_semantic_search_exact_match_summary_embedding(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    embeddings_map = setup_search_data["embeddings_map"]
    
    # Query with the embedding that corresponds to "dogs_query_summary_text"
    # Get the query embedding by calling the mocked embedding generation process
    # This ensures we use the same mechanism as data setup.
    # The 'generate_embeddings' function is mocked at the 'get_embedding_client' level.
    # We need a way to get a single query embedding.
    # The mock_vector_map was used to define the behavior of the mocked client.
    # We can access the expected vector directly from the map for the query.
    # Alternatively, if we had a direct mock for 'embed_query' equivalent, we'd use that.
    # Since generate_embeddings calls client.embeddings.create twice, we'll use the map.
    
    # The mock_vector_map is defined inside setup_search_data, so not directly accessible here.
    # However, the embeddings_map in setup_search_data *stores* the results of these mock calls.
    # For the query, we need the vector that *would be generated* for "dogs_query_summary_text".
    # This vector is already defined in the mock_vector_map within the fixture.
    # The tests should use the text keys that were defined in mock_vector_map for queries.
    
    # Let's use the text keys from mock_vector_map to get the query embeddings
    # The actual generate_embeddings will be called with these text keys.
    # The mock setup in the fixture will ensure these text keys map to the correct vectors.
    
    # Correct approach: The query embedding should be what the mocked `generate_embeddings`
    # would produce for the query text. The `embeddings_map` contains the *stored* embeddings.
    # For an exact match test, the query embedding should be identical to a stored one.
    
    query_summary_emb = embeddings_map["search_001"]["summary_emb"] # This is the vector for "summary_for_dogs_video"
                                                                # which is what "dogs_query_summary_text" maps to.
    
    # Sanity check: this query embedding should match what was stored for search_001's summary
    assert query_summary_emb == embeddings_map["search_001"]["summary_emb"]

    results_summary_only = semantic_search_clips_duckdb(
        conn=conn,
        query_summary_embedding=query_summary_emb,
        query_keyword_embedding=None, 
        summary_weight=1.0, 
        keyword_weight=0.0,
        match_count=1,
        similarity_threshold=0.95 
    )

    assert len(results_summary_only) >= 1, "Should find at least one match with summary_weight=1.0"
    
    found_clip = results_summary_only[0]
    assert found_clip["file_checksum"] == "search_001" 
    assert "combined_similarity_score" in found_clip
    assert found_clip["combined_similarity_score"] == pytest.approx(1.0)


def test_semantic_search_no_match(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    # Call generate_embeddings with a text key that the mock_vector_map in setup_search_data
    # will resolve to the "default_mismatched_query_text" vector.
    # The generate_embeddings function is mocked via get_embedding_client.
    summary_emb_diff, _ = generate_embeddings(summary_content="text_key_for_default_mismatch", keyword_content="any_keyword")
    query_different_emb = summary_emb_diff


    results = semantic_search_clips_duckdb(
        conn=conn,
        query_summary_embedding=query_different_emb,
        summary_weight=1.0, 
        keyword_weight=0.0,
        match_count=1,
        similarity_threshold=0.1 
    )
    assert len(results) == 0, "Should find no matches for a very different embedding"


def test_semantic_search_keyword_embedding_match(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    embeddings_map = setup_search_data["embeddings_map"]

    # For an exact match, the query embedding should be identical to what's stored.
    # "pasta_query_keyword_text" in mock_vector_map produces the same vector as
    # "keywords_for_pasta_video" which is stored for "search_002".
    query_keyword_emb = embeddings_map["search_002"]["keyword_emb"]
    
    # Sanity check
    assert query_keyword_emb == embeddings_map["search_002"]["keyword_emb"]

    results = semantic_search_clips_duckdb(
        conn=conn,
        query_keyword_embedding=query_keyword_emb,
        summary_weight=0.0, 
        keyword_weight=1.0, 
        match_count=1,
        similarity_threshold=0.95
    )
    assert len(results) == 1
    found_clip = results[0]

    assert found_clip["file_checksum"] == "search_002"
    assert found_clip["combined_similarity_score"] == pytest.approx(1.0)

# TODO: Add tests for hybrid_search_clips_duckdb
# TODO: Add tests for search_transcripts_duckdb (if its logic diverges from fulltext_search_clips_duckdb)
# Hybrid Search Tests
from video_ingest_tool.database.duckdb.search_logic import hybrid_search_clips_duckdb

def test_hybrid_search_fts_and_summary_semantic(db_conn_search: duckdb.DuckDBPyConnection, setup_search_data: Dict[str, Any]):
    conn = db_conn_search
    embeddings_map = setup_search_data["embeddings_map"]

    query_text = "pasta" # Should match search_002 via FTS
    # Query for search_002's summary embedding
    query_summary_emb = embeddings_map["search_002"]["summary_emb"] 

    results = hybrid_search_clips_duckdb(
        query_text=query_text,
        query_summary_embedding=query_summary_emb,
        query_keyword_embedding=None, # No keyword component for this test
        conn=conn,
        match_count=5,
        fts_weight=0.5,
        summary_weight=0.5,
        keyword_weight=0.0,
        rrf_k=60
    )

    assert len(results) > 0, "Hybrid search should return results"
    
    found_search_002 = False
    for res in results:
        assert "rrf_score" in res
        assert res["rrf_score"] > 0
        if res["file_checksum"] == "search_002":
            found_search_002 = True
            # Check if both FTS and semantic contributed (presence of debug scores)
            assert "fts_score_debug" in res or "summary_semantic_score_debug" in res
            # For this specific case, search_002 should have high scores from both
            if "fts_score_debug" in res:
                 assert res["fts_score_debug"] > 0
            if "summary_semantic_score_debug" in res:
                 assert res["summary_semantic_score_debug"] > 0.9 # Expecting near 1.0

    assert found_search_002, "search_002 (pasta) should be in hybrid results"

    # Check if results are sorted by rrf_score
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["rrf_score"] >= results[i+1]["rrf_score"]