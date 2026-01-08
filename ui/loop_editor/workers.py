import logging
from PyQt5.QtCore import QThread, pyqtSignal
from core.audio_analysis import AudioAnalyzer


class SaveWorker(QThread):
    """Worker thread for saving SCD files to prevent UI blocking"""

    finished = pyqtSignal(bool)  # True if successful, False if failed
    error = pyqtSignal(str)      # Error message

    def __init__(self, loop_manager):
        super().__init__()
        self.loop_manager = loop_manager

    def run(self):
        try:
            success = self.loop_manager.save_loop_points()
            self.finished.emit(success)
        except Exception as e:
            logging.exception("SaveWorker failed")
            self.error.emit(str(e))


class LoudnessWorker(QThread):
    """Background worker for loudness analysis and normalization"""

    analyze_finished = pyqtSignal(object)  # true loudness dict or None
    normalize_finished = pyqtSignal(bool, object)  # success, true loudness dict or None
    error = pyqtSignal(str)

    def __init__(self, mode: str, wav_path: str, target_i: float = -12.0, target_tp: float = -1.0, delta_i: float = None):
        super().__init__()
        self.mode = mode
        self.wav_path = wav_path
        self.target_i = target_i
        self.target_tp = target_tp
        self.delta_i = delta_i

    def run(self):
        try:
            analyzer = AudioAnalyzer()
            if self.mode == "analyze":
                loud = analyzer.measure_true_loudness(self.wav_path)
                self.analyze_finished.emit(loud)
            elif self.mode in ("normalize", "relative"):
                target_i = self.target_i
                if self.mode == "relative":
                    loud_before = analyzer.measure_true_loudness(self.wav_path)
                    if not loud_before or "input_i" not in loud_before:
                        self.normalize_finished.emit(False, None)
                        return
                    target_i = loud_before["input_i"] + (self.delta_i or 0.0)

                ok_path = analyzer.normalize_file_loudness(
                    self.wav_path,
                    target_i=target_i,
                    target_tp=self.target_tp,
                )
                if not ok_path:
                    self.normalize_finished.emit(False, None)
                    return
                loud = analyzer.measure_true_loudness(self.wav_path)
                self.normalize_finished.emit(True, loud)
            else:
                self.error.emit(f"Unknown loudness worker mode: {self.mode}")
        except Exception as e:
            logging.exception("LoudnessWorker failed")
            self.error.emit(str(e))
