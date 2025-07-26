"""Loop metadata reader using vgmstream for SCD files"""
import subprocess
import tempfile
import os
import json
from decimal import Decimal, getcontext
from utils.helpers import get_bundled_path

# Set high precision for metadata calculations
getcontext().prec = 50


class LoopMetadataReader:
    """High-precision loop metadata extraction using vgmstream"""
    
    def __init__(self, loop_manager=None):
        self.vgmstream_path = get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        self.loop_manager = loop_manager
        self.last_error = None
    
    def read_metadata(self, file_path):
        """
        Extract precise loop metadata from SCD file using vgmstream
        Returns dict with sample-accurate loop information
        """
        try:
            # Run vgmstream with metadata flag
            cmd = [
                self.vgmstream_path,
                "-m",  # Metadata mode
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                # Try without -m flag (some versions might not support it)
                cmd = [self.vgmstream_path, file_path]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            
            if result.returncode == 0:
                return self._parse_vgmstream_text_output(result.stdout + result.stderr)
            else:
                self.last_error = f"vgmstream error: {result.stderr}"
                return self._get_fallback_metadata(file_path)
                
        except subprocess.TimeoutExpired:
            self.last_error = "vgmstream timeout"
            return self._get_fallback_metadata(file_path)
        except FileNotFoundError:
            self.last_error = f"vgmstream-cli.exe not found at: {self.vgmstream_path}"
            return self._get_fallback_metadata(file_path)
        except Exception as e:
            self.last_error = f"Metadata extraction error: {e}"
            return self._get_fallback_metadata(file_path)

    def _parse_vgmstream_text_output(self, output):
        """Parse vgmstream text output for loop metadata"""
        metadata = {
            'file_format': 'SCD',
            'channels': 0,
            'sample_rate': 0,
            'total_samples': 0,
            'total_duration': 0.0,
            'has_loop': False,
            'loop_start': 0,
            'loop_end': 0,
            'loop_start_time': 0.0,
            'loop_end_time': 0.0,
            'loop_duration': 0.0,
            'encoding': 'Unknown',
            'bitrate': 0,
            'layout': 'Unknown',
            'precision': 'vgmstream',
            'source': 'vgmstream'
        }
        
        # Parse the output for metadata
        loop_start = None
        loop_end = None
        sample_rate = None
        total_samples = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'loop start:' in line:
                # Format: "loop start: 3042900 samples (1:09.000 seconds)"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'start:' and i + 1 < len(parts):
                        try:
                            loop_start = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
            
            elif 'loop end:' in line:
                # Format: "loop end: 6085800 samples (2:18.000 seconds)"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'end:' and i + 1 < len(parts):
                        try:
                            loop_end = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
            
            elif 'sample rate:' in line:
                # Format: "sample rate: 44100 Hz"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'rate:' and i + 1 < len(parts):
                        try:
                            sample_rate = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
            
            elif 'stream total samples:' in line:
                # Format: "stream total samples: 6085800"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'samples:' and i + 1 < len(parts):
                        try:
                            total_samples = int(parts[i + 1])
                        except ValueError:
                            pass
                        break
        
        # Update metadata with parsed values
        if sample_rate:
            metadata['sample_rate'] = sample_rate
        if total_samples:
            metadata['total_samples'] = total_samples
            if sample_rate:
                metadata['total_duration'] = float(total_samples) / float(sample_rate)
        
        # Check if we have valid loop points
        if loop_start is not None and loop_end is not None and sample_rate:
            metadata['has_loop'] = True
            metadata['loop_start'] = loop_start
            metadata['loop_end'] = loop_end
            metadata['loop_start_time'] = float(loop_start) / float(sample_rate)
            metadata['loop_end_time'] = float(loop_end) / float(sample_rate)
            metadata['loop_duration'] = metadata['loop_end_time'] - metadata['loop_start_time']
        
        return metadata
    
    def _parse_vgmstream_metadata(self, metadata):
        """Parse vgmstream JSON metadata with high precision"""
        try:
            # Extract core information
            sample_rate = Decimal(str(metadata.get('sampleRate', 44100)))
            total_samples = int(metadata.get('totalSamples', 0))
            
            # Extract loop information with precision
            loop_info = metadata.get('loopInfo', {})
            has_loop = loop_info.get('loopFlag', False)
            
            if has_loop:
                loop_start = int(loop_info.get('loopStart', 0))
                loop_end = int(loop_info.get('loopEnd', total_samples))
                
                # Validate loop points
                loop_start = max(0, min(loop_start, total_samples))
                loop_end = max(loop_start + 1, min(loop_end, total_samples))
            else:
                loop_start = 0
                loop_end = total_samples
            
            # Calculate precise durations
            total_duration = Decimal(str(total_samples)) / sample_rate
            loop_start_time = Decimal(str(loop_start)) / sample_rate
            loop_end_time = Decimal(str(loop_end)) / sample_rate
            loop_duration = loop_end_time - loop_start_time
            
            return {
                'file_format': metadata.get('fileFormat', 'Unknown'),
                'channels': int(metadata.get('channels', 2)),
                'sample_rate': int(sample_rate),
                'total_samples': total_samples,
                'total_duration': float(total_duration),
                'has_loop': has_loop,
                'loop_start': loop_start,
                'loop_end': loop_end,
                'loop_start_time': float(loop_start_time),
                'loop_end_time': float(loop_end_time),
                'loop_duration': float(loop_duration),
                'encoding': metadata.get('encoding', 'Unknown'),
                'bitrate': metadata.get('bitrate', 0),
                'layout': metadata.get('layout', 'Unknown'),
                'precision': 'high',  # Indicate high-precision metadata
                'source': 'vgmstream'
            }
            
        except Exception as e:
            self.last_error = f"Parsing error: {str(e)}"
            return self._get_fallback_metadata(None)
    
    def _get_fallback_metadata(self, file_path):
        """Provide fallback metadata when vgmstream fails"""
        return {
            'file_format': 'SCD',
            'channels': 2,
            'sample_rate': 44100,
            'total_samples': 0,
            'total_duration': 0.0,
            'has_loop': False,
            'loop_start': 0,
            'loop_end': 0,
            'loop_start_time': 0.0,
            'loop_end_time': 0.0,
            'loop_duration': 0.0,
            'encoding': 'Unknown',
            'bitrate': 0,
            'layout': 'Unknown',
            'precision': 'fallback',
            'source': 'fallback',
            'error': self.last_error or 'Unknown error'
        }
    
    def extract_loop_points_precise(self, file_path):
        """
        Extract only loop points with maximum precision
        Returns (loop_start_sample, loop_end_sample, sample_rate)
        """
        metadata = self.read_metadata(file_path)
        return (
            metadata['loop_start'],
            metadata['loop_end'],
            metadata['sample_rate']
        )
    
    def calculate_precise_time(self, sample, sample_rate):
        """Calculate precise time from sample position"""
        if sample_rate == 0:
            return 0.0
        
        sample_decimal = Decimal(str(sample))
        rate_decimal = Decimal(str(sample_rate))
        time_decimal = sample_decimal / rate_decimal
        
        return float(time_decimal)
    
    def calculate_precise_sample(self, time_seconds, sample_rate):
        """Calculate precise sample from time position"""
        if sample_rate == 0:
            return 0
        
        time_decimal = Decimal(str(time_seconds))
        rate_decimal = Decimal(str(sample_rate))
        sample_decimal = time_decimal * rate_decimal
        
        return int(sample_decimal)
    
    def validate_loop_points(self, start_sample, end_sample, total_samples):
        """Validate and correct loop points"""
        start_sample = max(0, min(start_sample, total_samples - 1))
        end_sample = max(start_sample + 1, min(end_sample, total_samples))
        
        return start_sample, end_sample
    
    def get_error_message(self):
        """Get last error message"""
        return self.last_error or "No error"
