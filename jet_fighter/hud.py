"""Heads-up display: gauges, radar screen, missile warning, minimap."""

import math

import pygame

from . import config as C


class HUD:
    def __init__(self):
        self.font = pygame.font.Font(C.FONT_NAME, 20)
        self.big_font = pygame.font.Font(C.FONT_NAME, 30)
        self.small_font = pygame.font.Font(C.FONT_NAME, 15)
        self.detected_flash = 0.0     # seconds of red flash remaining
        self.missile_warn = 0.0       # seconds of missile warning remaining
        self._warned_missiles = set() # missile ids already warned about

    def trigger_detected(self):
        self.detected_flash = 0.35

    def trigger_missile_warning(self, missile):
        self._warned_missiles.add(id(missile))
        self.missile_warn = 1.0

    def update(self, dt: float) -> None:
        self.detected_flash = max(0.0, self.detected_flash - dt)
        self.missile_warn = max(0.0, self.missile_warn - dt)

    def draw(self, surface: pygame.Surface, jet, radars, missiles, terrain,
             elapsed: float, goal_reached: bool) -> None:
        self._draw_speed_alt(surface, jet, terrain)
        self._draw_fuel(surface, jet)
        self._draw_radar_screen(surface, jet, radars)
        self._draw_minimap(surface, jet, radars, terrain)
        self._draw_warnings(surface, jet, radars, missiles, terrain)
        self._draw_goal(surface, jet, elapsed, goal_reached)

    # --- gauges ---
    def _draw_speed_alt(self, surface, jet, terrain):
        h = surface.get_size()[1]
        speed_kmh = int(jet.speed * 1.8)
        alt = max(0.0, jet.altitude(terrain))
        alt_m = int(alt * C.METRES_PER_PIXEL)
        text = self.font.render(f"SPD {speed_kmh:4d} km/h   ALT {alt_m:4d} m", True, C.HUD)
        surface.blit(text, (16, 12))
        # pitch ladder
        cx, cy = 90, 78
        pitch_deg = math.degrees(jet.pitch)
        for deg in range(-40, 41, 10):
            y = cy - (deg - pitch_deg) * 1.2
            if 30 < y < h - 60:
                width = 26 if deg % 20 == 0 else 14
                pygame.draw.line(surface, C.HUD_DIM, (cx - width, y), (cx + width, y), 1)
        pygame.draw.line(surface, C.HUD, (cx - 34, cy), (cx + 34, cy), 2)

    def _draw_fuel(self, surface, jet):
        w = 160
        x, y = 16, 40
        pygame.draw.rect(surface, C.HUD_DIM, (x, y, w, 12), 1)
        frac = jet.fuel / C.FUEL_MAX
        color = (120, 220, 120) if frac > 0.35 else (240, 120, 90)
        pygame.draw.rect(surface, color, (x + 1, y + 1, int((w - 2) * frac), 10))
        label = self.small_font.render("FUEL", True, C.HUD_DIM)
        surface.blit(label, (x + w + 8, y - 1))
        if jet.afterburner:
            ab = self.small_font.render("AFTERBURNER", True, C.FLAME)
            surface.blit(ab, (x + w + 8, y + 12))

    # --- radar scope (top-right) ---
    def _draw_radar_screen(self, surface, jet, radars):
        w, h = surface.get_size()
        cx, cy = w - 110, 100
        radius = 80
        pygame.draw.circle(surface, (8, 20, 14), (cx, cy), radius)
        pygame.draw.circle(surface, C.HUD_DIM, (cx, cy), radius, 1)
        pygame.draw.circle(surface, C.HUD_DIM, (cx, cy), radius // 2, 1)
        pygame.draw.line(surface, C.HUD_DIM, (cx - radius, cy), (cx + radius, cy), 1)
        pygame.draw.line(surface, C.HUD_DIM, (cx, cy - radius), (cx, cy + radius), 1)

        scale = radius / C.RADAR_RANGE
        for radar in radars:
            dx = (radar.x - jet.x) * scale
            dy = (radar.y - jet.y) * scale
            if dx * dx + dy * dy <= radius * radius:
                col = C.RADAR_BEAM if radar.detected else C.HUD
                pygame.draw.circle(surface, col, (int(cx + dx), int(cy + dy)), 3)
        # ownship blip (world +x is right on the scope, i.e. mission direction)
        pygame.draw.circle(surface, (120, 255, 120), (cx, cy), 3)
        # sweep ring: detected radars pulse red
        if self.detected_flash > 0:
            alpha_col = (255, 60, 60)
            pygame.draw.circle(surface, alpha_col, (cx, cy), radius, 2)

        label = self.small_font.render("RADAR", True, C.HUD_DIM)
        surface.blit(label, (cx - 20, cy + radius + 6))

    # --- minimap (bottom) ---
    def _draw_minimap(self, surface, jet, radars, terrain):
        w, h = surface.get_size()
        mw, mh = w - 40, 54
        x0, y0 = 20, h - mh - 14
        pygame.draw.rect(surface, (8, 20, 14, 200), (x0, y0, mw, mh))
        pygame.draw.rect(surface, C.HUD_DIM, (x0, y0, mw, mh), 1)

        def mx(world_x):
            return x0 + (world_x / C.WORLD_LENGTH) * mw

        # terrain silhouette
        pts = [(mx(x), y0 + mh - 6 - max(0.0, (C.SCREEN_H + 240 - y)) / 900.0 * (mh - 12))
               for x, y in _minimap_terrain_samples(terrain, mw)]
        if len(pts) > 1:
            pygame.draw.lines(surface, (60, 90, 70), False, pts, 1)

        # radars
        for radar in radars:
            rx = mx(radar.x)
            col = C.RADAR_BEAM if radar.detected else C.RADAR
            pygame.draw.circle(surface, col, (int(rx), y0 + 8), 3)
            pygame.draw.line(surface, col, (int(rx), y0 + 8), (int(rx), y0 + mh - 6), 1)

        # goal
        gx = mx(C.GOAL_X)
        pygame.draw.line(surface, C.GOAL, (gx, y0 + 4), (gx, y0 + mh - 4), 2)

        # jet
        jx = mx(jet.x)
        pygame.draw.circle(surface, (120, 255, 120), (int(jx), y0 + mh // 2), 3)

        label = self.small_font.render("MAP", True, C.HUD_DIM)
        surface.blit(label, (x0 + 4, y0 + 2))

    # --- warnings ---
    def _draw_warnings(self, surface, jet, radars, missiles, terrain):
        w, h = surface.get_size()
        # radar detection flash
        if self.detected_flash > 0:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            intensity = int(90 * (self.detected_flash / 0.35))
            s.fill((255, 40, 40, intensity))
            surface.blit(s, (0, 0))
            txt = self.big_font.render("RADAR CONTACT!", True, (255, 120, 120))
            surface.blit(txt, (w // 2 - txt.get_width() // 2, 60))

        # incoming missile warning
        incoming = [m for m in missiles
                    if math.hypot(m.x - jet.x, m.y - jet.y) < C.MISSILE_SPEED * C.MISSILE_WARN_TIME * 1.4]
        if incoming and self.missile_warn > 0:
            blink = int(pygame.time.get_ticks() / 150) % 2 == 0
            if blink:
                txt = self.big_font.render("MISSILE INBOUND!", True, (255, 80, 80))
                surface.blit(txt, (w // 2 - txt.get_width() // 2, 100))
            for m in incoming:
                # direction arrow at screen edge
                self._draw_arrow(surface, jet, m)

        # low altitude / ground proximity
        alt = jet.altitude(terrain)
        if 0 < alt < 60:
            txt = self.small_font.render("PULL UP!", True, (255, 200, 90))
            surface.blit(txt, (w // 2 - txt.get_width() // 2, h - 110))

    def _draw_arrow(self, surface, jet, missile):
        w, h = surface.get_size()
        dx = missile.x - jet.x
        dy = missile.y - jet.y
        angle = math.atan2(dy, dx)
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 40
        ax = cx + math.cos(angle) * r
        ay = cy + math.sin(angle) * r
        # triangle pointing from jet towards missile
        tip = (ax, ay)
        back = (ax - math.cos(angle) * 18, ay - math.sin(angle) * 18)
        left = (back[0] + math.sin(angle) * 8, back[1] - math.cos(angle) * 8)
        right = (back[0] - math.sin(angle) * 8, back[1] + math.cos(angle) * 8)
        pygame.draw.polygon(surface, (255, 80, 80), [tip, left, right])

    # --- goal / status ---
    def _draw_goal(self, surface, jet, elapsed, goal_reached):
        w = surface.get_size()[0]
        dist = max(0.0, C.GOAL_X - jet.x)
        dist_km = dist / 1000.0
        t = int(elapsed)
        txt = self.font.render(
            f"GOAL {dist_km:5.1f} km   TIME {t // 60:02d}:{t % 60:02d}", True, C.HUD)
        surface.blit(txt, (w - txt.get_width() - 16, 12))
        if goal_reached:
            big = self.big_font.render("GOAL REACHED!", True, C.GOAL)
            surface.blit(big, (w // 2 - big.get_width() // 2, 140))



def _minimap_terrain_samples(terrain, max_points):
    xs = terrain.xs
    if len(xs) <= max_points:
        return list(zip(xs, terrain.heights))
    step = len(xs) / max_points
    out = []
    for i in range(max_points):
        j = min(len(xs) - 1, int(i * step))
        out.append((xs[j], terrain.heights[j]))
    return out
