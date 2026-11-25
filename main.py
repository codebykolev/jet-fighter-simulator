#!/usr/bin/env python3
"""Jet Fighter Simulator.

Fly a jet fighter low over a mountain range, hide from rotating radar
sweeps behind the ridges, dodge missiles, and reach the goal beacon.

Run:  python3 main.py [--seed N] [--no-audio] [--fullscreen]
"""

import argparse
import sys

import pygame

from jet_fighter import config as C
from jet_fighter.game import Game


def parse_args(argv):
    p = argparse.ArgumentParser(description="Jet Fighter Simulator")
    p.add_argument("--seed", type=int, default=None,
                   help="mission seed (random if omitted)")
    p.add_argument("--no-audio", action="store_true", help="disable sound")
    p.add_argument("--fullscreen", action="store_true", help="fullscreen mode")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    pygame.init()
    pygame.display.set_caption(C.TITLE)
    flags = pygame.SCALED
    if args.fullscreen:
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), flags, vsync=1)
    clock = pygame.time.Clock()

    import random
    game = Game(seed=args.seed if args.seed is not None else random.randint(0, 10_000),
                with_audio=not args.no_audio)

    running = True
    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 1.0 / 30.0)

        for event in pygame.event.get():
            game.handle_event(event)
            if event.type == pygame.QUIT:
                running = False

        if game.state == "quit":
            running = False

        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
