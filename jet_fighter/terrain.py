"""Procedural mountain terrain.

The terrain is stored as a list of (x, height) samples. `height_at(x)`
interpolates between samples, which is what the jet, radars and goal
beacon all use for collision and placement.
"""

import math
import random
from dataclasses import dataclass

from . import config as C


@dataclass
class Terrain:
    xs: list
    heights: list

    def height_at(self, x: float) -> float:
        """Terrain surface height (y) at world x, clamped to the world ends."""
        xs = self.xs
        if x <= xs[0]:
            return self.heights[0]
        if x >= xs[-1]:
            return self.heights[-1]
        lo = _find_index(xs, x)
        x0, x1 = xs[lo], xs[lo + 1]
        t = (x - x0) / (x1 - x0)
        return self.heights[lo] * (1.0 - t) + self.heights[lo + 1] * t


def _hash01(i: int) -> float:
    """Deterministic pseudo-random value in [0, 1) for integer i."""
    s = math.sin(i * 12.9898 + 78.233) * 43758.5453
    return s - math.floor(s)


def _value_noise(x: float, freq: float) -> float:
    """Smooth value noise in [-1, 1]."""
    n = x * freq
    i = int(math.floor(n))
    f = n - i
    f = f * f * (3.0 - 2.0 * f)  # smoothstep
    a = _hash01(i)
    b = _hash01(i + 1)
    return (a * (1.0 - f) + b * f) * 2.0 - 1.0


def generate_terrain(seed: int | None = None) -> Terrain:
    """Generate a mountain ridge profile.

    Heights are y-coordinates (larger = lower on screen). The profile
    starts and ends near the bottom so the player can take off and land.
    A "valley corridor" is carved around the middle so the mission is
    flyable while still requiring the player to hug the terrain.
    """
    rng = random.Random(seed)
    xs = []
    heights = []
    x = -C.TERRAIN_SEGMENT * 4
    base = C.SCREEN_H + 180.0
    while x <= C.WORLD_LENGTH + C.TERRAIN_SEGMENT * 4:
        # layered ridges: big slow swells + sharper peaks + fine detail
        swell = _value_noise(x, 1.0 / 1400.0)
        peak = _value_noise(x + 5000.0, 1.0 / 320.0)
        detail = _value_noise(x + 9000.0, 1.0 / 90.0)
        h = base - (swell * 150.0 + peak * 110.0 + detail * 35.0)

        # gentle valley corridor: push the surface down (larger y) near mid
        # so there is a low, radar-shadowed path through the mountains
        corridor = 1.0 - abs(x - C.WORLD_LENGTH * 0.45) / (C.WORLD_LENGTH * 0.55)
        corridor = max(0.0, corridor)
        h += corridor * corridor * 260.0

        # takeoff / landing flats at both ends: flat = 1 at the very ends,
        # ramping down to 0 over the first/last stretch of the world
        end_flat = max(0.0,
                       min(1.0, (1500.0 - x) / 1500.0),
                       min(1.0, (x - (C.WORLD_LENGTH - 1200.0)) / 1200.0))
        h = h * (1.0 - end_flat) + (C.SCREEN_H + 60.0) * end_flat

        xs.append(x)
        heights.append(h)
        x += C.TERRAIN_SEGMENT * rng.uniform(0.7, 1.3)
    return Terrain(xs, heights)


def terrain_points_in_range(terrain: Terrain, x0: float, x1: float):
    """Yield (x, y) samples covering [x0, x1] for drawing."""
    xs = terrain.xs
    start = max(0, _find_index(xs, x0) - 1)
    for i in range(start, len(xs)):
        if xs[i] > x1:
            break
        yield xs[i], terrain.heights[i]


def _find_index(xs, x):
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    return lo
