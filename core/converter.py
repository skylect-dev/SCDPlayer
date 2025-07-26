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
        """Convert WAV to SCD using KH PC Sound Tools MusicEncoder (renamed SingleEncoder)"""
        try:
            wav_file = Path(wav_path)
            scd_file = Path(scd_path)
            
            if not wav_file.exists():
                logging.error(f"WAV file not found: {wav_path}")
                return False
            
            # Get KH PC Sound Tools paths
            khpc_tools_dir = get_bundled_path('khpc_tools')
            music_encoder_exe = Path(khpc_tools_dir) / 'SingleEncoder' / 'MusicEncoder.exe'
            template_scd = Path(khpc_tools_dir) / 'SingleEncoder' / 'test.scd'
            output_dir = Path(khpc_tools_dir) / 'SingleEncoder' / 'output'
            
            if not music_encoder_exe.exists():
                logging.error(f"MusicEncoder not found at: {music_encoder_exe}")
                return False
                
            if not template_scd.exists():
                logging.error(f"SCD template not found at: {template_scd}")
                return False
            
            # Create unique filenames to avoid conflicts
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            
            # Copy files to MusicEncoder directory (following the batch file pattern)
            encoder_dir = music_encoder_exe.parent
            encoder_template = encoder_dir / f'temp_template_{unique_id}.scd'
            encoder_wav = encoder_dir / f'input_{unique_id}.wav'
            encoder_output_dir = encoder_dir / 'output'
            encoder_output_scd = encoder_output_dir / encoder_template.name
            
            # Ensure output directory exists
            encoder_output_dir.mkdir(exist_ok=True)
            
            import shutil
            shutil.copy2(template_scd, encoder_template)
            shutil.copy2(wav_file, encoder_wav)
            
            try:
                # Run MusicEncoder from its own directory with files in same directory
                # Usage: MusicEncoder.exe <template.scd> <input.wav>
                logging.info(f"Converting WAV to SCD using KH PC Sound Tools: {wav_path} -> {scd_path}")
                result = subprocess.run(
                    [str(music_encoder_exe), str(encoder_template), str(encoder_wav)],
                    cwd=str(encoder_dir),
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minute timeout for conversion
                    startupinfo=self._create_subprocess_startupinfo(),
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode != 0:
                    logging.error(f"MusicEncoder failed with exit code {result.returncode}")
                    logging.error(f"MusicEncoder output: {result.stdout}")
                    logging.error(f"MusicEncoder errors: {result.stderr}")
                    return False
                
                # MusicEncoder puts the result in its own output/<filename>.scd directory
                if encoder_output_scd.exists():
                    shutil.copy2(encoder_output_scd, scd_file)
                    logging.info(f"SCD conversion completed successfully: {scd_path}")
                    return True
                else:
                    logging.error(f"MusicEncoder did not produce expected output file: {encoder_output_scd}")
                    return False
                    
            finally:
                # Clean up temp files from encoder directory
                encoder_template.unlink(missing_ok=True)
                encoder_wav.unlink(missing_ok=True)
                encoder_output_scd.unlink(missing_ok=True)
                
                # Clean up any other temp files in encoder directory
                self._cleanup_encoder_temps(encoder_dir)
            
        except subprocess.TimeoutExpired:
            logging.error("SCD conversion timed out")
            return False
        except Exception as e:
            logging.error(f"Error in WAV to SCD conversion: {e}")
            return False
    
    def _cleanup_encoder_temps(self, encoder_dir):
        """Clean up temporary files from encoder directory"""
        try:
            # Clean up any remaining temp files matching our patterns
            temp_patterns = ['temp_template_*.scd', 'input_*.wav']
            for pattern in temp_patterns:
                for temp_file in encoder_dir.glob(pattern):
                    try:
                        temp_file.unlink(missing_ok=True)
                    except:
                        pass
        except:
            pass
    
    def cleanup_temp_files(self) -> None:
        """Clean up all temporary files"""
        cleanup_temp_files(self.temp_files)
        self.temp_files = []
