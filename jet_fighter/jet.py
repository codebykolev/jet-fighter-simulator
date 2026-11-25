"""The player's jet fighter: physics, controls, drawing."""

import math
from dataclasses import dataclass

import pygame

from . import config as C


@dataclass
class Jet:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    pitch: float = 0.0          # nose angle, rad (positive = nose up)
    roll: float = 0.0           # cosmetic bank, rad
    throttle: float = 0.0       # 0..1
    afterburner: bool = False
    airborne: bool = False
    _takeoff_grace: float = 0.0   # seconds of gear-up grace after takeoff
    fuel: float = C.FUEL_MAX
    alive: bool = True
    landed: bool = False

    # --- controls ---
    def apply_input(self, keys, dt: float, on_ground: bool, terrain=None) -> None:
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        faster = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        slower = keys[pygame.K_LEFT] or keys[pygame.K_a]
        self.afterburner = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and self.fuel > 0

        if on_ground:
            # taxi / takeoff roll
            target_throttle = 1.0 if faster else (0.25 if slower else self.throttle)
            self.throttle += (target_throttle - self.throttle) * min(1.0, dt * 4)
            if up:
                self.pitch = min(C.MAX_PITCH, self.pitch + C.PITCH_SPEED * dt)
            elif down:
                self.pitch = max(-C.MAX_PITCH * 0.5, self.pitch - C.PITCH_SPEED * dt)
        else:
            self.throttle = 1.0 if faster else (0.0 if slower else self.throttle)
            if up:
                self.pitch = min(C.MAX_PITCH, self.pitch + C.PITCH_SPEED * dt)
            elif down:
                self.pitch = max(-C.MAX_PITCH, self.pitch - C.PITCH_SPEED * dt)
            else:
                # ease pitch back towards the flight path (auto-trim), so
                # releasing the stick settles the jet into stable flight
                direction = math.atan2(self.vy, self.vx) if self.vx > 1 else self.pitch
                self.pitch += (direction - self.pitch) * min(1.0, dt * 2.0)

        # cosmetic roll follows pitch input
        target_roll = (C.MAX_ROLL if up else (-C.MAX_ROLL if down else 0.0)) * 0.6
        self.roll += (target_roll - self.roll) * min(1.0, dt * 6)

        # ground proximity system: automatically ease the nose up when
        # skimming the terrain so a low pass does not end in CFIT
        if terrain is not None and self.airborne:
            clearance = terrain.height_at(self.x) - self.y
            if 0 < clearance < 70 and self.vy > 0:
                self.pitch = min(C.MAX_PITCH, self.pitch + C.PITCH_SPEED * 1.5 * dt)

    # --- physics ---
    def update(self, dt: float, terrain: "Terrain") -> str | None:
        """Advance physics. Returns 'crash', 'takeoff', 'land' or None."""
        if not self.alive:
            return None

        speed = math.hypot(self.vx, self.vy)
        thrust = C.THRUST * self.throttle
        if self.afterburner:
            thrust += C.AFTERBURNER_THRUST

        # fuel burn
        burn = C.FUEL_IDLE + (C.FUEL_FULL - C.FUEL_IDLE) * self.throttle
        if self.afterburner:
            burn += C.FUEL_AF
        self.fuel = max(0.0, self.fuel - burn * dt)
        if self.fuel <= 0.0:
            self.afterburner = False

        on_ground = (not self.airborne) and self.y >= terrain.height_at(self.x) - 2.0 and self.vy >= 0

        if on_ground:
            # rolling on the runway / ground
            self.y = terrain.height_at(self.x)
            self.vy = 0.0
            # rolling friction (constant) + linear aero drag
            ax = math.cos(self.pitch) * thrust - 40.0 - self.vx * C.DRAG * 0.6
            self.vx += ax * dt
            self.vx = max(0.0, min(self.vx, C.MAX_SPEED * 0.8))
            # takeoff: fast enough and nose held up (rotation). Lift then
            # carries the jet off the ground; this just flips the mode.
            if self.vx > 240.0 and self.pitch > math.radians(8) and not self.landed:
                self.airborne = True
                self._takeoff_grace = 1.2
                self.vy = -220.0
                self.y -= 3.0
                return "takeoff"
            if self.landed and self.vx < 5.0:
                self.vx = 0.0
            return None

        # airborne: thrust along the nose, gravity down, lift perpendicular
        # to the velocity vector, proportional to speed^2 and angle of attack
        direction = math.atan2(self.vy, self.vx) if speed > 1 else self.pitch
        ax = math.cos(self.pitch) * thrust
        ay = math.sin(self.pitch) * thrust + C.GRAVITY
        aoa = (self.pitch - direction + math.pi) % (2 * math.pi) - math.pi
        aoa = max(-math.radians(30), min(math.radians(30), aoa))
        # pitch damping: rotate the velocity vector towards the nose so the
        # angle of attack bleeds off and cannot stay parked at an extreme
        # attitude (this is what prevents a nose-high stall-spin)
        turn_rate = C.PITCH_DAMPING * math.sin(aoa) * (1.0 + speed / 500.0)
        turn = max(-0.5, min(0.5, turn_rate)) * dt
        if abs(turn) > 1e-5 and speed > 1:
            new_dir = direction + turn
            self.vx = speed * math.cos(new_dir)
            self.vy = speed * math.sin(new_dir)
            direction = new_dir
        # gravity always bends the flight path downwards; when the nose is
        # below the horizon, counteract part of it so a dive does not run away
        if direction > 0 and self.pitch < direction:
            self.vy -= C.GRAVITY * 0.35 * math.sin(direction) * dt
        lift = C.LIFT_COEFF * speed * speed * math.sin(aoa)
        # baseline lift: wings generate lift even at zero angle of attack, so
        # level flight at cruise speed neither climbs nor sinks
        baseline = C.LIFT_COEFF * speed * speed * math.sin(C.BASELINE_AOA)
        baseline = min(baseline, C.GRAVITY * 1.2)
        # extra 'flare' lift at very low speed so a nose-up attitude can
        # still rotate the flight path just after takeoff
        flare = (1.0 - min(1.0, speed / 350.0)) * C.GRAVITY * 0.55 * max(0.0, math.sin(aoa))
        lift += baseline + flare
        # blend lift direction: perpendicular to velocity when fast, straight
        # up relative to the nose when slow, so the jet can climb and turn
        # even at low speed without falling like a rock
        blend = min(1.0, speed / 350.0)
        lift_perp_x = math.sin(direction) * lift
        lift_perp_y = -math.cos(direction) * lift
        lift_up_x = math.sin(self.pitch) * lift
        lift_up_y = -math.cos(self.pitch) * lift
        ax += lift_perp_x * blend + lift_up_x * (1.0 - blend)
        ay += lift_perp_y * blend + lift_up_y * (1.0 - blend)
        # drag opposes motion
        ax -= self.vx * C.DRAG * 0.6
        ay -= self.vy * C.DRAG * 0.6

        self.vx += ax * dt
        self.vy += ay * dt
        speed = math.hypot(self.vx, self.vy)
        max_speed = C.MAX_SPEED * (1.6 if self.afterburner else 1.0)
        if speed > max_speed:
            scale = max_speed / speed
            self.vx *= scale
            self.vy *= scale
        # never stall to a hover: keep a minimum forward speed so the jet
        # always has airflow over the wings
        if self.vx < C.MIN_SPEED:
            self.vx = C.MIN_SPEED
            speed = math.hypot(self.vx, self.vy)

        self.x += self.vx * dt
        self.y += self.vy * dt

        ground = terrain.height_at(self.x)
        if self.y >= ground:
            self.y = ground
            # brief grace period after takeoff: the gear is still coming up,
            # so a re-touch right after rotating is not a landing or crash
            if self._takeoff_grace > 0.0:
                self._takeoff_grace -= dt
                self.vy = min(self.vy, -40.0)
                return None
            impact = abs(self.vy)
            angle = abs(self.pitch)
            steep = abs(self.vy) > abs(self.vx) * 0.35  # descending steeper than ~20 deg
            if impact > C.CRASH_SPEED or steep or angle > math.radians(25) or self.vx < 120:
                self.alive = False
                self.airborne = False
                return "crash"
            # survivable touchdown
            self.vy = 0.0
            self.airborne = False
            self.landed = True
            return "land"

        # world bounds
        if self.x < 40:
            self.x = 40
            self.vx = abs(self.vx)
        if self.x > C.WORLD_LENGTH - 40:
            self.x = C.WORLD_LENGTH - 40
            self.vx = -abs(self.vx)
        if self.y < 20:
            self.y = 20
            self.vy = max(0.0, self.vy)
        return None

    def altitude(self, terrain) -> float:
        """Height above ground in px (positive = airborne)."""
        return terrain.height_at(self.x) - self.y

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    # --- drawing ---
    def draw(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        sx = self.x - camera_x
        sy = self.y - camera_y
        # jet polygon pointing along +x, rotated by pitch
        body = [
            (34, 0),      # nose
            (18, -7),
            (-6, -9),
            (-26, -5),    # tail
            (-20, 0),
            (-26, 5),
            (-6, 9),
            (18, 7),
        ]
        wing = [(-2, 0), (-16, -26), (-24, -24), (-10, -2)]
        wing_m = [(-2, 0), (-16, 26), (-24, 24), (-10, 2)]
        tail = [(-24, 0), (-34, -12), (-38, -11), (-28, -2)]
        tail_m = [(-24, 0), (-34, 12), (-38, 11), (-28, 2)]
        fin = [(-6, -2), (-18, -16), (-22, -14), (-10, -3)]

        def rot(px, py):
            c, s = math.cos(self.pitch), math.sin(self.pitch)
            return (sx + px * c - py * s, sy + px * s + py * c)

        def poly(points, color):
            pygame.draw.polygon(surface, color, [rot(px, py) for px, py in points])

        # afterburner flame
        if self.afterburner and self.fuel > 0:
            flicker = 1.0 + 0.25 * math.sin(pygame.time.get_ticks() * 0.05)
            flame_len = 26 * flicker + 14
            pygame.draw.polygon(surface, C.FLAME, [
                rot(-26, -5), rot(-26 - flame_len, 0), rot(-26, 5)])
            pygame.draw.polygon(surface, C.FLAME_CORE, [
                rot(-26, -3), rot(-26 - flame_len * 0.6, 0), rot(-26, 3)])
        elif self.throttle > 0.1:
            pygame.draw.polygon(surface, C.FLAME, [
                rot(-26, -4), rot(-38, 0), rot(-26, 4)])

        poly(wing, C.JET_DARK)
        poly(wing_m, C.JET_DARK)
        poly(tail, C.JET_DARK)
        poly(tail_m, C.JET_DARK)
        poly(fin, C.JET_DARK)
        poly(body, C.JET_BODY)
        # cockpit
        pygame.draw.polygon(surface, (40, 70, 110), [
            rot(8, -3), rot(20, 0), rot(8, 3)])
        # fuselage stripe
        pygame.draw.line(surface, C.JET_DARK, rot(-24, 0), rot(30, 0), 2)
