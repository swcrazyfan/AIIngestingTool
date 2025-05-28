import pytest
from unittest.mock import patch, MagicMock, mock_open
from video_ingest_tool.steps.storage.thumbnail_upload import upload_thumbnails_step

SAMPLE_THUMBNAIL_PATH = "/tmp/thumb1.jpg"
SAMPLE_AI_THUMBNAIL_PATH = "/tmp/ai_thumb1.jpg"
SAMPLE_CLIP_ID = "clip123"
SAMPLE_USER_ID = "user456"
SAMPLE_THUMBNAIL_METADATA = [{"path": SAMPLE_AI_THUMBNAIL_PATH, "rank": "1", "timestamp": "1s", "description": "desc", "reason": "reason"}]

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def mock_auth_manager():
    with patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager") as MockAuthManager:
        yield MockAuthManager

@pytest.fixture
def mock_client():
    client = MagicMock()
    # Mock user response
    user = MagicMock()
    user.id = SAMPLE_USER_ID
    client.auth.get_user.return_value.user = user
    # Mock storage
    storage = MagicMock()
    client.storage.from_.return_value = storage
    storage.list.return_value = []
    storage.upload.return_value = None
    storage.get_public_url.return_value = "https://supabase.io/thumb.jpg"
    # Mock table update
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    return client

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_happy_path(MockAuthManager, mock_open_file, mock_exists, mock_logger, mock_client):
    # Setup mocks
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    data = {
        "thumbnail_paths": [SAMPLE_THUMBNAIL_PATH],
        "ai_thumbnail_paths": [SAMPLE_AI_THUMBNAIL_PATH],
        "ai_thumbnail_metadata": SAMPLE_THUMBNAIL_METADATA,
        "clip_id": SAMPLE_CLIP_ID
    }
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    assert "https://supabase.io/thumb.jpg" in result["thumbnail_urls"]
    assert "https://supabase.io/thumb.jpg" in result["ai_thumbnail_urls"]
    mock_logger.info.assert_any_call("Uploaded thumbnail: users/user456/videos/clip123/thumbnails/thumb1.jpg")
    mock_logger.info.assert_any_call("Uploaded AI thumbnail: users/user456/videos/clip123/thumbnails/ai_thumb1.jpg")
    mock_logger.info.assert_any_call(f"Updated clip record with thumbnail data: {SAMPLE_CLIP_ID}")

@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_no_thumbnails(MockAuthManager, mock_logger):
    MockAuthManager.return_value.get_authenticated_client.return_value = MagicMock()
    data = {"clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_skipped"] is True
    assert result["reason"] == "no_thumbnails"
    mock_logger.warning.assert_called_with("No thumbnails available for upload")

@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_no_clip_id(MockAuthManager, mock_logger):
    MockAuthManager.return_value.get_authenticated_client.return_value = MagicMock()
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH]}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_skipped"] is True
    assert result["reason"] == "no_clip_id"
    mock_logger.warning.assert_called_with("No clip_id available, thumbnails cannot be uploaded")

@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_not_authenticated(MockAuthManager, mock_logger):
    MockAuthManager.return_value.get_authenticated_client.return_value = None
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH], "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_skipped"] is True
    assert result["reason"] == "not_authenticated"
    mock_logger.warning.assert_called_with("Skipping thumbnail upload - not authenticated")

@patch("os.path.exists", return_value=False)
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_file_not_found(MockAuthManager, mock_exists, mock_logger, mock_client):
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH], "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    assert result["thumbnail_urls"] == []
    mock_logger.warning.assert_any_call(f"Thumbnail file not found: {SAMPLE_THUMBNAIL_PATH}")

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_file_already_exists(MockAuthManager, mock_open_file, mock_exists, mock_logger, mock_client):
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    # Simulate file already exists in storage
    mock_client.storage.from_.return_value.list.return_value = [{"name": "thumb1.jpg"}]
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH], "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    mock_logger.info.assert_any_call("Thumbnail already exists, skipping upload: users/user456/videos/clip123/thumbnails/thumb1.jpg")

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_upload_error(MockAuthManager, mock_open_file, mock_exists, mock_logger, mock_client):
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    # Simulate upload error
    mock_client.storage.from_.return_value.upload.side_effect = Exception("Upload failed")
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH], "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    mock_logger.error.assert_any_call("Error uploading thumbnail thumb1.jpg: Upload failed")

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_ai_thumbnail_missing_rank(MockAuthManager, mock_open_file, mock_exists, mock_logger, mock_client):
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    # AI thumbnail metadata missing rank
    ai_metadata = [{"path": SAMPLE_AI_THUMBNAIL_PATH}]
    data = {"ai_thumbnail_paths": [SAMPLE_AI_THUMBNAIL_PATH], "ai_thumbnail_metadata": ai_metadata, "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    mock_logger.warning.assert_any_call(f"Missing rank for AI thumbnail: {SAMPLE_AI_THUMBNAIL_PATH}")

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"data")
@patch("video_ingest_tool.steps.storage.thumbnail_upload.AuthManager")
def test_db_update_error(MockAuthManager, mock_open_file, mock_exists, mock_logger, mock_client):
    MockAuthManager.return_value.get_authenticated_client.return_value = mock_client
    # Simulate DB update error
    mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("DB error")
    data = {"thumbnail_paths": [SAMPLE_THUMBNAIL_PATH], "clip_id": SAMPLE_CLIP_ID}
    result = upload_thumbnails_step.fn(data, mock_logger)
    assert result["thumbnail_upload_success"] is True
    mock_logger.error.assert_any_call("Failed to update clips table: DB error") 