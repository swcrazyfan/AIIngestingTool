import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from video_ingest_tool.tasks.analysis.video_analysis import ai_video_analysis_step

SAMPLE_FILE_PATH = "/test/video.mp4"
SAMPLE_CHECKSUM = "samplechecksum"
SAMPLE_THUMBNAILS_DIR = "/tmp/thumbnails_test"
SAMPLE_COMPRESSED_PATH = "/tmp/compressed/video.mp4"
SAMPLE_ANALYSIS_JSON = {"summary": {"content_category": "cat", "overall": "summary", "key_activities": []}}
SAMPLE_RESULT_SUCCESS = {
    "success": True,
    "analysis_json": SAMPLE_ANALYSIS_JSON,
    "compressed_path": SAMPLE_COMPRESSED_PATH
}
SAMPLE_RESULT_FAIL = {"success": False, "error": "fail"}

@pytest.fixture
def mock_logger():
    return MagicMock()

# Happy path: all dependencies available, pre-compressed video exists
@patch("video_ingest_tool.tasks.analysis.video_analysis.HAS_VIDEO_PROCESSOR", True)
@patch("json.dump")
@patch("builtins.open", new_callable=mock_open)
@patch("os.makedirs")
@patch("video_ingest_tool.tasks.analysis.video_analysis._create_ai_summary")
@patch("video_ingest_tool.tasks.analysis.video_analysis.os.path.exists", return_value=True)
@patch("video_ingest_tool.tasks.analysis.video_analysis.VideoProcessor")
def test_happy_path(MockVideoProcessor, mock_exists, mock_create_summary, mock_makedirs, mock_open_file, mock_json_dump, request):
    mock_logger = request.getfixturevalue("mock_logger")
    mock_create_summary.return_value = {"summary": "ok"}
    mock_processor = MockVideoProcessor.return_value
    mock_processor.process.return_value = SAMPLE_RESULT_SUCCESS
    data = {"file_path": SAMPLE_FILE_PATH, "compressed_video_path": SAMPLE_COMPRESSED_PATH}
    # Patch VideoCompressor at the correct import location
    with patch("video_ingest_tool.video_processor.compression.VideoCompressor", autospec=True) as MockCompressor:
        MockCompressor.return_value.compress.return_value = SAMPLE_COMPRESSED_PATH
        result = ai_video_analysis_step.fn(data, SAMPLE_THUMBNAILS_DIR, mock_logger)
        # Check all output keys
        assert set(result.keys()) == {"ai_analysis_summary", "ai_analysis_file_path", "full_ai_analysis_data", "compressed_video_path", "ai_analysis_data"}
        assert result["ai_analysis_summary"] == {"summary": "ok"}
        assert result["ai_analysis_file_path"].endswith("_AI_analysis.json")
        assert result["full_ai_analysis_data"] == SAMPLE_ANALYSIS_JSON
        assert result["compressed_video_path"] == SAMPLE_COMPRESSED_PATH
        assert result["ai_analysis_data"] == {}
        mock_create_summary.assert_called_once_with(SAMPLE_ANALYSIS_JSON)
        mock_json_dump.assert_called_once()
        mock_makedirs.assert_called()
        mock_open_file.assert_called()
        # No real compression should be attempted
        MockCompressor.return_value.compress.assert_not_called()

# VideoProcessor not available
@patch("video_ingest_tool.tasks.analysis.video_analysis.HAS_VIDEO_PROCESSOR", False)
def test_videoprocessor_not_available(mock_logger):
    data = {"file_path": SAMPLE_FILE_PATH}
    result = ai_video_analysis_step.fn(data, SAMPLE_THUMBNAILS_DIR, mock_logger)
    # Check all output keys plus error
    assert set(result.keys()) == {"ai_analysis_summary", "ai_analysis_file_path", "full_ai_analysis_data", "compressed_video_path", "ai_analysis_data", "error"}
    assert result["ai_analysis_summary"] == {}
    assert result["ai_analysis_file_path"] is None
    assert result["full_ai_analysis_data"] == {}
    # compressed_video_path may be None or from input
    assert result["compressed_video_path"] is None or result["compressed_video_path"] == data.get("compressed_video_path")
    assert result["ai_analysis_data"] == {}
    assert "error" in result
    mock_logger.warning.assert_called()

# Missing file_path in data
@patch("video_ingest_tool.tasks.analysis.video_analysis.HAS_VIDEO_PROCESSOR", True)
def test_missing_file_path(mock_logger):
    data = {}
    result = ai_video_analysis_step.fn(data, SAMPLE_THUMBNAILS_DIR, mock_logger)
    # Check all output keys plus error
    assert set(result.keys()) == {"ai_analysis_summary", "ai_analysis_file_path", "full_ai_analysis_data", "compressed_video_path", "ai_analysis_data", "error"}
    assert result["ai_analysis_summary"] == {}
    assert result["ai_analysis_file_path"] is None
    assert result["full_ai_analysis_data"] == {}
    assert result["compressed_video_path"] is None
    assert result["ai_analysis_data"] == {}
    assert "error" in result
    mock_logger.error.assert_called()

# Pre-compressed video is used, no compression should occur
@patch("video_ingest_tool.tasks.analysis.video_analysis.HAS_VIDEO_PROCESSOR", True)
@patch("video_ingest_tool.tasks.analysis.video_analysis.os.path.exists", return_value=True)
@patch("video_ingest_tool.tasks.analysis.video_analysis.VideoProcessor")
def test_precompressed_video_used(MockVideoProcessor, mock_exists, request):
    mock_logger = request.getfixturevalue("mock_logger")
    mock_processor = MockVideoProcessor.return_value
    mock_processor.process.return_value = SAMPLE_RESULT_SUCCESS
    data = {"file_path": SAMPLE_FILE_PATH, "compressed_video_path": SAMPLE_COMPRESSED_PATH}
    with patch("video_ingest_tool.video_processor.compression.VideoCompressor") as MockCompressor:
        result = ai_video_analysis_step.fn(data, logger=mock_logger)
        assert result["compressed_video_path"] == SAMPLE_COMPRESSED_PATH
        mock_exists.assert_any_call(SAMPLE_COMPRESSED_PATH)
        MockCompressor.assert_not_called()

# No pre-compressed video, compression should be called
@patch("video_ingest_tool.steps.analysis.video_analysis.HAS_VIDEO_PROCESSOR", True)
@patch("video_ingest_tool.steps.analysis.video_analysis.os.path.exists", return_value=False)
@patch("video_ingest_tool.steps.analysis.video_analysis.VideoProcessor")
def test_compression_fallback(MockVideoProcessor, mock_exists, request):
    mock_logger = request.getfixturevalue("mock_logger")
    mock_processor = MockVideoProcessor.return_value
    mock_processor.process.return_value = SAMPLE_RESULT_SUCCESS
    data = {"file_path": SAMPLE_FILE_PATH}
    with patch("video_ingest_tool.video_processor.compression.VideoCompressor", autospec=True) as MockCompressor:
        MockCompressor.return_value.compress.return_value = SAMPLE_COMPRESSED_PATH
        ai_video_analysis_step.fn(data, SAMPLE_THUMBNAILS_DIR, mock_logger)
        MockCompressor.return_value.compress.assert_called_once()
        mock_exists.assert_called() 