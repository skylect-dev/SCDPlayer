"""Audio conversion functionality for SCDPlayer"""
import os
import subprocess
import shutil
import tempfile
from typing import Optional
from utils.helpers import get_bundled_path


class AudioConverter:
    """Handle audio file conversions"""
    
    def __init__(self):
        self.temp_files = []
    
    def convert_scd_to_wav(self, scd_path: str, out_path: Optional[str] = None) -> Optional[str]:
        """Convert SCD to WAV using vgmstream"""
        if out_path is None:
            # Use a temp file for playback
            fd, wav_path = tempfile.mkstemp(suffix='.wav', prefix='scdplayer_', dir=tempfile.gettempdir())
            os.close(fd)
        else:
            wav_path = out_path
        
        vgmstream_path = get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        if not os.path.exists(vgmstream_path):
            return None
        
        try:
            # Hide console window by setting creation flags
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            subprocess.run([vgmstream_path, '-o', wav_path, scd_path], 
                         check=True, 
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Track temp wavs for cleanup
            if out_path is None:
                self.temp_files.append(wav_path)
            return wav_path
        except Exception:
            return None
    
    def convert_with_ffmpeg(self, input_path: str, output_path: str, format: str) -> bool:
        """Convert audio files using bundled FFmpeg"""
        ffmpeg_path = get_bundled_path('ffmpeg', 'bin/ffmpeg.exe')
        if not os.path.exists(ffmpeg_path):
            return False
        
        try:
            # Hide console window by setting creation flags
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            cmd = [ffmpeg_path, '-i', input_path, '-y', output_path]
            subprocess.run(cmd, 
                         check=True, 
                         capture_output=True,
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception:
            return False
    
    def convert_to_wav_temp(self, input_path: str) -> Optional[str]:
        """Convert audio file to temporary WAV for playback"""
        try:
            # Create temp WAV file
            fd, wav_path = tempfile.mkstemp(suffix='.wav', prefix='scdplayer_', dir=tempfile.gettempdir())
            os.close(fd)
            
            # Convert using FFmpeg
            success = self.convert_with_ffmpeg(input_path, wav_path, 'wav')
            
            if success:
                # Track temp files for cleanup
                self.temp_files.append(wav_path)
                return wav_path
            else:
                # Clean up failed conversion
                try:
                    os.remove(wav_path)
                except:
                    pass
                return None
                
        except Exception:
            return None
    
    def convert_wav_to_scd(self, wav_path: str, scd_path: str) -> bool:
        """Convert WAV to SCD (placeholder implementation)"""
        # This is a placeholder - actual SCD encoding would require specialized tools
        # For now, we'll just copy the WAV file with SCD extension as a demonstration
        try:
            shutil.copy2(wav_path, scd_path)
            return True
        except Exception:
            return False
    
    def cleanup_temp_files(self) -> None:
        """Clean up all temporary files"""
        for temp_file in self.temp_files:
            try:
                os.remove(temp_file)
            except Exception:
                pass
        self.temp_files = []
