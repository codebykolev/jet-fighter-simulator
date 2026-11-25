"""Headless smoke tests: run with `python3 test_smoke.py` (no display needed).

Verifies terrain generation, jet physics (takeoff, flight, crash), radar
detection/occlusion, missile pursuit, and that the full game loop can run
for many frames offscreen without errors.
"""

import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

from jet_fighter import config as C
from jet_fighter.game import Game
from jet_fighter.jet import Jet
from jet_fighter.radar import Radar, place_radars
from jet_fighter.terrain import generate_terrain


def test_terrain():
    terrain = generate_terrain(seed=42)
    assert len(terrain.xs) > 100
    # heights must be finite and within a sane band
    for y in terrain.heights:
        assert 0 < y < C.SCREEN_H + 600, y
    # interpolation is continuous: midpoint of a segment matches average
    x0, x1 = terrain.xs[10], terrain.xs[11]
    mid = (x0 + x1) / 2
    expected = (terrain.heights[10] + terrain.heights[11]) / 2
    assert abs(terrain.height_at(mid) - expected) < 1e-6
    # determinism: same seed gives same terrain
    terrain2 = generate_terrain(seed=42)
    assert terrain.xs == terrain2.xs and terrain.heights == terrain2.heights
    print("ok - terrain")


def test_jet_takeoff_and_flight():
    terrain = generate_terrain(seed=7)
    jet = Jet(x=500.0, y=terrain.height_at(500.0) - 2.0)

    class Keys(dict):
        def __getitem__(self, k):
            return self.get(k, False)

    # full throttle on the ground -> must accelerate
    keys = Keys({pygame.K_RIGHT: True})
    for _ in range(120):
        jet.apply_input(keys, 1 / 60, on_ground=True, terrain=terrain)
        jet.update(1 / 60, terrain)
    assert jet.speed > 100, f"jet did not accelerate: {jet.speed}"

    # pull up -> should leave the ground
    keys = Keys({pygame.K_RIGHT: True, pygame.K_UP: True})
    took_off = False
    for _ in range(600):
        jet.apply_input(keys, 1 / 60, not jet.airborne, terrain=terrain)
        jet.update(1 / 60, terrain)
        if jet.altitude(terrain) > 30:
            took_off = True
            break
    assert took_off, "jet never took off"
    assert jet.alive

    # release the stick: the jet should settle into stable flight and stay
    # alive and airborne for a long stretch of straight-and-level flying
    keys = Keys({pygame.K_RIGHT: True})
    airborne_frames = 0
    for _ in range(600):
        jet.apply_input(keys, 1 / 60, not jet.airborne, terrain=terrain)
        jet.update(1 / 60, terrain)
        if jet.altitude(terrain) > 10:
            airborne_frames += 1
        assert jet.alive, "jet crashed during normal flight"
    assert airborne_frames > 300, f"jet spent too little time airborne: {airborne_frames}"
    print("ok - jet takeoff and flight")


def test_jet_crash():
    terrain = generate_terrain(seed=7)
    # slam into a mountainside at high speed, nose-down
    jet = Jet(x=500.0, y=100.0, vx=600.0, vy=500.0, pitch=-0.4)
    result = None
    for _ in range(120):
        result = jet.update(1 / 60, terrain)
        if result:
            break
    assert result == "crash", f"expected crash, got {result}"
    assert not jet.alive
    print("ok - jet crash")


def test_radar_occlusion():
    terrain = generate_terrain(seed=3)
    # put a radar on a flat testbed and a jet directly behind a tall ridge:
    # craft a terrain where the ridge blocks line of sight
    class FlatTerrain:
        def __init__(self, h):
            self.h = h
        def height_at(self, x):
            return self.h

    flat = FlatTerrain(700.0)
    jet = Jet(x=1000.0, y=650.0)
    radar = Radar(x=0.0, y=700.0, sweep=0.0)  # beam pointing +x at the jet
    # jet is 50px above ground, radar eye at 654; line of sight is clear
    assert radar._sees(jet, flat), "radar should see jet on flat ground"

    class RidgeTerrain:
        def height_at(self, x):
            return 300.0 if 400 < x < 600 else 700.0

    ridge = RidgeTerrain()
    assert not radar._sees(jet, ridge), "ridge should block the radar beam"
    print("ok - radar occlusion")


def test_radar_sweep_rotation():
    terrain = generate_terrain(seed=3)
    jet = Jet(x=800.0, y=600.0)
    radar = Radar(x=0.0, y=700.0, sweep=math.pi)  # pointing away (-x)
    assert not radar._sees(jet, terrain)
    radar.sweep = 0.0  # pointing at the jet
    # may or may not see depending on terrain; just ensure no crash and bool
    result = radar._sees(jet, terrain)
    assert isinstance(result, bool)
    print("ok - radar sweep")


def test_radar_place_and_fire():
    terrain = generate_terrain(seed=11)
    radars = place_radars(terrain, seed=11)
    assert len(radars) == C.RADAR_COUNT
    xs = [r.x for r in radars]
    assert all(1500 < x < C.WORLD_LENGTH - 1500 for x in xs)
    assert xs == sorted(xs)
    # radars sit on (or just above) the ground
    for r in radars:
        ground = terrain.height_at(r.x)
        assert r.y <= ground + 1.0, (r.y, ground)

    # force a detection and check a missile is launched
    jet = Jet(x=radars[0].x + 500.0, y=radars[0].y - 60.0)
    missiles = []
    # aim the sweep at the jet and use flat-ish local terrain assumption:
    # call update repeatedly; the sweep rotates so eventually it may fire
    fired = False
    for _ in range(600):
        radars[0].update(1 / 60, jet, terrain, missiles)
        if missiles:
            fired = True
            break
    # not guaranteed with real terrain occlusion; instead directly test the
    # fire path by faking detection
    missiles.clear()
    radars[0].cooldown = 0.0
    radars[0].detected = True
    radars[0].update(0.01, jet, terrain, missiles)
    assert len(missiles) == 1, "radar should launch a missile when detecting"
    print("ok - radar placement and firing")


def test_missile_pursuit():
    terrain = generate_terrain(seed=5)
    jet = Jet(x=2000.0, y=300.0)
    m = type("M", (), {})()  # placeholder, replaced below
    from jet_fighter.radar import Missile
    missile = Missile(x=1500.0, y=300.0)
    hit = None
    for _ in range(600):
        result = missile.update(1 / 60, jet, terrain)
        if result:
            hit = result
            break
    assert hit == "hit", f"missile should hit a stationary-ish target, got {hit}"
    print("ok - missile pursuit")


def test_full_game_loop():
    pygame.init()
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    game = Game(seed=123, with_audio=False)
    game.start_mission()

    # bot pilot: full throttle, gentle pull-up, periodic corrections
    class BotKeys(dict):
        def __getitem__(self, k):
            return self.get(k, False)

    frames = 0
    max_frames = 60 * 60  # up to 60 simulated seconds
    while game.state == "playing" and frames < max_frames:
        alt = game.jet.altitude(game.terrain)
        keys = BotKeys({pygame.K_RIGHT: True})
        # keep some altitude above ground
        if alt < 90:
            keys[pygame.K_UP] = True
        elif alt > 220:
            keys[pygame.K_DOWN] = True
        # monkey-patch get_pressed for this frame
        orig = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: keys
        try:
            game.update(1 / 60)
        finally:
            pygame.key.get_pressed = orig
        game.draw(screen)
        frames += 1

    assert frames > 60, "game ended suspiciously fast"
    assert game.state in ("win", "gameover"), game.state
    print(f"ok - full game loop ({frames} frames, ended as {game.state}, "
          f"distance {game.jet.x:.0f}/{C.WORLD_LENGTH:.0f})")
    pygame.quit()


def main():
    test_terrain()
    test_jet_takeoff_and_flight()
    test_jet_crash()
    test_radar_occlusion()
    test_radar_sweep_rotation()
    test_radar_place_and_fire()
    test_missile_pursuit()
    test_full_game_loop()
    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
