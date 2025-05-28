#!/usr/bin/env python
"""
Test script for AI thumbnail selection step.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any, List

# Import the AI thumbnail selection step
from video_ingest_tool.steps.analysis.ai_thumbnail_selection import ai_thumbnail_selection_step

# Sample valid data for testing
SAMPLE_FILE_PATH = "/test/video.mp4"
SAMPLE_CHECKSUM = "samplechecksum"
SAMPLE_THUMBNAILS_DIR = "/tmp/thumbnails_test"
SAMPLE_AI_ANALYSIS_DATA_VALID = {
    "visual_analysis": {
        "keyframe_analysis": {
            "recommended_thumbnails": [
                {"timestamp": "1s000ms", "rank": "1", "description": "Desc 1", "reason": "Reason 1"},
                {"timestamp": "5s000ms", "rank": "3", "description": "Desc 3", "reason": "Reason 3"},
                {"timestamp": "3s000ms", "rank": "2", "description": "Desc 2", "reason": "Reason 2"},
            ]
        }
    }
}
SAMPLE_AI_ANALYSIS_DATA_EMPTY_RECS = {
    "visual_analysis": {
        "keyframe_analysis": {
            "recommended_thumbnails": []
        }
    }
}
SAMPLE_AI_ANALYSIS_DATA_MISSING_KEYFRAME_ANALYSIS = {
    "visual_analysis": {}
}
SAMPLE_AI_ANALYSIS_DATA_MISSING_VISUAL_ANALYSIS = {}


@pytest.fixture
def mock_logger():
    return MagicMock()

@patch('video_ingest_tool.steps.analysis.ai_thumbnail_selection.extract_frame_at_timestamp')
@patch('os.makedirs')
def test_ai_thumbnail_selection_happy_path(mock_makedirs, mock_extract_frame, mock_logger):
    """Test the happy path where all inputs are valid and frames are extracted."""
    mock_extract_frame.side_effect = lambda fp, ts, op, ul: op # Return output_path on success

    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID
    }
    
    expected_base_name = "video"
    expected_thumb_dir_name = f"{expected_base_name}_{SAMPLE_CHECKSUM}"
    expected_thumb_dir_for_file = os.path.join(SAMPLE_THUMBNAILS_DIR, expected_thumb_dir_name)

    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)

    assert mock_extract_frame.call_count == 3
    expected_calls = [
        call(SAMPLE_FILE_PATH, "1s000ms", os.path.join(expected_thumb_dir_for_file, f"AI_{expected_base_name}_1s000ms_1.jpg"), mock_logger),
        call(SAMPLE_FILE_PATH, "5s000ms", os.path.join(expected_thumb_dir_for_file, f"AI_{expected_base_name}_5s000ms_3.jpg"), mock_logger),
        call(SAMPLE_FILE_PATH, "3s000ms", os.path.join(expected_thumb_dir_for_file, f"AI_{expected_base_name}_3s000ms_2.jpg"), mock_logger),
    ]
    # Order of calls to mock_extract_frame doesn't matter due to dict iteration
    mock_extract_frame.assert_has_calls(expected_calls, any_order=True)

    assert len(result["ai_thumbnail_paths"]) == 3
    assert len(result["ai_thumbnail_metadata"]) == 3

    # Check sorting by rank
    assert result["ai_thumbnail_metadata"][0]["rank"] == "1"
    assert result["ai_thumbnail_metadata"][1]["rank"] == "2"
    assert result["ai_thumbnail_metadata"][2]["rank"] == "3"
    
    assert result["ai_thumbnail_paths"][0].endswith("_1s000ms_1.jpg")
    assert result["ai_thumbnail_paths"][1].endswith("_3s000ms_2.jpg")
    assert result["ai_thumbnail_paths"][2].endswith("_5s000ms_3.jpg")

    assert result["ai_thumbnail_metadata"][0]["description"] == "Desc 1"
    assert result["ai_thumbnail_metadata"][1]["description"] == "Desc 2"
    assert result["ai_thumbnail_metadata"][2]["description"] == "Desc 3"

def test_missing_file_path_raises_value_error(mock_logger):
    """Test that ValueError is raised if file_path is missing."""
    data_input = {
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID
    }
    with pytest.raises(ValueError, match="Missing file_path or checksum in data"):
        ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)

def test_missing_checksum_raises_value_error(mock_logger):
    """Test that ValueError is raised if checksum is missing."""
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID
    }
    with pytest.raises(ValueError, match="Missing file_path or checksum in data"):
        ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)

def test_missing_thumbnails_dir_raises_value_error(mock_logger):
    """Test that ValueError is raised if thumbnails_dir is missing."""
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID
    }
    with pytest.raises(ValueError, match="Missing thumbnails_dir parameter"):
        ai_thumbnail_selection_step.fn(data_input, None, mock_logger)

@patch('os.makedirs')
def test_missing_full_ai_analysis_data(mock_makedirs, mock_logger):
    """Test behavior when full_ai_analysis_data is missing."""
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM
    }
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    mock_logger.warning.assert_called_with("No analysis results available, skipping AI thumbnail selection")


@patch('os.makedirs')
def test_empty_recommended_thumbnails(mock_makedirs, mock_logger):
    """Test behavior when recommended_thumbnails list is empty."""
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_EMPTY_RECS
    }
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    mock_logger.warning.assert_called_with("No recommended thumbnails in analysis results")


@patch('video_ingest_tool.steps.analysis.ai_thumbnail_selection.extract_frame_at_timestamp')
@patch('os.makedirs')
def test_partial_data_in_recommended_thumbnails(mock_makedirs, mock_extract_frame, mock_logger):
    """Test behavior when a recommended thumbnail is missing timestamp or rank."""
    mock_extract_frame.return_value = "dummy_path.jpg" # So one extraction happens
    
    ai_analysis_partial = {
        "visual_analysis": {
            "keyframe_analysis": {
                "recommended_thumbnails": [
                    {"timestamp": "1s000ms"}, # Missing rank
                    {"rank": "2"},             # Missing timestamp
                    {"timestamp": "3s000ms", "rank": "3"} # Valid
                ]
            }
        }
    }
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": ai_analysis_partial
    }
    
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    
    assert len(result["ai_thumbnail_paths"]) == 1
    assert len(result["ai_thumbnail_metadata"]) == 1
    assert result["ai_thumbnail_metadata"][0]["rank"] == "3"
    
    mock_logger.warning.assert_any_call("Missing timestamp or rank in thumbnail: {\'timestamp\': \'1s000ms\'}")
    mock_logger.warning.assert_any_call("Missing timestamp or rank in thumbnail: {\'rank\': \'2\'}")
    mock_extract_frame.assert_called_once() # Only the valid one should be called


@patch('video_ingest_tool.steps.analysis.ai_thumbnail_selection.extract_frame_at_timestamp')
@patch('os.makedirs')
def test_frame_extraction_failure(mock_makedirs, mock_extract_frame, mock_logger):
    """Test behavior when extract_frame_at_timestamp returns None."""
    mock_extract_frame.return_value = None # Simulate extraction failure for all
    
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID 
    }
    
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    assert mock_extract_frame.call_count == 3 # Attempted for all three
    mock_logger.error.assert_any_call("Failed to extract AI thumbnail at 1s000ms")
    mock_logger.error.assert_any_call("Failed to extract AI thumbnail at 5s000ms")
    mock_logger.error.assert_any_call("Failed to extract AI thumbnail at 3s000ms")

@patch('video_ingest_tool.steps.analysis.ai_thumbnail_selection.extract_frame_at_timestamp')
@patch('os.makedirs')
def test_mixed_extraction_success_and_failure(mock_makedirs, mock_extract_frame, mock_logger):
    """Test behavior with mixed success and failure from extract_frame_at_timestamp."""
    # Simulate success for rank 1 and 3, failure for rank 2
    def side_effect_func(fp, ts, op, ul):
        if "3s000ms_2" in op: # Corresponds to rank 2 item before sorting
            return None 
        return op

    mock_extract_frame.side_effect = side_effect_func
    
    data_input = {
        "file_path": SAMPLE_FILE_PATH,
        "checksum": SAMPLE_CHECKSUM,
        "full_ai_analysis_data": SAMPLE_AI_ANALYSIS_DATA_VALID
    }
    
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)

    assert len(result["ai_thumbnail_paths"]) == 2
    assert len(result["ai_thumbnail_metadata"]) == 2
    
    # Check that rank 1 and 3 are present, and rank 2 is missing
    ranks_present = [item["rank"] for item in result["ai_thumbnail_metadata"]]
    assert "1" in ranks_present
    assert "3" in ranks_present
    assert "2" not in ranks_present

    # Check sorting for the remaining items
    assert result["ai_thumbnail_metadata"][0]["rank"] == "1"
    assert result["ai_thumbnail_metadata"][1]["rank"] == "3"

    mock_logger.error.assert_called_once_with("Failed to extract AI thumbnail at 3s000ms")

@patch('os.makedirs')
def test_no_analysis_results_logs_warning(mock_makedirs, mock_logger):
    """Test that a warning is logged if analysis_results is not in data."""
    data_input = {
        'file_path': SAMPLE_FILE_PATH,
        'checksum': SAMPLE_CHECKSUM,
        # 'full_ai_analysis_data' is missing
    }
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    mock_logger.warning.assert_called_with("No analysis results available, skipping AI thumbnail selection")

@patch('os.makedirs')
def test_no_recommended_thumbnails_logs_warning(mock_makedirs, mock_logger):
    """Test that a warning is logged if recommended_thumbnails is empty or not found."""
    data_input = {
        'file_path': SAMPLE_FILE_PATH,
        'checksum': SAMPLE_CHECKSUM,
        'full_ai_analysis_data': SAMPLE_AI_ANALYSIS_DATA_MISSING_KEYFRAME_ANALYSIS # Does not contain recommended_thumbnails
    }
    result = ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    mock_logger.warning.assert_called_with("No recommended thumbnails in analysis results")
    
    data_input_empty_list = {
        'file_path': SAMPLE_FILE_PATH,
        'checksum': SAMPLE_CHECKSUM,
        'full_ai_analysis_data': SAMPLE_AI_ANALYSIS_DATA_EMPTY_RECS # Contains empty list
    }
    result = ai_thumbnail_selection_step.fn(data_input_empty_list, SAMPLE_THUMBNAILS_DIR, mock_logger)
    assert result == {"ai_thumbnail_paths": [], "ai_thumbnail_metadata": []}
    mock_logger.warning.assert_called_with("No recommended thumbnails in analysis results")

@patch('video_ingest_tool.steps.analysis.ai_thumbnail_selection.extract_frame_at_timestamp')
@patch('os.makedirs')
def test_thumbnail_filename_creation(mock_makedirs, mock_extract_frame, mock_logger):
    """Test the correct creation of thumbnail filenames."""
    mock_extract_frame.return_value = "dummy_path.jpg"

    data_input = {
        "file_path": "/a/b/c/my video file with spaces.mkv",
        "checksum": "testchecksum123",
        "full_ai_analysis_data": {
            "visual_analysis": {
                "keyframe_analysis": {
                    "recommended_thumbnails": [
                        {"timestamp": "10s500ms", "rank": "1", "description": "Test", "reason": "Test"}
                    ]
                }
            }
        }
    }
    
    expected_base_name = "my video file with spaces"
    expected_thumb_dir_name = f"{expected_base_name}_testchecksum123"
    expected_thumb_dir_for_file = os.path.join(SAMPLE_THUMBNAILS_DIR, expected_thumb_dir_name)

    ai_thumbnail_selection_step.fn(data_input, SAMPLE_THUMBNAILS_DIR, mock_logger)

    expected_output_path = os.path.join(expected_thumb_dir_for_file, f"AI_{expected_base_name}_10s500ms_1.jpg")
    mock_extract_frame.assert_called_once_with(
        "/a/b/c/my video file with spaces.mkv",
        "10s500ms",
        expected_output_path,
        mock_logger
    )

if __name__ == "__main__":
    pytest.main() 