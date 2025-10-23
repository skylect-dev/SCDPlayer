"""Real-time audio analysis for visualizers"""
import numpy as np
import logging
from pathlib import Path
import wave
import struct


class AudioAnalyzer:
    """Analyzes audio files to provide spectrum data for visualizers"""
    
    def __init__(self):
        self.audio_data = None
        self.sample_rate = 44100
        self.channels = 2
        self.current_file = None
        self.fft_size = 4096  # Increased for better frequency resolution
        self.num_bars = 64  # Increased for finer frequency detail
        self.prev_spectrum = np.zeros(64)  # For smoothing
        self.smoothing_factor = 0.3  # 70% of new data, 30% of old data
        
    def load_file(self, file_path):
        """Load audio file for analysis"""
        try:
            if not file_path or not Path(file_path).exists():
                return False
                
            self.current_file = file_path
            
            # Read WAV file
            with wave.open(file_path, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                self.channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                sample_width = wav_file.getsampwidth()
                
                # Read all audio data
                audio_bytes = wav_file.readframes(n_frames)
                
                # Convert bytes to numpy array
                if sample_width == 1:  # 8-bit
                    dtype = np.uint8
                    self.audio_data = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32)
                    self.audio_data = (self.audio_data - 128) / 128.0
                elif sample_width == 2:  # 16-bit
                    dtype = np.int16
                    self.audio_data = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32)
                    self.audio_data = self.audio_data / 32768.0
                elif sample_width == 3:  # 24-bit
                    # Convert 24-bit to 32-bit
                    audio_data_24bit = np.frombuffer(audio_bytes, dtype=np.uint8)
                    n_samples = len(audio_data_24bit) // 3
                    audio_data_32bit = np.zeros(n_samples, dtype=np.int32)
                    
                    for i in range(n_samples):
                        # Combine 3 bytes into int32
                        byte1 = audio_data_24bit[i * 3]
                        byte2 = audio_data_24bit[i * 3 + 1]
                        byte3 = audio_data_24bit[i * 3 + 2]
                        
                        # Sign extend from 24-bit to 32-bit
                        value = (byte3 << 24) | (byte2 << 16) | (byte1 << 8)
                        audio_data_32bit[i] = value >> 8  # Arithmetic shift preserves sign
                    
                    self.audio_data = audio_data_32bit.astype(np.float32) / (2**23)
                elif sample_width == 4:  # 32-bit
                    dtype = np.int32
                    self.audio_data = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32)
                    self.audio_data = self.audio_data / (2**31)
                else:
                    logging.error(f"Unsupported sample width: {sample_width}")
                    return False
                
                # If stereo, mix to mono for simpler analysis
                if self.channels == 2:
                    self.audio_data = self.audio_data.reshape(-1, 2).mean(axis=1)
                
                logging.info(f"Loaded audio for visualization: {self.sample_rate}Hz, {len(self.audio_data)} samples")
                return True
                
        except Exception as e:
            logging.error(f"Failed to load audio for analysis: {e}")
            self.audio_data = None
            return False
    
    def get_spectrum_at_position(self, position_ms):
        """Get frequency spectrum at specific playback position"""
        if self.audio_data is None or len(self.audio_data) == 0:
            return np.zeros(self.num_bars)
        
        try:
            # Convert position from milliseconds to sample index
            position_samples = int((position_ms / 1000.0) * self.sample_rate)
            
            # Clamp to valid range
            position_samples = max(0, min(position_samples, len(self.audio_data) - self.fft_size))
            
            # Extract audio chunk for FFT
            audio_chunk = self.audio_data[position_samples:position_samples + self.fft_size]
            
            # Apply Hanning window to reduce spectral leakage
            window = np.hanning(len(audio_chunk))
            windowed_chunk = audio_chunk * window
            
            # Perform FFT
            fft_data = np.fft.rfft(windowed_chunk)
            fft_magnitude = np.abs(fft_data)
            
            # Convert to decibels
            fft_db = 20 * np.log10(fft_magnitude + 1e-10)  # Add small value to avoid log(0)
            
            # Normalize against a fixed reference level instead of per-frame max
            # This prevents everything from always appearing maxed out
            min_db = -20  # Minimum threshold (raise to suppress weak bars)
            max_db = 80    # Maximum reference (full scale)
            
            # Clamp and normalize to 0-1 range
            fft_db = np.clip(fft_db, min_db, max_db)
            fft_db = (fft_db - min_db) / (max_db - min_db)
            
            # Bin the FFT data into num_bars frequency bands (log scale for better visualization)
            spectrum = self._bin_fft_to_bars(fft_db)
            
            # Apply smoothing and boost for better visualization
            spectrum = np.power(spectrum, 0.5)  # Stronger compression: dominant bars stand out more
            
            # Apply temporal smoothing to reduce jitter
            # Mix 30% new data with 70% previous data
            spectrum = (self.smoothing_factor * spectrum) + ((1 - self.smoothing_factor) * self.prev_spectrum)
            self.prev_spectrum = spectrum.copy()
            
            return spectrum
            
        except Exception as e:
            logging.debug(f"Error getting spectrum: {e}")
            return np.zeros(self.num_bars)
    
    def _bin_fft_to_bars(self, fft_data):
        """Bin FFT data into frequency bars using Mel scale (perceptual spacing)"""
        num_fft_bins = len(fft_data)
        bars = np.zeros(self.num_bars)

        # Mel scale binning
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)

        def mel_to_hz(mel):
            return 700 * (10**(mel / 2595) - 1)

        # FFT bin frequencies
        nyquist = self.sample_rate / 2
        bin_freqs = np.linspace(0, nyquist, num_fft_bins)

        # Mel scale edges
        min_hz = 0
        max_hz = nyquist
        min_mel = hz_to_mel(min_hz)
        max_mel = hz_to_mel(max_hz)
        mel_points = np.linspace(min_mel, max_mel, self.num_bars + 1)
        hz_points = mel_to_hz(mel_points)
        bin_edges = np.searchsorted(bin_freqs, hz_points)
        bin_edges[0] = 1  # skip DC only
        bin_edges[-1] = num_fft_bins - 1

        # Ensure strictly increasing (no duplicates)
        for i in range(1, len(bin_edges)):
            if bin_edges[i] <= bin_edges[i-1]:
                bin_edges[i] = bin_edges[i-1] + 1

        for i in range(self.num_bars):
            start_bin = bin_edges[i]
            end_bin = bin_edges[i + 1]
            if end_bin > start_bin:
                bars[i] = np.mean(fft_data[start_bin:end_bin])
        return bars
    
    def get_volume_at_position(self, position_ms):
        """Get RMS volume at specific position"""
        if self.audio_data is None or len(self.audio_data) == 0:
            return 0.0
        
        try:
            # Convert position from milliseconds to sample index
            position_samples = int((position_ms / 1000.0) * self.sample_rate)
            
            # Extract a small chunk (100ms)
            chunk_size = int(self.sample_rate * 0.1)
            start = max(0, position_samples)
            end = min(len(self.audio_data), start + chunk_size)
            
            audio_chunk = self.audio_data[start:end]
            
            # Calculate RMS volume
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            
            return min(rms * 5.0, 1.0)  # Boost and clamp to 0-1
            
        except Exception as e:
            logging.debug(f"Error getting volume: {e}")
            return 0.0
    
    def clear(self):
        """Clear loaded audio data"""
        self.audio_data = None
        self.current_file = None
