"""
Water caustics effect widget for fancy mode.
Procedural animation using noise and gradient-based highlights (matching HTML version).
OPTIMIZED: NumPy vectorization for 10-50x speedup.
"""

from __future__ import annotations
import math
import time
import numpy as np
from qt_compat import QtCore, QtGui, QtWidgets


class WaterCausticsWidget(QtWidgets.QWidget):
    """Procedural water caustics background (matches HTML version)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_time = time.time()

        # Animation settings - 30 FPS like HTML
        self.fps = 30
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)

        # Rendering resolution (VERY low for performance - will scale up)
        # HTML uses 360x202, we'll use even lower: 180x101
        self.render_width = 180
        self.render_height = 101

        # Effect parameters - ADJUSTED for more visibility
        self.scale = 2.2
        self.distortion_strength = 1.8
        self.base_brightness = 0.15  # Increased from 0.05 for brighter base
        self.intensity_scale = 6.0   # Increased from 4.5 for brighter highlights
        self.threshold = 0.35         # Lowered from 0.45 for more visible caustics

        # Make widget transparent to mouse events
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)


    def start_animation(self):
        """Start the animation timer."""
        self.start_time = time.time()  # Reset start time
        if not self.timer.isActive():
            self.timer.start(1000 // self.fps)
        self.show()
        self.update()

    def stop_animation(self):
        """Stop the animation timer."""
        self.timer.stop()

    @staticmethod
    def _hash2(x, y):
        """2D hash for noise - VECTORIZED (works on arrays)."""
        n = x * 127.1 + y * 311.7
        return np.modf(np.sin(n) * 43758.5453123)[0]  # Fractional part

    def _value_noise(self, x, y):
        """Value noise function - VECTORIZED (works on arrays)."""
        ix = np.floor(x).astype(int)
        iy = np.floor(y).astype(int)
        fx = x - ix
        fy = y - iy

        # Get hash values at grid corners
        a = self._hash2(ix, iy)
        b = self._hash2(ix + 1, iy)
        c = self._hash2(ix, iy + 1)
        d = self._hash2(ix + 1, iy + 1)

        # Hermite interpolation
        u = fx * fx * (3 - 2 * fx)
        v = fy * fy * (3 - 2 * fy)

        # Bilinear interpolation
        ab = a + (b - a) * u
        cd = c + (d - c) * u
        return ab + (cd - ab) * v

    def _fbm(self, x, y, octaves: int = 4):
        """Fractal Brownian Motion - VECTORIZED (works on arrays)."""
        value = np.zeros_like(x)
        amplitude = 0.5
        frequency = 1.0

        for _ in range(octaves):
            value += amplitude * self._value_noise(x * frequency, y * frequency)
            frequency *= 2.0
            amplitude *= 0.5

        return value

    def paintEvent(self, event):
        """Render procedural caustics - VECTORIZED with NumPy for 10-50x speedup."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

        width = self.width()
        height = self.height()

        if width == 0 or height == 0:
            return

        # Global time (convert seconds to appropriate scale)
        current_time = (time.time() - self.start_time) * 0.25

        # Create coordinate grids (vectorized - single allocation)
        px = np.arange(self.render_width, dtype=np.float32)
        py = np.arange(self.render_height, dtype=np.float32)
        px_grid, py_grid = np.meshgrid(px, py)

        # Normalize coords to [-1, 1] (vectorized)
        nx = (px_grid / self.render_width) * 2 - 1
        ny = (py_grid / self.render_height) * 2 - 1

        # Base coordinates (vectorized)
        u = nx * self.scale
        v = ny * self.scale

        # Flow/turbulence distortion (vectorized)
        warp1 = self._fbm(u + current_time * 0.7, v - current_time * 0.4 + 10.0)
        warp2 = self._fbm(u - current_time * 0.5 + 20.0, v + current_time * 0.6)

        u += (warp1 - 0.5) * self.distortion_strength
        v += (warp2 - 0.5) * self.distortion_strength

        # Main noise field (vectorized)
        n = self._fbm(u + current_time * 1.1, v - current_time * 1.3)

        # Gradient magnitude for caustic highlights (vectorized)
        eps = 0.03
        nx1 = self._fbm(u + eps, v)
        nx2 = self._fbm(u - eps, v)
        ny1 = self._fbm(u, v + eps)
        ny2 = self._fbm(u, v - eps)
        gx = nx1 - nx2
        gy = ny1 - ny2
        grad_mag = np.sqrt(gx * gx + gy * gy)

        # Combine for intensity (vectorized)
        intensity = n + grad_mag * 2.0
        intensity = np.maximum(0, intensity - self.threshold) * self.intensity_scale
        intensity = intensity ** 2.2  # Pseudo-bloom

        # Color: soft green water + warm highlights (vectorized)
        water_r, water_g, water_b = 0.7, 0.9, 0.8
        highlight_r, highlight_g, highlight_b = 1.4, 1.25, 1.0

        r = np.clip((water_r * self.base_brightness + highlight_r * intensity) * 255, 0, 255).astype(np.uint8)
        g = np.clip((water_g * self.base_brightness + highlight_g * intensity) * 255, 0, 255).astype(np.uint8)
        b = np.clip((water_b * self.base_brightness + highlight_b * intensity) * 255, 0, 255).astype(np.uint8)

        # Combine RGB channels into RGBA (Qt expects 32-bit ARGB)
        # Format: 0xAARRGGBB
        alpha = np.full_like(r, 255, dtype=np.uint8)
        rgba = (alpha.astype(np.uint32) << 24) | (r.astype(np.uint32) << 16) | (g.astype(np.uint32) << 8) | b.astype(np.uint32)

        # Create QImage from NumPy array
        image = QtGui.QImage(rgba.data, self.render_width, self.render_height,
                            self.render_width * 4, QtGui.QImage.Format.Format_ARGB32)

        # Keep reference to prevent garbage collection
        image._numpy_data = rgba

        # Scale up to widget size and draw
        scaled_image = image.scaled(
            width, height,
            QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        painter.drawImage(0, 0, scaled_image)


class FullWindowCausticsOverlay(QtWidgets.QWidget):
    """Full-window caustics background overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Create the caustics widget
        self.caustics = WaterCausticsWidget(self)

    def start_animation(self):
        """Start the caustics animation."""
        self.lower()  # Put behind everything FIRST
        self.show()  # Then show
        self.caustics.setGeometry(self.rect())
        self.caustics.show()
        self.caustics.start_animation()
        self.caustics.raise_()  # Make sure caustics widget is visible within overlay

    def stop_animation(self):
        """Stop the caustics animation."""
        self.caustics.stop_animation()
        self.hide()

    def resizeEvent(self, event):
        """Update caustics widget to fill entire overlay."""
        super().resizeEvent(event)
        self.caustics.setGeometry(self.rect())
