import pytest
from PySide6.QtWidgets import QApplication
import sys

# Ensure QApplication instance for PySide6 GUI tests
app = QApplication.instance() or QApplication(sys.argv)

from video_silence_cutter.gui.trimming_slider import TrimmingSlider

def test_trimming_slider_initial_state():
    slider = TrimmingSlider()
    assert slider.start_sec == 0.0
    assert slider.end_sec == 0.0
    assert slider.duration_sec == 0.0
    assert slider.zoom_factor == 1.0
    assert slider.audio_intervals == []

def test_trimming_slider_set_trim_range():
    slider = TrimmingSlider()
    slider.set_trim_range(10.0, 50.0, 100.0)
    assert slider.start_sec == 10.0
    assert slider.end_sec == 50.0
    assert slider.duration_sec == 100.0

def test_trimming_slider_set_zoom_factor():
    slider = TrimmingSlider()
    slider.set_zoom_factor(2.5)
    assert slider.zoom_factor == 2.5

    # Out of bounds clamping check
    slider.set_zoom_factor(15.0)
    assert slider.zoom_factor == 10.0

    slider.set_zoom_factor(0.5)
    assert slider.zoom_factor == 1.0

def test_trimming_slider_set_audio_intervals():
    slider = TrimmingSlider()
    intervals = [(5.0, 12.0), (20.0, 35.0)]
    slider.set_audio_presence_intervals(intervals)
    assert slider.audio_intervals == intervals

def test_trimming_slider_set_cut_intervals():
    slider = TrimmingSlider()
    assert slider.cut_intervals == []

    slider.set_cut_intervals([(5.0, 10.0), (20.0, 25.0)])
    assert slider.cut_intervals == [(5.0, 10.0), (20.0, 25.0)]

    slider.set_cut_intervals([])
    assert slider.cut_intervals == []
