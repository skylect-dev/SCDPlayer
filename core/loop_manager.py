"""Loop point management for audio files"""
import os
import json
import wave
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
    
    def is_valid(self) -> bool:
        """Check if loop points are valid"""
        return self.start_sample >= 0 and self.end_sample > self.start_sample


class LoopPointManager:
    """Manages loop points for audio files"""
    
    def __init__(self):
        self.current_loop: Optional[LoopPoint] = None
        self.sample_rate: int = 44100
        self.total_samples: int = 0
        
    def set_loop_points(self, start_sample: int, end_sample: int) -> bool:
        """Set loop points and validate them"""
        print(f"Debug: Setting loop points - start_sample: {start_sample}, end_sample: {end_sample}")
        if start_sample < 0 or end_sample <= start_sample or end_sample > self.total_samples:
            return False
            
        self.current_loop = LoopPoint(start_sample, end_sample)
        return True
    
    def clear_loop_points(self):
        """Clear current loop points"""
        self.current_loop = None
    
    def get_loop_times(self) -> Tuple[float, float]:
        """Get loop points as time in seconds"""
        if not self.current_loop or self.sample_rate == 0:
            return (0.0, 0.0)
            
        start_time = self.current_loop.start_sample / self.sample_rate
        end_time = self.current_loop.end_sample / self.sample_rate
        return (start_time, end_time)
    
    def set_loop_times(self, start_time: float, end_time: float) -> bool:
        """Set loop points from time in seconds"""
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        return self.set_loop_points(start_sample, end_sample)
    
    def samples_to_time(self, samples: int) -> float:
        """Convert samples to time in seconds"""
        if self.sample_rate == 0:
            return 0.0
        return samples / self.sample_rate
    
    def time_to_samples(self, time_seconds: float) -> int:
        """Convert time to samples"""
        return int(time_seconds * self.sample_rate)
    
    def read_wav_loop_points(self, wav_path: str) -> bool:
        """Read loop points from WAV file metadata"""
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                self.total_samples = wav_file.getnframes()
                
                # Try to read loop points from WAV metadata
                # This would need to be expanded to read actual BWF or other metadata chunks
                # For now, we'll return False and rely on manual setting
                return False
                
        except Exception:
            return False
    
    def write_wav_with_loop_points(self, input_path: str, output_path: str, 
                                  trim_after_loop: bool = False) -> bool:
        """Write WAV file with loop point metadata compatible with Audacity"""
        if not self.current_loop:
            return False
            
        try:
            import soundfile as sf
            import wave
            import struct
            import tempfile
            import os
            
            # Read the audio data
            data, sample_rate = sf.read(input_path)
            
            # If trimming, only keep audio up to loop end
            if trim_after_loop:
                data = data[:self.current_loop.end_sample]
            
            # Write to temporary file first using soundfile
            temp_dir = tempfile.gettempdir()
            temp_wav = os.path.join(temp_dir, f"temp_loop_{os.getpid()}.wav")
            
            sf.write(temp_wav, data, sample_rate, format='WAV', subtype='PCM_16')
            
            # Now add the loop metadata using wave module
            self._add_loop_metadata_to_wav(temp_wav, output_path)
            
            # Clean up temporary file
            try:
                os.remove(temp_wav)
            except:
                pass
            
            return True
            
        except ImportError:
            print("soundfile library not available")
            return False
        except Exception as e:
            print(f"Error writing WAV with loop points: {e}")
            return False
    
    def _add_loop_metadata_to_wav(self, input_wav: str, output_wav: str):
        """Add Audacity-compatible loop metadata to WAV file using ID3v2 tags"""
        import struct
        import os
        
        # Read the original WAV file
        with open(input_wav, 'rb') as infile:
            wav_data = bytearray(infile.read())
        
        if not self.current_loop:
            # If no loop points, just copy the file
            with open(output_wav, 'wb') as outfile:
                outfile.write(wav_data)
            return
        
        # Create ID3v2 tags exactly like Audacity does
        def create_txxx_frame(description: str, value: str) -> bytes:
            """Create a TXXX (user-defined text) frame for ID3v2"""
            # TXXX frame format:
            # Frame ID (4 bytes): TXXX
            # Size (4 bytes): size of frame data (excluding header)
            # Flags (2 bytes): 0x0000
            # Text encoding (1 byte): 0x00 (ISO-8859-1)
            # Description (null-terminated)
            # Value (null-terminated)
            
            encoding = b'\x00'  # ISO-8859-1
            desc_bytes = description.encode('iso-8859-1') + b'\x00'
            value_bytes = value.encode('iso-8859-1') + b'\x00'
            
            frame_data = encoding + desc_bytes + value_bytes
            frame_size = len(frame_data)
            
            return b'TXXX' + struct.pack('>I', frame_size) + b'\x00\x00' + frame_data
        
        # Create frames for LoopStart and LoopEnd
        loop_start_frame = create_txxx_frame('LoopStart', str(self.current_loop.start_sample))
        loop_end_frame = create_txxx_frame('LoopEnd', str(self.current_loop.end_sample))
        
        # Create ID3v2 header
        id3_data = loop_start_frame + loop_end_frame
        id3_size = len(id3_data)
        
        # ID3v2 header: ID3 + version (2.3) + flags + size
        # Size is encoded as synchsafe integer (7 bits per byte)
        def encode_synchsafe(size):
            return struct.pack('>4B', 
                               (size >> 21) & 0x7F,
                               (size >> 14) & 0x7F, 
                               (size >> 7) & 0x7F,
                               size & 0x7F)
        
        id3_header = b'ID3' + b'\x03\x00' + b'\x00' + encode_synchsafe(id3_size)
        id3_chunk_data = id3_header + id3_data
        
        # Pad to even length for WAV alignment
        if len(id3_chunk_data) % 2:
            id3_chunk_data += b'\x00'
        
        # Create the id3 chunk for WAV (note: lowercase 'id3 ' with space)
        id3_chunk = b'id3 ' + struct.pack('<I', len(id3_chunk_data)) + id3_chunk_data
        
        # Update RIFF size to account for new chunk
        original_size = struct.unpack('<I', wav_data[4:8])[0]
        new_size = original_size + len(id3_chunk)
        wav_data[4:8] = struct.pack('<I', new_size)
        
        # Append the id3 chunk at the end (like Audacity does)
        wav_data.extend(id3_chunk)
        
        # Write the modified WAV file
        with open(output_wav, 'wb') as outfile:
            outfile.write(wav_data)
        
        print(f"Added Audacity-compatible ID3v2 loop metadata: LoopStart={self.current_loop.start_sample}, LoopEnd={self.current_loop.end_sample}")
    
    def _write_loop_metadata(self, wav_file):
        """Write loop point metadata to WAV file"""
        # This is a placeholder - real implementation would write BWF or other standard chunks
        # For the community workflow, we might need to use a different library like soundfile
        pass
    
    def export_loop_info(self) -> Dict[str, Any]:
        """Export loop information for saving to external metadata"""
        if not self.current_loop:
            return {}
            
        return {
            'LoopStart': str(self.current_loop.start_sample),
            'LoopEnd': str(self.current_loop.end_sample),
            'SampleRate': str(self.sample_rate),
            'TotalSamples': str(self.total_samples)
        }
    
    def save_loop_metadata_json(self, filepath: str) -> bool:
        """Save loop metadata to a JSON file for preservation during SCD conversion"""
        try:
            metadata = self.export_loop_info()
            if not metadata:
                return False
                
            json_path = filepath + '.loop_metadata.json'
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving loop metadata: {e}")
            return False
    
    def load_loop_metadata_json(self, filepath: str) -> bool:
        """Load loop metadata from a JSON file"""
        try:
            json_path = filepath + '.loop_metadata.json'
            if not os.path.exists(json_path):
                return False
                
            with open(json_path, 'r') as f:
                metadata = json.load(f)
            
            if 'LoopStart' in metadata and 'LoopEnd' in metadata:
                start_sample = int(metadata['LoopStart'])
                end_sample = int(metadata['LoopEnd'])
                self.sample_rate = int(metadata.get('SampleRate', 44100))
                self.total_samples = int(metadata.get('TotalSamples', 0))
                
                self.current_loop = LoopPoint(start_sample, end_sample)
                return True
            return False
        except Exception as e:
            print(f"Error loading loop metadata: {e}")
            return False
    
    def save_scd_loop_metadata(self, scd_filepath: str, trim_after_loop: bool = False) -> bool:
        """Save loop metadata to native SCD header locations using vgmstream format specification"""
        try:
            if not self.current_loop:
                return False
            
            import shutil
            
            # Create backup of original SCD
            backup_path = scd_filepath + '.backup'
            shutil.copy2(scd_filepath, backup_path)
            
            # Read the SCD file
            with open(scd_filepath, 'rb') as f:
                scd_data = bytearray(f.read())
            
            # Verify this is a valid SCD file
            if len(scd_data) < 64 or scd_data[:8] != b'SEDBSSCF':
                print("Warning: Not a valid SCD file")
                # Restore backup
                try:
                    shutil.copy2(backup_path, scd_filepath)
                    os.remove(backup_path)
                except:
                    pass
                return False
            
            # Parse SCD header structure based on vgmstream sqex_scd.c
            big_endian = scd_data[0x0c] == 0x01
            
            # Get tables offset (usually 0x30 or 0x20)
            if big_endian:
                tables_offset = struct.unpack('>H', scd_data[0x0e:0x10])[0]
            else:
                tables_offset = struct.unpack('<H', scd_data[0x0e:0x10])[0]
            
            # Get headers table info
            if big_endian:
                headers_entries = struct.unpack('>H', scd_data[tables_offset+0x04:tables_offset+0x06])[0]
                headers_offset = struct.unpack('>I', scd_data[tables_offset+0x0c:tables_offset+0x10])[0]
            else:
                headers_entries = struct.unpack('<H', scd_data[tables_offset+0x04:tables_offset+0x06])[0]
                headers_offset = struct.unpack('<I', scd_data[tables_offset+0x0c:tables_offset+0x10])[0]
            
            if headers_entries == 0:
                print("No headers found in SCD file")
                # Restore backup
                try:
                    shutil.copy2(backup_path, scd_filepath)
                    os.remove(backup_path)
                except:
                    pass
                return False
            
            # Find the first valid header entry (non-dummy)
            meta_offset = None
            for i in range(headers_entries):
                entry_offset_start = headers_offset + i * 4
                if entry_offset_start + 4 > len(scd_data):
                    continue
                    
                if big_endian:
                    entry_offset = struct.unpack('>I', scd_data[entry_offset_start:entry_offset_start+4])[0]
                else:
                    entry_offset = struct.unpack('<I', scd_data[entry_offset_start:entry_offset_start+4])[0]
                
                # Check if this entry has a valid codec (not -1 for dummy)
                if entry_offset + 0x10 <= len(scd_data):
                    if big_endian:
                        codec = struct.unpack('>i', scd_data[entry_offset+0x0c:entry_offset+0x10])[0]
                    else:
                        codec = struct.unpack('<i', scd_data[entry_offset+0x0c:entry_offset+0x10])[0]
                    
                    if codec != -1:
                        meta_offset = entry_offset
                        break
            
            if meta_offset is None:
                print("No valid stream header found in SCD file")
                # Restore backup
                try:
                    shutil.copy2(backup_path, scd_filepath)
                    os.remove(backup_path)
                except:
                    pass
                return False
            
            # Write loop points to the native SCD locations (offsets 0x10 and 0x14 from meta_offset)
            # These are the exact locations vgmstream reads from
            loop_start_offset = meta_offset + 0x10
            loop_end_offset = meta_offset + 0x14
            
            if loop_end_offset + 4 > len(scd_data):
                print("File too small to write loop metadata")
                # Restore backup
                try:
                    shutil.copy2(backup_path, scd_filepath)
                    os.remove(backup_path)
                except:
                    pass
                return False
            
            # Pack and write loop points in the correct endianness
            print(f"Debug: About to save loop points - start_sample: {self.current_loop.start_sample}, end_sample: {self.current_loop.end_sample}")
            if big_endian:
                loop_start_bytes = struct.pack('>I', self.current_loop.start_sample)
                loop_end_bytes = struct.pack('>I', self.current_loop.end_sample)
            else:
                loop_start_bytes = struct.pack('<I', self.current_loop.start_sample)
                loop_end_bytes = struct.pack('<I', self.current_loop.end_sample)
            
            scd_data[loop_start_offset:loop_start_offset + 4] = loop_start_bytes
            scd_data[loop_end_offset:loop_end_offset + 4] = loop_end_bytes
            
            # Write back the modified SCD
            with open(scd_filepath, 'wb') as f:
                f.write(scd_data)
                
            # Remove backup on success
            try:
                os.remove(backup_path)
            except:
                pass
                
            print(f"Successfully saved loop metadata to native SCD locations (meta_offset+0x10/0x14): {self.current_loop.start_sample} -> {self.current_loop.end_sample}")
            return True
            
        except Exception as e:
            print(f"Error saving SCD loop metadata: {e}")
            # Restore backup on failure
            try:
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, scd_filepath)
                    os.remove(backup_path)
            except:
                pass
            return False
    
    def inject_loop_metadata_into_scd(self, scd_filepath: str) -> bool:
        """Attempt to inject loop metadata into SCD file in a format vgmstream can read"""
        try:
            if not self.current_loop:
                return False
            
            # Read the SCD file
            with open(scd_filepath, 'rb') as f:
                scd_data = bytearray(f.read())
            
            # Verify this is a valid SCD file
            if len(scd_data) < 256 or scd_data[:8] != b'SEDBSSCF':
                print("Warning: Unrecognized SCD format")
                return False
            
            # Strategy: Since we can't easily reverse-engineer the exact SCD loop format,
            # we'll try multiple approaches that might work with vgmstream
            
            # Approach 1: Store in header area that has unused space
            # Based on analysis, offsets 20-31 appear to be unused (all zeros)
            loop_start = self.current_loop.start_sample
            loop_end = self.current_loop.end_sample
            
            # Try storing at offset 20 in a format similar to other audio formats
            # Store as: [loop_start (4 bytes)] [loop_end (4 bytes)] [loop_count (4 bytes)]
            loop_offset = 20
            
            # Store loop metadata
            scd_data[loop_offset:loop_offset+4] = struct.pack('<I', loop_start)
            scd_data[loop_offset+4:loop_offset+8] = struct.pack('<I', loop_end)
            scd_data[loop_offset+8:loop_offset+12] = struct.pack('<I', 0)  # Loop count/type
            
            # Approach 2: Also store at the end with a marker that we can read back
            # This ensures we can at least read our own saves
            end_marker = b'SCDLOOP\x00'  # 8-byte marker
            loop_data = struct.pack('<II', loop_start, loop_end)
            
            # Append at end
            scd_data.extend(end_marker + loop_data)
            
            # Write back the modified SCD
            with open(scd_filepath, 'wb') as f:
                f.write(scd_data)
                
            print(f"Injected loop metadata into SCD: {loop_start} -> {loop_end}")
            print(f"  Header location: offset {loop_offset}")
            print(f"  Backup location: end of file")
            return True
            
        except Exception as e:
            print(f"Error injecting loop metadata into SCD: {e}")
            return False
    
    def read_loop_metadata_from_scd(self, scd_filepath: str) -> bool:
        """Read loop metadata from SCD file using vgmstream (now reads from native SCD locations)"""
        try:
            # Use vgmstream to read native SCD loop points
            from ui.metadata_reader import LoopMetadataReader
            
            reader = LoopMetadataReader()
            metadata = reader.read_metadata(scd_filepath)
            
            if metadata.get('has_loop', False):
                start_sample = metadata.get('loop_start', 0)
                end_sample = metadata.get('loop_end', 0)
                
                self.sample_rate = metadata.get('sample_rate', 44100)
                self.total_samples = metadata.get('total_samples', 0)
                
                self.current_loop = LoopPoint(start_sample, end_sample)
                print(f"Read native loop metadata from SCD using vgmstream: {start_sample} -> {end_sample}")
                return True
            else:
                print("No loop metadata found in SCD file")
                return False
                
        except Exception as e:
            print(f"Error reading loop metadata from SCD: {e}")
            return False
