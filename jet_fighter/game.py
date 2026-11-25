"""Core game: world setup, update loop, rendering, and state machine."""

import math
import random

import pygame

from . import config as C
from .audio import Audio
from .hud import HUD
from .jet import Jet
from .radar import Missile, Radar, place_radars
from .terrain import Terrain, generate_terrain, terrain_points_in_range

# game states
MENU = "menu"
PLAYING = "playing"
WIN = "win"
GAMEOVER = "gameover"


class Game:
    def __init__(self, seed: int | None = None, with_audio: bool = True):
        self.seed = seed
        self.audio = Audio(enabled=with_audio)
        self.hud = HUD()
        self.state = MENU
        self.elapsed = 0.0
        self.score = 0.0
        self._menu_sel = 0
        self._clouds = []
        self._init_world()

    # ------------------------------------------------------------------ world
    def _init_world(self) -> None:
        rng = random.Random(self.seed)
        self.terrain: Terrain = generate_terrain(self.seed)
        self.radars: list[Radar] = place_radars(self.terrain, self.seed)
        self.missiles: list[Missile] = []

        start_x = 500.0
        ground = self.terrain.height_at(start_x)
        self.jet = Jet(x=start_x, y=ground - 8.0, vx=0.0)

        self.goal_x = C.GOAL_X
        self.goal_y = self.terrain.height_at(self.goal_x) - 140.0

        # decorative clouds (world-space x, parallax layer, y, size)
        self._clouds = [
            (rng.uniform(0, C.WORLD_LENGTH), rng.uniform(0.2, 0.8),
             rng.uniform(60, 380), rng.uniform(40, 110))
            for _ in range(26)
        ]
        self.camera_x = 0.0
        self.camera_y = 0.0

    def start_mission(self) -> None:
        self._init_world()
        self.state = PLAYING
        self.elapsed = 0.0
        self.score = 0.0
        self.audio.stop_engine()

    # ------------------------------------------------------------------ input
    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.state = "quit"
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            if self.state == PLAYING:
                self.state = MENU
                self.audio.stop_engine()
            elif self.state in (WIN, GAMEOVER):
                self.state = MENU
            return
        if self.state == MENU:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_mission()
            elif event.key == pygame.K_r:
                self.seed = random.randint(0, 10_000)
        elif self.state in (WIN, GAMEOVER):
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_mission()
            elif event.key == pygame.K_m:
                self.state = MENU

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        if self.state != PLAYING:
            return
        self.elapsed += dt
        keys = pygame.key.get_pressed()

        on_ground = not self.jet.airborne
        self.jet.apply_input(keys, dt, on_ground, self.terrain)
        event = self.jet.update(dt, self.terrain)
        if event == "crash":
            self.audio.play("explosion", 0.9)
            self.audio.stop_engine()
            self.state = GAMEOVER
            self.score = self._compute_score(high_score=False)
            return

        # radars + missiles
        for radar in self.radars:
            radar.update(dt, self.jet, self.terrain, self.missiles)
            if radar.detected:
                self.hud.trigger_detected()
        for m in self.missiles[:]:
            if not m.warned and math.hypot(m.x - self.jet.x, m.y - self.jet.y) < C.MISSILE_SPEED * C.MISSILE_WARN_TIME:
                m.warned = True
                self.hud.trigger_missile_warning(m)
                self.audio.play("ping", 0.5)
            result = m.update(dt, self.jet, self.terrain)
            if result == "hit":
                self.audio.play("explosion", 0.9)
                self.audio.stop_engine()
                self.jet.alive = False
                self.state = GAMEOVER
                self.score = self._compute_score(high_score=False)
                return
            if result == "expired":
                self.missiles.remove(m)
        # cull warned flags for missiles that flew away
        self.hud._warned_missiles.intersection_update({id(m) for m in self.missiles})

        # engine sound bed follows throttle
        self.audio.engine_loop(self.jet.throttle, self.jet.afterburner and self.jet.fuel > 0)

        # goal check: fly past the beacon, reasonably low and alive
        if self.jet.alive and self.jet.x >= self.goal_x:
            self.state = WIN
            self.audio.stop_engine()
            self.audio.play("win", 0.8)
            self.score = self._compute_score(high_score=True)

        # continuous low-altitude score: reward nap-of-the-earth flying
        alt = self.jet.altitude(self.terrain)
        if self.jet.alive and not on_ground:
            self.score += dt * (30.0 + max(0.0, (120.0 - min(alt, 120.0))) * 0.8)

        self.hud.update(dt)
        self._update_camera(dt)

    def _compute_score(self, high_score: bool) -> float:
        base = self.score
        base += max(0.0, self.jet.x) / 10.0          # distance flown
        if high_score:
            base += 5000.0 - min(5000.0, self.elapsed * 20.0)  # time bonus
        return base

    def _update_camera(self, dt: float) -> None:
        # lead the jet, keep it around 35% from the left edge
        target_x = self.jet.x - C.SCREEN_W * C.CAMERA_LEAD
        ground = self.terrain.height_at(self.jet.x)
        # follow the jet vertically but keep the terrain visible: the camera
        # centers on a point between the jet and the ground below it
        focus_y = (self.jet.y + ground) / 2.0
        target_y = focus_y - C.SCREEN_H * 0.45
        target_y = max(-260.0, target_y)
        k = min(1.0, dt * 4.0)
        self.camera_x += (target_x - self.camera_x) * k
        self.camera_y += (target_y - self.camera_y) * k
        self.camera_x = max(0.0, min(self.camera_x, C.WORLD_LENGTH - C.SCREEN_W))

    # ------------------------------------------------------------------ render
    def draw(self, surface: pygame.Surface) -> None:
        if self.state == MENU:
            self._draw_menu(surface)
            return
        self._draw_background(surface)
        self._draw_terrain(surface)
        self._draw_goal(surface)
        self._draw_radars(surface)
        self._draw_missiles(surface)
        self.jet.draw(surface, self.camera_x, self.camera_y)
        self.hud.draw(surface, self.jet, self.radars, self.missiles,
                      self.terrain, self.elapsed, self.state == WIN)
        if self.state == WIN:
            self._draw_end_screen(surface, "MISSION COMPLETE",
                                  f"Score: {int(self.score)}", C.GOAL)
        elif self.state == GAMEOVER:
            self._draw_end_screen(surface, "SHOT DOWN / CRASHED",
                                  f"Score: {int(self.score)}", (255, 90, 90))

    def _draw_background(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        # vertical sky gradient
        for y in range(0, h, 4):
            t = y / h
            col = tuple(int(C.SKY_TOP[i] + (C.SKY_BOTTOM[i] - C.SKY_TOP[i]) * t)
                        for i in range(3))
            pygame.draw.rect(surface, col, (0, y, w, 4))
        # sun
        pygame.draw.circle(surface, C.SUN, (int(w * 0.78), int(h * 0.18)), 46)
        pygame.draw.circle(surface, tuple(min(255, c + 40) for c in C.SUN),
                           (int(w * 0.78), int(h * 0.18)), 60, 3)
        # clouds with parallax
        for (cx, layer, cy, size) in self._clouds:
            sx = (cx - self.camera_x * layer) % (C.WORLD_LENGTH + 400) - 200
            self._draw_cloud(surface, int(sx), int(cy - self.camera_y * 0.3), int(size))

    def _draw_cloud(self, surface, x, y, size) -> None:
        col = (230, 238, 246)
        for dx, dy, r in ((-size * 0.5, 4, size * 0.45), (0, -6, size * 0.6),
                          (size * 0.5, 4, size * 0.45)):
            pygame.draw.circle(surface, col, (int(x + dx), int(y + dy)), int(r))
            pygame.draw.circle(surface, col, (int(x + dx), int(y + dy + r * 0.5)),
                               int(r))

    def _draw_terrain(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        x0 = self.camera_x - 100
        x1 = self.camera_x + w + 100

        # far ridge (parallax, lighter): offset copy of terrain, drawn higher
        far_pts = [(x - self.camera_x * 0.85,
                    y * 0.72 - self.camera_y * 0.5 - 60)
                   for x, y in terrain_points_in_range(self.terrain, x0 * 1.18, x1 * 1.18)]
        if len(far_pts) > 2:
            pygame.draw.polygon(surface, C.MOUNTAIN_FAR,
                                [(0, h)] + far_pts + [(w, h)])

        # near ridge
        near_pts = [(x - self.camera_x, y - self.camera_y)
                    for x, y in terrain_points_in_range(self.terrain, x0, x1)]
        if len(near_pts) > 2:
            pygame.draw.polygon(surface, C.MOUNTAIN_NEAR,
                                [(0, h)] + near_pts + [(w, h)])
            # snow caps where the ridge is high
            snow = []
            for (x, y) in near_pts:
                world_y = y + self.camera_y
                if world_y < C.SCREEN_H - 60:
                    snow.append((x, y))
            if len(snow) > 1:
                for (x, y) in snow:
                    pygame.draw.polygon(surface, C.MOUNTAIN_SNOW,
                                        [(x - 7, y), (x, y - 9), (x + 7, y),
                                         (x + 5, y + 4), (x, y + 2), (x - 5, y + 4)])
            # grass strip along the top edge
            pygame.draw.lines(surface, C.GRASS, False, near_pts, 3)

    def _draw_goal(self, surface: pygame.Surface) -> None:
        gx = self.goal_x - self.camera_x
        gy = self.goal_y - self.camera_y
        if -100 < gx < C.SCREEN_W + 100:
            # beacon mast
            base_y = self.terrain.height_at(self.goal_x) - self.camera_y
            pygame.draw.line(surface, (90, 110, 90), (gx, base_y), (gx, gy), 4)
            # pulsing rings
            pulse = (pygame.time.get_ticks() / 1000.0) % 1.0
            for i in range(3):
                r = int(18 + (pulse + i / 3.0) % 1.0 * 46)
                alpha = int(200 * (1.0 - ((pulse + i / 3.0) % 1.0)))
                s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*C.GOAL, alpha), (r + 2, r + 2), r, 2)
                surface.blit(s, (gx - r - 2, gy - r - 2))
            pygame.draw.circle(surface, C.GOAL, (int(gx), int(gy)), 10)
            pygame.draw.circle(surface, (220, 255, 225), (int(gx), int(gy)), 5)

    def _draw_radars(self, surface: pygame.Surface) -> None:
        for radar in self.radars:
            rx = radar.x - self.camera_x
            if not (-200 < rx < C.SCREEN_W + 200):
                continue
            ry = radar.y - self.camera_y
            top_y = ry - radar.tower_h
            # tower
            pygame.draw.line(surface, (70, 70, 80), (rx, ry), (rx, top_y), 5)
            pygame.draw.line(surface, (50, 50, 60), (rx - 12, ry), (rx + 12, ry), 4)
            # dish
            pygame.draw.circle(surface, C.RADAR, (int(rx), int(top_y)), 7)
            # sweep beam (wedge, clipped to a sector polygon)
            bx, by = radar.beam_end
            bx -= self.camera_x
            by -= self.camera_y
            beam_col = (*C.RADAR_BEAM, 60) if radar.detected else (*C.RADAR_BEAM, 35)
            s = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(s, beam_col, (rx, top_y), (bx, by), 3)
            # faint wedge
            half = C.RADAR_SWEEP_WIDTH
            for a in (radar.sweep - half, radar.sweep, radar.sweep + half):
                ex = rx + math.cos(a) * C.RADAR_RANGE
                ey = top_y + math.sin(a) * C.RADAR_RANGE
                pygame.draw.line(s, beam_col, (rx, top_y), (ex, ey), 1)
            surface.blit(s, (0, 0))
            # detection indicator
            if radar.detected:
                pygame.draw.circle(surface, (255, 60, 60), (int(rx), int(top_y)), 11, 2)

    def _draw_missiles(self, surface: pygame.Surface) -> None:
        for m in self.missiles:
            mx = m.x - self.camera_x
            my = m.y - self.camera_y
            if -50 < mx < C.SCREEN_W + 50 and -50 < my < C.SCREEN_H + 50:
                # contrail
                tail_len = 30
                tx = mx - math.cos(m.angle) * tail_len
                ty = my - math.sin(m.angle) * tail_len
                pygame.draw.line(surface, (200, 200, 210), (tx, ty), (mx, my), 2)
                # missile body
                c, s = math.cos(m.angle), math.sin(m.angle)
                pts = [(mx + 10 * c, my + 10 * s),
                       (mx - 8 * c + 4 * s, my - 8 * s - 4 * c),
                       (mx - 8 * c - 4 * s, my - 8 * s + 4 * c)]
                pygame.draw.polygon(surface, (240, 240, 245), pts)
                # flame
                pygame.draw.polygon(surface, C.FLAME, [
                    (mx - 8 * c + 3 * s, my - 8 * s - 3 * c),
                    (mx - 20 * c, my - 20 * s),
                    (mx - 8 * c - 3 * s, my - 8 * s + 3 * c)])

    # ------------------------------------------------------------------ menu
    def _draw_menu(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        for y in range(0, h, 4):
            t = y / h
            col = tuple(int(C.SKY_TOP[i] + (C.SKY_BOTTOM[i] - C.SKY_TOP[i]) * t)
                        for i in range(3))
            pygame.draw.rect(surface, col, (0, y, w, 4))
        # title
        title_font = pygame.font.Font(C.FONT_NAME, 64)
        sub_font = pygame.font.Font(C.FONT_NAME, 24)
        title = title_font.render("JET FIGHTER SIMULATOR", True, C.TEXT)
        surface.blit(title, (w // 2 - title.get_width() // 2, 110))
        sub = sub_font.render("Fly low. Avoid the radar. Reach the goal.",
                              True, C.HUD)
        surface.blit(sub, (w // 2 - sub.get_width() // 2, 190))

        lines = [
            "CONTROLS",
            "  UP / W        pull up (nose up)",
            "  DOWN / S      push down (nose down)",
            "  RIGHT / D     full throttle",
            "  LEFT / A      idle throttle",
            "  SHIFT         afterburner (drains fuel)",
            "  ESC           menu",
            "",
            "TIPS",
            "  * Radar beams are blocked by mountains: hug the terrain.",
            "  * Stay below the ridge line and the sweep cannot see you.",
            "  * Watch the radar scope: red blips are hunting you.",
            "  * Fuel is limited: use afterburner sparingly.",
            "  * Take off from the flat at the left: full throttle, then pull up.",
        ]
        y = 250
        for line in lines:
            col = C.HUD if line in ("CONTROLS", "TIPS") else C.TEXT
            txt = sub_font.render(line, True, col)
            surface.blit(txt, (w // 2 - 320, y))
            y += 30

        seed_txt = sub_font.render(f"Mission seed: {self.seed}  (R = new random mission)",
                                   True, C.HUD_DIM)
        surface.blit(seed_txt, (w // 2 - seed_txt.get_width() // 2, h - 90))
        start = sub_font.render("Press ENTER to start", True, C.GOAL)
        blink = int(pygame.time.get_ticks() / 500) % 2 == 0
        if blink:
            surface.blit(start, (w // 2 - start.get_width() // 2, h - 55))

    def _draw_end_screen(self, surface, title, subtitle, color) -> None:
        w, h = surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 160))
        surface.blit(overlay, (0, 0))
        f1 = pygame.font.Font(C.FONT_NAME, 56)
        f2 = pygame.font.Font(C.FONT_NAME, 28)
        t1 = f1.render(title, True, color)
        t2 = f2.render(subtitle, True, C.TEXT)
        t3 = f2.render("ENTER = fly again   M = menu   ESC = quit", True, C.HUD_DIM)
        surface.blit(t1, (w // 2 - t1.get_width() // 2, h // 2 - 80))
        surface.blit(t2, (w // 2 - t2.get_width() // 2, h // 2 - 20))
        surface.blit(t3, (w // 2 - t3.get_width() // 2, h // 2 + 30))
