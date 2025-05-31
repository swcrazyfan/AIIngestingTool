import pytest
import duckdb
import uuid
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from video_ingest_tool.database.duckdb.crud import upsert_clip_data
from video_ingest_tool.database.duckdb.search_logic import (
    semantic_search_clips_duckdb,
    hybrid_search_clips_duckdb,
    fulltext_search_clips_duckdb,
    find_similar_clips_duckdb # Add the import here
)
from video_ingest_tool.database.duckdb.schema import initialize_schema
from video_ingest_tool.database.duckdb.mappers import prepare_clip_data_for_db
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.embeddings import generate_embeddings # Using the real function
from video_ingest_tool.config import settings # To check for API key

from video_ingest_tool.models import (
    VideoIngestOutput, FileInfo, VideoDetails, AnalysisDetails,
    VideoCodecDetails, VideoResolution, VideoColorDetails, VideoHDRDetails, VideoExposureDetails,
    CameraDetails, CameraFocalLength, CameraSettings, CameraLocation,
    ComprehensiveAIAnalysis, AIAnalysisSummary, Transcript, Embeddings
)

# Helper to create simplified VideoIngestOutput for testing
def get_integration_test_vio(
    checksum_val: str,
    id_val: uuid.UUID,
    summary_text: str, # Used for content_summary and summary embedding
    keyword_text: str, # Used for keyword embedding
    summary_embedding_list: Optional[List[float]] = None,
    keyword_embedding_list: Optional[List[float]] = None
) -> VideoIngestOutput:
    now = datetime.now(timezone.utc)
    file_name = f"{checksum_val}_integration.mp4"
    
    ai_summary = AIAnalysisSummary(overall=summary_text, content_category="Integration Test")
    ai_analysis_obj = ComprehensiveAIAnalysis(summary=ai_summary)
    
    return VideoIngestOutput(
        id=str(id_val),
        file_info=FileInfo(
            local_path=f"/integration/test/{file_name}",
            file_name=file_name,
            file_checksum=checksum_val,
            file_size_bytes=1000,
            created_at=now,
            processed_at=now
        ),
        video=VideoDetails( # Minimal video details
            duration_seconds=10.0, container="mp4",
            codec=VideoCodecDetails(name="h264"), resolution=VideoResolution(width=1280, height=720),
            color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)), exposure=VideoExposureDetails()
        ),
        camera=CameraDetails( # Provide default instances for required nested models
            focal_length=CameraFocalLength(),
            settings=CameraSettings(),
            location=CameraLocation()
        ),
        analysis=AnalysisDetails(
            content_summary=summary_text,
            content_tags=["integration_test", summary_text.split(" ")[0].lower() if summary_text else "generic"],
            ai_analysis=ai_analysis_obj
        ),
        thumbnails=[],
        embeddings=Embeddings(
            summary_embedding=summary_embedding_list,
            keyword_embedding=keyword_embedding_list
        ) if summary_embedding_list or keyword_embedding_list else None
    )

@pytest.fixture(scope="module")
def integration_db_conn():
    from dotenv import load_dotenv
    load_dotenv() # Load .env file for environment variables

    # Check for API key before running integration tests that need it
    # Assuming settings.DEEPINFRA_API_KEY or similar is configured
    # settings object might pick up from env vars loaded by load_dotenv()
    # or os.getenv will pick it up directly.
    api_key = os.getenv("DEEPINFRA_API_KEY") or getattr(settings, "DEEPINFRA_API_KEY", None)
    if not api_key:
        pytest.skip("DEEPINFRA_API_KEY not found in environment or settings, skipping integration tests.")

    conn = get_db_connection(db_path=':memory:')
    try:
        conn.execute("SET TimeZone = 'UTC';")
        initialize_schema(conn, create_fts=True) # Ensure FTS index is also created
        yield conn
    finally:
        conn.close()

@pytest.mark.integration # Mark as an integration test
def test_semantic_search_with_real_embeddings(integration_db_conn: duckdb.DuckDBPyConnection):
    conn = integration_db_conn

    doc1_summary_text = "A sunny day at the beach with blue waves."
    doc1_keyword_text = "beach, sun, ocean, holiday"
    doc2_summary_text = "A delicious recipe for homemade apple pie."
    doc2_keyword_text = "apple pie, baking, dessert, recipe"

    # 1. Generate real embeddings and prepare data
    doc1_id = uuid.uuid4()
    doc1_summary_emb, doc1_keyword_emb = generate_embeddings(
        summary_content=doc1_summary_text, 
        keyword_content=doc1_keyword_text
    )
    vio1 = get_integration_test_vio(
        "integ_doc_001", doc1_id, doc1_summary_text, doc1_keyword_text, 
        doc1_summary_emb, doc1_keyword_emb
    )
    prepared_data1 = prepare_clip_data_for_db(vio1, None)
    upsert_clip_data(prepared_data1, conn)

    doc2_id = uuid.uuid4()
    doc2_summary_emb, doc2_keyword_emb = generate_embeddings(
        summary_content=doc2_summary_text,
        keyword_content=doc2_keyword_text
    )
    vio2 = get_integration_test_vio(
        "integ_doc_002", doc2_id, doc2_summary_text, doc2_keyword_text,
        doc2_summary_emb, doc2_keyword_emb
    )
    prepared_data2 = prepare_clip_data_for_db(vio2, None)
    upsert_clip_data(prepared_data2, conn)
    
    conn.commit()

    # 2. Perform semantic search for one of the documents
    query_summary_text = "A day at the seaside with clear water." # Similar to doc1
    
    # Generate query embedding using the real embedding function
    query_summary_emb_real, _ = generate_embeddings(summary_content=query_summary_text, keyword_content="")

    results = semantic_search_clips_duckdb(
        conn=conn,
        query_summary_embedding=query_summary_emb_real,
        match_count=1,
        summary_weight=1.0,
        keyword_weight=0.0,
        similarity_threshold=0.5 # Adjust threshold as real embeddings might not be perfect matches
    )

    assert len(results) > 0, "Semantic search with real embeddings should find a match."
    
    # We expect doc1 to be the top match
    found_clip = results[0]
    assert found_clip["file_checksum"] == "integ_doc_001"
    assert "combined_similarity_score" in found_clip
    # Score assertion might be tricky with real embeddings, focus on correct document retrieval
    assert found_clip["combined_similarity_score"] > 0.5 

    print(f"Found clip: {found_clip['file_checksum']} with score: {found_clip['combined_similarity_score']}")
    print(f"Expected integ_doc_001 (ID: {doc1_id}), Found ID: {found_clip['id']}")

# TODO: Add integration test for hybrid_search_clips_duckdb with real embeddings
# TODO: Add integration test for fulltext_search_clips_duckdb (though it doesn't use embeddings)


# --- Integration Tests for find_similar_clips_duckdb ---

# Helper to create VIO with all embedding types for find_similar_clips tests
def get_full_integration_test_vio(
    checksum_val: str,
    id_val: uuid.UUID,
    summary_text: str,
    keyword_text: str,
    thumb_desc_1: str, # Text to use for generating thumbnail_1_embedding
    thumb_desc_2: str,
    thumb_desc_3: str,
    summary_embedding_list: Optional[List[float]] = None,
    keyword_embedding_list: Optional[List[float]] = None,
    thumb_1_embedding_list: Optional[List[float]] = None,
    thumb_2_embedding_list: Optional[List[float]] = None,
    thumb_3_embedding_list: Optional[List[float]] = None,
) -> VideoIngestOutput:
    now = datetime.now(timezone.utc)
    file_name = f"{checksum_val}_full_integ.mp4"
    
    # Create a dummy file path for thumbnail generation as it expects a path
    # The SigLIP server will process the description text if path is not a real image.
    dummy_thumb_path = f"/tmp/{checksum_val}_thumb_placeholder.txt"
    with open(dummy_thumb_path, "w") as f:
        f.write("placeholder")

    ai_summary = AIAnalysisSummary(overall=summary_text, content_category="Integration Similar Test")
    ai_analysis_obj = ComprehensiveAIAnalysis(summary=ai_summary)
    
    vio = VideoIngestOutput(
        id=str(id_val),
        file_info=FileInfo(
            local_path=f"/integration/similar/{file_name}", file_name=file_name, file_checksum=checksum_val,
            file_size_bytes=1000, created_at=now, processed_at=now
        ),
        video=VideoDetails(
            duration_seconds=10.0, container="mp4", codec=VideoCodecDetails(name="h264"),
            resolution=VideoResolution(width=1280, height=720),
            color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)), exposure=VideoExposureDetails()
        ),
        camera=CameraDetails(focal_length=CameraFocalLength(), settings=CameraSettings(), location=CameraLocation()),
        analysis=AnalysisDetails(content_summary=summary_text, content_tags=["similar_integ_test"], ai_analysis=ai_analysis_obj),
    thumbnails=[dummy_thumb_path, dummy_thumb_path, dummy_thumb_path], # List of string paths
    embeddings=Embeddings(
        summary_embedding=summary_embedding_list, keyword_embedding=keyword_embedding_list,
        thumbnail_1_embedding=thumb_1_embedding_list, thumbnail_2_embedding=thumb_2_embedding_list,
            thumbnail_3_embedding=thumb_3_embedding_list
        )
    )
    # Clean up dummy file
    if os.path.exists(dummy_thumb_path):
        os.remove(dummy_thumb_path)
    return vio

@pytest.fixture(scope="module")
def setup_similar_clips_data(integration_db_conn: duckdb.DuckDBPyConnection):
    conn = integration_db_conn
    data_for_test = {}
    
    # Import image embedding function here to ensure it's patched correctly if tests run in parallel
    # or if other tests modify its behavior globally.
    from video_ingest_tool.embeddings_image import generate_thumbnail_embedding as gen_thumb_emb_real

    # Data definitions
    clips_defs = [
        {"id": uuid.uuid4(), "checksum": "sim_clip_A", "summary": "Red apple on a table", "keywords": "fruit, food, still life", "thumb1": "Close up of a shiny red apple", "thumb2": "Apple with a leaf", "thumb3": "Half an apple showing seeds"},
        {"id": uuid.uuid4(), "checksum": "sim_clip_B", "summary": "Green pear next to a window", "keywords": "fruit, healthy, window light", "thumb1": "A single green pear", "thumb2": "Pear with water droplets", "thumb3": "Sliced pear"},
        {"id": uuid.uuid4(), "checksum": "sim_clip_C", "summary": "Red car driving fast on a road", "keywords": "vehicle, speed, transportation", "thumb1": "Sports car in motion", "thumb2": "Close up of a red car's wheel", "thumb3": "Blurry background indicating speed"},
        {"id": uuid.uuid4(), "checksum": "sim_clip_D", "summary": "Another red apple, but bruised", "keywords": "fruit, apple, imperfect", "thumb1": "Red apple with a small bruise", "thumb2": "Apple from a different angle", "thumb3": "Apple core"},
    ]

    for clip_def in clips_defs:
        # Generate text embeddings (summary, keyword)
        text_summary_emb, text_keyword_emb = generate_embeddings(
            summary_content=clip_def["summary"],
            keyword_content=clip_def["keywords"]
        )
        # Generate "thumbnail" embeddings using text descriptions via SigLIP
        # The generate_thumbnail_embedding function takes image_path and description.
        # We'll use a placeholder for image_path and the text for description.
        # The SigLIP server provided can handle text inputs for its /v1/embeddings endpoint.
        placeholder_img_path = "placeholder.txt" # SigLIP server's get_embedding handles text if not valid image
        if not os.path.exists(placeholder_img_path): # Create if doesn't exist for image_path arg
            with open(placeholder_img_path, "w") as f: f.write("text")

        thumb1_emb = gen_thumb_emb_real(image_path=placeholder_img_path, description=clip_def["thumb1"])
        thumb2_emb = gen_thumb_emb_real(image_path=placeholder_img_path, description=clip_def["thumb2"])
        thumb3_emb = gen_thumb_emb_real(image_path=placeholder_img_path, description=clip_def["thumb3"])

        vio = get_full_integration_test_vio(
            checksum_val=clip_def["checksum"], id_val=clip_def["id"],
            summary_text=clip_def["summary"], keyword_text=clip_def["keywords"],
            thumb_desc_1=clip_def["thumb1"], thumb_desc_2=clip_def["thumb2"], thumb_desc_3=clip_def["thumb3"],
            summary_embedding_list=text_summary_emb, keyword_embedding_list=text_keyword_emb,
            thumb_1_embedding_list=thumb1_emb, thumb_2_embedding_list=thumb2_emb, thumb_3_embedding_list=thumb3_emb
        )
        prepared_data = prepare_clip_data_for_db(vio, None)
        upsert_clip_data(prepared_data, conn)
        data_for_test[clip_def["checksum"]] = {"id": str(clip_def["id"]), "vio": vio}
    
    if os.path.exists(placeholder_img_path): # Clean up placeholder
        os.remove(placeholder_img_path)
        
    conn.commit()
    return data_for_test

@pytest.mark.integration
def test_find_similar_clips_text_mode_integration(integration_db_conn: duckdb.DuckDBPyConnection, setup_similar_clips_data: Dict[str, Any]):
    conn = integration_db_conn
    source_clip_id = setup_similar_clips_data["sim_clip_A"]["id"] # Red apple

    results = find_similar_clips_duckdb(
        source_clip_id=source_clip_id,
        conn=conn,
        mode="text",
        match_count=1,
        similarity_threshold=0.1 # Lower threshold for real embeddings
    )
    assert len(results) > 0, "Should find at least one similar clip in text mode"
    # Expect sim_clip_D (another red apple) to be most similar based on text
    # This depends heavily on the actual embedding model's behavior
    found_checksums = [r["file_checksum"] for r in results]
    print(f"Text mode similar to {source_clip_id} (sim_clip_A): {found_checksums}")
    assert "sim_clip_D" in found_checksums or "sim_clip_B" in found_checksums # Allow for some variance

@pytest.mark.integration
def test_find_similar_clips_visual_mode_integration(integration_db_conn: duckdb.DuckDBPyConnection, setup_similar_clips_data: Dict[str, Any]):
    conn = integration_db_conn
    source_clip_id = setup_similar_clips_data["sim_clip_A"]["id"] # Red apple

    results = find_similar_clips_duckdb(
        source_clip_id=source_clip_id,
        conn=conn,
        mode="visual",
        match_count=1,
        similarity_threshold=0.1
    )
    assert len(results) > 0, "Should find at least one similar clip in visual mode"
    found_checksums = [r["file_checksum"] for r in results]
    print(f"Visual mode similar to {source_clip_id} (sim_clip_A): {found_checksums}")
    # Expect sim_clip_D (another red apple, visually similar descriptions)
    assert "sim_clip_D" in found_checksums  or "sim_clip_B" in found_checksums

@pytest.mark.integration
def test_find_similar_clips_combined_mode_integration(integration_db_conn: duckdb.DuckDBPyConnection, setup_similar_clips_data: Dict[str, Any]):
    conn = integration_db_conn
    source_clip_id = setup_similar_clips_data["sim_clip_A"]["id"] # Red apple

    results = find_similar_clips_duckdb(
        source_clip_id=source_clip_id,
        conn=conn,
        mode="combined",
        match_count=1,
        similarity_threshold=0.1
    )
    assert len(results) > 0, "Should find at least one similar clip in combined mode"
    found_checksums = [r["file_checksum"] for r in results]
    print(f"Combined mode similar to {source_clip_id} (sim_clip_A): {found_checksums}")
    # Expect sim_clip_D to be a strong candidate
    assert "sim_clip_D" in found_checksums or "sim_clip_B" in found_checksums

@pytest.mark.integration
def test_find_similar_clips_excludes_source(integration_db_conn: duckdb.DuckDBPyConnection, setup_similar_clips_data: Dict[str, Any]):
    conn = integration_db_conn
    source_clip_id = setup_similar_clips_data["sim_clip_A"]["id"]
    source_checksum = "sim_clip_A"

    results = find_similar_clips_duckdb(
        source_clip_id=source_clip_id,
        conn=conn,
        mode="combined",
        match_count=3 # Request more to see if source would have appeared
    )
    found_checksums = [r["file_checksum"] for r in results]
    assert source_checksum not in found_checksums, "Source clip itself should be excluded from results"