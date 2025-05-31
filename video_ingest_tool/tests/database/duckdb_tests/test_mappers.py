import pytest
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

# Use real mappers and models
from video_ingest_tool.database.duckdb.mappers import prepare_clip_data_for_db, _generate_searchable_content
from video_ingest_tool.models import (
    VideoIngestOutput, FileInfo, VideoDetails, VideoCodecDetails, VideoResolution,
    VideoColorDetails, VideoHDRDetails, VideoExposureDetails, CameraDetails,
    CameraFocalLength, CameraSettings, CameraLocation, AnalysisDetails,
    ComprehensiveAIAnalysis, AIAnalysisSummary, AudioAnalysis, Transcript, TranscriptSegment,
    SpeakerAnalysis, SoundEvent, AudioQuality, VisualAnalysis, ShotType, TechnicalQuality,
    TextAndGraphics, DetectedText, DetectedLogo, KeyframeAnalysis, RecommendedKeyframe,
    ContentAnalysis, Entities, PersonDetail, Activity, ContentWarning,
    AudioTrack, SubtitleTrack,
    Location as ModelLocation # Alias if needed
)

# TRANSCRIPT_PREVIEW_MAX_LENGTH removed

# --- Test Data Fixtures ---
@pytest.fixture
def sample_file_info_model() -> FileInfo:
    # FileInfo model now has local_path instead of file_path
    return FileInfo(
        local_path="/local/test/video.mp4", # Was file_path
        file_name="video.mp4",
        file_checksum="testchecksum123",
        file_size_bytes=12345678,
        created_at=datetime(2023, 1, 1, 11, 55, 0), # For created_at
        processed_at=datetime(2023, 1, 1, 12, 0, 0) # For processed_at
        # container_format is not in FileInfo, it's in VideoDetails
        # technical_metadata is not in FileInfo, it's part of VideoDetails.codec
    )

@pytest.fixture
def sample_video_details_model() -> VideoDetails:
    codec = VideoCodecDetails(
        name="h264",
        profile="High",
        level="4.1",
        bitrate_kbps=5000,
        bit_depth=8,
        chroma_subsampling="4:2:0",
        pixel_format="yuv420p"
    )
    resolution = VideoResolution(width=1920, height=1080, aspect_ratio="16:9")
    hdr_details = VideoHDRDetails(is_hdr=False)
    color = VideoColorDetails(
        color_space="bt709",
        color_primaries="bt709",
        transfer_characteristics="bt709",
        matrix_coefficients="bt709",
        hdr=hdr_details
    )
    exposure = VideoExposureDetails(warning=False, stops=0.0)
    return VideoDetails(
        duration_seconds=120.5,
        codec=codec,
        container="mp4",
        resolution=resolution,
        frame_rate=29.97,
        color=color,
        exposure=exposure
    )

@pytest.fixture
def sample_camera_details_model() -> CameraDetails:
    focal_length = CameraFocalLength(value_mm=50.0, category="Standard", source="EXIF")
    settings = CameraSettings(iso=100, shutter_speed="1/50", f_stop=1.8)
    location = CameraLocation(gps_latitude=34.0522, gps_longitude=-118.2437)
    return CameraDetails(
        make="TestMake",
        model="TestModel",
        lens_model="TestLens 50mm",
        focal_length=focal_length,
        settings=settings,
        location=location
    )

@pytest.fixture
def sample_analysis_details_model() -> AnalysisDetails:
    transcript = Transcript(
        full_text="This is a sample transcript for testing purposes. It is long enough to be truncated for the preview.",
        segments=[TranscriptSegment(timestamp="00:00:01.000", text="This is a sample", speaker="SPEAKER_00")]
    )
    audio_analysis = AudioAnalysis(transcript=transcript)
    
    # RecommendedKeyframe model does not have local_path.
    # The mapper's primary_thumbnail_path derivation will be None or based on future logic.
    recommended_keyframes = [
        RecommendedKeyframe(timestamp="00:00:10.000", reason="Good shot", visual_quality="High")
    ]
    keyframe_analysis = KeyframeAnalysis(recommended_keyframes=recommended_keyframes)
    visual_analysis = VisualAnalysis(keyframe_analysis=keyframe_analysis)
    
    ai_summary = AIAnalysisSummary(overall="Test summary overall.", content_category="Test Category")
    
    ai_analysis = ComprehensiveAIAnalysis(
        summary=ai_summary,
        visual_analysis=visual_analysis,
        audio_analysis=audio_analysis,
        # content_analysis can be None or populated
    )
    return AnalysisDetails(
        content_tags=["test", "sample", "mapper"],
        content_summary="A test video for mappers.", # This is from AnalysisDetails itself
        ai_analysis=ai_analysis
    )

@pytest.fixture
def sample_audio_tracks_model() -> List[AudioTrack]:
    return [AudioTrack(track_id="1", codec="aac", channels=2, language="eng")]

@pytest.fixture
def sample_subtitle_tracks_model() -> List[SubtitleTrack]:
    return [SubtitleTrack(track_id="1", format="srt", language="eng", embedded=True)]


@pytest.fixture
def sample_ai_selected_thumbnail_metadata() -> List[Dict[str, Any]]:
    return [
        {"path": "/local/test/ai_thumb_rank1.jpg", "timestamp": "00:00:10.000", "rank": 1, "description": "Best AI thumb", "reason": "High quality"},
        {"path": "/local/test/ai_thumb_rank2.jpg", "timestamp": "00:00:20.000", "rank": 2, "description": "Second best", "reason": "Good focus"},
    ]

@pytest.fixture
def sample_video_ingest_output_model(
    sample_file_info_model: FileInfo,
    sample_video_details_model: VideoDetails,
    sample_camera_details_model: CameraDetails,
    sample_analysis_details_model: AnalysisDetails,
    sample_audio_tracks_model: List[AudioTrack],
    sample_subtitle_tracks_model: List[SubtitleTrack]
    # ai_selected_thumbnail_metadata is now passed separately to the mapper
) -> VideoIngestOutput:
    # VideoIngestOutput.thumbnails is List[str] (paths for initially generated, not AI selected)
    thumbnails_paths = ["/local/test/gen_thumb1.jpg", "/local/test/gen_thumb2.jpg"]
    return VideoIngestOutput(
        id=str(uuid.UUID("123e4567-e89b-12d3-a456-426614174000")), # Fixed UUID for predictable tests
        file_info=sample_file_info_model,
        video=sample_video_details_model,
        audio_tracks=sample_audio_tracks_model,
        subtitle_tracks=sample_subtitle_tracks_model,
        camera=sample_camera_details_model,
        thumbnails=thumbnails_paths,
        analysis=sample_analysis_details_model
    )

@pytest.fixture
def sample_embeddings() -> Dict[str, List[float]]:
    return {
        "summary_embedding": [0.1] * 1024,
        "keyword_embedding": [0.2] * 1024,
        "thumbnail_1_embedding": [0.3] * 768,
        "thumbnail_2_embedding": [0.4] * 768,
        "thumbnail_3_embedding": [0.5] * 768,
    }

# --- Test Cases ---

def test_prepare_clip_data_for_db_with_real_models(
    sample_video_ingest_output_model: VideoIngestOutput,
    sample_embeddings: Dict[str, List[float]],
    sample_ai_selected_thumbnail_metadata: List[Dict[str, Any]]
):
    """Test mapping with real Pydantic models and AI thumbnail metadata."""
    vio = sample_video_ingest_output_model
    prepared_data = prepare_clip_data_for_db(vio, sample_embeddings, sample_ai_selected_thumbnail_metadata)

    assert prepared_data is not None
    assert prepared_data["id"] == vio.id
    assert prepared_data["local_path"] == vio.file_info.local_path # Changed from file_path
    assert "file_path" not in prepared_data # Ensure old file_path is gone
    assert prepared_data["file_name"] == vio.file_info.file_name
    assert prepared_data["file_checksum"] == vio.file_info.file_checksum
    assert prepared_data["file_size_bytes"] == vio.file_info.file_size_bytes
    assert prepared_data["created_at"] == vio.file_info.created_at
    assert prepared_data["processed_at"] == vio.file_info.processed_at
    assert isinstance(prepared_data["updated_at"], datetime)

    assert prepared_data["duration_seconds"] == vio.video.duration_seconds
    assert prepared_data["width"] == vio.video.resolution.width
    assert prepared_data["height"] == vio.video.resolution.height
    assert prepared_data["frame_rate"] == vio.video.frame_rate
    assert prepared_data["codec"] == vio.video.codec.name
    assert prepared_data["container"] == vio.video.container
    assert json.loads(prepared_data["technical_metadata"]) == vio.video.codec.model_dump()
    
    assert prepared_data["camera_make"] == vio.camera.make
    assert prepared_data["camera_model"] == vio.camera.model
    assert json.loads(prepared_data["camera_details"]) == vio.camera.model_dump()

    assert prepared_data["content_summary"] == vio.analysis.content_summary
    assert prepared_data["content_tags"] == vio.analysis.content_tags
    
    if vio.analysis.ai_analysis:
        ai = vio.analysis.ai_analysis
        assert prepared_data["content_category"] == (ai.summary.content_category if ai.summary else None)
        
        if ai.audio_analysis and ai.audio_analysis.transcript:
            tr = ai.audio_analysis.transcript
            assert prepared_data["full_transcript"] == tr.full_text
            # transcript_preview should now be the same as full_text
            assert prepared_data["transcript_preview"] == tr.full_text
            assert json.loads(prepared_data["transcript_segments_json"]) == [s.model_dump() for s in tr.segments]

        # Check primary_thumbnail_path (sourced from sample_ai_selected_thumbnail_metadata)
        assert prepared_data["primary_thumbnail_path"] == sample_ai_selected_thumbnail_metadata[0]["path"] # Rank 1
        
        # Check ai_selected_thumbnails_json (sourced from sample_ai_selected_thumbnail_metadata)
        assert json.loads(prepared_data["ai_selected_thumbnails_json"]) == sample_ai_selected_thumbnail_metadata
            
        assert json.loads(prepared_data["full_ai_analysis_json"]) == ai.model_dump()
    
    assert json.loads(prepared_data["audio_tracks"]) == [t.model_dump() for t in vio.audio_tracks]
    assert json.loads(prepared_data["subtitle_tracks"]) == [t.model_dump() for t in vio.subtitle_tracks]
    assert prepared_data["thumbnails"] == vio.thumbnails

    # Embeddings
    assert prepared_data["summary_embedding"] == sample_embeddings["summary_embedding"]
    # ... other embeddings

    # Check searchable_content
    assert isinstance(prepared_data["searchable_content"], str)
    assert vio.file_info.file_name in prepared_data["searchable_content"]
    if vio.analysis and vio.analysis.content_summary: # Check if analysis exists
        assert vio.analysis.content_summary in prepared_data["searchable_content"]


def test_generate_searchable_content_with_real_models(sample_video_ingest_output_model: VideoIngestOutput):
    """Test the _generate_searchable_content helper function with real models."""
    vio = sample_video_ingest_output_model
    content = _generate_searchable_content(vio)
    
    assert content is not None
    assert isinstance(content, str)
    
    assert vio.file_info.file_name in content
    if vio.analysis.content_summary:
        assert vio.analysis.content_summary in content
    if vio.analysis.content_tags:
        for tag in vio.analysis.content_tags:
            assert tag in content
    
    if vio.analysis.ai_analysis:
        ai = vio.analysis.ai_analysis
        if ai.summary and ai.summary.overall:
            assert ai.summary.overall in content
        if ai.summary and ai.summary.content_category:
            assert ai.summary.content_category in content
        if ai.audio_analysis and ai.audio_analysis.transcript:
            tr = ai.audio_analysis.transcript
            if tr.full_text:
                assert tr.full_text in content
                # If transcript_preview is the same as full_text, it's already covered.


def test_prepare_clip_data_minimal_real_input():
    """Test with minimal valid real VideoIngestOutput."""
    # This test will also pass ai_selected_thumbnail_metadata as None or empty
    minimal_file_info = FileInfo(
        local_path="/local/minimal/video.mkv",
        file_name="video_minimal.mkv",
        file_checksum="minimalsum",
        file_size_bytes=1000,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow()
    )
    # For VideoDetails, its sub-models like VideoCodecDetails are not Optional.
    # We need to provide them, even if their internal fields are optional.
    minimal_codec = VideoCodecDetails()
    minimal_resolution = VideoResolution()
    minimal_hdr = VideoHDRDetails(is_hdr=False) # is_hdr is not optional
    minimal_color = VideoColorDetails(hdr=minimal_hdr)
    minimal_exposure = VideoExposureDetails()

    minimal_video_details = VideoDetails(
        codec=minimal_codec,
        resolution=minimal_resolution,
        color=minimal_color,
        exposure=minimal_exposure
        # duration_seconds, container, frame_rate are optional
    )
    
    # For CameraDetails, its sub-models are not Optional
    minimal_focal = CameraFocalLength()
    minimal_cam_settings = CameraSettings()
    minimal_cam_loc = CameraLocation()
    minimal_camera_details = CameraDetails(
        focal_length=minimal_focal,
        settings=minimal_cam_settings,
        location=minimal_cam_loc
    )

    minimal_analysis_details = AnalysisDetails() # content_tags, summary, ai_analysis are optional or have defaults

    minimal_vio = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=minimal_file_info,
        video=minimal_video_details,
        camera=minimal_camera_details,
        analysis=minimal_analysis_details
        # audio_tracks, subtitle_tracks, thumbnails have defaults
    )
    embeddings = {}
    ai_thumb_meta_empty = []

    prepared_data = prepare_clip_data_for_db(minimal_vio, embeddings, ai_thumb_meta_empty)
    assert prepared_data is not None
    assert prepared_data["file_checksum"] == "minimalsum"
    assert prepared_data["primary_thumbnail_path"] is None # No AI thumbs provided
    assert prepared_data["ai_selected_thumbnails_json"] is None # No AI thumbs provided
    assert prepared_data["id"] == minimal_vio.id
    assert prepared_data["summary_embedding"] is None

    searchable = _generate_searchable_content(minimal_vio)
    assert searchable is not None
    assert "video_minimal.mkv" in searchable

# Removed test_prepare_clip_data_missing_file_info_checksum because Pydantic model validation
# for FileInfo.file_checksum (being a non-optional str) prevents this state from reaching the mapper.

def test_prepare_clip_data_various_none_fields(
    sample_file_info_model: FileInfo,
    sample_video_details_model: VideoDetails, # Keep some core parts
    sample_embeddings: Dict[str, List[float]]
):
    """Test mapper when many optional fields or sub-objects are None."""
    # Create a VideoIngestOutput with many fields set to None or empty
    vio_with_nones = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=sample_file_info_model, # Essential
        video=sample_video_details_model,   # Essential
        audio_tracks=[], # Empty list
        subtitle_tracks=[], # Empty list
        camera=CameraDetails( # CameraDetails itself is not optional, but its fields are
            make=None, model=None, lens_model=None,
            focal_length=CameraFocalLength(value_mm=None, category=None, source=None),
            settings=CameraSettings(iso=None, shutter_speed=None, f_stop=None),
            location=CameraLocation(gps_latitude=None, gps_longitude=None)
        ),
        thumbnails=[], # Empty list
        analysis=AnalysisDetails( # AnalysisDetails itself is not optional
            content_tags=[],
            content_summary=None,
            ai_analysis=ComprehensiveAIAnalysis( # ai_analysis is optional within AnalysisDetails
                summary=AIAnalysisSummary(overall=None, content_category=None, key_activities=[]),
                visual_analysis=VisualAnalysis(
                    shot_types=[],
                    technical_quality=TechnicalQuality(overall_focus_quality=None, stability_assessment=None, usability_rating=None), # Sub-fields are optional
                    keyframe_analysis=KeyframeAnalysis(recommended_keyframes=[]) # recommended_keyframes is not Optional
                ),
                audio_analysis=AudioAnalysis(
                    transcript=Transcript(full_text=None, segments=[]), # segments is not Optional
                    speaker_analysis=SpeakerAnalysis(speaker_count=0, speakers=[]), # speakers is not Optional
                    sound_events=[], # sound_events is not Optional
                    audio_quality=AudioQuality(clarity=None, background_noise_level=None, dialogue_intelligibility=None)
                ),
                content_analysis=ContentAnalysis( # content_analysis is Optional
                    entities=Entities(people_count=0, people_details=[], locations=[], objects_of_interest=[]), # sub-fields not Optional
                    activity_summary=[], # not Optional
                    content_warnings=[] # not Optional
                )
            )
        )
    )

    prepared_data = prepare_clip_data_for_db(vio_with_nones, sample_embeddings, None) # No AI thumbs

    assert prepared_data is not None
    assert prepared_data["id"] == vio_with_nones.id
    assert prepared_data["local_path"] == vio_with_nones.file_info.local_path

    # Check fields that should be None or default
    assert prepared_data["camera_make"] is None
    assert prepared_data["camera_model"] is None
    loaded_camera_details = json.loads(prepared_data["camera_details"])
    assert loaded_camera_details["make"] is None
    assert loaded_camera_details["focal_length"]["value_mm"] is None


    assert prepared_data["content_category"] is None
    assert prepared_data["content_summary"] is None # From AnalysisDetails.content_summary
    assert prepared_data["content_tags"] == [] # Empty list

    assert prepared_data["full_transcript"] is None
    assert prepared_data["transcript_preview"] is None
    assert json.loads(prepared_data["transcript_segments_json"]) == []

    assert prepared_data["thumbnails"] == []
    assert prepared_data["primary_thumbnail_path"] is None
    assert prepared_data["ai_selected_thumbnails_json"] is None # No AI metadata passed
    
    loaded_full_ai_json = json.loads(prepared_data["full_ai_analysis_json"])
    assert loaded_full_ai_json["summary"]["overall"] is None
    assert loaded_full_ai_json["visual_analysis"]["shot_types"] == []

    assert prepared_data["audio_tracks"] == "[]" # Expect JSON string for empty list
    assert json.loads(prepared_data["audio_tracks"]) == []
    assert prepared_data["subtitle_tracks"] == "[]" # Expect JSON string for empty list
    assert json.loads(prepared_data["subtitle_tracks"]) == []

    # Embeddings should still be there
    assert prepared_data["summary_embedding"] == sample_embeddings["summary_embedding"]

def test_generate_searchable_content_minimal_vio():
    """Test _generate_searchable_content with a VIO having minimal data (e.g. no AI analysis)."""
    minimal_file_info = FileInfo(local_path="minimal.mp4", file_name="minimal.mp4", file_checksum="min", file_size_bytes=1)
    minimal_vio = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=minimal_file_info,
        video=VideoDetails(
            codec=VideoCodecDetails(),
            resolution=VideoResolution(),
            color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)),
            exposure=VideoExposureDetails()
        ),
        camera=CameraDetails(
            focal_length=CameraFocalLength(),
            settings=CameraSettings(),
            location=CameraLocation()
        ),
        analysis=AnalysisDetails(content_summary="Minimal summary.", content_tags=["minimal_tag"], ai_analysis=None) # No AI analysis
    )
    content = _generate_searchable_content(minimal_vio)
    assert content is not None
    assert "minimal.mp4" in content
    assert "Minimal summary." in content
    assert "minimal_tag" in content

def test_generate_searchable_content_no_text_fields():
    """Test _generate_searchable_content when all relevant text fields in VIO are None or empty."""
    no_text_file_info = FileInfo(local_path="no_text.mp4", file_name="", file_checksum="notext", file_size_bytes=1) # Changed file_name=None to file_name=""
    no_text_vio = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=no_text_file_info,
        video=VideoDetails(codec=VideoCodecDetails(), resolution=VideoResolution(), color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)), exposure=VideoExposureDetails()),
        camera=CameraDetails(focal_length=CameraFocalLength(), settings=CameraSettings(), location=CameraLocation()),
        analysis=AnalysisDetails(
            content_summary=None,
            content_tags=[],
            ai_analysis=ComprehensiveAIAnalysis( # AI analysis exists but its text fields are None/empty
                summary=AIAnalysisSummary(overall=None, content_category=None, key_activities=[]),
                audio_analysis=AudioAnalysis(transcript=Transcript(full_text=None))
                # Other AI parts can be default
            )
        )
    )
    content = _generate_searchable_content(no_text_vio)
    assert content is None

def test_json_field_structures_and_defaults(
    sample_file_info_model: FileInfo, # Use a basic FileInfo
    sample_embeddings: Dict[str, List[float]] # For completeness of prepare_clip_data_for_db call
):
    """Test the structure of serialized JSON fields, especially when parts of AI analysis are missing."""
    # Create VIO with missing AI analysis components
    vio_partial_ai = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=sample_file_info_model,
        video=VideoDetails( # Simplified VideoDetails
            codec=VideoCodecDetails(name="h264"),
            resolution=VideoResolution(width=1280, height=720),
            color=VideoColorDetails(hdr=VideoHDRDetails(is_hdr=False)),
            exposure=VideoExposureDetails()
        ),
        camera=CameraDetails( # Simplified CameraDetails
            make="PartialCam",
            focal_length=CameraFocalLength(),
            settings=CameraSettings(),
            location=CameraLocation()
        ),
        analysis=AnalysisDetails(
            content_summary="Partial AI summary.",
            ai_analysis=ComprehensiveAIAnalysis( # AI object exists
                summary=AIAnalysisSummary(overall="Overall from partial AI.", content_category="Partial Cat"),
                visual_analysis=None, # Visual analysis is missing
                audio_analysis=AudioAnalysis(transcript=None), # Audio analysis exists, but no transcript
                content_analysis=None # Content analysis missing
            )
        ),
        audio_tracks=[],
        subtitle_tracks=[],
        thumbnails=[]
    )

    prepared_data = prepare_clip_data_for_db(vio_partial_ai, sample_embeddings, None)
    assert prepared_data is not None

    # CameraDetails (should still serialize fine even if some internal fields are default/None)
    cam_details = json.loads(prepared_data["camera_details"])
    assert cam_details["make"] == "PartialCam"
    assert cam_details["focal_length"]["value_mm"] is None # Default from empty CameraFocalLength

    # TechnicalMetadata (VideoCodecDetails)
    tech_meta = json.loads(prepared_data["technical_metadata"])
    assert tech_meta["name"] == "h264"

    # TranscriptSegments should be None as transcript was None
    assert prepared_data["transcript_segments_json"] is None
    assert prepared_data["full_transcript"] is None
    assert prepared_data["transcript_preview"] is None


    # AI Selected Thumbnails (None because ai_selected_thumbnail_metadata was None)
    assert prepared_data["ai_selected_thumbnails_json"] is None
    assert prepared_data["primary_thumbnail_path"] is None

    # Full AI Analysis (should serialize what's there, with None for missing parts)
    full_ai = json.loads(prepared_data["full_ai_analysis_json"])
    assert full_ai["summary"]["overall"] == "Overall from partial AI."
    assert full_ai["visual_analysis"] is None # Was set to None
    assert full_ai["audio_analysis"]["transcript"] is None # Was set to None
    assert full_ai["content_analysis"] is None # Was set to None

# Further tests to consider:
# - Behavior when VideoIngestOutput itself is None or not the right type (e.g. passed to mapper).