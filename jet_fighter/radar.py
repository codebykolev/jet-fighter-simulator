"""Radar stations: rotating sweeps, terrain-masked detection, missiles."""

import math
from dataclasses import dataclass, field

from . import config as C


@dataclass
class Missile:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    age: float = 0.0
    warned: bool = False

    def update(self, dt: float, target, terrain: "Terrain") -> str | None:
        """Chase the target. Returns 'hit', 'expired' or None."""
        self.age += dt
        if self.age > C.MISSILE_LIFETIME:
            return "expired"

        # proportional pursuit towards the target
        if target is not None:
            dx = target.x - self.x
            dy = target.y - self.y
            dist = math.hypot(dx, dy) or 1.0
            desired_vx = dx / dist * C.MISSILE_SPEED
            desired_vy = dy / dist * C.MISSILE_SPEED
            # limit turn rate
            max_delta = C.MISSILE_TURN_RATE * dt * C.MISSILE_SPEED
            delta_vx = max(-max_delta, min(max_delta, desired_vx - self.vx))
            delta_vy = max(-max_delta, min(max_delta, desired_vy - self.vy))
            self.vx += delta_vx
            self.vy += delta_vy
            speed = math.hypot(self.vx, self.vy)
            if speed > 0:
                scale = min(1.0, C.MISSILE_SPEED / speed)
                self.vx *= scale
                self.vy *= scale

        self.x += self.vx * dt
        self.y += self.vy * dt

        if target is not None and math.hypot(self.x - target.x, self.y - target.y) < C.MISSILE_HIT_RADIUS:
            return "hit"
        if self.y >= terrain.height_at(self.x):
            return "expired"  # crashed into a mountain
        return None

    @property
    def angle(self) -> float:
        return math.atan2(self.vy, self.vx)


@dataclass
class Radar:
    x: float
    y: float                      # base y (on the terrain surface)
    sweep: float = 0.0            # current sweep angle (rad, 0 = +x axis)
    cooldown: float = 3.0
    detected: bool = field(default=False, compare=False)

    tower_h = 46.0

    def update(self, dt: float, jet, terrain: "Terrain", missiles: list) -> None:
        self.sweep += C.RADAR_SWEEP_SPEED * dt
        self.cooldown -= dt
        self.detected = self._sees(jet, terrain)
        if self.detected and self.cooldown <= 0.0:
            self.cooldown = C.RADAR_COOLDOWN
            missiles.append(Missile(x=self.x, y=self.y - self.tower_h,
                                   vx=C.MISSILE_SPEED * 0.3, vy=-C.MISSILE_SPEED * 0.2))

    def _sees(self, jet, terrain: "Terrain") -> bool:
        """True if the sweep beam points at the jet and terrain doesn't block it."""
        dx = jet.x - self.x
        dy = (jet.y - self.tower_h * 0.6) - (self.y - self.tower_h)
        dist = math.hypot(dx, dy)
        if dist > C.RADAR_RANGE or dist < 40.0:
            return False
        # angular distance between sweep direction and jet direction
        beam_angle = math.atan2(dy, dx)
        diff = (beam_angle - self.sweep + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) > C.RADAR_SWEEP_WIDTH:
            return False
        # terrain occlusion: march along the beam, check the ridge line.
        # The jet is hidden if the terrain rises above the line of sight,
        # with a little relief so low-flying behind a ridge counts as hidden.
        eye_y = self.y - self.tower_h
        steps = 24
        for i in range(1, steps + 1):
            t = i / steps
            px = self.x + dx * t
            py = eye_y + dy * t
            ground = terrain.height_at(px)
            # beam passes (ground height - eye height) below the surface
            occluded_height = ground - C.RADAR_ALT_RELIEF * (ground - eye_y)
            if py >= occluded_height:
                return False
        return True

    @property
    def beam_end(self):
        """Endpoint of the active sweep beam, for drawing."""
        length = C.RADAR_RANGE
        return (self.x + math.cos(self.sweep) * length,
                (self.y - self.tower_h) + math.sin(self.sweep) * length)


def place_radars(terrain: "Terrain", seed: int | None = None) -> list:
    """Scatter radars along the world on exposed ridge tops.

    A radar is only placed where the ground stays below its dish over a wide
    neighbourhood, so it always has a clear field of fire over the valley
    floor — that is what makes flying low behind ridges worthwhile.
    """
    import random
    rng = random.Random(None if seed is None else seed + 999)
    radars = []
    x = 2500.0
    attempts = 0
    while x < C.WORLD_LENGTH - 2500.0 and len(radars) < C.RADAR_COUNT and attempts < 500:
        attempts += 1
        # candidate ridge top near x
        ground = terrain.height_at(x)
        top = ground
        for probe in (-160.0, -80.0, 0.0, 80.0, 160.0):
            top = min(top, terrain.height_at(x + probe))
        # require a clear field of fire: the ground must stay below the dish
        # over a wide window around the site
        clear = True
        for probe in range(-900, 901, 100):
            if terrain.height_at(x + probe) < top - 10.0:
                clear = False
                break
        if not clear:
            # no exposed ridge here: scan forward in smaller steps to find one
            x += 150.0
            continue
        radars.append(Radar(x=x, y=top, sweep=rng.uniform(0, 2 * math.pi),
                            cooldown=rng.uniform(1.0, 4.0)))
        x += rng.uniform(C.RADAR_MIN_GAP, C.RADAR_MAX_GAP)
    return radars
