# AI Video Feature Implementation

## 1. Overview
Implementation of AI video analysis using HEVC compression and Gemini Flash 2.5 with structured output.

## 2. Video Compression Pipeline

```python
from google import genai
from google.genai import types
import av
import os
import sys
from typing import Dict, Any, Optional

class VideoCompressor:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            'width': 1280,  # 720p
            'height': 720,
            'fps': 1,
            'video_bitrate': '1800k',
            'audio_bitrate': '16k',
            'audio_channels': 1,
            **(config or {})
        }

    def compress(self, input_path: str) -> str:
        try:
            output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
            
            with av.open(input_path) as input_container:
                with av.open(output_path, mode='w') as output_container:
                    # Configure video stream
                    codec_name = 'hevc_videotoolbox' if self._has_videotoolbox() else 'libx265'
                    stream = output_container.add_stream(codec_name, rate=1)
                    stream.width = self.config['width']
                    stream.height = self.config['height']
                    stream.pix_fmt = 'yuv420p'
                    stream.codec_context.bit_rate = 1800000  # 1800k
                    
                    # Configure audio stream
                    audio_stream = output_container.add_stream('aac')
                    audio_stream.bit_rate = 16000  # 16k
                    audio_stream.channels = 1
                    
                    # Process frames
                    self._process_streams(input_container, output_container)
                    
            return output_path
                    
        except Exception as e:
            raise RuntimeError(f"Compression failed: {str(e)}")

    def _has_videotoolbox(self) -> bool:
        return sys.platform == "darwin" and self._check_videotoolbox()

    def _check_videotoolbox(self) -> bool:
        try:
            codec = av.CodecContext.create('hevc_videotoolbox', 'w')
            return True
        except:
            return False
            
    def _process_streams(self, input_container, output_container):
        for packet in input_container.demux():
            # Process video frames
            if packet.stream.type == 'video':
                frames = packet.decode()
                if not frames:
                    continue
                for frame in frames:
                    if frame.time * frame.time_base.numerator >= frame.time_base.denominator:
                        packets = output_container.streams.video[0].encode(frame)
                        for pkt in packets:
                            output_container.mux(pkt)
                            
            # Process audio frames
            elif packet.stream.type == 'audio':
                frames = packet.decode()
                if not frames:
                    continue
                for frame in frames:
                    packets = output_container.streams.audio[0].encode(frame)
                    for pkt in packets:
                        output_container.mux(pkt)
```

## 3. Gemini Analysis Integration

```python
class VideoAnalyzer:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        
    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        # Load video bytes
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
        
        # Create video part
        video_part = types.Part.from_bytes(
            data=video_bytes,
            mime_type="video/mp4"
        )
        
        # Define analysis schema
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "OBJECT",
                    "properties": {
                        "overall": {"type": "STRING"},
                        "audio_key_points": {"type": "STRING"}
                    },
                    "required": ["overall", "audio_key_points"]
                },
                "scenes": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "timestamp": {"type": "STRING"},
                            "type": {"type": "STRING"},  # interior/exterior
                            "description": {"type": "STRING"},
                            "people_count": {"type": "INTEGER"},
                            "quality": {
                                "type": "OBJECT",
                                "properties": {
                                    "blur_level": {"type": "INTEGER", "minimum": 0, "maximum": 100},
                                    "noise_level": {"type": "INTEGER", "minimum": 0, "maximum": 100},
                                    "focus_score": {"type": "INTEGER", "minimum": 0, "maximum": 100}
                                }
                            }
                        }
                    }
                },
                "audio": {
                    "type": "OBJECT",
                    "properties": {
                        "has_dialogue": {"type": "BOOLEAN"},
                        "key_phrases": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "sounds": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "timestamp": {"type": "STRING"},
                                    "type": {"type": "STRING"},
                                    "description": {"type": "STRING"}
                                }
                            }
                        }
                    }
                },
                "entities": {
                    "type": "OBJECT",
                    "properties": {
                        "total_people": {"type": "INTEGER"},
                        "people_details": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "count": {"type": "INTEGER"},
                                    "description": {"type": "STRING"}
                                }
                            }
                        },
                        "locations": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "animals": {"type": "ARRAY", "items": {"type": "STRING"}}
                    }
                }
            },
            "required": ["summary", "scenes", "audio", "entities"]
        }

        # Request analysis from Gemini
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[
                "Analyze this video and provide:",
                "1. Overall summary and key audio points",
                "2. Scene details including interior/exterior, people count, and quality",
                "3. Audio elements including dialogue and sounds",
                "4. Entity counts and descriptions",
                video_part
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
        )
        
        return response.text  # Returns structured JSON
```

## 4. Pipeline Integration

```python
@pipeline.register_step(
    name="ai_video_analysis",
    enabled=True,
    description="Analyze video content using Gemini Flash 2.5"
)
def analyze_video_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """Process video through compression and AI analysis pipeline"""
    input_path = data['file_path']
    
    try:
        # 1. Compress video
        compressor = VideoCompressor()
        compressed_path = compressor.compress(input_path)
        
        # 2. Analyze compressed video
        analyzer = VideoAnalyzer(api_key=os.getenv('GEMINI_API_KEY'))
        analysis_results = analyzer.analyze_video(compressed_path)
        
        # 3. Save results
        output_path = f"{os.path.splitext(input_path)[0]}_analysis.json"
        with open(output_path, 'w') as f:
            json.dump(json.loads(analysis_results), f, indent=2)
        
        return {
            'success': True,
            'analysis_path': output_path,
            'compressed_path': compressed_path
        }
    
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
```

## 5. Usage Example

```python
# Initialize pipeline
pipeline = Pipeline()

# Process video
result = pipeline.execute_step(
    "ai_video_analysis",
    {"file_path": "input_video.mp4"}
)

# Handle results
if result['success']:
    print(f"Analysis saved to: {result['analysis_path']}")
    with open(result['analysis_path']) as f:
        analysis = json.load(f)
        print(f"Summary: {analysis['summary']['overall']}")
        print(f"Found {analysis['entities']['total_people']} people")
else:
    print(f"Analysis failed: {result.get('error', 'Unknown error')}")