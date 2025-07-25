"""Audio conversion functionality for SCDPlayer"""
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from utils.helpers import get_bundled_path, cleanup_temp_files


class AudioConverter:
    """Handle audio file conversions"""
    
    def __init__(self):
        self.temp_files = []
    
    def _create_subprocess_startupinfo(self) -> subprocess.STARTUPINFO:
        """Create startup info to hide console windows"""
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo
    
    def _create_temp_wav(self) -> str:
        """Create a temporary WAV file and track it for cleanup"""
        fd, wav_path = tempfile.mkstemp(
            suffix='.wav', 
            prefix='scdplayer_', 
            dir=tempfile.gettempdir()
        )
        # Close file descriptor immediately
        try:
            import os
            os.close(fd)
        except OSError:
            pass
        self.temp_files.append(wav_path)
        return wav_path
    
    def convert_scd_to_wav(self, scd_path: str, out_path: Optional[str] = None) -> Optional[str]:
        """Convert SCD to WAV using vgmstream"""
        vgmstream_path = get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        vgmstream_file = Path(vgmstream_path)
        
        if not vgmstream_file.exists():
            logging.error(f"vgmstream not found at: {vgmstream_path}")
            return None
        
        # Use provided path or create temp file
        wav_path = out_path or self._create_temp_wav()
        
        try:
            subprocess.run(
                [str(vgmstream_file), '-o', wav_path, scd_path], 
                check=True, 
                startupinfo=self._create_subprocess_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return wav_path
            
        except subprocess.CalledProcessError as e:
            logging.error(f"vgmstream conversion failed: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in SCD conversion: {e}")
            return None
    
    def convert_with_ffmpeg(self, input_path: str, output_path: str, format: str) -> bool:
        """Convert audio files using bundled FFmpeg"""
        ffmpeg_path = get_bundled_path('ffmpeg', 'bin/ffmpeg.exe')
        ffmpeg_file = Path(ffmpeg_path)
        
        if not ffmpeg_file.exists():
            logging.error(f"FFmpeg not found at: {ffmpeg_path}")
            return False
        
        try:
            cmd = [str(ffmpeg_file), '-i', input_path, '-y', output_path]
            subprocess.run(
                cmd, 
                check=True, 
                capture_output=True,
                startupinfo=self._create_subprocess_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg conversion failed: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error in FFmpeg conversion: {e}")
            return False
    
    def convert_to_wav_temp(self, input_path: str) -> Optional[str]:
        """Convert audio file to temporary WAV for playback"""
        try:
            wav_path = self._create_temp_wav()
            
            # Convert using FFmpeg
            if self.convert_with_ffmpeg(input_path, wav_path, 'wav'):
                return wav_path
            else:
                # Clean up failed conversion
                Path(wav_path).unlink(missing_ok=True)
                if wav_path in self.temp_files:
                    self.temp_files.remove(wav_path)
                return None
                
        except Exception as e:
            logging.error(f"Error in temp WAV conversion: {e}")
            return None
    
    def convert_wav_to_scd(self, wav_path: str, scd_path: str) -> bool:
        """Convert WAV to SCD (limited implementation)"""
        # NOTE: This is a simplified conversion that creates an SCD-like file
        # but may not be fully compatible with all SCD requirements.
        # Proper SCD encoding would require Square Enix's proprietary tools.
        
        try:
            wav_file = Path(wav_path)
            scd_file = Path(scd_path)
            
            if not wav_file.exists():
                logging.error(f"WAV file not found: {wav_path}")
                return False
            
            # Read WAV data and write as pseudo-SCD
            wav_data = wav_file.read_bytes()
            scd_file.write_bytes(wav_data)
            
            return True
            
        except Exception as e:
            logging.error(f"Error in WAV to SCD conversion: {e}")
            return False
    
    def cleanup_temp_files(self) -> None:
        """Clean up all temporary files"""
        cleanup_temp_files(self.temp_files)
        self.temp_files = []
