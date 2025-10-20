"""
Metadata reader for audio files using vgmstream
Provides loop point detection and audio file information
"""
import logging
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from utils.helpers import get_bundled_path


class LoopMetadataReader:
    """
    Read audio file metadata and loop points using vgmstream
    
    This uses vgmstream-cli.exe to reliably read loop points from all supported
    audio formats, including SCD files with various codecs.
    """
    
    def __init__(self):
        self.vgmstream_path = get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        
    def read_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Read metadata from audio file using vgmstream
        
        Returns dictionary with:
        - has_loop: bool
        - loop_start: int (samples)
        - loop_end: int (samples) 
        - sample_rate: int
        - total_samples: int
        - channels: int
        - format: str
        - duration: float (seconds)
        """
        try:
            if not Path(self.vgmstream_path).exists():
                logging.error(f"vgmstream not found at: {self.vgmstream_path}")
                return self._empty_metadata()
            
            if not Path(file_path).exists():
                logging.error(f"Audio file not found: {file_path}")
                return self._empty_metadata()
            
            # Run vgmstream with metadata output
            result = subprocess.run(
                [self.vgmstream_path, '-m', file_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=self._create_subprocess_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                logging.error(f"vgmstream failed to read {file_path}: {result.stderr}")
                return self._empty_metadata()
            
            # Parse vgmstream output
            return self._parse_vgmstream_output(result.stdout, file_path)
            
        except Exception as e:
            logging.error(f"Error reading metadata from {file_path}: {e}")
            return self._empty_metadata()
    
    def _parse_vgmstream_output(self, output: str, file_path: str) -> Dict[str, Any]:
        """Parse vgmstream -m output to extract metadata"""
        metadata = self._empty_metadata()
        
        try:
            lines = output.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Sample rate
                if 'sample rate:' in line.lower():
                    match = re.search(r'(\d+)\s*Hz', line, re.IGNORECASE)
                    if match:
                        metadata['sample_rate'] = int(match.group(1))
                
                # Channels
                elif 'channels:' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        metadata['channels'] = int(match.group(1))
                
                # Total samples
                elif 'stream total samples:' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        metadata['total_samples'] = int(match.group(1))
                
                # Loop start
                elif 'loop start:' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        metadata['loop_start'] = int(match.group(1))
                        metadata['has_loop'] = True
                
                # Loop end  
                elif 'loop end:' in line.lower():
                    match = re.search(r'(\d+)', line)
                    if match:
                        metadata['loop_end'] = int(match.group(1))
                        metadata['has_loop'] = True
                
                # Format/encoding
                elif 'encoding:' in line.lower():
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        metadata['format'] = parts[1].strip()
            
            # Calculate duration
            if metadata['sample_rate'] > 0 and metadata['total_samples'] > 0:
                metadata['duration'] = metadata['total_samples'] / metadata['sample_rate']
            
            # Validate loop points
            if metadata['has_loop']:
                if (metadata['loop_start'] >= metadata['loop_end'] or 
                    metadata['loop_end'] > metadata['total_samples']):
                    logging.warning(f"Invalid loop points detected: {metadata['loop_start']} -> {metadata['loop_end']}")
                    metadata['has_loop'] = False
                else:
                    logging.info(f"Loop points detected: {metadata['loop_start']} -> {metadata['loop_end']} samples")
            
            # Set file path for reference
            metadata['file_path'] = file_path
            
            return metadata
            
        except Exception as e:
            logging.error(f"Error parsing vgmstream output: {e}")
            return self._empty_metadata()
    
    def _empty_metadata(self) -> Dict[str, Any]:
        """Return empty metadata structure"""
        return {
            'has_loop': False,
            'loop_start': 0,
            'loop_end': 0,
            'sample_rate': 44100,
            'total_samples': 0,
            'channels': 2,
            'format': 'unknown',
            'duration': 0.0,
            'file_path': ''
        }
    
    def _create_subprocess_startupinfo(self):
        """Create subprocess startup info for Windows"""
        import platform
        if platform.system() == 'Windows':
            import subprocess
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None
    
    def check_loop_support(self, file_path: str) -> bool:
        """Check if file format supports loop points"""
        file_ext = Path(file_path).suffix.lower()
        
        # Known formats that support loop points
        loop_supported_formats = {'.scd', '.ogg', '.wav'}  # WAV with smpl chunk
        
        return file_ext in loop_supported_formats
    
    def get_quick_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic file info without full metadata parsing (faster)"""
        try:
            result = subprocess.run(
                [self.vgmstream_path, '-i', file_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5,  # Quick timeout
                startupinfo=self._create_subprocess_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                # Basic parsing for quick info
                output = result.stdout
                info = {'supported': True, 'format': 'unknown'}
                
                if 'sample rate:' in output.lower():
                    match = re.search(r'(\d+)\s*Hz', output, re.IGNORECASE)
                    if match:
                        info['sample_rate'] = int(match.group(1))
                
                if 'channels:' in output.lower():
                    match = re.search(r'channels:\s*(\d+)', output, re.IGNORECASE)
                    if match:
                        info['channels'] = int(match.group(1))
                
                return info
            else:
                return {'supported': False, 'error': result.stderr}
                
        except Exception as e:
            return {'supported': False, 'error': str(e)}
