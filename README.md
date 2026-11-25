# Jet Fighter Simulator

A side-scrolling jet fighter game built with **pygame**. You fly low over a
procedurally generated mountain range, hide from rotating radar sweeps behind
the ridges, dodge heat-seeking missiles, and reach the goal beacon at the far
end of the map.

## Run

```bash
python3 main.py                 # random mission
python3 main.py --seed 42       # fixed mission
python3 main.py --no-audio      # silent (e.g. headless machines)
python3 main.py --fullscreen
```

Requires: `pygame` (and optionally `numpy` for synthesized sound effects —
without it the game runs silently).

## Controls

| Key | Action |
| --- | --- |
| `UP` / `W` | Pull up (nose up) |
| `DOWN` / `S` | Push down (nose down) |
| `RIGHT` / `D` | Full throttle |
| `LEFT` / `A` | Idle throttle |
| `SHIFT` (hold) | Afterburner (extra thrust, drains fuel fast) |
| `ESC` | Pause / back to menu |

## How to play

- **Take off** from the flat strip at the left: hold full throttle, then pull
  up once you have speed.
- **Stay low.** Radar beams are blocked by mountains — fly in the valleys and
  behind ridge lines and the sweep cannot see you. The radar scope (top right)
  shows blips: green = safe, red = you are being tracked.
- **Missiles.** When a radar locks you it fires. A red `MISSILE INBOUND!`
  warning and a screen-edge arrow show the threat direction. Jink hard and put
  a ridge between you and the missile.
- **Fuel** is limited. Afterburner gives a big speed boost but burns fuel fast.
- **Goal.** Cross the green beacon at the far end of the map. Score rewards
  distance, low-altitude flying, and finishing quickly.

## Project layout

```
main.py                  entry point
jet_fighter/
  config.py              tunable constants (physics, radar, colours)
  terrain.py             procedural mountain generation + height queries
  jet.py                 jet physics, controls, rendering
  radar.py               radar sweeps, terrain-masked detection, missiles
  hud.py                 HUD, radar scope, minimap, warnings
  audio.py               procedurally synthesized sound effects (numpy)
  game.py                world, camera, game loop, menu/win/game-over
test_smoke.py            headless smoke + physics tests (SDL dummy driver)
```

## Tests

```bash
python3 test_smoke.py
```

Runs fully headless (SDL dummy video/audio drivers) and checks terrain
generation, takeoff/flight/crash physics, radar occlusion, missile pursuit,
and a full bot-piloted game loop.
