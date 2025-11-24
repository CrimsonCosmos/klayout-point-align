"""
Benchmark script to test water caustics performance.
"""
import time
import numpy as np

# Import the widget (just to test the rendering functions)
from water_caustics_widget import WaterCausticsWidget

print("Testing NumPy-vectorized water caustics performance...")
print("=" * 60)

# Create a dummy widget (no GUI needed for benchmark)
class DummyWidget:
    def __init__(self):
        self.start_time = time.time()
        self.render_width = 180
        self.render_height = 101
        self.scale = 2.2
        self.distortion_strength = 1.8
        self.base_brightness = 0.05
        self.intensity_scale = 4.5
        self.threshold = 0.45

    @staticmethod
    def _hash2(x, y):
        """2D hash for noise - VECTORIZED."""
        n = x * 127.1 + y * 311.7
        return np.modf(np.sin(n) * 43758.5453123)[0]

    def _value_noise(self, x, y):
        """Value noise function - VECTORIZED."""
        ix = np.floor(x).astype(int)
        iy = np.floor(y).astype(int)
        fx = x - ix
        fy = y - iy

        a = self._hash2(ix, iy)
        b = self._hash2(ix + 1, iy)
        c = self._hash2(ix, iy + 1)
        d = self._hash2(ix + 1, iy + 1)

        u = fx * fx * (3 - 2 * fx)
        v = fy * fy * (3 - 2 * fy)

        ab = a + (b - a) * u
        cd = c + (d - c) * u
        return ab + (cd - ab) * v

    def _fbm(self, x, y, octaves: int = 4):
        """Fractal Brownian Motion - VECTORIZED."""
        value = np.zeros_like(x)
        amplitude = 0.5
        frequency = 1.0

        for _ in range(octaves):
            value += amplitude * self._value_noise(x * frequency, y * frequency)
            frequency *= 2.0
            amplitude *= 0.5

        return value

    def render_frame(self):
        """Render a single frame."""
        current_time = (time.time() - self.start_time) * 0.00025

        # Create coordinate grids
        px = np.arange(self.render_width, dtype=np.float32)
        py = np.arange(self.render_height, dtype=np.float32)
        px_grid, py_grid = np.meshgrid(px, py)

        # Normalize coords
        nx = (px_grid / self.render_width) * 2 - 1
        ny = (py_grid / self.render_height) * 2 - 1

        # Base coordinates
        u = nx * self.scale
        v = ny * self.scale

        # Flow/turbulence distortion
        warp1 = self._fbm(u + current_time * 0.7, v - current_time * 0.4 + 10.0)
        warp2 = self._fbm(u - current_time * 0.5 + 20.0, v + current_time * 0.6)

        u += (warp1 - 0.5) * self.distortion_strength
        v += (warp2 - 0.5) * self.distortion_strength

        # Main noise field
        n = self._fbm(u + current_time * 1.1, v - current_time * 1.3)

        # Gradient magnitude
        eps = 0.03
        nx1 = self._fbm(u + eps, v)
        nx2 = self._fbm(u - eps, v)
        ny1 = self._fbm(u, v + eps)
        ny2 = self._fbm(u, v - eps)
        gx = nx1 - nx2
        gy = ny1 - ny2
        grad_mag = np.sqrt(gx * gx + gy * gy)

        # Intensity
        intensity = n + grad_mag * 2.0
        intensity = np.maximum(0, intensity - self.threshold) * self.intensity_scale
        intensity = intensity ** 2.2

        # Color
        water_r, water_g, water_b = 0.7, 0.9, 0.8
        highlight_r, highlight_g, highlight_b = 1.4, 1.25, 1.0

        r = np.clip((water_r * self.base_brightness + highlight_r * intensity) * 255, 0, 255).astype(np.uint8)
        g = np.clip((water_g * self.base_brightness + highlight_g * intensity) * 255, 0, 255).astype(np.uint8)
        b = np.clip((water_b * self.base_brightness + highlight_b * intensity) * 255, 0, 255).astype(np.uint8)

        return r, g, b

widget = DummyWidget()

# Warm-up run
print("Warming up...")
widget.render_frame()

# Benchmark
print("\nRunning benchmark (30 frames)...")
num_frames = 30
start = time.time()

for i in range(num_frames):
    widget.render_frame()
    if (i + 1) % 10 == 0:
        print(f"  Rendered {i + 1} frames...")

end = time.time()
elapsed = end - start

print("\n" + "=" * 60)
print(f"Results:")
print(f"  Frames rendered: {num_frames}")
print(f"  Total time: {elapsed:.3f} seconds")
print(f"  Time per frame: {elapsed/num_frames*1000:.1f} ms")
print(f"  Effective FPS: {num_frames/elapsed:.1f}")
print(f"  Resolution: {widget.render_width}x{widget.render_height}")
print(f"  Pixels per frame: {widget.render_width * widget.render_height:,}")
print("=" * 60)

if num_frames/elapsed >= 25:
    print("✅ EXCELLENT: Smooth 30 FPS animation achievable!")
elif num_frames/elapsed >= 15:
    print("✓ GOOD: Should run at 15-30 FPS")
elif num_frames/elapsed >= 10:
    print("⚠ ACCEPTABLE: Will run at 10-15 FPS (slightly choppy)")
else:
    print("❌ SLOW: <10 FPS (too slow for smooth animation)")
