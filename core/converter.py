"""Audio conversion functionality for SCDToolkit"""
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from utils.helpers import get_bundled_path, cleanup_temp_files
from core.audio_analysis import AudioAnalyzer


class AudioConverter:
    """Handle audio file conversions"""
    
    def __init__(self):
        self.temp_files = []
        self._dotnet_checked = False
        self._dotnet_available = False
        self._sanitized_cache = {}  # path -> {'mtime': float, 'size': int, 'ok': bool}
        self._cache_path = Path(tempfile.gettempdir()) / "scdtoolkit_scd_cache.json"
        self._load_sanitize_cache()

    def _load_sanitize_cache(self):
        try:
            if self._cache_path.exists():
                import json
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._sanitized_cache = data
        except Exception:
            self._sanitized_cache = {}

    def _save_sanitize_cache(self):
        try:
            import json
            self._cache_path.write_text(json.dumps(self._sanitized_cache), encoding="utf-8")
        except Exception:
            pass

    def _cache_sanitized(self, scd_file: Path):
        """Record a sanitized SCD (gain + loudness applied) by path/mtime/size."""
        try:
            stat = scd_file.stat()
            key = str(scd_file.resolve())
            self._sanitized_cache[key] = {"mtime": stat.st_mtime, "size": stat.st_size, "ok": True}
            self._save_sanitize_cache()
        except Exception:
            pass

    def is_sanitized(self, scd_path: str) -> bool:
        """Return True if the cached metadata matches the on-disk SCD."""
        try:
            scd_file = Path(scd_path)
            stat = scd_file.stat()
            key = str(scd_file.resolve())
            entry = self._sanitized_cache.get(key)
            return bool(entry and entry.get("ok") and entry.get("mtime") == stat.st_mtime and entry.get("size") == stat.st_size)
        except Exception:
            return False

    def mark_sanitized(self, scd_path: str):
        """Public helper to record sanitized state after external operations."""
        try:
            self._cache_sanitized(Path(scd_path))
        except Exception:
            pass

    def clear_sanitize_cache(self) -> bool:
        """Clear sanitize cache from memory and disk."""
        try:
            self._sanitized_cache.clear()
            if self._cache_path.exists():
                self._cache_path.unlink(missing_ok=True)
            return True
        except Exception:
            return False
    
    def check_dotnet_available(self) -> bool:
        """
        Check if .NET 5.0+ runtime is available (cached result)
        
        Returns:
            True if .NET 5.0+ is available
        """
        if not self._dotnet_checked:
            from utils.dotnet_installer import DotNetRuntimeChecker
            self._dotnet_available, version = DotNetRuntimeChecker.check_dotnet_installed()
            self._dotnet_checked = True
            if self._dotnet_available:
                logging.info(f".NET runtime available: {version}")
            else:
                logging.info(".NET 5.0+ runtime not found")
        
        return self._dotnet_available
    
    def invalidate_dotnet_cache(self):
        """Force re-check of .NET availability (call after installation)"""
        self._dotnet_checked = False
        self._dotnet_available = False
    
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
            prefix='scdtoolkit_', 
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
    
    def convert_scd_to_wav(self, scd_path: str, out_path: Optional[str] = None, preserve_loop_points: bool = True) -> Optional[str]:
        """Convert SCD to WAV using vgmstream and preserve loop points"""
        vgmstream_path = get_bundled_path('vgmstream', 'vgmstream-cli.exe')
        vgmstream_file = Path(vgmstream_path)
        
        if not vgmstream_file.exists():
            logging.error(f"vgmstream not found at: {vgmstream_path}")
            return None
        
        # Use provided path or create temp file
        wav_path = out_path or self._create_temp_wav()
        
        try:
            subprocess.run(
                [str(vgmstream_file), '-i', '-o', wav_path, scd_path], 
                check=True, 
                startupinfo=self._create_subprocess_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Auto-apply loop points if requested
            if preserve_loop_points and Path(wav_path).exists():
                try:
                    from ui.metadata_reader import LoopMetadataReader
                    from core.loop_manager import HybridLoopManager
                    
                    # Read loop points from original SCD
                    reader = LoopMetadataReader()
                    metadata = reader.read_metadata(scd_path)
                    
                    if metadata.get('loop_start', 0) > 0 or metadata.get('loop_end', 0) > 0:
                        # Apply loop points to WAV
                        loop_manager = HybridLoopManager()
                        if loop_manager._write_wav_loop_metadata(wav_path, metadata['loop_start'], metadata['loop_end']):
                            logging.info(f"Applied loop points to WAV: {metadata['loop_start']} -> {metadata['loop_end']}")
                        else:
                            logging.debug("Could not write loop metadata to WAV")
                    else:
                        logging.debug("No loop points found in SCD")
                        
                except Exception as e:
                    logging.debug(f"Could not preserve loop points: {e}")
            
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

    def normalize_wav_loudness(self, wav_path: str, target_i: float = -12.0, target_tp: float = -1.0) -> bool:
        """Normalize WAV loudness in-place using true loudnorm targets.

        Returns True on success; logs and returns False on failure (non-fatal).
        """
        try:
            analyzer = AudioAnalyzer()
            result = analyzer.normalize_file_loudness(wav_path, target_i=target_i, target_tp=target_tp)
            if result:
                logging.info(f"Normalized WAV to {target_i} LUFS / {target_tp} dBTP: {wav_path}")
                return True
            logging.warning("Loudness normalization failed; proceeding without change")
            return False
        except Exception as e:
            logging.warning(f"Error during loudness normalization: {e}")
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
    
    def convert_wav_to_scd(self, wav_path: str, scd_path: str, original_scd_path: str = None, quality: int = 10) -> bool:
        """
        Convert WAV to SCD using KH PC Sound Tools MusicEncoder
        
        Args:
            wav_path: Path to input WAV file
            scd_path: Path to output SCD file
            original_scd_path: Optional path to original SCD to use as template (preserves codec/settings)
            quality: Quality level 0-10 (default 10 = highest quality, 0 = lowest quality)
        
        Note: MusicEncoder requires all files to be in the same directory as the executable
        """
        # Validate quality parameter
        quality = max(0, min(10, int(quality)))  # Clamp to 0-10 range
        try:
            wav_file = Path(wav_path)
            scd_file = Path(scd_path)
            
            if not wav_file.exists():
                logging.error(f"WAV file not found: {wav_path}")
                return False
            
            # Get KH PC Sound Tools paths
            khpc_tools_dir = get_bundled_path('khpc_tools')
            music_encoder_exe = Path(khpc_tools_dir) / 'SingleEncoder' / 'MusicEncoder.exe'
            encoder_dir = music_encoder_exe.parent
            output_dir = encoder_dir / 'output'
            
            if not music_encoder_exe.exists():
                logging.error(f"MusicEncoder not found at: {music_encoder_exe}")
                return False
            
            # Determine template SCD to use
            if original_scd_path and Path(original_scd_path).exists():
                # Use original SCD as template to preserve codec and compression settings
                template_scd = Path(original_scd_path)
                logging.info(f"Using original SCD as template: {template_scd.name}")
                
                # Analyze original for comparison
                try:
                    # Import check - SCDCodecDetector may not be available
                    from core.loop_manager import SCDCodecDetector
                    detector = SCDCodecDetector()
                    original_info = detector.detect_codec_from_scd(str(template_scd))
                    if "error" not in original_info:
                        logging.info(f"Template codec: {original_info['codec_name']} (0x{original_info['codec_id']:02X})")
                        logging.info(f"Template sample rate: {original_info['sample_rate']:,} Hz")
                        logging.info(f"Template channels: {original_info['channels']}")
                except ImportError:
                    # SCDCodecDetector not available - skip analysis
                    pass
                except Exception as e:
                    logging.debug(f"Could not analyze template SCD: {e}")
                    
            else:
                # Fallback to default template
                template_scd = encoder_dir / 'test.scd'
                if not template_scd.exists():
                    logging.error(f"SCD template not found at: {template_scd}")
                    return False
                logging.info("Using default SCD template")
                logging.warning("Using default template - output may not match original codec/compression")
            
            # Create unique filenames to avoid conflicts (required for MusicEncoder)
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            
            # CRITICAL: MusicEncoder requires files to be in its own directory
            # Following exact pattern from mass_convert.bat
            encoder_template = encoder_dir / f'template_{unique_id}.scd'
            encoder_wav = encoder_dir / f'input_{unique_id}.wav'
            encoder_output_scd = output_dir / encoder_template.name
            
            # Ensure output directory exists
            output_dir.mkdir(exist_ok=True)
            
            # Copy files to MusicEncoder directory (following mass_convert.bat pattern)
            import shutil
            shutil.copy2(template_scd, encoder_template)
            shutil.copy2(wav_file, encoder_wav)
            
            # Log file sizes for debugging
            template_size = encoder_template.stat().st_size
            wav_size = encoder_wav.stat().st_size
            logging.info(f"Template SCD size: {template_size:,} bytes")
            logging.info(f"Input WAV size: {wav_size:,} bytes")
            
            try:
                # Run MusicEncoder from its own directory with files in same directory
                # Usage: MusicEncoder.exe <template.scd> <input.wav> [quality]
                # Quality is optional parameter 0-10 (default 10)
                # This follows the exact pattern from mass_convert.bat
                logging.info(f"Converting WAV to SCD using KH PC Sound Tools: {wav_path} -> {scd_path}")
                logging.info(f"MusicEncoder command: {music_encoder_exe.name} {encoder_template.name} {encoder_wav.name} {quality}")
                logging.info(f"Quality level: {quality}/10 {'(highest)' if quality == 10 else '(lowest)' if quality == 0 else ''}")
                
                result = subprocess.run(
                    [str(music_encoder_exe), str(encoder_template.name), str(encoder_wav.name), str(quality)],
                    cwd=str(encoder_dir),  # CRITICAL: Run from MusicEncoder directory
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=120,  # 2 minute timeout for conversion
                    startupinfo=self._create_subprocess_startupinfo(),
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode != 0:
                    logging.error(f"MusicEncoder failed with exit code {result.returncode}")
                    logging.error(f"MusicEncoder output: {result.stdout}")
                    logging.error(f"MusicEncoder errors: {result.stderr}")
                    return False
                
                # MusicEncoder puts the result in output/<template_name>.scd
                if encoder_output_scd.exists():
                    output_size = encoder_output_scd.stat().st_size
                    logging.info(f"Output SCD size: {output_size:,} bytes")
                    
                    # Compare sizes and analyze output
                    if original_scd_path and Path(original_scd_path).exists():
                        original_size = Path(original_scd_path).stat().st_size
                        size_ratio = output_size / original_size
                        logging.info(f"Size comparison: Original={original_size:,}, New={output_size:,} (ratio: {size_ratio:.2f}x)")
                        
                        if size_ratio > 2.0:
                            logging.warning(f"🚨 Output file is {size_ratio:.1f}x larger than original!")
                            logging.warning("This suggests MusicEncoder changed the audio duration or codec.")
                            logging.warning("Consider using direct loop point editing instead of WAV round-trip.")
                        elif size_ratio > 1.5:
                            logging.warning(f"⚠️  Output file is {size_ratio:.1f}x larger than original - codec mismatch?")
                    
                    # Analyze output file to check for issues
                    try:
                        # Import check - SCDCodecDetector may not be available
                        from core.loop_manager import SCDCodecDetector
                        from ui.metadata_reader import LoopMetadataReader
                        
                        detector = SCDCodecDetector()
                        output_info = detector.detect_codec_from_scd(str(encoder_output_scd))
                        if "error" not in output_info:
                            logging.info(f"Output codec: {output_info['codec_name']} (0x{output_info['codec_id']:02X})")
                            
                            # Check duration
                            reader = LoopMetadataReader()
                            metadata = reader.read_metadata(str(encoder_output_scd))
                            if metadata['duration'] > 0:
                                logging.info(f"Output duration: {metadata['duration']:.2f} seconds")
                                
                                # Compare with original if available
                                if original_scd_path and Path(original_scd_path).exists():
                                    orig_metadata = reader.read_metadata(original_scd_path)
                                    if orig_metadata['duration'] > 0:
                                        duration_ratio = metadata['duration'] / orig_metadata['duration']
                                        if duration_ratio > 1.1:  # More than 10% longer
                                            logging.error(f"🚨 DURATION MISMATCH: Output is {duration_ratio:.2f}x longer than original!")
                                            logging.error(f"Original: {orig_metadata['duration']:.2f}s, Output: {metadata['duration']:.2f}s")
                                            logging.error("MusicEncoder may have introduced audio artifacts or padding.")
                    except ImportError:
                        # SCDCodecDetector not available - skip analysis
                        pass
                    except Exception as e:
                        logging.debug(f"Could not analyze output file: {e}")
                    
                    shutil.copy2(encoder_output_scd, scd_file)
                    self._patch_scd_volume(scd_file, target_gain=1.2)
                    self._cache_sanitized(scd_file)
                    logging.info(f"SCD conversion completed: {scd_path}")
                    return True
                else:
                    logging.error(f"MusicEncoder did not produce expected output file: {encoder_output_scd}")
                    logging.error(f"Expected output directory contents: {list(output_dir.iterdir()) if output_dir.exists() else 'Directory does not exist'}")
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

    def _read_scd_volume(self, scd_path: Path) -> Optional[tuple]:
        """Read current SCD gain float and position; returns (gain, offset) or None"""
        try:
            import struct
            import math

            data = scd_path.read_bytes()
            if len(data) < 0x60:
                return None

            table_off = int.from_bytes(data[0x50:0x54], 'little')
            if table_off <= 0 or table_off + 12 > len(data):
                return None

            volume_pos = table_off + 8
            current_gain = struct.unpack('<f', data[volume_pos:volume_pos + 4])[0]
            if not math.isfinite(current_gain) or current_gain < 0.0 or current_gain > 10.0:
                return None
            return current_gain, volume_pos
        except Exception:
            return None

    def _patch_scd_volume(self, scd_path: Path, target_gain: float = 1.0) -> bool:
        """Patch SCD header playback gain float to avoid quiet output.

        The gain float for BGM is at (table_ptr + 0x08), where table_ptr is read from 0x50.
        This is typically at 0x128 for standard BGM files.
        """
        try:
            import struct

            gain_info = self._read_scd_volume(scd_path)
            if not gain_info:
                logging.warning("SCD volume float not found or invalid")
                return False

            current_gain, volume_pos = gain_info
            data = bytearray(scd_path.read_bytes())
            data[volume_pos:volume_pos + 4] = struct.pack('<f', float(target_gain))
            scd_path.write_bytes(data)
            logging.info(f"Patched SCD volume float at 0x{volume_pos:X}: {current_gain:.3f} -> {target_gain:.3f}")
            return True
        except Exception as e:
            logging.warning(f"Failed to patch SCD volume: {e}")
            return False

    def ensure_scd_ready_for_export(self, scd_path: str, target_gain: float = 1.2, target_lufs: float = -12.0,
                                     lufs_tolerance: float = 0.4) -> str:
        """Ensure an SCD has target gain and loudness. Returns path to patched copy (or original)."""
        scd_file = Path(scd_path)
        if not scd_file.exists():
            return scd_path

        # Fast path: if we've already sanitized this exact file in this session, skip work
        stat = scd_file.stat()
        key = str(scd_file.resolve())
        cache_entry = self._sanitized_cache.get(key)
        if cache_entry:
            cached_mtime = cache_entry.get("mtime")
            cached_size = cache_entry.get("size")
            cached_ok = cache_entry.get("ok", False)
            if cached_ok and cached_mtime == stat.st_mtime and cached_size == stat.st_size:
                return scd_path

        temp_wav = None
        temp_scd_path = None
        sanitized_path = scd_path

        try:
            gain_info = self._read_scd_volume(scd_file)
            needs_gain = (not gain_info) or abs(gain_info[0] - target_gain) > 0.01

            # Convert to WAV for loudness check
            temp_wav = self._create_temp_wav()
            wav_path = self.convert_scd_to_wav(str(scd_file), out_path=temp_wav, preserve_loop_points=True)
            if not wav_path:
                # Still try to patch gain if that's all we can do
                if needs_gain:
                    temp_fd, temp_scd = tempfile.mkstemp(suffix=".scd", prefix="scdtoolkit_gain_")
                    os.close(temp_fd)
                    temp_scd_path = Path(temp_scd)
                    shutil.copy2(scd_file, temp_scd_path)
                    self._patch_scd_volume(temp_scd_path, target_gain=target_gain)
                    sanitized_path = str(temp_scd_path)
                return sanitized_path

            analyzer = AudioAnalyzer()
            loudness = analyzer.measure_true_loudness(wav_path, target_i=target_lufs, target_tp=-1.0)
            needs_loudnorm = False
            if loudness and 'input_i' in loudness:
                needs_loudnorm = abs(loudness['input_i'] - target_lufs) > lufs_tolerance

            if needs_loudnorm:
                self.normalize_wav_loudness(wav_path, target_i=target_lufs, target_tp=-1.0)

                temp_fd, temp_scd = tempfile.mkstemp(suffix=".scd", prefix="scdtoolkit_norm_")
                os.close(temp_fd)
                temp_scd_path = Path(temp_scd)
                if self.convert_wav_to_scd(wav_path, str(temp_scd_path), original_scd_path=str(scd_file), quality=10):
                    sanitized_path = str(temp_scd_path)
                    needs_gain = False  # convert_wav_to_scd already patches gain
                    self._cache_sanitized(temp_scd_path)
                else:
                    try:
                        temp_scd_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    temp_scd_path = None
            elif needs_gain:
                temp_fd, temp_scd = tempfile.mkstemp(suffix=".scd", prefix="scdtoolkit_gain_")
                os.close(temp_fd)
                temp_scd_path = Path(temp_scd)
                shutil.copy2(scd_file, temp_scd_path)
                self._patch_scd_volume(temp_scd_path, target_gain=target_gain)
                sanitized_path = str(temp_scd_path)
                self._cache_sanitized(temp_scd_path)

            return sanitized_path
        finally:
            # Clean up temp WAV
            try:
                if temp_wav and Path(temp_wav).exists():
                    Path(temp_wav).unlink(missing_ok=True)
                if temp_wav and temp_wav in self.temp_files:
                    self.temp_files.remove(temp_wav)
            except Exception:
                pass

            # Cache sanitized result (persisted) by path/mtime/size
            self._cache_sanitized(scd_file)

