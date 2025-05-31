"""
Models for the video ingest tool.

Contains all Pydantic models used for data validation and JSON serialization.
"""

import uuid
import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, validator

# ===== Video Metadata Models =====

class AudioTrack(BaseModel):
    """Audio track metadata"""
    track_id: Optional[str] = None
    codec: Optional[str] = None
    codec_id: Optional[str] = None
    channels: Optional[int] = None
    channel_layout: Optional[str] = None
    sample_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    bit_rate_kbps: Optional[int] = None
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    
class SubtitleTrack(BaseModel):
    """Subtitle track metadata"""
    track_id: Optional[str] = None
    format: Optional[str] = None
    language: Optional[str] = None
    codec_id: Optional[str] = None
    embedded: Optional[bool] = None

class FileInfo(BaseModel):
    local_path: str # Renamed from file_path
    file_name: str
    file_checksum: str
    file_size_bytes: int
    created_at: Optional[datetime.datetime] = None
    processed_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

class VideoCodecDetails(BaseModel):
    name: Optional[str] = None
    profile: Optional[str] = None
    level: Optional[str] = None
    bitrate_kbps: Optional[int] = None
    bit_depth: Optional[int] = None
    chroma_subsampling: Optional[str] = None
    pixel_format: Optional[str] = None
    bitrate_mode: Optional[str] = None
    cabac: Optional[bool] = None
    ref_frames: Optional[int] = None
    gop_size: Optional[int] = None
    scan_type: Optional[str] = None
    field_order: Optional[str] = None
    format_name: Optional[str] = None
    format_long_name: Optional[str] = None
    codec_long_name: Optional[str] = None
    file_size_bytes: Optional[int] = None

class VideoResolution(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[str] = None

class VideoHDRDetails(BaseModel):
    is_hdr: bool = False
    format: Optional[str] = None # Corresponds to old hdr_format
    master_display: Optional[str] = None
    max_cll: Optional[int] = None
    max_fall: Optional[int] = None

class VideoColorDetails(BaseModel):
    color_space: Optional[str] = None
    color_primaries: Optional[str] = None
    transfer_characteristics: Optional[str] = None
    matrix_coefficients: Optional[str] = None
    color_range: Optional[str] = None
    hdr: VideoHDRDetails

class VideoExposureDetails(BaseModel):
    warning: Optional[bool] = None
    stops: Optional[float] = None
    overexposed_percentage: Optional[float] = None
    underexposed_percentage: Optional[float] = None

class VideoDetails(BaseModel):
    duration_seconds: Optional[float] = None
    codec: VideoCodecDetails
    container: Optional[str] = None
    resolution: VideoResolution
    frame_rate: Optional[float] = None
    color: VideoColorDetails
    exposure: VideoExposureDetails

class CameraFocalLength(BaseModel):
    value_mm: Optional[float] = None
    category: Optional[str] = None
    source: Optional[str] = None  # "EXIF" or "AI"

class CameraSettings(BaseModel):
    iso: Optional[int] = None
    shutter_speed: Optional[Union[str, float]] = None
    f_stop: Optional[float] = None
    exposure_mode: Optional[str] = None
    white_balance: Optional[str] = None

class CameraLocation(BaseModel):
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    location_name: Optional[str] = None

class CameraDetails(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    lens_model: Optional[str] = None
    focal_length: CameraFocalLength
    settings: CameraSettings
    location: CameraLocation
    camera_serial_number: Optional[str] = None

# ===== AI Analysis Models =====

class ShotType(BaseModel):
    """Individual shot segment with ordered descriptive attributes.
    - 'shot_attributes_ordered': A list of 2-5 descriptive attributes for the shot, ordered by prominence/accuracy (most defining first). Attributes can describe framing, angle, movement, production techniques, or visual style.
    """
    timestamp: str
    duration_seconds: Optional[float] = None
    shot_attributes_ordered: List[str]
    description: str
    confidence: Optional[float] = None

class TechnicalQuality(BaseModel):
    """Technical quality assessment"""
    overall_focus_quality: Optional[str] = None
    stability_assessment: Optional[str] = None
    detected_artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    usability_rating: Optional[str] = None

class DetectedText(BaseModel):
    """Detected text element"""
    timestamp: str
    text_content: Optional[str] = None
    text_type: Optional[str] = None
    readability: Optional[str] = None

class DetectedLogo(BaseModel):
    """Detected logo or icon"""
    timestamp: str
    description: str
    element_type: str
    size: Optional[str] = None

class TextAndGraphics(BaseModel):
    """Text and graphics analysis"""
    detected_text: List[DetectedText] = Field(default_factory=list)
    detected_logos_icons: List[DetectedLogo] = Field(default_factory=list)

class RecommendedKeyframe(BaseModel):
    """Recommended keyframe for thumbnails"""
    timestamp: str
    reason: str
    visual_quality: str

class KeyframeAnalysis(BaseModel):
    """Keyframe analysis results"""
    recommended_keyframes: List[RecommendedKeyframe] = Field(default_factory=list)

class VisualAnalysis(BaseModel):
    """Complete visual analysis results"""
    shot_types: List[ShotType] = Field(default_factory=list)
    technical_quality: Optional[TechnicalQuality] = None
    text_and_graphics: Optional[TextAndGraphics] = None
    keyframe_analysis: Optional[KeyframeAnalysis] = None

class TranscriptSegment(BaseModel):
    """Individual transcript segment"""
    timestamp: str
    speaker: Optional[str] = None
    text: str
    confidence: Optional[float] = None

class Transcript(BaseModel):
    """Complete transcript"""
    full_text: Optional[str] = None
    segments: List[TranscriptSegment] = Field(default_factory=list)

class Speaker(BaseModel):
    """Speaker information"""
    speaker_id: str
    speaking_time_seconds: float
    segments_count: Optional[int] = None

class SpeakerAnalysis(BaseModel):
    """Speaker analysis results"""
    speaker_count: int = 0
    speakers: List[Speaker] = Field(default_factory=list)

class SoundEvent(BaseModel):
    """Detected sound event"""
    timestamp: str
    event_type: str
    description: str
    duration_seconds: Optional[float] = None
    prominence: Optional[str] = None

class AudioQuality(BaseModel):
    """Audio quality assessment"""
    clarity: Optional[str] = None
    background_noise_level: Optional[str] = None
    dialogue_intelligibility: Optional[str] = None

class AudioAnalysis(BaseModel):
    """Complete audio analysis results"""
    transcript: Optional[Transcript] = None
    speaker_analysis: Optional[SpeakerAnalysis] = None
    sound_events: List[SoundEvent] = Field(default_factory=list)
    audio_quality: Optional[AudioQuality] = None

class PersonDetail(BaseModel):
    """Individual person details"""
    description: str
    role: Optional[str] = None
    visibility_duration: Optional[str] = None

class Location(BaseModel):
    """Location information"""
    name: str
    type: str
    description: Optional[str] = None

class ObjectOfInterest(BaseModel):
    """Object of interest"""
    object: str
    significance: str
    timestamp: Optional[str] = None

class Entities(BaseModel):
    """Entity detection results"""
    people_count: int = 0
    people_details: List[PersonDetail] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    objects_of_interest: List[ObjectOfInterest] = Field(default_factory=list)

class Activity(BaseModel):
    """Activity or action"""
    activity: str
    timestamp: str
    duration: Optional[str] = None
    importance: str

class ContentWarning(BaseModel):
    """Content warning"""
    type: str
    description: str
    timestamp: Optional[str] = None

class ContentAnalysis(BaseModel):
    """Complete content analysis results"""
    entities: Optional[Entities] = None
    activity_summary: List[Activity] = Field(default_factory=list)
    content_warnings: List[ContentWarning] = Field(default_factory=list)

class AIAnalysisSummary(BaseModel):
    """AI analysis summary"""
    overall: Optional[str] = None
    key_activities: List[str] = Field(default_factory=list)
    content_category: Optional[str] = None

class ComprehensiveAIAnalysis(BaseModel):
    """Complete AI analysis results from Gemini"""
    summary: Optional[AIAnalysisSummary] = None
    visual_analysis: Optional[VisualAnalysis] = None
    audio_analysis: Optional[AudioAnalysis] = None
    content_analysis: Optional[ContentAnalysis] = None
    analysis_file_path: Optional[str] = None  # Path to detailed JSON file

class AnalysisDetails(BaseModel):
    """Analysis details including both basic and AI analysis"""
    scene_changes: List[float] = Field(default_factory=list)
    content_tags: List[str] = Field(default_factory=list)
    content_summary: Optional[str] = None
    ai_analysis: Optional[ComprehensiveAIAnalysis] = None  # New comprehensive AI analysis

class VideoIngestOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_info: FileInfo
    video: VideoDetails
    audio_tracks: List[AudioTrack] = Field(default_factory=list)
    subtitle_tracks: List[SubtitleTrack] = Field(default_factory=list)
    camera: CameraDetails
    thumbnails: List[str] = Field(default_factory=list)
    analysis: AnalysisDetails
