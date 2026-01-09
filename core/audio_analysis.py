import json
import logging
import subprocess
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
from dataclasses import dataclass


@dataclass
class VolumeAdjustment:
    """Container for volume adjustment results"""
    original_peak_db: float
    target_peak_db: float
    gain_applied_db: float
    normalization_type: str
    adjusted_audio: np.ndarray
    clipping_prevented: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display"""
        return {
            'Original Peak': f"{self.original_peak_db:.1f} dB",
            'Target Peak': f"{self.target_peak_db:.1f} dB", 
            'Gain Applied': f"{self.gain_applied_db:+.1f} dB",
            'Method': self.normalization_type,
            'Clipping Prevented': "Yes" if self.clipping_prevented else "No"
        }


@dataclass
class AudioLevels:
    """Container for comprehensive audio level analysis"""
    peak_db: float          # Peak level in dB
    rms_db: float          # RMS level in dB  
    lufs: float            # Loudness Units relative to Full Scale
    dynamic_range_db: float # Dynamic range in dB
    crest_factor_db: float # Crest factor (peak-to-RMS ratio) in dB
    clips_detected: int    # Number of clipped samples
    clip_percentage: float # Percentage of audio that clips
    
    # Additional metrics
    peak_linear: float     # Peak level (0.0 to 1.0)
    rms_linear: float      # RMS level (0.0 to 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy display"""
        return {
            'Peak Level': f"{self.peak_db:.1f} dB" if self.peak_db > -60 else "< -60 dB",
            'RMS Level': f"{self.rms_db:.1f} dB" if self.rms_db > -60 else "< -60 dB", 
            'LUFS': f"{self.lufs:.1f} LUFS" if self.lufs > -60 else "< -60 LUFS",
            'Dynamic Range': f"{self.dynamic_range_db:.1f} dB",
            'Crest Factor': f"{self.crest_factor_db:.1f} dB",
            'Clipping': f"{self.clips_detected} samples ({self.clip_percentage:.2f}%)" if self.clips_detected > 0 else "None detected"
        }


class AudioAnalyzer:
    """Advanced audio analysis for level detection and loudness measurement"""
    
    def __init__(self):
        self.sample_rate = 44100

    def _ffmpeg_path(self) -> Path:
        """Get the bundled ffmpeg.exe path."""
        return Path(__file__).parent.parent / "ffmpeg" / "bin" / "ffmpeg.exe"

    def _subprocess_kwargs(self) -> Dict[str, Any]:
        """Hide console windows on Windows and keep default behavior elsewhere."""
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}
        return {}

    def _read_wav_format(self, wav_path: str) -> Tuple[int, int, str]:
        """Return (channels, sample_rate, sample_fmt) preserving source format when possible."""
        try:
            import wave

            with wave.open(wav_path, 'rb') as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                sampwidth = wf.getsampwidth()
            if sampwidth == 1:
                sample_fmt = "u8"
            elif sampwidth == 2:
                sample_fmt = "s16"
            elif sampwidth == 3:
                sample_fmt = "s32"
            else:
                sample_fmt = "s32"
            return channels, sample_rate, sample_fmt
        except Exception as e:
            logging.warning(f"Could not read WAV format, defaulting to s16: {e}")
            return 2, 44100, "s16"

    def measure_true_loudness(self, wav_path: str, target_i: float = -12.0, target_tp: float = -1.0) -> Optional[Dict[str, float]]:
        """Run ffmpeg loudnorm analysis to get true LUFS and true peak."""
        try:
            ffmpeg_path = self._ffmpeg_path()
            if not ffmpeg_path.exists():
                logging.warning("ffmpeg not found for loudness analysis")
                return None

            channels, sample_rate, sample_fmt = self._read_wav_format(wav_path)

            cmd = [
                str(ffmpeg_path),
                "-hide_banner", "-y",
                "-i", wav_path,
                "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json",
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-sample_fmt", sample_fmt,
                "-f", "null", "-"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **self._subprocess_kwargs())
            if result.returncode != 0:
                logging.error(f"ffmpeg loudnorm analysis failed: {result.stderr}")
                return None

            # ffmpeg writes the JSON block to stderr; extract between the first '{' and last '}'
            err = result.stderr
            start = err.find('{')
            end = err.rfind('}')
            if start == -1 or end == -1 or end <= start:
                logging.error("Could not parse loudnorm analysis output (no JSON block found)")
                return None

            loudnorm_json = err[start:end + 1]
            try:
                data = json.loads(loudnorm_json)
            except Exception as parse_err:
                logging.error(f"Could not parse loudnorm analysis JSON: {parse_err}")
                return None
            return {
                "input_i": float(data.get("input_i", 0.0)),
                "input_tp": float(data.get("input_tp", 0.0)),
                "input_lra": float(data.get("input_lra", 0.0)),
                "input_thresh": float(data.get("input_thresh", 0.0)),
                "target_offset": float(data.get("target_offset", 0.0)),
            }
        except Exception as e:
            logging.error(f"True loudness analysis failed: {e}")
            return None

    def normalize_file_loudness(self, wav_path: str, target_i: float = -12.0, target_tp: float = -1.0) -> Optional[str]:
        """
        Apply two-pass ffmpeg loudnorm to a WAV file in place and return the path.

        This uses true LUFS and true peak normalization for accurate in-game loudness.
        """
        temp_out = None
        try:
            ffmpeg_path = self._ffmpeg_path()
            if not ffmpeg_path.exists():
                logging.error("ffmpeg not found for loudness normalization")
                return None

            channels, sample_rate, sample_fmt = self._read_wav_format(wav_path)

            analyze = self.measure_true_loudness(wav_path, target_i=target_i, target_tp=target_tp)
            if not analyze:
                return None

            return self.apply_loudnorm_second_pass(
                wav_path,
                analyze,
                target_i=target_i,
                target_tp=target_tp,
                channels=channels,
                sample_rate=sample_rate,
                sample_fmt=sample_fmt,
            )

        except Exception as e:
            logging.error(f"Loudness normalization failed: {e}")
            return None
        finally:
            try:
                if temp_out and Path(temp_out).exists():
                    Path(temp_out).unlink()
            except Exception:
                pass

    def apply_loudnorm_second_pass(
        self,
        wav_path: str,
        analyze: Dict[str, float],
        *,
        target_i: float = -12.0,
        target_tp: float = -1.0,
        channels: int = 2,
        sample_rate: int = 44100,
        sample_fmt: str = "s16",
    ) -> Optional[str]:
        """Apply the loudnorm second pass using precomputed measurements.

        This avoids re-running the first-pass analysis when the caller already
        measured loudness.
        """
        temp_out = None
        try:
            ffmpeg_path = self._ffmpeg_path()
            if not ffmpeg_path.exists():
                logging.error("ffmpeg not found for loudness normalization")
                return None

            temp_fd, temp_out = tempfile.mkstemp(suffix="_loudnorm.wav", prefix="scdtoolkit_")
            os.close(temp_fd)
            Path(temp_out).unlink(missing_ok=True)

            filter_second_pass = (
                f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:"
                f"measured_I={analyze['input_i']}:"
                f"measured_LRA={analyze['input_lra']}:"
                f"measured_TP={analyze['input_tp']}:"
                f"measured_thresh={analyze['input_thresh']}:"
                f"offset={analyze['target_offset']}:"
                f"print_format=summary"
            )

            cmd_second = [
                str(ffmpeg_path),
                "-hide_banner", "-y",
                "-i", wav_path,
                "-af", filter_second_pass,
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-sample_fmt", sample_fmt,
                str(temp_out)
            ]

            result = subprocess.run(
                cmd_second,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._subprocess_kwargs(),
            )
            if result.returncode != 0:
                logging.error(f"ffmpeg loudnorm second pass failed: {result.stderr}")
                return None

            max_attempts = 5
            for attempt in range(1, max_attempts + 1):
                try:
                    Path(temp_out).replace(wav_path)
                    return wav_path
                except PermissionError as e:
                    if attempt == max_attempts:
                        logging.error("Loudness normalization failed: could not replace output (file locked)")
                        return None
                    backoff = 0.2 * attempt
                    logging.warning(
                        f"Replace failed (attempt {attempt}/{max_attempts}), retrying after {backoff:.2f}s: {e}"
                    )
                    time.sleep(backoff)
                except Exception as e:
                    logging.error(f"Loudness normalization failed during replace: {e}")
                    return None
        finally:
            try:
                if temp_out and Path(temp_out).exists():
                    Path(temp_out).unlink()
            except Exception:
                pass

        
    def analyze_audio_levels(self, audio_data: np.ndarray, sample_rate: int = 44100) -> AudioLevels:
        """
        Comprehensive audio level analysis
        
        Args:
            audio_data: Normalized audio data (-1.0 to 1.0)
            sample_rate: Sample rate in Hz
            
        Returns:
            AudioLevels object with all analysis results
        """
        self.sample_rate = sample_rate
        
        if len(audio_data) == 0:
            return self._create_silence_levels()
        
        # Ensure audio is in proper range
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # Basic level calculations
        peak_linear = np.max(np.abs(audio_data))
        rms_linear = np.sqrt(np.mean(audio_data ** 2))
        
        # Convert to dB (avoid log(0) by using a floor)
        peak_db = self._linear_to_db(peak_linear) if peak_linear > 0 else -np.inf
        rms_db = self._linear_to_db(rms_linear) if rms_linear > 0 else -np.inf
        
        # Crest factor (peak-to-RMS ratio)
        crest_factor_linear = peak_linear / rms_linear if rms_linear > 0 else 0
        crest_factor_db = self._linear_to_db(crest_factor_linear) if crest_factor_linear > 0 else 0
        
        # LUFS calculation (simplified - full LUFS requires K-weighting filter)
        # This is an approximation for basic loudness measurement
        lufs = self._calculate_approximate_lufs(audio_data)
        
        # Dynamic range calculation
        dynamic_range_db = self._calculate_dynamic_range(audio_data)
        
        # Clipping detection
        clips_detected, clip_percentage = self._detect_clipping(audio_data)
        
        return AudioLevels(
            peak_db=peak_db,
            rms_db=rms_db,
            lufs=lufs,
            dynamic_range_db=dynamic_range_db,
            crest_factor_db=crest_factor_db,
            clips_detected=clips_detected,
            clip_percentage=clip_percentage,
            peak_linear=peak_linear,
            rms_linear=rms_linear
        )
    
    def analyze_audio_segments(self, audio_data: np.ndarray, segment_duration: float = 1.0) -> Dict[str, Any]:
        """
        Analyze audio in segments for time-based level information
        
        Args:
            audio_data: Normalized audio data
            segment_duration: Duration of each segment in seconds
            
        Returns:
            Dictionary with segment-by-segment analysis
        """
        segment_samples = int(segment_duration * self.sample_rate)
        num_segments = len(audio_data) // segment_samples
        
        if num_segments == 0:
            return {'segments': [], 'summary': self.analyze_audio_levels(audio_data)}
        
        segments = []
        for i in range(num_segments):
            start_idx = i * segment_samples
            end_idx = min((i + 1) * segment_samples, len(audio_data))
            segment_data = audio_data[start_idx:end_idx]
            
            segment_analysis = self.analyze_audio_levels(segment_data, self.sample_rate)
            segments.append({
                'start_time': start_idx / self.sample_rate,
                'end_time': end_idx / self.sample_rate,
                'levels': segment_analysis
            })
        
        # Overall summary
        summary = self.analyze_audio_levels(audio_data, self.sample_rate)
        
        return {
            'segments': segments,
            'summary': summary,
            'segment_duration': segment_duration,
            'total_segments': num_segments
        }
    
    def get_gain_recommendation(self, levels: AudioLevels) -> Dict[str, Any]:
        """
        Provide gain adjustment recommendations based on game audio analysis
        
        Args:
            levels: AudioLevels object from analysis
            
        Returns:
            Dictionary with gain recommendations and reasoning
        """
        recommendations = []
        
        # Peak level recommendations based on real game audio (0.0 to -0.6dB typical)
        if levels.peak_db > 0.1:
            recommendations.append({
                'type': 'warning',
                'message': f'Peak level exceeds game audio ({levels.peak_db:.1f} dB). Clipping likely.',
                'suggestion': f'Reduce gain by {abs(levels.peak_db + 0.2):.1f} dB to match typical game audio (-0.2dB).'
            })
        elif levels.peak_db > -0.1:
            recommendations.append({
                'type': 'info',
                'message': f'Peak level matches maximum game audio ({levels.peak_db:.1f} dB).',
                'suggestion': 'Level is at maximum game audio range. No adjustment needed.'
            })
        elif levels.peak_db < -10:
            recommendations.append({
                'type': 'info', 
                'message': f'Peak level is low ({levels.peak_db:.1f} dB).',
                'suggestion': f'Could increase gain by up to {abs(levels.peak_db + 0.2):.1f} dB to match typical game audio.'
            })
        elif -0.6 <= levels.peak_db <= -0.1:
            recommendations.append({
                'type': 'info',
                'message': f'Peak level is within game audio range ({levels.peak_db:.1f} dB).',
                'suggestion': 'Good dynamic range preserved.'
            })
        
        # RMS level recommendations based on real game audio (-13 to -18dB typical)
        if levels.rms_db > -10:
            recommendations.append({
                'type': 'warning',
                'message': f'RMS level is higher than game audio ({levels.rms_db:.1f} dB).',
                'suggestion': 'Consider reducing to -13 to -18dB range typical of game audio.'
            })
        elif -18 <= levels.rms_db <= -13:
            recommendations.append({
                'type': 'info',
                'message': f'RMS level matches game audio range ({levels.rms_db:.1f} dB).',
                'suggestion': 'RMS level is optimal for game audio integration.'
            })
        elif levels.rms_db < -25:
            recommendations.append({
                'type': 'info',
                'message': f'RMS level is low ({levels.rms_db:.1f} dB).',
                'suggestion': 'Could increase to -13 to -18dB range to match game audio.'
            })
        
        # LUFS recommendations based on game audio (-14 to -18 LUFS typical)
        if levels.lufs > -10:
            recommendations.append({
                'type': 'warning',
                'message': f'Loudness exceeds game audio ({levels.lufs:.1f} LUFS).',
                'suggestion': 'Consider reducing to -14 to -18 LUFS range typical of game audio.'
            })
        elif -18 <= levels.lufs <= -14:
            recommendations.append({
                'type': 'info',
                'message': f'Loudness matches game audio range ({levels.lufs:.1f} LUFS).',
                'suggestion': 'LUFS level is optimal for game audio integration.'
            })
        elif levels.lufs < -25:
            recommendations.append({
                'type': 'info',
                'message': f'Loudness is low ({levels.lufs:.1f} LUFS).',
                'suggestion': 'Could increase to -14 to -18 LUFS range to match game audio.'
            })
        
        # Clipping warnings
        if levels.clips_detected > 0:
            recommendations.append({
                'type': 'error',
                'message': f'Audio clipping detected ({levels.clips_detected} samples).',
                'suggestion': 'Reduce gain to eliminate distortion.'
            })
        
        # Dynamic range assessment - game audio typically has good dynamic range
        if levels.dynamic_range_db < 6:
            recommendations.append({
                'type': 'warning',
                'message': f'Low dynamic range ({levels.dynamic_range_db:.1f} dB).',
                'suggestion': 'Audio may be over-compressed compared to typical game audio.'
            })
        elif levels.dynamic_range_db > 30:
            recommendations.append({
                'type': 'info',
                'message': f'High dynamic range ({levels.dynamic_range_db:.1f} dB).',
                'suggestion': 'Good dynamic range preserved.'
            })
        
        return {
            'recommendations': recommendations,
            'overall_status': 'good' if not any(r['type'] == 'error' for r in recommendations) else 'issues_detected'
        }
    
    def _linear_to_db(self, linear_value: float) -> float:
        """Convert linear amplitude to dB"""
        if linear_value <= 0:
            return -np.inf
        return 20 * np.log10(linear_value)
    
    def _calculate_approximate_lufs(self, audio_data: np.ndarray) -> float:
        """
        Calculate approximate LUFS (simplified without K-weighting)
        This is a basic approximation - full LUFS requires proper K-weighting filter
        """
        # Use RMS with a slight adjustment to approximate LUFS
        rms = np.sqrt(np.mean(audio_data ** 2))
        if rms <= 0:
            return -np.inf
        
        # Convert to approximate LUFS (this is simplified)
        lufs_approx = -0.691 + 10 * np.log10(rms ** 2)
        return lufs_approx
    
    def _calculate_dynamic_range(self, audio_data: np.ndarray, percentile_low: float = 10.0, percentile_high: float = 95.0) -> float:
        """
        Calculate dynamic range as the difference between high and low percentiles
        
        Args:
            audio_data: Audio data
            percentile_low: Lower percentile (default 10%)
            percentile_high: Upper percentile (default 95%)
        """
        abs_data = np.abs(audio_data)
        
        # Remove silence (very low values)
        non_silent = abs_data[abs_data > 0.001]  # -60 dB threshold
        
        if len(non_silent) == 0:
            return 0.0
        
        low_val = np.percentile(non_silent, percentile_low)
        high_val = np.percentile(non_silent, percentile_high)
        
        if low_val <= 0:
            return self._linear_to_db(high_val)
        
        return self._linear_to_db(high_val) - self._linear_to_db(low_val)
    
    def _detect_clipping(self, audio_data: np.ndarray, threshold: float = 0.99) -> Tuple[int, float]:
        """
        Detect clipping in audio data
        
        Args:
            audio_data: Audio data (-1.0 to 1.0)
            threshold: Clipping threshold (default 0.99)
            
        Returns:
            Tuple of (number_of_clipped_samples, percentage_clipped)
        """
        clipped_samples = np.sum(np.abs(audio_data) >= threshold)
        clip_percentage = (clipped_samples / len(audio_data)) * 100 if len(audio_data) > 0 else 0
        
        return int(clipped_samples), clip_percentage
    
    def _create_silence_levels(self) -> AudioLevels:
        """Create AudioLevels object for silent audio"""
        return AudioLevels(
            peak_db=-np.inf,
            rms_db=-np.inf,
            lufs=-np.inf,
            dynamic_range_db=0.0,
            crest_factor_db=0.0,
            clips_detected=0,
            clip_percentage=0.0,
            peak_linear=0.0,
            rms_linear=0.0
        )
    
    def normalize_peak(self, audio_data: np.ndarray, target_db: float = -1.0) -> VolumeAdjustment:
        """
        Normalize audio to a target peak level
        
        Args:
            audio_data: Input audio data
            target_db: Target peak level in dB
            
        Returns:
            VolumeAdjustment object with results
        """
        try:
            # Analyze current levels
            levels = self.analyze_audio_levels(audio_data)
            original_peak = levels.peak_db
            
            if original_peak == -np.inf:
                return VolumeAdjustment(
                    original_peak_db=original_peak,
                    target_peak_db=target_db,
                    gain_applied_db=0.0,
                    normalization_type="Peak Normalization (Silent Audio)",
                    adjusted_audio=audio_data.copy(),
                    clipping_prevented=False
                )
            
            # Calculate required gain
            gain_db = target_db - original_peak
            gain_linear = 10 ** (gain_db / 20)
            
            # Apply gain
            adjusted_audio = audio_data * gain_linear
            
            # Check for clipping and prevent it
            clipping_prevented = False
            max_val = np.max(np.abs(adjusted_audio))
            if max_val > 0.99:
                # Reduce gain to prevent clipping
                safety_factor = 0.99 / max_val
                adjusted_audio *= safety_factor
                actual_gain_db = gain_db + 20 * np.log10(safety_factor)
                clipping_prevented = True
            else:
                actual_gain_db = gain_db
            
            return VolumeAdjustment(
                original_peak_db=original_peak,
                target_peak_db=target_db,
                gain_applied_db=actual_gain_db,
                normalization_type="Peak Normalization",
                adjusted_audio=adjusted_audio,
                clipping_prevented=clipping_prevented
            )
            
        except Exception as e:
            logging.error(f"Error in peak normalization: {e}")
            return VolumeAdjustment(0, 0, 0, "Error", audio_data.copy(), False)
    
    def normalize_rms(self, audio_data: np.ndarray, target_db: float = -12.0) -> VolumeAdjustment:
        """
        Normalize audio to a target RMS level
        
        Args:
            audio_data: Input audio data
            target_db: Target RMS level in dB
            
        Returns:
            VolumeAdjustment object with results
        """
        try:
            # Analyze current levels
            levels = self.analyze_audio_levels(audio_data)
            original_peak = levels.peak_db
            original_rms = levels.rms_db
            
            if original_rms == -np.inf:
                return VolumeAdjustment(
                    original_peak_db=original_peak,
                    target_peak_db=target_db,
                    gain_applied_db=0.0,
                    normalization_type="RMS Normalization (Silent Audio)",
                    adjusted_audio=audio_data.copy(),
                    clipping_prevented=False
                )
            
            # Calculate required gain based on RMS
            gain_db = target_db - original_rms
            gain_linear = 10 ** (gain_db / 20)
            
            # Apply gain
            adjusted_audio = audio_data * gain_linear
            
            # Check for clipping and prevent it
            clipping_prevented = False
            max_val = np.max(np.abs(adjusted_audio))
            if max_val > 0.99:
                # Reduce gain to prevent clipping
                safety_factor = 0.99 / max_val
                adjusted_audio *= safety_factor
                actual_gain_db = gain_db + 20 * np.log10(safety_factor)
                clipping_prevented = True
            else:
                actual_gain_db = gain_db
            
            # Calculate what the new peak will be
            new_levels = self.analyze_audio_levels(adjusted_audio)
            actual_target_peak = new_levels.peak_db
            
            return VolumeAdjustment(
                original_peak_db=original_peak,
                target_peak_db=actual_target_peak,
                gain_applied_db=actual_gain_db,
                normalization_type="RMS Normalization",
                adjusted_audio=adjusted_audio,
                clipping_prevented=clipping_prevented
            )
            
        except Exception as e:
            logging.error(f"Error in RMS normalization: {e}")
            return VolumeAdjustment(0, 0, 0, "Error", audio_data.copy(), False)
    
    def auto_level_adjustment(self, audio_data: np.ndarray) -> VolumeAdjustment:
        """
        Intelligent auto-leveling that targets realistic game audio levels
        
        Args:
            audio_data: Input audio data
            
        Returns:
            VolumeAdjustment object with results
        """
        try:
            # Analyze current levels
            levels = self.analyze_audio_levels(audio_data)
            
            # Choose normalization strategy based on current levels and game audio standards
            if levels.peak_db <= -10:
                # Very quiet audio - normalize to typical game audio peak (-0.2dB)
                result = self.normalize_peak(audio_data, target_db=-0.2)
                result.normalization_type = "Auto Level (Peak to Game Standard)"
                return result
            elif levels.peak_db > 0.1:
                # Audio is clipping or too hot - bring down to conservative game level
                result = self.normalize_peak(audio_data, target_db=-0.6)
                result.normalization_type = "Auto Level (Peak Reduced - Clipping Prevention)"
                return result
            elif levels.rms_db < -25:
                # RMS is very low - use RMS normalization to game audio range
                result = self.normalize_rms(audio_data, target_db=-15.0)
                result.normalization_type = "Auto Level (RMS to Game Range)"
                return result
            elif levels.rms_db > -10:
                # RMS is too high - reduce to game audio range
                result = self.normalize_rms(audio_data, target_db=-15.0)
                result.normalization_type = "Auto Level (RMS Reduced to Game Range)"
                return result
            elif -0.6 <= levels.peak_db <= 0.0 and -18 <= levels.rms_db <= -13:
                # Already in game audio range - minimal adjustment to typical level
                result = self.normalize_peak(audio_data, target_db=-0.2)
                result.normalization_type = "Auto Level (Fine-tune to Game Standard)"
                return result
            else:
                # General case - normalize to typical game audio peak
                result = self.normalize_peak(audio_data, target_db=-0.2)
                result.normalization_type = "Auto Level (Peak to Game Standard)"
                return result
                
        except Exception as e:
            logging.error(f"Error in auto level adjustment: {e}")
            return VolumeAdjustment(0, 0, 0, "Auto Level (Error)", audio_data.copy(), False)
