import struct
import logging
import os
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

class LoopPoint:
    """Represents a loop point with start and end samples"""
    def __init__(self, start_sample: int, end_sample: int):
        self.start_sample = start_sample
        self.end_sample = end_sample
    
    def __str__(self) -> str:
        return f"Loop({self.start_sample} -> {self.end_sample})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def duration_samples(self) -> int:
        """Get loop duration in samples"""
        return self.end_sample - self.start_sample
    
    def to_seconds(self, sample_rate: int) -> Tuple[float, float]:
        """Convert to seconds at given sample rate"""
        return (self.start_sample / sample_rate, self.end_sample / sample_rate)

class HybridLoopManager:
    """
    Hybrid loop point manager using WAV metadata for editing
    
    This approach avoids the complexities of direct SCD binary editing
    by using WAV files as the editing medium, then converting back to SCD.
    """
    
    def __init__(self):
        self.current_loop: Optional[LoopPoint] = None
        self.sample_rate: int = 44100
        self.total_samples: int = 0
        self.current_file_path: Optional[str] = None
        self.temp_wav_path: Optional[str] = None
        self.original_scd_path: Optional[str] = None
        
    def _create_subprocess_startupinfo(self):
        """Create startup info to hide console windows in built exe"""
        try:
            import subprocess
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        except:
            return None
        
    def load_file_for_editing(self, file_path: str) -> bool:
        """
        Load a file for loop editing
        
        For SCD files: Creates temp WAV with preserved loop metadata
        For WAV files: Uses directly
        For other formats: Converts to WAV first
        """
        try:
            file_path = Path(file_path).resolve()
            self.current_file_path = str(file_path)
            
            if file_path.suffix.lower() == '.scd':
                return self._load_scd_for_editing(str(file_path))
            elif file_path.suffix.lower() == '.wav':
                return self._load_wav_for_editing(str(file_path))
            else:
                return self._load_other_format_for_editing(str(file_path))
                
        except Exception as e:
            logging.error(f"Failed to load file for editing: {e}")
            return False
    
    def load_wav_file(self, wav_path: str) -> bool:
        """
        Load a WAV file directly for loop editing
        
        Args:
            wav_path: Path to the WAV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self._load_wav_for_editing(wav_path)
    
    def _load_scd_for_editing(self, scd_path: str) -> bool:
        """Load SCD file by creating temp WAV with preserved loop metadata"""
        try:
            self.original_scd_path = scd_path
            
            # Create temp WAV from SCD
            self.temp_wav_path = self._create_temp_wav_from_scd(scd_path)
            if not self.temp_wav_path:
                return False
            
            # Read WAV properties and loop metadata
            return self._analyze_wav_file(self.temp_wav_path)
            
        except Exception as e:
            logging.error(f"Failed to load SCD for editing: {e}")
            return False
    
    def _load_wav_for_editing(self, wav_path: str) -> bool:
        """Load WAV file directly for editing"""
        try:
            self.temp_wav_path = wav_path
            self.original_scd_path = None
            
            return self._analyze_wav_file(wav_path)
            
        except Exception as e:
            logging.error(f"Failed to load WAV for editing: {e}")
            return False
    
    def _load_other_format_for_editing(self, file_path: str) -> bool:
        """Convert other audio formats to WAV for editing"""
        try:
            # Create temp WAV file
            temp_fd, temp_wav_path = tempfile.mkstemp(suffix='.wav', prefix='audio_edit_')
            os.close(temp_fd)
            
            # Convert using ffmpeg
            ffmpeg_path = Path(__file__).parent.parent / "ffmpeg" / "bin" / "ffmpeg.exe"
            
            result = subprocess.run([
                str(ffmpeg_path),
                '-i', file_path,
                '-acodec', 'pcm_s16le',
                '-ar', '48000',  # Standard sample rate for game audio
                '-y',  # Overwrite output
                temp_wav_path
            ], capture_output=True, text=True, encoding='utf-8', errors='replace',
               startupinfo=self._create_subprocess_startupinfo(),
               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            if result.returncode != 0 or not Path(temp_wav_path).exists():
                logging.error(f"Failed to convert audio file: {result.stderr}")
                return False
            
            self.temp_wav_path = temp_wav_path
            self.original_scd_path = None
            
            return self._analyze_wav_file(temp_wav_path)
            
        except Exception as e:
            logging.error(f"Failed to convert audio file: {e}")
            return False
    
    def _create_temp_wav_from_scd(self, scd_path: str) -> Optional[str]:
        """Create temporary WAV file from SCD with preserved loop metadata"""
        try:
            # Create temp file
            temp_fd, temp_wav_path = tempfile.mkstemp(suffix='.wav', prefix='scd_edit_')
            os.close(temp_fd)
            
            # Extract audio using vgmstream
            vgmstream_path = Path(__file__).parent.parent / "vgmstream" / "vgmstream-cli.exe"
            
            result = subprocess.run([
                str(vgmstream_path),
                '-i',  # Ignore loop, play once
                '-o', temp_wav_path,
                scd_path
            ], capture_output=True, text=True, encoding='utf-8', errors='replace',
               startupinfo=self._create_subprocess_startupinfo(),
               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            if result.returncode != 0 or not Path(temp_wav_path).exists():
                logging.error(f"Failed to extract WAV from SCD: {result.stderr}")
                return None
            
            # Read original loop points from SCD using vgmstream metadata
            loop_start, loop_end = self._read_scd_loop_points(scd_path)
            
            # Write loop metadata to the temp WAV
            if loop_start != 0 or loop_end != 0:
                self._write_wav_loop_metadata(temp_wav_path, loop_start, loop_end)
                logging.info(f"Preserved loop points {loop_start}->{loop_end} in temp WAV")
            
            return temp_wav_path
            
        except Exception as e:
            logging.error(f"Error creating temp WAV from SCD: {e}")
            return None
    
    def _read_scd_loop_points(self, scd_path: str) -> Tuple[int, int]:
        """Read loop points from SCD using vgmstream"""
        try:
            from ui.metadata_reader import LoopMetadataReader
            
            reader = LoopMetadataReader()
            metadata = reader.read_metadata(scd_path)
            
            if metadata.get('has_loop', False):
                return (metadata.get('loop_start', 0), metadata.get('loop_end', 0))
            else:
                return (0, 0)
                
        except Exception as e:
            logging.error(f"Error reading SCD loop points: {e}")
            return (0, 0)
    
    def _analyze_wav_file(self, wav_path: str) -> bool:
        """Analyze WAV file properties and read loop metadata"""
        try:
            # Read WAV properties using ffprobe
            ffprobe_path = Path(__file__).parent.parent / "ffmpeg" / "bin" / "ffprobe.exe"
            
            result = subprocess.run([
                str(ffprobe_path),
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                wav_path
            ], capture_output=True, text=True, encoding='utf-8', errors='replace',
               startupinfo=self._create_subprocess_startupinfo(),
               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            if result.returncode != 0:
                logging.error(f"Failed to analyze WAV file: {result.stderr}")
                return False
            
            import json
            info = json.loads(result.stdout)
            
            # Extract audio properties
            stream = info['streams'][0]
            self.sample_rate = int(stream['sample_rate'])
            duration = float(stream['duration'])
            self.total_samples = int(duration * self.sample_rate)
            
            # Read loop metadata from WAV
            loop_start, loop_end = self._read_wav_loop_metadata(wav_path)
            
            if loop_start != 0 or loop_end != 0:
                self.current_loop = LoopPoint(loop_start, loop_end)
                logging.info(f"Loaded with loop points: {self.current_loop}")
            else:
                self.current_loop = None
                logging.info("No loop points found")
            
            logging.info(f"Loaded: {Path(wav_path).name} ({self.sample_rate}Hz, {self.total_samples} samples)")
            return True
            
        except Exception as e:
            logging.error(f"Error analyzing WAV file: {e}")
            return False

    def trim_audio(self, trim_start_samples: int, trim_end_samples: int) -> bool:
        """Trim the working WAV to the given sample range"""
        try:
            if not self.temp_wav_path or not Path(self.temp_wav_path).exists():
                logging.error("No working WAV to trim")
                return False

            if trim_end_samples <= trim_start_samples:
                logging.error("Invalid trim range")
                return False

            # Clamp to available samples
            trim_start_samples = max(0, trim_start_samples)
            trim_end_samples = min(self.total_samples, trim_end_samples)
            if trim_end_samples <= trim_start_samples:
                logging.error("Trim range collapsed after clamping")
                return False

            # Calculate seconds
            start_sec = trim_start_samples / self.sample_rate if self.sample_rate else 0
            end_sec = trim_end_samples / self.sample_rate if self.sample_rate else 0

            # Create temp output
            temp_fd, temp_out_path = tempfile.mkstemp(suffix='.wav', prefix='trim_')
            os.close(temp_fd)
            temp_out = Path(temp_out_path)

            ffmpeg_path = Path(__file__).parent.parent / "ffmpeg" / "bin" / "ffmpeg.exe"

            result = subprocess.run([
                str(ffmpeg_path),
                '-i', self.temp_wav_path,
                '-af', f'atrim=start={start_sec}:end={end_sec}',
                '-ar', str(self.sample_rate),
                '-ac', '2',
                '-sample_fmt', 's16',
                '-y',
                str(temp_out)
            ], capture_output=True, text=True, encoding='utf-8', errors='replace',
               startupinfo=self._create_subprocess_startupinfo(),
               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            if result.returncode != 0 or not temp_out.exists():
                logging.error(f"ffmpeg trim failed: {result.stderr}")
                return False

            # Swap in trimmed WAV (overwrite original temp wav)
            shutil.move(str(temp_out), self.temp_wav_path)

            # Re-read audio info
            if not self._analyze_wav_file(self.temp_wav_path):
                logging.error("Failed to analyze trimmed WAV")
                return False

            # Adjust loop points relative to trim start
            if self.current_loop:
                new_start = max(0, self.current_loop.start_sample - trim_start_samples)
                new_end = max(new_start + 1, min(self.current_loop.end_sample - trim_start_samples, self.total_samples))
                self.current_loop = LoopPoint(new_start, new_end)

            return True

        except Exception as e:
            logging.error(f"Error trimming audio: {e}")
            return False
    
    def _write_wav_loop_metadata(self, wav_filepath: str, loop_start: int, loop_end: int) -> bool:
        """Write loop metadata to WAV file in Audacity-compatible format"""
        try:
            # Read the existing WAV file
            with open(wav_filepath, 'rb') as f:
                wav_data = f.read()
            
            # Check if it's a valid WAV file
            if not wav_data.startswith(b'RIFF') or wav_data[8:12] != b'WAVE':
                logging.error(f"Not a valid WAV file: {wav_filepath}")
                return False
            
            # Remove existing ID3 chunk if present
            id3_pos = wav_data.find(b'id3 ')
            if id3_pos != -1:
                chunk_size = struct.unpack('<I', wav_data[id3_pos+4:id3_pos+8])[0]
                wav_data = wav_data[:id3_pos] + wav_data[id3_pos+8+chunk_size:]
                logging.debug("Removed existing ID3 metadata from WAV")
            
            # Create ID3v2.3 metadata with TXXX frames
            def create_txxx_frame(key: str, value: str) -> bytes:
                text_data = b'\x00' + key.encode('utf-8') + b'\x00' + value.encode('utf-8')
                frame_size = len(text_data)
                frame_header = b'TXXX' + struct.pack('>I', frame_size) + b'\x00\x00'
                return frame_header + text_data
            
            # Create TXXX frames for loop points
            loop_start_frame = create_txxx_frame('LoopStart', str(loop_start))
            loop_end_frame = create_txxx_frame('LoopEnd', str(loop_end))
            
            # Create ID3v2.3 header
            id3_content = loop_start_frame + loop_end_frame
            id3_size = len(id3_content)
            id3_header = b'ID3\x03\x00\x00' + struct.pack('>I', id3_size)
            
            # Create id3 chunk for WAV file
            id3_chunk_data = id3_header + id3_content
            id3_chunk_size = len(id3_chunk_data)
            
            # Add padding if odd size (WAV chunks must be word-aligned)
            if id3_chunk_size % 2:
                id3_chunk_data += b'\x00'
                id3_chunk_size += 1
            
            # Create the id3 chunk header
            id3_chunk = b'id3 ' + struct.pack('<I', id3_chunk_size) + id3_chunk_data
            
            # Append the id3 chunk to the end of the WAV file
            new_wav_data = wav_data + id3_chunk
            
            # Update the RIFF chunk size in the header
            new_file_size = len(new_wav_data) - 8
            new_wav_data = new_wav_data[:4] + struct.pack('<I', new_file_size) + new_wav_data[8:]
            
            # Create backup and write new file
            backup_path = wav_filepath + '.backup'
            if Path(backup_path).exists():
                Path(backup_path).unlink()
            
            shutil.move(wav_filepath, backup_path)
            
            with open(wav_filepath, 'wb') as f:
                f.write(new_wav_data)
            
            logging.debug(f"Wrote loop metadata to WAV: {loop_start} -> {loop_end}")
            
            # Remove backup on success
            try:
                Path(backup_path).unlink()
            except:
                pass
            
            return True
            
        except Exception as e:
            logging.error(f"Error writing WAV loop metadata: {e}")
            return False
    
    def _read_wav_loop_metadata(self, wav_filepath: str) -> Tuple[int, int]:
        """Read loop metadata from WAV file"""
        try:
            with open(wav_filepath, 'rb') as f:
                data = f.read()
            
            logging.debug(f"Reading loop metadata from: {wav_filepath}")
            
            # Find ID3 chunk
            id3_pos = data.find(b'id3 ')
            if id3_pos == -1:
                logging.debug("No id3 chunk found in WAV file")
                return (0, 0)
            
            chunk_size = struct.unpack('<I', data[id3_pos+4:id3_pos+8])[0]
            id3_data = data[id3_pos+8:id3_pos+8+chunk_size]
            
            logging.debug(f"Found id3 chunk at position {id3_pos}, size {chunk_size}")
            
            if not id3_data.startswith(b'ID3'):
                logging.debug("ID3 chunk doesn't start with ID3 header")
                return (0, 0)
            
            loop_start = 0
            loop_end = 0
            
            # Parse TXXX frames
            pos = 10  # Skip ID3 header
            while pos < len(id3_data) - 10:
                frame_id = id3_data[pos:pos+4]
                if frame_id == b'TXXX':
                    frame_size = struct.unpack('>I', id3_data[pos+4:pos+8])[0]
                    frame_data = id3_data[pos+10:pos+10+frame_size]
                    
                    if b'LoopStart' in frame_data:
                        parts = frame_data.split(b'\x00')
                        if len(parts) >= 3:
                            loop_start = int(parts[2].decode('utf-8'))
                    elif b'LoopEnd' in frame_data:
                        parts = frame_data.split(b'\x00')
                        if len(parts) >= 3:
                            loop_end = int(parts[2].decode('utf-8'))
                    
                    pos += 10 + frame_size
                else:
                    break
            
            logging.info(f"Read loop metadata: {loop_start} -> {loop_end}")
            return (loop_start, loop_end)
            
        except Exception as e:
            logging.debug(f"Error reading WAV loop metadata: {e}")
            return (0, 0)
    
    def set_loop_points(self, start_sample: int, end_sample: int) -> bool:
        """Set loop points in the current file"""
        try:
            if not self.temp_wav_path:
                logging.error("No file loaded for editing")
                return False
            
            if start_sample < 0 or end_sample <= start_sample:
                logging.error("Invalid loop points")
                return False
            
            if end_sample > self.total_samples:
                logging.warning(f"End sample {end_sample} exceeds total samples {self.total_samples}")
                end_sample = self.total_samples
            
            # Update internal state
            self.current_loop = LoopPoint(start_sample, end_sample)
            
            # Write to WAV metadata
            success = self._write_wav_loop_metadata(self.temp_wav_path, start_sample, end_sample)
            
            if success:
                logging.info(f"Loop points set: {self.current_loop}")
            else:
                logging.error("Failed to write loop points to WAV")
            
            return success
            
        except Exception as e:
            logging.error(f"Error setting loop points: {e}")
            return False
    
    def get_loop_points(self) -> Tuple[int, int]:
        """Get current loop points as (start, end) sample numbers"""
        if self.current_loop:
            return (self.current_loop.start_sample, self.current_loop.end_sample)
        return (0, 0)
    
    def has_loop_points(self) -> bool:
        """Check if loop points are currently set"""
        return self.current_loop is not None
    
    def clear_loop_points(self) -> bool:
        """Clear current loop points"""
        try:
            if not self.temp_wav_path:
                return False
            
            self.current_loop = None
            
            # Remove loop metadata from WAV
            success = self._write_wav_loop_metadata(self.temp_wav_path, 0, 0)
            
            if success:
                logging.info("Loop points cleared")
            
            return success
            
        except Exception as e:
            logging.error(f"Error clearing loop points: {e}")
            return False
    
    def save_changes(self, output_path: Optional[str] = None) -> bool:
        """
        Save changes back to original format
        
        For SCD files: Converts WAV back to SCD
        For WAV files: Saves directly (if output_path specified)
        """
        try:
            if not self.temp_wav_path:
                logging.error("No file loaded for saving")
                return False
            
            if self.original_scd_path:
                # Save as SCD
                scd_output = output_path or self.original_scd_path
                return self._convert_wav_to_scd(self.temp_wav_path, scd_output)
            else:
                # Save as WAV
                if output_path:
                    shutil.copy2(self.temp_wav_path, output_path)
                    logging.info(f"Saved WAV to: {output_path}")
                    return True
                else:
                    logging.info("WAV changes saved in place")
                    return True
            
        except Exception as e:
            logging.error(f"Error saving changes: {e}")
            return False
    
    def _convert_wav_to_scd(self, wav_path: str, scd_output_path: str) -> bool:
        """Convert WAV file to SCD using MusicEncoder"""
        try:
            # Paths
            encoder_dir = Path(__file__).parent.parent / "khpc_tools" / "SingleEncoder"
            encoder_exe = encoder_dir / "MusicEncoder.exe"
            template_scd = encoder_dir / "test.scd"
            
            if not encoder_exe.exists() or not template_scd.exists():
                logging.error("MusicEncoder or template SCD not found")
                return False
            
            # Copy WAV to encoder directory
            wav_name = f"temp_convert_{os.getpid()}.wav"
            scd_name = f"temp_convert_{os.getpid()}.scd"
            temp_wav_path = encoder_dir / wav_name
            temp_scd_path = encoder_dir / scd_name
            
            # Copy files
            shutil.copy2(wav_path, temp_wav_path)
            shutil.copy2(template_scd, temp_scd_path)
            
            # Run MusicEncoder
            result = subprocess.run([
                str(encoder_exe),
                scd_name,
                wav_name
            ], cwd=encoder_dir, capture_output=True, text=True, encoding='utf-8', errors='replace',
               startupinfo=self._create_subprocess_startupinfo(),
               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            # Move result from output directory
            output_path = encoder_dir / "output" / scd_name
            if output_path.exists():
                shutil.move(str(output_path), scd_output_path)
                logging.info(f"Successfully converted WAV to SCD: {scd_output_path}")
                success = True
            else:
                logging.error("MusicEncoder did not produce output file")
                success = False
            
            # Cleanup temp files
            try:
                temp_wav_path.unlink(missing_ok=True)
                temp_scd_path.unlink(missing_ok=True)
            except:
                pass
            
            return success
            
        except Exception as e:
            logging.error(f"Error converting WAV to SCD: {e}")
            return False
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded file"""
        return {
            "original_path": self.current_file_path,
            "temp_wav_path": self.temp_wav_path,
            "is_scd_editing": self.original_scd_path is not None,
            "sample_rate": self.sample_rate,
            "total_samples": self.total_samples,
            "duration_seconds": self.total_samples / self.sample_rate if self.sample_rate > 0 else 0,
            "has_loop": self.has_loop_points(),
            "loop_info": {
                "start_sample": self.current_loop.start_sample if self.current_loop else 0,
                "end_sample": self.current_loop.end_sample if self.current_loop else 0,
                "start_seconds": self.current_loop.start_sample / self.sample_rate if self.current_loop and self.sample_rate > 0 else 0,
                "end_seconds": self.current_loop.end_sample / self.sample_rate if self.current_loop and self.sample_rate > 0 else 0,
                "duration_samples": self.current_loop.duration_samples() if self.current_loop else 0,
                "duration_seconds": self.current_loop.duration_samples() / self.sample_rate if self.current_loop and self.sample_rate > 0 else 0
            }
        }
    
    def get_wav_path(self) -> Optional[str]:
        """Get the path to the WAV file being edited"""
        return self.temp_wav_path
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            if self.temp_wav_path and self.original_scd_path:  # Only delete temp files we created
                temp_path = Path(self.temp_wav_path)
                if temp_path.exists() and temp_path.name.startswith(('scd_edit_', 'audio_edit_')):
                    temp_path.unlink()
                    logging.debug(f"Cleaned up temp file: {self.temp_wav_path}")
        except Exception as e:
            logging.debug(f"Error during cleanup: {e}")
        
        # Reset state
        self.current_loop = None
        self.current_file_path = None
        self.temp_wav_path = None
        self.original_scd_path = None
    
    def save_loop_points(self) -> bool:
        """
        Save current loop points to the original file
        
        Workflow:
        - For SCD: WAV (with ID3 tags) → SCD via MusicEncoder
        - For WAV: Update ID3 tags in place
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.current_loop:
                logging.info("No loop points to save")
                return True
            
            # First, inject ID3 tags into the temp WAV
            success = self._write_wav_loop_metadata(
                self.temp_wav_path, 
                self.current_loop.start_sample, 
                self.current_loop.end_sample
            )
            
            if not success:
                logging.error("Failed to write loop metadata to WAV")
                return False
            
            logging.info(f"Saved loop metadata: {self.current_loop.start_sample} -> {self.current_loop.end_sample}")
            
            # If original was SCD, convert back to SCD
            if self.original_scd_path:
                logging.info(f"Converting back to SCD: {self.original_scd_path}")
                return self._convert_wav_to_scd(self.temp_wav_path, self.original_scd_path)
            else:
                # If original was WAV, we're done (metadata already written)
                logging.info("Loop metadata saved to WAV file")
                return True
                
        except Exception as e:
            logging.error(f"Error saving loop points: {e}")
            return False
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.cleanup()
