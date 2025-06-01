import pytest
import duckdb
import uuid
from datetime import datetime, timezone, timedelta # Import timedelta

from video_ingest_tool.database.duckdb.crud import (
    upsert_clip_data,
    get_clip_details,
    find_clip_by_checksum,
    delete_clip_by_id,
    get_all_clips,
    list_clips_advanced_duckdb # Added import
)
from video_ingest_tool.database.duckdb.schema import initialize_schema
from video_ingest_tool.database.duckdb.mappers import prepare_clip_data_for_db
# Import get_db_connection
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.models import (
    VideoIngestOutput, FileInfo, VideoDetails, AnalysisDetails,
    VideoCodecDetails, VideoResolution, VideoColorDetails, VideoHDRDetails, VideoExposureDetails,
    CameraDetails, CameraFocalLength, CameraSettings, CameraLocation, # Added Camera models for completeness
    Embeddings, # Import Embeddings model
    ComprehensiveAIAnalysis, AIAnalysisSummary # Import for nested data
)

# Sample data for testing - can be expanded or moved to fixtures
def get_sample_video_ingest_output(checksum_val: str, id_val: uuid.UUID = None) -> VideoIngestOutput:
    """Helper to create a minimal VideoIngestOutput for testing mappers and crud."""
    now = datetime.now(timezone.utc)

    # Create default instances for required nested models in VideoDetails
    default_codec = VideoCodecDetails(name="h264", profile="High", level="4.1", bit_depth=8, chroma_subsampling="4:2:0", pixel_format="yuv420p")
    default_resolution = VideoResolution(width=1920, height=1080, aspect_ratio="16:9")
    default_hdr = VideoHDRDetails(is_hdr=False)
    default_color = VideoColorDetails(color_space="bt709", color_primaries="bt709", transfer_characteristics="bt709", matrix_coefficients="bt709", hdr=default_hdr)
    default_exposure = VideoExposureDetails(warning=False, stops=0.0)
    
    # Create default instances for CameraDetails and its sub-models
    default_focal_length = CameraFocalLength(value_mm=50.0, category="Standard", source="EXIF")
    default_cam_settings = CameraSettings(iso=100, shutter_speed="1/50", f_stop=1.8)
    default_cam_location = CameraLocation(gps_latitude=34.0522, gps_longitude=-118.2437)
    default_camera_details = CameraDetails(
        make="TestMake", model="TestModel", lens_model="TestLens",
        focal_length=default_focal_length, settings=default_cam_settings, location=default_cam_location
    )

    return VideoIngestOutput(
        id=str(id_val) if id_val else str(uuid.uuid4()), # Convert UUID to string
        file_info=FileInfo(
            local_path=f"/test/path/{checksum_val}.mp4",
            file_name=f"{checksum_val}.mp4",
            file_checksum=checksum_val,
            file_size_bytes=1024000,
            created_at=now,
            processed_at=now
        ),
        video=VideoDetails(
            duration_seconds=60.5,
            container="mp4",
            codec=default_codec,
            resolution=default_resolution,
            color=default_color,
            exposure=default_exposure
            # frame_rate is optional
        ),
        camera=default_camera_details, # Camera is not optional in VideoIngestOutput
        analysis=AnalysisDetails(
            content_summary="A test video summary."
            # Other fields in AnalysisDetails like ai_analysis are optional or have defaults
        ),
        thumbnails=[] # Example, this is List[str]
        # audio_tracks and subtitle_tracks default to empty lists if not provided
    )

@pytest.fixture(scope="function")
def db_conn():
    """Fixture for an in-memory DuckDB connection with schema initialized."""
    # Use the centralized get_db_connection to ensure extensions are loaded
    conn = get_db_connection(db_path=':memory:')
    try:
        conn.execute("SET TimeZone = 'UTC';") # Configure session timezone to UTC
        initialize_schema(conn, create_fts=True) # CRUD tests don't rely on FTS, but setup full schema.
        yield conn
    finally:
        conn.close()

def test_upsert_new_clip(db_conn):
    """Test inserting a completely new clip."""
    conn = db_conn
    checksum = f"new_checksum_{uuid.uuid4().hex[:8]}"
    clip_id_uuid = uuid.uuid4()

    # 1. Prepare data using VideoIngestOutput and mapper
    video_output_data = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid)
    
    # For upsert, mapper needs embeddings. For this test, we can mock them or provide Nones.
    # The schema has embedding columns, so mapper will try to .get() them.
    # crud.upsert_clip_data itself doesn't care about embeddings content, only that the keys exist if provided by mapper.
    mock_embeddings = {
        "summary_embedding": None, # Or [0.1] * 1024 if testing actual embedding storage
        "keyword_embedding": None,
        "thumbnail_1_embedding": None,
        "thumbnail_2_embedding": None,
        "thumbnail_3_embedding": None,
    }
    video_output_data.embeddings = Embeddings(**mock_embeddings) # Assign to the model
    
    # ai_selected_thumbnail_metadata is also needed by the mapper
    mock_ai_thumbnails_metadata = [
        {"rank": 1, "path": f"/test/thumb_{checksum}_1.jpg", "timestamp_seconds": 10.0, "description": "Thumb 1"},
        {"rank": 2, "path": f"/test/thumb_{checksum}_2.jpg", "timestamp_seconds": 20.0, "description": "Thumb 2"},
    ]

    prepared_data = prepare_clip_data_for_db(video_output_data, mock_ai_thumbnails_metadata) # mock_embeddings removed from call
    assert prepared_data is not None, "Mapper failed to prepare data"
    assert prepared_data["id"] == str(clip_id_uuid)
    assert prepared_data["file_checksum"] == checksum

    # 2. Upsert the data
    returned_id_str = upsert_clip_data(prepared_data, conn)
    assert returned_id_str is not None, "upsert_clip_data returned None on new insert"
    assert returned_id_str == str(clip_id_uuid), "Returned ID does not match provided ID for new insert"

    # 3. Verify data in DB using get_clip_details
    retrieved_clip = get_clip_details(returned_id_str, conn)
    assert retrieved_clip is not None, "Failed to retrieve newly inserted clip"
    assert str(retrieved_clip["id"]) == str(clip_id_uuid) # Compare string representations
    assert retrieved_clip["file_checksum"] == checksum
    assert retrieved_clip["file_name"] == f"{checksum}.mp4"
    assert retrieved_clip["content_summary"] == "A test video summary."
    
    # Verify created_at and updated_at (updated_at should be very recent)
    assert "created_at" in retrieved_clip and retrieved_clip["created_at"] is not None
    assert "updated_at" in retrieved_clip and retrieved_clip["updated_at"] is not None
    
    # Ensure created_at from prepared_data is stored
    # DuckDB might store with slightly different precision or timezone handling, compare reasonably
    original_created_at = prepared_data.get("created_at")
    db_created_at = retrieved_clip.get("created_at")

    if isinstance(original_created_at, datetime) and isinstance(db_created_at, datetime):
        # Make both timezone-aware (UTC) if they are naive, or ensure they are comparable
        if original_created_at.tzinfo is None:
            original_created_at = original_created_at.replace(tzinfo=timezone.utc)
        if db_created_at.tzinfo is None: # DuckDB might return naive UTC
            db_created_at = db_created_at.replace(tzinfo=timezone.utc)
        
        # Allow for small differences due to DB storage/retrieval precision
        time_difference_created = abs((original_created_at - db_created_at).total_seconds())
        assert time_difference_created < 1, f"created_at mismatch: original {original_created_at}, db {db_created_at}"
    else:
        assert original_created_at == db_created_at, f"created_at type mismatch or value mismatch"

    # updated_at should be close to now
    time_difference_updated = abs((datetime.now(timezone.utc) - retrieved_clip["updated_at"].replace(tzinfo=timezone.utc)).total_seconds())
    assert time_difference_updated < 5, "updated_at seems too old"

def test_upsert_existing_clip(db_conn):
    """Test updating an existing clip using the upsert logic."""
    conn = db_conn
    checksum = f"existing_checksum_{uuid.uuid4().hex[:8]}"
    clip_id_uuid = uuid.uuid4()

    # 1. Initial insert
    video_output_initial = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid)
    mock_embeddings = {
        "summary_embedding": [0.1] * 1024, "keyword_embedding": [0.2] * 1024,
        "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None,
    }
    video_output_initial.embeddings = Embeddings(**mock_embeddings) # Assign to the model
    mock_ai_thumbnails_initial = [{"rank": 1, "path": f"/test/thumb_{checksum}_initial.jpg", "description": "Initial"}]
    
    prepared_initial_data = prepare_clip_data_for_db(video_output_initial, mock_ai_thumbnails_initial) # mock_embeddings removed
    assert prepared_initial_data is not None
    
    initial_upsert_id = upsert_clip_data(prepared_initial_data, conn)
    assert initial_upsert_id == str(clip_id_uuid)

    retrieved_initial_clip = get_clip_details(initial_upsert_id, conn)
    assert retrieved_initial_clip is not None
    initial_created_at = retrieved_initial_clip["created_at"]
    initial_updated_at = retrieved_initial_clip["updated_at"]
    assert retrieved_initial_clip["content_summary"] == "A test video summary."

    # 2. Prepare updated data for the same clip
    # Ensure some time passes for updated_at to be different
    import time
    time.sleep(0.1) # Small delay

    video_output_updated = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid) # Same ID and checksum
    video_output_updated.analysis.content_summary = "Updated video summary." # Change a field
    
    # Potentially update embeddings or AI thumbnails if testing that part of update
    updated_mock_embeddings = {
        "summary_embedding": [0.9] * 1024, "keyword_embedding": [0.8] * 1024, # Changed embeddings
        "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None,
    }
    video_output_updated.embeddings = Embeddings(**updated_mock_embeddings) # Assign to the model
    mock_ai_thumbnails_updated = [{"rank": 1, "path": f"/test/thumb_{checksum}_updated.jpg", "description": "Updated"}]

    prepared_updated_data = prepare_clip_data_for_db(video_output_updated, mock_ai_thumbnails_updated) # updated_mock_embeddings removed
    assert prepared_updated_data is not None
    
    # Explicitly set created_at in the data for the update operation to be the same as the initial one.
    # This makes the test's intention clearer: we are checking if the DB update operation itself changes created_at,
    # when created_at is not in the DO UPDATE SET clause.
    prepared_updated_data["created_at"] = initial_created_at

    # ID in prepared_updated_data should still be the original clip_id_uuid for the ON CONFLICT logic to work as expected
    # if we were to change ID here, it would be an attempt to insert a new record with same checksum, which is a constraint violation.
    # The upsert logic in crud.py uses the ID from clip_data for the INSERT part.
    # ON CONFLICT (file_checksum) ensures the correct row is targeted for UPDATE.
    assert prepared_updated_data["id"] == str(clip_id_uuid)


    # 3. Upsert the updated data
    updated_upsert_id = upsert_clip_data(prepared_updated_data, conn)
    assert updated_upsert_id is not None
    # The ID returned by upsert (due to RETURNING id) should be the ID of the existing row that was updated.
    assert updated_upsert_id == str(clip_id_uuid)


    # 4. Verify the update
    retrieved_updated_clip = get_clip_details(updated_upsert_id, conn)
    assert retrieved_updated_clip is not None
    assert str(retrieved_updated_clip["id"]) == str(clip_id_uuid) # Compare string representations
    assert retrieved_updated_clip["file_checksum"] == checksum
    assert retrieved_updated_clip["content_summary"] == "Updated video summary." # Verify updated field
    
    # Verify embeddings were updated using pytest.approx for float comparisons
    assert retrieved_updated_clip["summary_embedding"] == pytest.approx([0.9] * 1024)

    # Verify created_at is UNCHANGED (within a small tolerance for precision)
    assert retrieved_updated_clip["created_at"] == pytest.approx(initial_created_at, abs=timedelta(seconds=1)), "created_at should not change significantly on update"
    
    # Verify updated_at IS CHANGED and is newer
    assert retrieved_updated_clip["updated_at"] is not None
    assert retrieved_updated_clip["updated_at"] > initial_updated_at, "updated_at should be newer after update"

def test_upsert_clip_data_missing_checksum(db_conn):
    """Test upsert_clip_data when file_checksum is missing."""
    conn = db_conn
    clip_id_uuid = uuid.uuid4()
    # Prepare data without 'file_checksum'
    # Mapper normally ensures this, but crud should also be robust or document expectation.
    # For this test, we'll manually create a dict similar to what mapper would output.
    prepared_data_no_checksum = {
        "id": str(clip_id_uuid),
        "local_path": "/test/no_checksum.mp4",
        "file_name": "no_checksum.mp4",
        # "file_checksum": "some_checksum", # Missing
        "file_size_bytes": 1000,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "content_summary": "Test no checksum"
        # Add other fields as expected by the crud function if they are strictly required by SQL
    }
    returned_id = upsert_clip_data(prepared_data_no_checksum, conn)
    assert returned_id is None, "upsert_clip_data should return None if checksum is missing"

def test_upsert_clip_data_missing_id(db_conn):
    """Test upsert_clip_data when id is missing."""
    conn = db_conn
    checksum = f"checksum_no_id_{uuid.uuid4().hex[:8]}"
    prepared_data_no_id = {
        # "id": str(uuid.uuid4()), # Missing
        "local_path": "/test/no_id.mp4",
        "file_name": "no_id.mp4",
        "file_checksum": checksum,
        "file_size_bytes": 1000,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "content_summary": "Test no id"
    }
    returned_id = upsert_clip_data(prepared_data_no_id, conn)
    assert returned_id is None, "upsert_clip_data should return None if id is missing"

def test_get_clip_details(db_conn):
    """Test retrieving a clip by its ID."""
    conn = db_conn
    checksum = f"details_checksum_{uuid.uuid4().hex[:8]}"
    clip_id_uuid = uuid.uuid4()

    video_output = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid)
    mock_embeddings_dict = {"summary_embedding": None, "keyword_embedding": None, "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None}
    video_output.embeddings = Embeddings(**mock_embeddings_dict)
    prepared_data = prepare_clip_data_for_db(video_output, None) # mock_embeddings removed
    assert prepared_data is not None
    
    upserted_id = upsert_clip_data(prepared_data, conn)
    assert upserted_id == str(clip_id_uuid)

    retrieved_clip = get_clip_details(upserted_id, conn)
    assert retrieved_clip is not None
    assert str(retrieved_clip["id"]) == upserted_id
    assert retrieved_clip["file_checksum"] == checksum
    assert retrieved_clip["file_name"] == f"{checksum}.mp4"

    # Test getting a non-existent clip
    non_existent_id = str(uuid.uuid4())
    retrieved_non_existent = get_clip_details(non_existent_id, conn)
    assert retrieved_non_existent is None

def test_find_clip_by_checksum(db_conn):
    """Test finding a clip by its file_checksum."""
    conn = db_conn
    checksum = f"find_checksum_{uuid.uuid4().hex[:8]}"
    clip_id_uuid = uuid.uuid4()

    video_output = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid)
    mock_embeddings_dict = {"summary_embedding": None, "keyword_embedding": None, "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None}
    video_output.embeddings = Embeddings(**mock_embeddings_dict)
    prepared_data = prepare_clip_data_for_db(video_output, None) # mock_embeddings removed
    assert prepared_data is not None

    upserted_id = upsert_clip_data(prepared_data, conn)
    assert upserted_id == str(clip_id_uuid)

    retrieved_clip = find_clip_by_checksum(checksum, conn)
    assert retrieved_clip is not None
    assert str(retrieved_clip["id"]) == upserted_id
    assert retrieved_clip["file_checksum"] == checksum

    # Test finding a non-existent checksum
    non_existent_checksum = "non_existent_checksum_value"
    retrieved_non_existent = find_clip_by_checksum(non_existent_checksum, conn)
    assert retrieved_non_existent is None

def test_delete_clip_by_id(db_conn):
    """Test deleting a clip by its ID."""
    conn = db_conn
    checksum = f"delete_checksum_{uuid.uuid4().hex[:8]}"
    clip_id_uuid = uuid.uuid4()

    video_output = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id_uuid)
    mock_embeddings_dict = {"summary_embedding": None, "keyword_embedding": None, "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None}
    video_output.embeddings = Embeddings(**mock_embeddings_dict)
    prepared_data = prepare_clip_data_for_db(video_output, None) # mock_embeddings removed
    assert prepared_data is not None
    
    upserted_id_str = upsert_clip_data(prepared_data, conn)
    assert upserted_id_str == str(clip_id_uuid)
    conn.commit() # Ensure data is committed before trying to verify/delete

    # Verify it exists
    assert get_clip_details(upserted_id_str, conn) is not None

    # Delete it
    delete_result = delete_clip_by_id(upserted_id_str, conn)
    conn.commit() # Commit the delete operation
    assert delete_result is True

    # Verify it's gone
    assert get_clip_details(upserted_id_str, conn) is None

    # Test deleting a non-existent ID
    non_existent_id = str(uuid.uuid4())
    delete_non_existent_result = delete_clip_by_id(non_existent_id, conn)
    assert delete_non_existent_result is False

def test_get_all_clips(db_conn):
    """Test retrieving all clips with pagination."""
    conn = db_conn
    
    # Insert a few clips
    ids_inserted = []
    for i in range(5):
        checksum = f"all_clips_checksum_{i}_{uuid.uuid4().hex[:8]}"
        clip_id = uuid.uuid4()
        ids_inserted.append(str(clip_id))
        video_output = get_sample_video_ingest_output(checksum_val=checksum, id_val=clip_id)
        mock_embeddings_dict = {"summary_embedding": None, "keyword_embedding": None, "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None}
        video_output.embeddings = Embeddings(**mock_embeddings_dict)
        prepared_data = prepare_clip_data_for_db(video_output, None) # mock_embeddings removed
        assert prepared_data is not None
        upsert_clip_data(prepared_data, conn)

    # Test get all (default limit)
    all_clips = get_all_clips(conn)
    assert len(all_clips) == 5
    retrieved_ids = sorted([str(clip["id"]) for clip in all_clips]) # Convert UUIDs to strings
    assert retrieved_ids == sorted(ids_inserted)

    # Test limit
    limited_clips = get_all_clips(conn, limit=2)
    assert len(limited_clips) == 2

    # Test offset
    offset_clips = get_all_clips(conn, limit=2, offset=1)
    assert len(offset_clips) == 2
    
    # Ensure offset clips are different from first two and are part of the original set
    first_two_ids = [str(clip["id"]) for clip in limited_clips] # Convert to str
    offset_ids = [str(clip["id"]) for clip in offset_clips]   # Convert to str
    
    # Verify offset_clips content
    # Items in offset_clips should be from the original inserted set
    for oid_str in offset_ids:
        assert oid_str in ids_inserted
    
    # If offset is 1, the very first item from the full list (ordered by created_at DESC)
    # should NOT be in the offset_clips.
    # And the second item from the full list SHOULD be the first item in offset_clips.
    all_clips_sorted_ids = sorted([str(c["id"]) for c in get_all_clips(conn)], key=lambda x_id: ids_inserted.index(x_id), reverse=True) # Assuming created_at DESC means reverse order of insertion for test
    
    if len(all_clips_sorted_ids) > 1 and len(offset_ids) > 0:
         # This relies on the default ORDER BY created_at DESC in get_all_clips
         # For this test, let's assume created_at order matches reverse insertion order for simplicity
         # A more robust test might explicitly control created_at values.
        
        # The first item of all_clips (index 0) should not be in offset_clips if offset is > 0
        assert all_clips[0]["id"] not in offset_ids # all_clips is already sorted by created_at DESC

        # The second item of all_clips (index 1) should be the first item of offset_clips (limit=2, offset=1)
        if len(all_clips) > 1 and len(offset_clips) > 0:
            assert all_clips[1]["id"] == offset_clips[0]["id"]

    # Test limit + offset exceeding total items
    exceeding_clips = get_all_clips(conn, limit=3, offset=3) # Should get 2 items (e.g. if 5 total, offset 3 means items 3, 4)
    # If 5 items (0,1,2,3,4), offset 3 means start from index 3. Limit 3 would try to get 3,4. So 2 items.
    assert len(exceeding_clips) == 2

    # Test offset beyond total items
    empty_clips = get_all_clips(conn, offset=10)
    assert len(empty_clips) == 0

def test_list_clips_advanced(db_conn):
    """Test retrieving clips with advanced sorting and filtering."""
    conn = db_conn
    
    # Insert sample data with varying fields for sorting/filtering
    clip_data_list = [
        get_sample_video_ingest_output(checksum_val="adv_cs1", id_val=uuid.uuid4()),
        get_sample_video_ingest_output(checksum_val="adv_cs2", id_val=uuid.uuid4()),
        get_sample_video_ingest_output(checksum_val="adv_cs3", id_val=uuid.uuid4()),
        get_sample_video_ingest_output(checksum_val="adv_cs4", id_val=uuid.uuid4()),
        get_sample_video_ingest_output(checksum_val="adv_cs5", id_val=uuid.uuid4()),
    ]

    # Modify some data for distinctness
    clip_data_list[0].file_info.file_name = "zeta_clip.mp4"
    clip_data_list[0].video.duration_seconds = 120.5
    clip_data_list[0].file_info.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    if clip_data_list[0].analysis.ai_analysis is None: clip_data_list[0].analysis.ai_analysis = ComprehensiveAIAnalysis()
    if clip_data_list[0].analysis.ai_analysis.summary is None: clip_data_list[0].analysis.ai_analysis.summary = AIAnalysisSummary()
    clip_data_list[0].analysis.ai_analysis.summary.content_category = "CategoryA"

    clip_data_list[1].file_info.file_name = "alpha_clip.mp4"
    clip_data_list[1].video.duration_seconds = 30.0
    clip_data_list[1].file_info.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    if clip_data_list[1].analysis.ai_analysis is None: clip_data_list[1].analysis.ai_analysis = ComprehensiveAIAnalysis()
    if clip_data_list[1].analysis.ai_analysis.summary is None: clip_data_list[1].analysis.ai_analysis.summary = AIAnalysisSummary()
    clip_data_list[1].analysis.ai_analysis.summary.content_category = "CategoryB"

    clip_data_list[2].file_info.file_name = "gamma_clip.mp4"
    clip_data_list[2].video.duration_seconds = 180.0
    clip_data_list[2].file_info.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    if clip_data_list[2].analysis.ai_analysis is None: clip_data_list[2].analysis.ai_analysis = ComprehensiveAIAnalysis()
    if clip_data_list[2].analysis.ai_analysis.summary is None: clip_data_list[2].analysis.ai_analysis.summary = AIAnalysisSummary()
    clip_data_list[2].analysis.ai_analysis.summary.content_category = "CategoryA"
    
    clip_data_list[3].file_info.file_name = "beta_clip.mp4"
    clip_data_list[3].video.duration_seconds = 60.2
    clip_data_list[3].file_info.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    # Ensure ai_analysis and summary exist if we want to test filtering for None/missing content_category
    if clip_data_list[3].analysis.ai_analysis is None: clip_data_list[3].analysis.ai_analysis = ComprehensiveAIAnalysis()
    if clip_data_list[3].analysis.ai_analysis.summary is None: clip_data_list[3].analysis.ai_analysis.summary = AIAnalysisSummary()
    clip_data_list[3].analysis.ai_analysis.summary.content_category = None # Explicitly None

    clip_data_list[4].file_info.file_name = "delta_clip.mp4"
    clip_data_list[4].video.duration_seconds = 90.0
    clip_data_list[4].file_info.created_at = datetime.now(timezone.utc) # Most recent
    if clip_data_list[4].analysis.ai_analysis is None: clip_data_list[4].analysis.ai_analysis = ComprehensiveAIAnalysis()
    if clip_data_list[4].analysis.ai_analysis.summary is None: clip_data_list[4].analysis.ai_analysis.summary = AIAnalysisSummary()
    clip_data_list[4].analysis.ai_analysis.summary.content_category = "CategoryB"


    mock_embeddings_dict = {"summary_embedding": None, "keyword_embedding": None, "thumbnail_1_embedding": None, "thumbnail_2_embedding": None, "thumbnail_3_embedding": None}
    
    inserted_ids = []
    for video_output in clip_data_list:
        video_output.embeddings = Embeddings(**mock_embeddings_dict) # Assign embeddings
        prepared_data = prepare_clip_data_for_db(video_output, None) # mock_embeddings removed from call
        assert prepared_data is not None
        upsert_id = upsert_clip_data(prepared_data, conn)
        assert upsert_id is not None
        inserted_ids.append(upsert_id)
    
    conn.commit()

    # 1. Test default sorting (created_at DESC)
    default_sorted_clips = list_clips_advanced_duckdb(conn)
    assert len(default_sorted_clips) == 5
    assert default_sorted_clips[0]["file_name"] == "delta_clip.mp4" # Most recent
    assert default_sorted_clips[4]["file_name"] == "gamma_clip.mp4" # Oldest

    # 2. Test sorting by file_name ASC
    filename_asc_clips = list_clips_advanced_duckdb(conn, sort_by="file_name", sort_order="asc")
    assert len(filename_asc_clips) == 5
    assert filename_asc_clips[0]["file_name"] == "alpha_clip.mp4"
    assert filename_asc_clips[4]["file_name"] == "zeta_clip.mp4"

    # 3. Test sorting by duration_seconds DESC
    duration_desc_clips = list_clips_advanced_duckdb(conn, sort_by="duration_seconds", sort_order="desc")
    assert len(duration_desc_clips) == 5
    assert duration_desc_clips[0]["file_name"] == "gamma_clip.mp4" # 180.0s
    assert duration_desc_clips[4]["file_name"] == "alpha_clip.mp4" # 30.0s

    # 4. Test filtering by content_category = "CategoryA"
    category_a_clips = list_clips_advanced_duckdb(conn, filters={"content_category": "CategoryA"})
    assert len(category_a_clips) == 2
    for clip in category_a_clips:
        assert clip["content_category"] == "CategoryA"

    # 5. Test filtering by content_category = "CategoryB" and sort by duration_seconds ASC
    category_b_duration_asc = list_clips_advanced_duckdb(conn,
                                                       filters={"content_category": "CategoryB"},
                                                       sort_by="duration_seconds",
                                                       sort_order="asc")
    assert len(category_b_duration_asc) == 2
    assert category_b_duration_asc[0]["file_name"] == "alpha_clip.mp4" # 30.0s
    assert category_b_duration_asc[1]["file_name"] == "delta_clip.mp4" # 90.0s

    # 6. Test limit and offset
    limited_offset_clips = list_clips_advanced_duckdb(conn, limit=2, offset=1, sort_by="file_name", sort_order="asc")
    assert len(limited_offset_clips) == 2
    assert limited_offset_clips[0]["file_name"] == "beta_clip.mp4" # Second in alpha sort
    assert limited_offset_clips[1]["file_name"] == "delta_clip.mp4" # Third in alpha sort

    # 7. Test filtering with an operator (e.g., duration_seconds >= 100)
    long_duration_clips = list_clips_advanced_duckdb(conn, filters={"duration_seconds >=": 100.0})
    assert len(long_duration_clips) == 2 # zeta (120.5), gamma (180.0)
    for clip in long_duration_clips:
        assert clip["duration_seconds"] >= 100.0

    # 8. Test filtering for a non-existent category
    no_category_clips = list_clips_advanced_duckdb(conn, filters={"content_category": "CategoryNonExistent"})
    assert len(no_category_clips) == 0
    
    # 9. Test with invalid sort column (should default to created_at)
    invalid_sort_clips = list_clips_advanced_duckdb(conn, sort_by="invalid_column")
    assert len(invalid_sort_clips) == 5
    assert invalid_sort_clips[0]["file_name"] == "delta_clip.mp4" # Default sort by created_at desc

    # 10. Test filtering by a field that might be NULL (content_category for beta_clip)
    # This requires the filter implementation to handle IS NULL or specific value checks.
    # The current simple equality filter in list_clips_advanced_duckdb won't find NULLs with `column = ?` if value is None.
    # To test for NULLs, the filter key would need to be "content_category IS NULL" or similar.
    # For now, let's test filtering for a specific value that exists.
    
    # 11. Test multiple filters
    multi_filter_clips = list_clips_advanced_duckdb(conn, filters={"content_category": "CategoryA", "duration_seconds <": 150.0})
    assert len(multi_filter_clips) == 1
    assert multi_filter_clips[0]["file_name"] == "zeta_clip.mp4" # CategoryA and 120.5s
    assert multi_filter_clips[0]["content_category"] == "CategoryA"
    assert multi_filter_clips[0]["duration_seconds"] < 150.0

    # 12. Test case-insensitive LIKE filter (if supported by your filter logic)
    # Assuming list_clips_advanced_duckdb supports "column_name ILIKE ?"
    like_filter_clips = list_clips_advanced_duckdb(conn, filters={"file_name ILIKE": "%zeta%"})
    assert len(like_filter_clips) == 1
    assert like_filter_clips[0]["file_name"] == "zeta_clip.mp4"