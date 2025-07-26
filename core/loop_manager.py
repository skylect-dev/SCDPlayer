"""
Loop point management for SCD files - Clean codec-aware implementation
Based on vgmstream sqex_scd.c source analysis

Key insights from vgmstream source:
- SCD header format: SEDB + SSCF signature
- Stream header at meta_offset contains:
  - stream_size (0x00), channels (0x04), sample_rate (0x08), codec (0x0c)
  - loop_start (0x10), loop_end (0x14) - BUT only for non-OGG codecs!
- Codec 0x06 (OGG Vorbis): "loop values are in bytes, let init_vgmstream_ogg_vorbis find loop comments instead"
- Other codecs store loop points in SCD header at meta_offset + 0x10/0x14
"""
import logging
import struct
from typing import Optional, Tuple, Dict, Any
from pathlib import Path


class LoopPoint:
    """Represents a loop point with sample-accurate positioning"""
    
    def __init__(self, start_sample: int = 0, end_sample: int = 0):
        self.start_sample = start_sample
        self.end_sample = end_sample
    
    def __str__(self):
        return f"Loop({self.start_sample} -> {self.end_sample})"
    
    def is_valid(self, total_samples: int = 0) -> bool:
        """Check if loop points are valid"""
        return (self.start_sample >= 0 and 
                self.end_sample > self.start_sample and
                (total_samples == 0 or self.end_sample <= total_samples))


class SCDCodecDetector:
    """
    SCD codec detection based on vgmstream sqex_scd.c source
    
    Detects codec type and determines loop storage method:
    - Codec 0x00/0x01: PCM - header loops (byte offsets)
    - Codec 0x03: PS-ADPCM - header loops 
    - Codec 0x06: OGG Vorbis - OGG comment loops (IGNORE header values!)
    - Codec 0x07: MPEG - header loops (byte offsets)
    - Codec 0x0A/0x15: DSP ADPCM - header loops
    - Codec 0x0B: XMA2 - header loops
    - Codec 0x0C/0x17: MS ADPCM - header loops
    - Codec 0x0E: ATRAC3 - header loops
    - Codec 0x16: ATRAC9 - extradata loops
    """
    
    CODEC_NAMES = {
        0x00: "PCM_BE",
        0x01: "PCM_LE", 
        0x03: "PS_ADPCM",
        0x06: "OGG_VORBIS",
        0x07: "MPEG",
        0x0A: "DSP_ADPCM",
        0x0B: "XMA2",
        0x0C: "MS_ADPCM",
        0x0E: "ATRAC3",
        0x15: "DSP_ADPCM_V2",
        0x16: "ATRAC9",
        0x17: "MS_ADPCM_V2"
    }
    
    def detect_codec_from_scd(self, scd_path: str) -> Dict[str, Any]:
        """
        Parse SCD file to detect codec and metadata locations
        Based on vgmstream sqex_scd.c structure
        """
        try:
            with open(scd_path, 'rb') as f:
                # Check SCD signature
                signature = f.read(8)
                if signature[:4] != b'SEDB' or signature[4:8] != b'SSCF':
                    return {"error": "Not a valid SCD file", "codec_id": -1}
                
                # Check endianness (offset 0x0c)
                f.seek(0x0c)
                big_endian = f.read(1)[0] == 0x01
                read_32 = self._read_32be if big_endian else self._read_32le
                read_16 = self._read_16be if big_endian else self._read_16le
                
                # Get version and tables offset
                f.seek(0x08)
                version = read_32(f.read(4))
                
                f.seek(0x0e)
                tables_offset = read_16(f.read(2))
                
                # Find meta_offset from table3 (headers table)
                f.seek(tables_offset + 0x04)
                headers_entries = read_16(f.read(2))
                
                f.seek(tables_offset + 0x0c)
                headers_offset = read_32(f.read(4))
                
                if headers_entries == 0:
                    return {"error": "No audio streams found", "codec_id": -1}
                
                # Get first stream's meta_offset
                f.seek(headers_offset)
                meta_offset = read_32(f.read(4))
                
                # Read stream header at meta_offset
                f.seek(meta_offset)
                stream_size = read_32(f.read(4))
                channels = read_32(f.read(4))
                sample_rate = read_32(f.read(4))
                codec = read_32(f.read(4))
                loop_start = read_32(f.read(4))  # offset 0x10
                loop_end = read_32(f.read(4))    # offset 0x14
                
                return {
                    "codec_id": codec,
                    "codec_name": self.CODEC_NAMES.get(codec, f"UNKNOWN_0x{codec:02X}"),
                    "big_endian": big_endian,
                    "version": version,
                    "meta_offset": meta_offset,
                    "stream_size": stream_size,
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "header_loop_start": loop_start,
                    "header_loop_end": loop_end,
                    "loop_storage": self._get_loop_storage_method(codec),
                    "supports_header_save": codec != 0x06,  # All except OGG Vorbis
                    "supports_comment_save": codec == 0x06   # Only OGG Vorbis
                }
                
        except Exception as e:
            logging.error(f"Error detecting SCD codec: {e}")
            return {"error": str(e), "codec_id": -1}
    
    def _get_loop_storage_method(self, codec_id: int) -> str:
        """Determine how loop points are stored for this codec"""
        if codec_id == 0x06:  # OGG Vorbis
            return "ogg_comments"
        elif codec_id == 0x16:  # ATRAC9
            return "extradata"
        else:
            return "scd_header"
    
    def _read_32le(self, data: bytes) -> int:
        return struct.unpack('<I', data)[0]
    
    def _read_32be(self, data: bytes) -> int:
        return struct.unpack('>I', data)[0]
    
    def _read_16le(self, data: bytes) -> int:
        return struct.unpack('<H', data)[0]
    
    def _read_16be(self, data: bytes) -> int:
        return struct.unpack('>H', data)[0]


class LoopPointManager:
    """
    Manages loop points for SCD files - Phase 1 Implementation with codec awareness
    
    This implementation:
    - Reads loop points via vgmstream (reliable for all codecs)
    - Detects SCD codec type using vgmstream source analysis
    - Prepares for codec-specific saving in future phases
    """
    
    def __init__(self):
        self.current_loop: Optional[LoopPoint] = None
        self.sample_rate: int = 44100
        self.total_samples: int = 0
        self.current_file_path: Optional[str] = None
        self.codec_detector = SCDCodecDetector()
        self.codec_info: Dict[str, Any] = {}
        
    def set_file_context(self, file_path: str, sample_rate: int, total_samples: int):
        """Set the current file context for loop operations"""
        self.current_file_path = file_path
        self.sample_rate = sample_rate
        self.total_samples = total_samples
        
        # Detect codec info for SCD files
        if file_path.lower().endswith('.scd'):
            self.codec_info = self.codec_detector.detect_codec_from_scd(file_path)
            if "error" not in self.codec_info:
                logging.info(f"Detected SCD codec: {self.codec_info['codec_name']} (0x{self.codec_info['codec_id']:02X})")
                logging.info(f"Loop storage method: {self.codec_info['loop_storage']}")
            else:
                logging.warning(f"Could not detect SCD codec: {self.codec_info['error']}")
        else:
            self.codec_info = {}
        
        logging.info(f"Loop context set: {Path(file_path).name} ({sample_rate}Hz, {total_samples} samples)")
        
    def set_loop_points(self, start_sample: int, end_sample: int) -> bool:
        """Set loop points for UI display and editing"""
        if start_sample < 0 or end_sample <= start_sample or end_sample > self.total_samples:
            logging.warning(f"Invalid loop points: {start_sample} -> {end_sample} (total: {self.total_samples})")
            return False
            
        self.current_loop = LoopPoint(start_sample, end_sample)
        logging.info(f"Loop points set: {self.current_loop}")
        return True
    
    def clear_loop_points(self):
        """Clear current loop points"""
        self.current_loop = None
        logging.info("Loop points cleared")
    
    def get_loop_times(self) -> Tuple[float, float]:
        """Get loop points as time in seconds"""
        if not self.current_loop or self.sample_rate == 0:
            return (0.0, 0.0)
            
        start_time = self.current_loop.start_sample / self.sample_rate
        end_time = self.current_loop.end_sample / self.sample_rate
        return (start_time, end_time)
    
    def get_loop_samples(self) -> Tuple[int, int]:
        """Get loop points as sample positions"""
        if not self.current_loop:
            return (0, 0)
        return (self.current_loop.start_sample, self.current_loop.end_sample)
    
    def has_loop_points(self) -> bool:
        """Check if current file has loop points"""
        return self.current_loop is not None and self.current_loop.is_valid(self.total_samples)
    
    def read_loop_metadata_from_scd(self, scd_filepath: str) -> bool:
        """Read loop metadata from SCD file using vgmstream (works for all codec types)"""
        try:
            # Import here to avoid circular imports
            from ui.metadata_reader import LoopMetadataReader
            
            reader = LoopMetadataReader()
            metadata = reader.read_metadata(scd_filepath)
            
            if metadata.get('has_loop', False):
                start_sample = metadata.get('loop_start', 0)
                end_sample = metadata.get('loop_end', 0)
                
                # Update file context (this will also detect codec)
                self.set_file_context(
                    scd_filepath,
                    metadata.get('sample_rate', 44100),
                    metadata.get('total_samples', 0)
                )
                
                # Set loop points
                self.current_loop = LoopPoint(start_sample, end_sample)
                
                logging.info(f"Read loop metadata from SCD via vgmstream: {self.current_loop}")
                return True
            else:
                logging.info(f"No loop metadata found in SCD file: {scd_filepath}")
                self.clear_loop_points()
                return False
                
        except Exception as e:
            logging.error(f"Error reading loop metadata from SCD: {e}")
            self.clear_loop_points()
            return False
    
    def get_codec_info(self) -> Dict[str, Any]:
        """Get codec information for current file"""
        if not self.current_file_path:
            return {"codec": "unknown", "supports_save": False}
        
        if self.codec_info and "error" not in self.codec_info:
            return {
                "codec_id": self.codec_info.get("codec_id", -1),
                "codec_name": self.codec_info.get("codec_name", "unknown"),
                "loop_storage": self.codec_info.get("loop_storage", "unknown"),
                "supports_header_save": self.codec_info.get("supports_header_save", False),
                "supports_comment_save": self.codec_info.get("supports_comment_save", False),
                "file_path": self.current_file_path,
                "sample_rate": self.sample_rate,
                "total_samples": self.total_samples
            }
        
        return {
            "codec": "unknown",
            "supports_save": False,
            "file_path": self.current_file_path,
            "sample_rate": self.sample_rate,
            "total_samples": self.total_samples
        }
    
    def can_save_loop_points(self) -> bool:
        """Check if we can save loop points for the current file"""
        codec_info = self.get_codec_info()
        return (codec_info.get("supports_header_save", False) or 
                codec_info.get("supports_comment_save", False))
    
    def save_loop_points_to_scd(self, scd_filepath: str) -> bool:
        """
        Save loop points to SCD file - codec-aware implementation
        
        Phase 1: Framework ready, but saving not implemented
        Phase 2: Will add header-based saving for PCM/ADPCM/MPEG/etc
        Phase 3: Will add OGG comment-based saving for Vorbis
        """
        if not self.current_loop:
            logging.error("No loop points to save")
            return False
        
        codec_info = self.get_codec_info()
        if "codec_id" not in codec_info or codec_info["codec_id"] == -1:
            logging.error("Cannot save - unknown codec")
            return False
        
        codec_id = codec_info["codec_id"]
        loop_storage = codec_info.get("loop_storage", "unknown")
        
        logging.info(f"Ready to save loop points for codec 0x{codec_id:02X} ({codec_info.get('codec_name', 'unknown')})")
        logging.info(f"Loop storage method: {loop_storage}")
        logging.info(f"Loop points: {self.current_loop}")
        
        # Phase 1: Just log what we would do
        if loop_storage == "scd_header":
            logging.info("Phase 2+: Would save to SCD header at meta_offset + 0x10/0x14")
            # TODO Phase 2: Implement header-based saving
        elif loop_storage == "ogg_comments":
            logging.info("Phase 3+: Would save to OGG comment tags (LOOPSTART/LOOPEND)")
            # TODO Phase 3: Implement OGG comment saving
        else:
            logging.warning(f"Unsupported loop storage method: {loop_storage}")
            return False
        
        logging.warning("Loop point saving not yet implemented - this is Phase 1 (foundation only)")
        return False


# Phase 2+ classes (placeholders)
class HeaderBasedLoopSaver:
    """Phase 2: Save loop points to SCD header for PCM, ADPCM, MPEG, etc."""
    pass


class OGGCommentLoopSaver:
    """Phase 3: Save loop points to OGG comment tags for Vorbis codec."""
    pass
