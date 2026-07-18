import os
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
)


def _fmt(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


class _JumpSlider(QSlider):
    """Slider that seeks to the clicked position instead of paging."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            ratio = event.position().x() / max(self.width(), 1)
            val = int(self.minimum() + (self.maximum() - self.minimum()) * ratio)
            self.setValue(val)
        super().mousePressEvent(event)


class PlayerBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self._seeking = False

        self._audio = QAudioOutput()
        self._audio.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio)

        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)

        self._build_ui()
        self._set_controls_enabled(False)

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(4)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(24, 20)
        self._play_btn.clicked.connect(self._toggle_play)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setFixedSize(24, 20)
        self._stop_btn.clicked.connect(self._player.stop)

        self._name_lbl = QLabel("—")
        self._name_lbl.setStyleSheet("color: palette(dark);")

        self._slider = _JumpSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setFixedWidth(90)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_lbl.setStyleSheet("color: palette(dark);")

        lay.addWidget(self._play_btn)
        lay.addWidget(self._stop_btn)
        lay.addWidget(self._name_lbl)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._time_lbl)

    def load(self, path: str):
        self._player.setSource(QUrl.fromLocalFile(path))
        self._name_lbl.setText(os.path.basename(path))
        self._set_controls_enabled(True)
        self._player.play()

    def _set_controls_enabled(self, enabled: bool):
        self._play_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)
        self._slider.setEnabled(enabled)

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_slider_pressed(self):
        self._seeking = True

    def _on_slider_released(self):
        self._player.setPosition(self._slider.value())
        self._seeking = False

    def _on_position(self, pos: int):
        if not self._seeking:
            self._slider.setValue(pos)
        self._time_lbl.setText(f"{_fmt(pos)} / {_fmt(self._player.duration())}")

    def _on_duration(self, dur: int):
        self._slider.setRange(0, dur)

    def _on_state(self, state):
        self._play_btn.setText(
            "⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶"
        )
