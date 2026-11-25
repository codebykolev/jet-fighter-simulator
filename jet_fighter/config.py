"""Tunable constants for the jet fighter simulator."""

import math

# --- Display ---
SCREEN_W = 1280
SCREEN_H = 720
# Vertical world scale: 1 px of altitude = this many metres (for the HUD)
METRES_PER_PIXEL = 0.3
FPS = 60
TITLE = "Jet Fighter Simulator"

# --- World ---
WORLD_LENGTH = 24000.0          # total horizontal length of the mission in px
TERRAIN_SEGMENT = 60.0          # x distance between terrain height samples
GOAL_X = WORLD_LENGTH - 600.0   # x position of the goal beacon

# --- Jet physics ---
GRAVITY = 260.0                 # px/s^2 pulling the jet down
THRUST = 620.0                  # forward acceleration at full throttle
AFTERBURNER_THRUST = 1150.0     # extra acceleration with afterburner
MAX_SPEED = 1100.0
MIN_SPEED = 90.0
DRAG = 0.35                     # linear drag coefficient (1/s)
LIFT_COEFF = 0.0052             # lift = LIFT_COEFF * speed^2 * sin(angle of attack)
BASELINE_AOA = 0.14             # wing lift at zero angle of attack (rad), ~8 deg
CRUISE_SPEED = 600.0            # reference speed for balanced level flight
PITCH_SPEED = 2.4               # rad/s nose rotation rate
PITCH_DAMPING = 2.2             # how fast the flight path follows the nose (1/s)
MAX_PITCH = math.radians(55)
ROLL_SPEED = 3.0
MAX_ROLL = math.radians(80)
FUEL_MAX = 100.0
FUEL_IDLE = 0.4                 # fuel/s at idle throttle
FUEL_FULL = 1.2                 # fuel/s at full throttle
FUEL_AF = 4.0                   # fuel/s with afterburner
CRASH_SPEED = 140.0             # ground impact slower than this is survivable

# --- Camera ---
CAMERA_LEAD = 0.35              # fraction of screen ahead of the jet
CAMERA_MIN_ALT = 120.0          # camera tries to stay this far above terrain

# --- Radar ---
RADAR_COUNT = 5
RADAR_MIN_GAP = 2600.0
RADAR_MAX_GAP = 4200.0
RADAR_SWEEP_SPEED = math.radians(55)     # rotation speed of the sweep (rad/s)
RADAR_SWEEP_WIDTH = math.radians(16)     # angular half-width of the beam
RADAR_RANGE = 2600.0
RADAR_ALT_RELIEF = 0.55                  # terrain below ~55% of radar height still occludes
RADAR_COOLDOWN = 6.0                     # seconds between missile launches per radar

# --- Missiles ---
MISSILE_SPEED = 760.0
MISSILE_TURN_RATE = math.radians(150)
MISSILE_LIFETIME = 6.0
MISSILE_HIT_RADIUS = 34.0
MISSILE_WARN_TIME = 1.6                   # seconds of warning before impact

# --- Colours ---
SKY_TOP = (18, 32, 62)
SKY_BOTTOM = (96, 140, 190)
SUN = (250, 230, 160)
MOUNTAIN_FAR = (74, 92, 118)
MOUNTAIN_NEAR = (46, 58, 74)
MOUNTAIN_SNOW = (226, 232, 240)
GRASS = (52, 96, 60)
JET_BODY = (210, 216, 224)
JET_DARK = (120, 128, 138)
FLAME = (255, 170, 60)
FLAME_CORE = (255, 240, 170)
RADAR = (200, 70, 70)
RADAR_BEAM = (255, 90, 90)
GOAL = (90, 230, 130)
HUD = (190, 235, 200)
HUD_DIM = (110, 150, 125)
TEXT = (235, 240, 245)

# --- Fonts ---
FONT_NAME = None  # pygame default
