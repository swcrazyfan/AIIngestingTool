import pytest
import json
import uuid
from datetime import datetime, timezone, timedelta
import structlog # Import structlog

from video_ingest_tool.api.server import create_app
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.schema import initialize_schema, create_fts_index_for_clips
from video_ingest_tool.database.duckdb import crud as duckdb_crud
from video_ingest_tool.database.duckdb.mappers import prepare_clip_data_for_db
from video_ingest_tool.models import (
    VideoIngestOutput, FileInfo, VideoDetails, AnalysisDetails, CameraDetails, Embeddings,
    VideoCodecDetails, VideoResolution, VideoColorDetails, VideoHDRDetails, VideoExposureDetails,
    CameraFocalLength, CameraSettings, CameraLocation, ComprehensiveAIAnalysis, AIAnalysisSummary
)

logger = structlog.get_logger(__name__) # Define logger for the test file

# Need to import duckdb for direct connection creation in app_instance
import duckdb
# Import the wrapper from the connection module to use it in test_db_conn
from video_ingest_tool.database.duckdb import connection as duckdb_connection_module


@pytest.fixture(scope="session")
def app_instance():
    """Create and configure a new app instance for each test session.
    Manages a single in-memory DuckDB connection for the entire test session.
    """
    app, _ = create_app(debug=True)
    app.config.update({
        "TESTING": True,
        "DUCKDB_PATH": ":memory:", # Signal to use in-memory
        "SERVER_NAME": "localhost.test"
    })

    # Create and initialize the single in-memory DB for the session
    actual_session_conn = duckdb.connect(database=":memory:", read_only=False)
    logger.info("Session-scoped actual in-memory DuckDB connection created for testing.")
    
    extensions_to_load = ["fts", "vss"]
    for ext_name in extensions_to_load:
        try:
            actual_session_conn.execute(f"INSTALL {ext_name};")
            logger.info(f"Installed DuckDB extension {ext_name} on session DB.")
        except Exception:
            logger.debug(f"DuckDB extension {ext_name} likely already installed on session DB.")
            pass
        try:
            actual_session_conn.execute(f"LOAD {ext_name};")
            logger.info(f"Loaded DuckDB extension {ext_name} on session DB.")
        except Exception as e_load:
            if "already loaded" in str(e_load).lower():
                logger.debug(f"DuckDB extension {ext_name} already loaded on session DB.")
            else:
                logger.error(f"Failed to load extension {ext_name} on session DB.", error=str(e_load))
                raise

    actual_session_conn.execute("SET TimeZone = 'UTC';")
    initialize_schema(actual_session_conn, create_fts=True)
    logger.info("Schema initialized on session-scoped in-memory DuckDB.")

    if not hasattr(app, 'extensions'):
        app.extensions = {}
    # Store the *actual* connection object on the app context
    app.extensions['_duckdb_actual_test_conn'] = actual_session_conn
    
    yield app

    # Teardown: close the session-scoped connection
    logger.info("Closing session-scoped actual in-memory DuckDB connection.")
    if hasattr(app, 'extensions') and '_duckdb_actual_test_conn' in app.extensions:
        app.extensions['_duckdb_actual_test_conn'].close()
        del app.extensions['_duckdb_actual_test_conn']

@pytest.fixture(scope="session")
def client(app_instance):
    """A test client for the app."""
    return app_instance.test_client()

@pytest.fixture(scope="function") # Function scope for test_db_conn using the session's actual conn
def test_db_conn(app_instance):
    """
    Provides a wrapper around the session-scoped in-memory DuckDB connection.
    The actual connection is managed by app_instance and stored in app.extensions.
    """
    if hasattr(app_instance, 'extensions') and '_duckdb_actual_test_conn' in app_instance.extensions:
        actual_conn = app_instance.extensions['_duckdb_actual_test_conn']
        # Each test function gets a new wrapper around the same actual session connection.
        # This wrapper's close() is a no-op, protecting the actual_conn.
        return duckdb_connection_module._InMemoryConnectionWrapper(actual_conn)
    else:
        pytest.fail("Session-scoped actual DuckDB connection not found in app context.")

@pytest.fixture(scope="function")
def sample_clips_data(test_db_conn): # test_db_conn is now the session-scoped connection
    """Populate the test database with sample clip data for API tests. Cleans up before adding."""
    conn = test_db_conn
    
    # Clean up relevant tables before each test function that uses this fixture
    try:
        logger.debug("Cleaning app_data.clips table for new test function.")
        conn.execute("DELETE FROM app_data.clips;")
        conn.commit() # Ensure cleanup is committed
    except Exception as e_del:
        logger.error(f"Error cleaning clips table in sample_clips_data: {e_del}")
        # Depending on the error, might want to raise it or handle differently
        # If table doesn't exist on first run of first test, this might fail.
        # initialize_schema should have created it.
        pass # Continue if delete fails (e.g., table not there on very first run, though schema should exist)

    clip_ids_inserted = []
    base_time = datetime.now(timezone.utc)

    for i in range(5):
        checksum = f"api_test_checksum_{i}_{uuid.uuid4().hex[:8]}"
        clip_id_uuid = uuid.uuid4()
        
        # Create minimal VideoIngestOutput
        vio = VideoIngestOutput(
            id=str(clip_id_uuid),
            file_info=FileInfo(
                local_path=f"/test/api_vid_{i}.mp4",
                file_name=f"api_vid_{i}.mp4",
                file_checksum=checksum,
                file_size_bytes=1000000 + (i * 1000),
                created_at=base_time - timedelta(days=i), # Vary creation time
                processed_at=base_time - timedelta(minutes=i*10)
            ),
            video=VideoDetails(
                duration_seconds=60.0 + i,
                codec=VideoCodecDetails(name="h264"),
                resolution=VideoResolution(width=1920, height=1080),
                color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)),
                exposure=VideoExposureDetails()
            ),
            camera=CameraDetails(
                make=f"CamMake{i}", model=f"CamModel{i}",
                focal_length=CameraFocalLength(), settings=CameraSettings(), location=CameraLocation()
            ),
            analysis=AnalysisDetails(
                content_summary=f"API test summary for clip {i}",
                content_tags=[f"tag{i}", "api_test"],
                ai_analysis=ComprehensiveAIAnalysis(
                    summary=AIAnalysisSummary(content_category=f"Category{i % 2}")
                )
            ),
            embeddings=Embeddings() # Add empty embeddings
        )
        
        # Mapper needs ai_selected_thumbnail_metadata, can be None for this test
        prepared_data = prepare_clip_data_for_db(vio, None)
        assert prepared_data is not None, f"Mapper failed for clip {i}"
        
        upserted_id = duckdb_crud.upsert_clip_data(prepared_data, conn)
        assert upserted_id == str(clip_id_uuid), f"Upsert failed for clip {i}"
        clip_ids_inserted.append(str(clip_id_uuid))
    
    conn.commit() # Ensure data is committed
    
    # Recreate FTS index after data insertion
    logger.info("Recreating FTS index for app_data.clips after sample data insertion.")
    try:
        create_fts_index_for_clips(conn)
        conn.commit() # Commit FTS index creation
        logger.info("FTS index recreated successfully.")
    except Exception as e_fts:
        logger.error(f"Error recreating FTS index in sample_clips_data: {e_fts}")
        pytest.fail(f"Failed to recreate FTS index: {e_fts}")
        
    return clip_ids_inserted

def test_list_clips_default(client, sample_clips_data):
    """Test GET /api/clips with default parameters."""
    response = client.get('/api/clips')
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert "data" in data
    api_response_data = data["data"]

    assert "clips" in api_response_data
    assert isinstance(api_response_data["clips"], list)
    assert len(api_response_data["clips"]) <= 20 # Default limit in API
    assert len(api_response_data["clips"]) == len(sample_clips_data) # Expect all 5 test clips by default

    # Check if default sorting (created_at desc) is applied
    # The first clip returned should be the most recently created one from sample_clips_data
    # sample_clips_data created_at: base_time - timedelta(days=i)
    # So, clip 0 is oldest, clip 4 is newest. Default sort is 'created_at desc'.
    if len(api_response_data["clips"]) > 1:
        # Convert created_at strings to datetime objects for comparison
        # Assuming created_at is in ISO format from the API
        # The API returns the direct output from ClipsCommand, which gets it from duckdb_crud.
        # duckdb_crud.list_clips_advanced_duckdb returns dicts with datetime objects.
        # The create_success_response in middleware might convert datetimes to strings.
        # Let's assume they are strings for now and parse them.
        
        # The API returns 'created_at' from the DB.
        # The sample data has clip_ids_inserted[0] as oldest, clip_ids_inserted[4] as newest.
        # Default sort is created_at desc, so newest should be first.
        
        # file_name for newest (i=0 in loop, created_at=base_time) is "api_vid_0.mp4"
        # file_name for oldest (i=4 in loop, created_at=base_time - timedelta(days=4)) is "api_vid_4.mp4"
        # ClipsCommand default sort is 'created_at' 'desc'.
        # So, api_vid_0.mp4 should be first.
        
        # The sample_clips_data fixture creates clips with decreasing created_at times.
        # Clip 0: base_time
        # Clip 1: base_time - 1 day
        # Clip 4: base_time - 4 days (oldest)
        # Default sort is created_at desc, so clip 0 should be first.
        assert api_response_data["clips"][0]["file_name"] == "api_vid_0.mp4"
        assert api_response_data["clips"][-1]["file_name"] == "api_vid_4.mp4"

def test_list_clips_pagination(client, sample_clips_data):
    """Test GET /api/clips with limit and offset parameters."""
    # Test limit
    response_limit = client.get('/api/clips?limit=2')
    assert response_limit.status_code == 200
    data_limit = response_limit.get_json()["data"]
    assert len(data_limit["clips"]) == 2
    assert data_limit["limit"] == 2

    # Test offset
    # Expecting 5 total clips. Default sort created_at desc.
    # Clip 0 (api_vid_0.mp4) is newest. Clip 4 (api_vid_4.mp4) is oldest.
    response_offset = client.get('/api/clips?limit=2&offset=1') # Get 2nd and 3rd newest
    assert response_offset.status_code == 200
    data_offset = response_offset.get_json()["data"]
    assert len(data_offset["clips"]) == 2
    assert data_offset["offset"] == 1
    assert data_offset["clips"][0]["file_name"] == "api_vid_1.mp4" # Second newest
    assert data_offset["clips"][1]["file_name"] == "api_vid_2.mp4" # Third newest

    # Test offset beyond total items
    response_offset_beyond = client.get('/api/clips?offset=10')
    assert response_offset_beyond.status_code == 200
    data_offset_beyond = response_offset_beyond.get_json()["data"]
    assert len(data_offset_beyond["clips"]) == 0

def test_list_clips_sorting(client, sample_clips_data):
    """Test GET /api/clips with sort_by and sort_order parameters."""
    # Sort by file_name ascending
    response_sort_name_asc = client.get('/api/clips?sort_by=file_name&sort_order=asc')
    assert response_sort_name_asc.status_code == 200
    data_sort_name_asc = response_sort_name_asc.get_json()["data"]
    assert len(data_sort_name_asc["clips"]) == 5
    assert data_sort_name_asc["clips"][0]["file_name"] == "api_vid_0.mp4" # Sorted alphabetically
    assert data_sort_name_asc["clips"][4]["file_name"] == "api_vid_4.mp4"

    # Sort by duration_seconds descending
    response_sort_duration_desc = client.get('/api/clips?sort_by=duration_seconds&sort_order=desc')
    assert response_sort_duration_desc.status_code == 200
    data_sort_duration_desc = response_sort_duration_desc.get_json()["data"]
    assert len(data_sort_duration_desc["clips"]) == 5
    # Clip 4 has duration 64.0, Clip 0 has duration 60.0
    assert data_sort_duration_desc["clips"][0]["file_name"] == "api_vid_4.mp4"
    assert data_sort_duration_desc["clips"][-1]["file_name"] == "api_vid_0.mp4"

def test_list_clips_filtering(client, sample_clips_data):
    """Test GET /api/clips with a simple filter."""
    # Filter by content_category = Category0
    # Clips with index 0, 2, 4 will have Category0
    filters_json = json.dumps({"content_category": "Category0"})
    response = client.get(f'/api/clips?filters={filters_json}')
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data["clips"]) == 3
    for clip in data["clips"]:
        assert clip["content_category"] == "Category0"

    # Filter by content_category = Category1
    # Clips with index 1, 3 will have Category1
    filters_json_cat1 = json.dumps({"content_category": "Category1"})
    response_cat1 = client.get(f'/api/clips?filters={filters_json_cat1}')
    assert response_cat1.status_code == 200
    data_cat1 = response_cat1.get_json()["data"]
    assert len(data_cat1["clips"]) == 2
    for clip in data_cat1["clips"]:
        assert clip["content_category"] == "Category1"

    # Test with a filter that yields no results
    filters_json_no_results = json.dumps({"content_category": "NonExistentCategory"})
    response_no_results = client.get(f'/api/clips?filters={filters_json_no_results}')
    assert response_no_results.status_code == 200
    data_no_results = response_no_results.get_json()["data"]
    assert len(data_no_results["clips"]) == 0
    
    # Test invalid filter JSON string
    invalid_filters_json = '{"content_category": "Category0"' # Missing closing brace
    response_invalid_filter = client.get(f'/api/clips?filters={invalid_filters_json}')
    assert response_invalid_filter.status_code == 400 # Expect Bad Request
    error_data_invalid = response_invalid_filter.get_json()
    assert error_data_invalid["success"] is False
    assert "Invalid 'filters' format" in error_data_invalid["error"] # Changed from error["message"]


def test_get_clip_details_api(client, sample_clips_data):
    """Test GET /api/clips/{clip_id}."""
    clip_id_to_test = sample_clips_data[0] # Get the first inserted clip ID

    response = client.get(f'/api/clips/{clip_id_to_test}')
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert "data" in data
    clip_details = data["data"]["clip"] # ClipsCommand returns {"clip": details} under "data"
    
    assert clip_details is not None
    assert str(clip_details["id"]) == clip_id_to_test
    assert clip_details["file_name"] == "api_vid_0.mp4" # Corresponds to i=0 in fixture

    # Test non-existent clip_id
    non_existent_clip_id = str(uuid.uuid4())
    response_not_found = client.get(f'/api/clips/{non_existent_clip_id}')
    assert response_not_found.status_code == 404
    data_not_found = response_not_found.get_json()
    assert data_not_found["success"] is False
    assert "Clip not found" in data_not_found["error"] # Changed from error["message"]

def test_search_api_query_default(client, sample_clips_data):
    """Test GET /api/search with a simple query and default parameters."""
    # One of the sample clips has "API test summary for clip 0"
    # The API endpoint /api/search uses 'q' as the query parameter.
    response = client.get('/api/search?q=summary for clip 0')
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert "data" in data
    api_response_data = data["data"] # SearchCommand returns results under 'data'
    assert "results" in api_response_data
    assert isinstance(api_response_data["results"], list)
    # We expect at least one result matching "summary for clip 0"
    assert len(api_response_data["results"]) > 0
    found_clip = False
    for clip in api_response_data["results"]:
        if "api_vid_0.mp4" == clip.get("file_name"):
            found_clip = True
            break
    assert found_clip, "Expected to find api_vid_0.mp4 in search results for 'summary for clip 0'"

def test_search_api_query_with_limit(client, sample_clips_data):
    """Test GET /api/search with a query and limit."""
    # All sample clips contain "api_test" tag or "API test summary"
    response = client.get('/api/search?q=api_test&limit=2')
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert "results" in data
    assert len(data["results"]) == 2

def test_search_api_query_specific_type(client, sample_clips_data):
    """Test GET /api/search with a specific search_type (e.g., keyword)."""
    # This test assumes 'keyword' search type is functional.
    # The actual behavior depends on the SearchCommand's implementation for 'keyword'.
    # 'Category0' is in content_category for clips 0, 2, 4.
    # The searchable_content includes content_category (from AIAnalysisSummary).
    response = client.get('/api/search?q=Category0&type=keyword') # 'type' is the param for search_type
    assert response.status_code == 200
    json_response = response.get_json() # Get the whole JSON response
    assert json_response["success"] is True
    assert "data" in json_response
    assert "results" in json_response["data"] # Check for "results" within the "data" field
    assert isinstance(json_response["data"]["results"], list)
    
    # Depending on FTS setup, "Category0" should match clips 0, 2, 4
    # Check if at least one of the expected clips is found.
    # The exact number can vary based on FTS indexing and keyword search logic.
    found_expected_clip = False
    # In sample_clips_data, clips with i=0,2,4 have Category0
    expected_filenames_for_category0 = ["api_vid_0.mp4", "api_vid_2.mp4", "api_vid_4.mp4"]
    
    returned_filenames = [clip.get("file_name") for clip in json_response["data"]["results"]]
    match_count = 0
    for fname in expected_filenames_for_category0:
        if fname in returned_filenames:
            # Further check if the content_category is indeed Category0 for these matches
            for clip_res in json_response["data"]["results"]: # Use json_response["data"] here too
                if clip_res.get("file_name") == fname and clip_res.get("content_category") == "Category0":
                    match_count +=1
                    break # count this file once
    # We expect all 3 clips with Category0 to be found by a keyword search for "Category0"
    # However, the log shows "No FTS results found for query: 'Category0'".
    # This means match_count will be 0. The FTS setup or query needs checking if this is unexpected.
    # For now, let's assert based on what the log indicates (0 results for 'Category0' FTS).
    # This might indicate an issue with FTS indexing of 'content_category' or how it's searched.
    # The FTS index includes 'searchable_content', 'file_name', 'content_summary', 'transcript_preview', 'content_tags'.
    # 'content_category' is not directly indexed for FTS. It's part of 'searchable_content'.
    # If 'Category0' is not found in 'searchable_content' by FTS, this will be 0.
    # Let's assume for now that the FTS query for "Category0" should yield results if present in searchable_content.
    # The log "No FTS results found for query: 'Category0'" is key.
    # This test might be flawed if Category0 isn't properly in searchable_content or FTS isn't picking it up.
    # We expect 3 clips to have "Category0".
    assert len(json_response["data"]["results"]) >= 3, f"Expected at least 3 FTS results for 'Category0', got {len(json_response['data']['results'])}"
    assert match_count == 3, f"Expected 3 clips with 'Category0' in their content_category, found {match_count}. Results: {returned_filenames}"


def test_search_api_empty_query(client, sample_clips_data):
    """Test GET /api/search with an empty query."""
    response = client.get('/api/search?q=') # Empty query
    # The API server's /api/search endpoint requires a non-empty 'q' parameter.
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "MISSING_QUERY" == data["code"] # The 'code' key is at the top level of the JSON response

def test_search_api_no_results(client, sample_clips_data):
    """Test GET /api/search with a query that yields no results."""
    response = client.get('/api/search?q=ThisSpecificStringShouldYieldNoResultsAtAll')
    assert response.status_code == 200 # Search itself succeeds
    data = response.get_json()["data"]
    assert "results" in data
    assert len(data["results"]) == 0

# TODO: Add tests for /api/search/recent and /api/search/similar if their behavior changed
# or if they weren't covered by other test suites.
# For now, focusing on the core /api/clips and /api/search?q=...