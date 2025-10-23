from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QColor

class MiniBarVisualizer(QWidget):
    def __init__(self, parent=None, bar_count=4, bar_color=QColor(0, 120, 212)):
        super().__init__(parent)
        self.bar_count = bar_count
        self.bar_color = bar_color
        self.anim_phase = 0
        self.setFixedSize(14, 14)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(100)

    def update_animation(self):
        self.anim_phase = (self.anim_phase + 1) % 8
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        bar_w = w // (self.bar_count * 2)
        spacing = bar_w
        for i in range(self.bar_count):
            # Animate bar height with a simple phase offset
            phase = (self.anim_phase + i * 2) % 8
            bar_h = h // 3 + int((h // 2) * abs((phase - 4) / 4))
            x = i * (bar_w + spacing)
            y = h - bar_h
            painter.setBrush(self.bar_color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(x, y, bar_w, bar_h)
