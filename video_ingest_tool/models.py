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
    file_path: str
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

class AnalysisDetails(BaseModel):
    scene_changes: List[float] = Field(default_factory=list)
    content_tags: List[str] = Field(default_factory=list)
    content_summary: Optional[str] = None

class VideoIngestOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_info: FileInfo
    video: VideoDetails
    audio_tracks: List[AudioTrack] = Field(default_factory=list)
    subtitle_tracks: List[SubtitleTrack] = Field(default_factory=list)
    camera: CameraDetails
    thumbnails: List[str] = Field(default_factory=list)
    analysis: AnalysisDetails
