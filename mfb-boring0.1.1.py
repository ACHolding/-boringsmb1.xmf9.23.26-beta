#!/usr/bin/env python3.14
"""
Mario Forever Boring Edition by AC Kondo — 0.1.1
FILES=OFF · Boring Engine (full NSMB2 homage) · 60fps
OST: full SMB1 NES square-wave composition (FILES=OFF)
Bosses: Bowser Jr on *-4 · Final: Kamek on 8-4
No Nintendo assets, ROMs, or proprietary code.
"""

from __future__ import annotations

import array
import math
import random
import sys
import time
from typing import Optional

# Prefer Python 3.14+
if sys.version_info < (3, 14):
    print("Mario Forever Boring Edition requires Python 3.14+", file=sys.stderr)
    # still allow run if user insists; warn only
    pass

try:
    import pygame
except ImportError as e:
    raise SystemExit("Install pygame-ce: python3.14 -m pip install pygame-ce") from e

# ── meta ──────────────────────────────────────────────────────────────────
TITLE = "Mario Forever Boring Edition"
AUTHOR = "AC Kondo"
VERSION = "0.1.1"
FILES = False  # OFF forever
ENGINE = "Boring Engine · full NSMB2 · 60fps"
ENGINE_TAG = "powered by Boring Engine"

W, H = 960, 540
FPS = 60
TILE = 32

# ── Boring Engine — full NSMB2-style player (homage, FILES=OFF) @ 60 Hz ──
GRAVITY_UP = 0.38
GRAVITY_FALL = 0.82
GRAVITY_POUND = 1.35
JUMP_V = -10.4
JUMP_V2 = -11.2
JUMP_V3 = -12.0
JUMP_LONG = -7.2
JUMP_WALL = -10.0
JUMP_CUT = 0.46
WALK_ACC = 0.30
RUN_ACC = 0.42
AIR_ACC = 0.24
SKID_ACC = 0.60
FRICTION = 0.76
AIR_FRIC = 0.965
SLIDE_FRIC = 0.92
MAX_WALK = 3.2
MAX_RUN = 5.8
MAX_P = 6.4
MAX_FALL = 12.0
MAX_POUND = 16.0
COYOTE = 6
JUMP_BUF = 8
STOMP_BOUNCE = -6.8
WALL_SLIDE_MAX = 2.4
WALL_JUMP_PUSH = 5.2
P_BUILD = 1.8
P_DECAY = 2.2
P_MAX = 100.0
TRIPLE_WINDOW = 14
SLIDE_MIN_V = 2.8
CROUCH_H = 22
STAND_H = 36
BIG_H = 48
INVULN = 90
WALL_INSET = 4
BOOT_FRAMES = int(FPS * 2.4)

# tiles
AIR, GROUND, BRICK, QBLOCK, QUSED, PIPE, HARD, SPIKE, FLAG, CASTLE, COIN, CLOUD = range(12)
SOLID = frozenset({GROUND, BRICK, QBLOCK, QUSED, PIPE, HARD, CASTLE})

# boring palette (intentionally drab)
SKY = (118, 132, 148)
GROUND_C = (92, 78, 62)
BRICK_C = (110, 88, 70)
PIPE_C = (70, 96, 70)
HARD_C = (70, 70, 78)
ACCENT = (160, 140, 90)
UI_BG = (40, 42, 48)
UI_FG = (210, 210, 205)
UI_DIM = (140, 140, 135)
PLAYER_C = (180, 70, 60)
JR_C = (70, 130, 70)
KAMEK_C = (160, 90, 180)

THEME_OVER, THEME_UNDER, THEME_ATH, THEME_CASTLE = range(4)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def stage_key(w: int, s: int) -> str:
    return f"{w}-{s}"


def world_theme(w: int, s: int) -> int:
    if s == 4:
        return THEME_CASTLE
    if w in (2, 6):
        return THEME_UNDER
    if w in (3, 7):
        return THEME_ATH
    return THEME_OVER


def stage_seed(w: int, s: int) -> int:
    return w * 10007 + s * 997 + 4242


# ── FILES=OFF audio (square / pulse NES homage) ───────────────────────────
def _sq(freq: float, ms: int, vol: float = 0.18, duty: float = 0.25, rate: int = 22050):
    n = max(1, int(rate * ms / 1000))
    buf = array.array("h")
    amp = int(32767 * vol)
    period = max(1, int(rate / max(20.0, freq)))
    high = max(1, int(period * duty))
    for i in range(n):
        buf.append(amp if (i % period) < high else -amp)
    try:
        return pygame.mixer.Sound(buffer=buf)
    except Exception:
        return None


# Note map (Hz) — SMB1-style homage, FILES=OFF synth
_N = {
    "G2": 98.00, "A2": 110.00, "A#2": 116.54, "B2": 123.47,
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "D#3": 155.56,
    "E3": 164.81, "F3": 174.61, "F#3": 185.00, "G3": 196.00,
    "G#3": 207.65, "A3": 220.00, "A#3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13,
    "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "D#5": 622.25,
    "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99,
    "A5": 880.00, "—": 0.0,
}

# Pulse lengths (ms) @ ~100 BPM homage — do NOT name these W/H (screen size)
DUR_Q, DUR_E, DUR_S, DUR_H, DUR_W = 200, 100, 50, 400, 800


def _phrase(*notes):
    """notes: ('E4', DUR_E), ('—', DUR_S), ..."""
    return list(notes)


# Full SMB1 overworld-style composition (A B C B A′ loop) — homage, not a dump
# Prefixed OST_* so we never clobber tile ids (CASTLE) or screen size (W/H)
OST_OVERWORLD = (
    # A — famous hook
    _phrase(
        ("E4", DUR_E), ("E4", DUR_E), ("—", DUR_E), ("E4", DUR_E), ("—", DUR_E), ("C4", DUR_E), ("E4", DUR_E), ("—", DUR_E),
        ("G4", DUR_H), ("—", DUR_H), ("G3", DUR_H), ("—", DUR_H),
    )
    # B — climb
    + _phrase(
        ("C4", DUR_Q), ("—", DUR_E), ("G3", DUR_Q), ("—", DUR_E), ("E3", DUR_Q), ("—", DUR_E),
        ("A3", DUR_Q), ("—", DUR_E), ("B3", DUR_Q), ("—", DUR_E), ("A#3", DUR_E), ("A3", DUR_Q), ("—", DUR_E),
        ("G3", DUR_E), ("E4", DUR_E), ("G4", DUR_E), ("A4", DUR_Q), ("—", DUR_E),
        ("F4", DUR_E), ("G4", DUR_E), ("—", DUR_E), ("E4", DUR_Q), ("—", DUR_E),
        ("C4", DUR_E), ("D4", DUR_E), ("B3", DUR_Q), ("—", DUR_Q),
    )
    # C — mid bridge
    + _phrase(
        ("C4", DUR_Q), ("—", DUR_E), ("G3", DUR_Q), ("—", DUR_E), ("E3", DUR_Q), ("—", DUR_E),
        ("A3", DUR_Q), ("—", DUR_E), ("B3", DUR_Q), ("—", DUR_E), ("A#3", DUR_E), ("A3", DUR_Q), ("—", DUR_E),
        ("G3", DUR_E), ("E4", DUR_E), ("G4", DUR_E), ("A4", DUR_Q), ("—", DUR_E),
        ("F4", DUR_E), ("G4", DUR_E), ("—", DUR_E), ("E4", DUR_Q), ("—", DUR_E),
        ("C4", DUR_E), ("D4", DUR_E), ("B3", DUR_Q), ("—", DUR_Q),
    )
    # D — high flourish
    + _phrase(
        ("C5", DUR_E), ("—", DUR_E), ("G4", DUR_E), ("—", DUR_E), ("E4", DUR_E), ("—", DUR_E), ("A4", DUR_E), ("B4", DUR_E),
        ("A4", DUR_E), ("G4", DUR_E), ("E4", DUR_E), ("C4", DUR_E), ("D4", DUR_E), ("B3", DUR_Q), ("—", DUR_E),
        ("G4", DUR_E), ("F#4", DUR_E), ("F4", DUR_E), ("D#4", DUR_Q), ("E4", DUR_E), ("—", DUR_E),
        ("G#3", DUR_E), ("A3", DUR_E), ("C4", DUR_E), ("—", DUR_E), ("A3", DUR_E), ("C4", DUR_E), ("D4", DUR_Q), ("—", DUR_E),
        ("G4", DUR_E), ("F#4", DUR_E), ("F4", DUR_E), ("D#4", DUR_Q), ("E4", DUR_E), ("—", DUR_E),
        ("C5", DUR_E), ("—", DUR_E), ("C5", DUR_E), ("C5", DUR_Q), ("—", DUR_Q),
    )
    # E — reprise hook → loop
    + _phrase(
        ("E4", DUR_E), ("E4", DUR_E), ("—", DUR_E), ("E4", DUR_E), ("—", DUR_E), ("C4", DUR_E), ("E4", DUR_E), ("—", DUR_E),
        ("G4", DUR_H), ("—", DUR_H), ("G3", DUR_H), ("—", DUR_H),
        ("C4", DUR_Q), ("—", DUR_E), ("G3", DUR_Q), ("—", DUR_E), ("E3", DUR_Q), ("—", DUR_E),
        ("A3", DUR_Q), ("—", DUR_E), ("B3", DUR_Q), ("—", DUR_E), ("A#3", DUR_E), ("A3", DUR_Q), ("—", DUR_H),
    )
)

OST_UNDERWORLD = (
    _phrase(
        ("C4", DUR_Q), ("—", DUR_S), ("C5", DUR_Q), ("—", DUR_S), ("A4", DUR_Q), ("—", DUR_S),
        ("A#4", DUR_Q), ("—", DUR_S), ("A4", DUR_E), ("G4", DUR_E), ("F4", DUR_E), ("D4", DUR_E), ("C4", DUR_Q), ("—", DUR_E),
        ("E4", DUR_E), ("—", DUR_E), ("G4", DUR_E), ("—", DUR_E), ("C5", DUR_H), ("—", DUR_E),
        ("A4", DUR_E), ("—", DUR_E), ("A#4", DUR_E), ("—", DUR_E), ("B4", DUR_E), ("—", DUR_E), ("C5", DUR_H), ("—", DUR_Q),
    )
    + _phrase(
        ("C4", DUR_Q), ("E4", DUR_E), ("G4", DUR_E), ("C5", DUR_Q), ("—", DUR_E), ("A4", DUR_Q), ("—", DUR_E),
        ("A#4", DUR_E), ("A4", DUR_E), ("G4", DUR_E), ("F4", DUR_E), ("E4", DUR_Q), ("D4", DUR_Q), ("C4", DUR_H), ("—", DUR_H),
    )
)

OST_CASTLE = (
    _phrase(
        ("E3", DUR_E), ("E3", DUR_E), ("—", DUR_E), ("E3", DUR_E), ("C4", DUR_Q), ("E3", DUR_E),
        ("G3", DUR_H), ("—", DUR_E), ("G2", DUR_H), ("—", DUR_Q),
        ("E3", DUR_E), ("E3", DUR_E), ("—", DUR_E), ("E3", DUR_E), ("C4", DUR_Q), ("E3", DUR_E),
        ("G3", DUR_H), ("—", DUR_E), ("G2", DUR_H), ("—", DUR_Q),
    )
    + _phrase(
        ("A3", DUR_E), ("B3", DUR_E), ("C4", DUR_E), ("D4", DUR_E), ("E4", DUR_Q), ("—", DUR_E),
        ("A3", DUR_E), ("B3", DUR_E), ("C4", DUR_E), ("A3", DUR_Q), ("—", DUR_Q),
        ("G#3", DUR_E), ("A3", DUR_E), ("B3", DUR_E), ("G#3", DUR_Q), ("—", DUR_E),
        ("E3", DUR_E), ("E3", DUR_E), ("—", DUR_E), ("E3", DUR_H), ("—", DUR_H),
    )
)

OST_BOSS = (
    _phrase(
        ("A3", DUR_S), ("A3", DUR_S), ("A3", DUR_S), ("A3", DUR_S), ("C4", DUR_E), ("A3", DUR_E),
        ("D4", DUR_E), ("C4", DUR_E), ("A3", DUR_Q), ("—", DUR_E),
        ("A3", DUR_S), ("A3", DUR_S), ("A3", DUR_S), ("A3", DUR_S), ("C4", DUR_E), ("A3", DUR_E),
        ("F4", DUR_E), ("E4", DUR_E), ("D4", DUR_Q), ("—", DUR_E),
    )
    + _phrase(
        ("E4", DUR_E), ("—", DUR_S), ("E4", DUR_E), ("—", DUR_S), ("E4", DUR_E), ("C4", DUR_E), ("A3", DUR_Q),
        ("G3", DUR_E), ("A3", DUR_E), ("C4", DUR_E), ("A3", DUR_Q), ("—", DUR_Q),
        ("D4", DUR_E), ("D4", DUR_E), ("C4", DUR_E), ("A#3", DUR_E), ("A3", DUR_H), ("—", DUR_Q),
    )
)

OST_MENU = (
    _phrase(
        ("E4", DUR_E), ("G4", DUR_E), ("A4", DUR_Q), ("—", DUR_E), ("G4", DUR_E), ("E4", DUR_Q), ("—", DUR_E),
        ("C4", DUR_E), ("D4", DUR_E), ("E4", DUR_Q), ("—", DUR_E), ("G3", DUR_H), ("—", DUR_E),
        ("E4", DUR_E), ("G4", DUR_E), ("A4", DUR_Q), ("B4", DUR_E), ("A4", DUR_E), ("G4", DUR_Q), ("—", DUR_E),
        ("E4", DUR_E), ("C4", DUR_E), ("D4", DUR_Q), ("B3", DUR_H), ("—", DUR_Q),
    )
)


class Audio:
    def __init__(self):
        self.ok = False
        self.muted = False
        self._queue: list = []
        self._i = 0
        self._wait = 0
        self._track = "menu"
        self._music_ch = None
        self.sfx: dict = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.ok = True
            pygame.mixer.set_num_channels(16)
            self._music_ch = pygame.mixer.Channel(0)
        except Exception:
            self.ok = False
        if self.ok:
            self.sfx = {
                "jump": _sq(520, 70, 0.16),
                "stomp": _sq(180, 55, 0.2),
                "coin": _sq(880, 45, 0.16),
                "bump": _sq(110, 40, 0.18),
                "hurt": _sq(140, 180, 0.22, 0.4),
                "power": _sq(660, 100, 0.18),
                "clear": _sq(740, 220, 0.18),
                "boss_hit": _sq(90, 90, 0.22, 0.3),
                "win": _sq(880, 300, 0.2),
            }
            self.set_track("off")  # menus silent — OST only in-game

    def play(self, name: str):
        if not self.ok or self.muted:
            return
        s = self.sfx.get(name)
        if s:
            s.play()

    def stop_music(self):
        self._queue = []
        self._track = "off"
        self._i = 0
        self._wait = 0
        if self._music_ch is not None:
            self._music_ch.stop()

    def set_track(self, name: str):
        self._track = name
        self._i = 0
        self._wait = 0
        if name in ("off", "menu", "none", ""):
            self.stop_music()
            return
        if name == "over":
            self._queue = OST_OVERWORLD
        elif name == "under":
            self._queue = OST_UNDERWORLD
        elif name == "castle":
            self._queue = OST_CASTLE
        elif name == "boss":
            self._queue = OST_BOSS
        else:
            self.stop_music()

    def update(self, dt_ms: float = 16.0):
        if not self.ok or self.muted or not self._queue:
            return
        self._wait -= dt_ms
        if self._wait > 0:
            return
        note, dur = self._queue[self._i % len(self._queue)]
        self._i += 1
        self._wait = float(dur)
        freq = _N.get(note, 0.0)
        if freq > 0:
            ch = _sq(freq, max(35, int(dur) - 12), 0.11, 0.125)
            if ch and self._music_ch is not None:
                self._music_ch.play(ch)
            elif ch:
                ch.play()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self._music_ch is not None:
            self._music_ch.stop()


# ── graphics (procedural, boring) ─────────────────────────────────────────
def make_surf(w, h, color=None):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if color:
        s.fill(color)
    return s


def tile_surf(kind: int, theme: int) -> pygame.Surface:
    s = make_surf(TILE, TILE)
    if kind == GROUND:
        c = (60, 70, 80) if theme == THEME_UNDER else (50, 50, 58) if theme == THEME_CASTLE else GROUND_C
        s.fill(c)
        pygame.draw.rect(s, (c[0] + 20, c[1] + 15, c[2] + 10), (0, 0, TILE, 6))
    elif kind == BRICK:
        s.fill(BRICK_C)
        pygame.draw.line(s, (80, 60, 50), (0, TILE // 2), (TILE, TILE // 2), 1)
        pygame.draw.line(s, (80, 60, 50), (TILE // 2, 0), (TILE // 2, TILE), 1)
    elif kind in (QBLOCK, QUSED):
        s.fill(ACCENT if kind == QBLOCK else (90, 80, 70))
        if kind == QBLOCK:
            f = pygame.font.SysFont("Courier New", 18, bold=True)
            q = f.render("?", True, (40, 40, 40))
            s.blit(q, q.get_rect(center=(TILE // 2, TILE // 2)))
    elif kind == PIPE:
        s.fill(PIPE_C)
        pygame.draw.rect(s, (50, 70, 50), (0, 0, 4, TILE))
        pygame.draw.rect(s, (90, 120, 90), (TILE - 4, 0, 4, TILE))
    elif kind == HARD:
        s.fill(HARD_C)
        pygame.draw.rect(s, (90, 90, 100), (2, 2, TILE - 4, TILE - 4), 1)
    elif kind == SPIKE:
        pygame.draw.polygon(s, (160, 160, 160), [(0, TILE), (TILE // 2, 4), (TILE, TILE)])
    elif kind == FLAG:
        s.fill((0, 0, 0, 0))
        pygame.draw.rect(s, (200, 200, 200), (TILE // 2 - 1, 0, 2, TILE))
        pygame.draw.polygon(s, (180, 60, 60), [(TILE // 2, 2), (TILE - 2, 10), (TILE // 2, 18)])
    elif kind == CASTLE:
        s.fill((55, 55, 62))
        pygame.draw.rect(s, (40, 40, 48), (8, 14, 16, 18))
    elif kind == COIN:
        pygame.draw.ellipse(s, (200, 180, 60), (8, 6, 16, 20))
        pygame.draw.ellipse(s, (240, 220, 100), (11, 9, 10, 14))
    elif kind == CLOUD:
        pygame.draw.ellipse(s, (170, 175, 180), (2, 10, 28, 14))
    return s


def player_frames() -> list:
    frames = []
    for i in range(3):
        s = make_surf(28, 40)
        # boring red rectangle Mario
        pygame.draw.rect(s, PLAYER_C, (4, 8, 20, 22))
        pygame.draw.rect(s, (220, 180, 140), (6, 2, 16, 12))  # face
        pygame.draw.rect(s, (40, 40, 40), (10, 6, 3, 3))
        pygame.draw.rect(s, (40, 40, 40), (17, 6, 3, 3))
        pygame.draw.rect(s, (40, 60, 140), (4, 28, 9, 10))  # legs
        pygame.draw.rect(s, (40, 60, 140), (15, 28 + (i % 2), 9, 10))
        frames.append(s)
    return frames


def jr_surf() -> pygame.Surface:
    s = make_surf(40, 44)
    pygame.draw.ellipse(s, JR_C, (4, 10, 32, 28))
    pygame.draw.ellipse(s, (240, 200, 140), (10, 4, 20, 16))
    pygame.draw.rect(s, (40, 40, 40), (14, 10, 3, 3))
    pygame.draw.rect(s, (40, 40, 40), (23, 10, 3, 3))
    pygame.draw.rect(s, (180, 50, 50), (12, 0, 16, 8))  # bandana
    return s


def kamek_surf() -> pygame.Surface:
    s = make_surf(44, 48)
    pygame.draw.ellipse(s, KAMEK_C, (6, 12, 32, 30))
    pygame.draw.ellipse(s, (240, 220, 200), (12, 6, 20, 16))
    pygame.draw.polygon(s, (90, 50, 120), [(8, 8), (22, 0), (36, 8), (22, 14)])  # hat
    pygame.draw.rect(s, (200, 180, 40), (30, 20, 12, 4))  # wand
    pygame.draw.circle(s, (255, 240, 100), (42, 18), 5)
    return s


# ── level generation ──────────────────────────────────────────────────────
def generate_level(world: int, stage: int) -> dict:
    rng = random.Random(stage_seed(world, stage))
    theme = world_theme(world, stage)
    is_boss = stage == 4
    if is_boss:
        width = 40
        height = 15
        tiles = [[AIR for _ in range(width)] for _ in range(height)]
        gy = 13
        for x in range(width):
            for y in range(gy, height):
                tiles[y][x] = HARD if theme == THEME_CASTLE else GROUND
        for x in range(width):
            tiles[2][x] = HARD  # ceiling
        # platforms
        for px in (8, 18, 28):
            for i in range(4):
                tiles[9][px + i] = HARD
        enemies = []
        boss = "kamek" if world == 8 else "jr"
        return {
            "world": world, "stage": stage, "key": stage_key(world, stage),
            "width": width, "height": height, "tiles": tiles, "theme": theme,
            "enemies": enemies, "spawn": (3 * TILE, (gy - 1) * TILE),
            "goal_x": (width - 3) * TILE, "time": 300, "boss": boss,
        }

    width = 100 + world * 10 + stage * 6 + rng.randint(0, 16)
    height = 15
    tiles = [[AIR for _ in range(width)] for _ in range(height)]
    gy = 13
    x = 0
    while x < width:
        run = rng.randint(5, 12)
        gap = 0
        if 10 < x < width - 18 and rng.random() < 0.14 + world * 0.012:
            gap = rng.randint(2, 3 + min(2, world // 3))
        for i in range(run):
            if x + i >= width:
                break
            for y in range(gy, height):
                tiles[y][x + i] = HARD if theme == THEME_CASTLE else GROUND
        x += run + gap
    for i in range(12):
        for y in range(gy, height):
            tiles[y][i] = GROUND if theme != THEME_CASTLE else HARD
    for i in range(width - 14, width):
        for y in range(gy, height):
            tiles[y][i] = GROUND if theme != THEME_CASTLE else HARD

    # pipes
    for _ in range(2 + world // 2):
        px = rng.randint(14, width - 18)
        ph = rng.randint(2, 3)
        top = gy - ph
        for dy in range(ph):
            tiles[top + dy][px] = PIPE
            tiles[top + dy][px + 1] = PIPE

    # blocks
    for _ in range(5 + world + stage):
        bx = rng.randint(10, width - 14)
        by = gy - rng.randint(3, 5)
        if by < 2:
            continue
        ln = rng.randint(1, 4)
        for i in range(ln):
            if bx + i >= width - 2:
                break
            if tiles[by][bx + i] == AIR:
                tiles[by][bx + i] = QBLOCK if rng.random() < 0.4 else BRICK

    if theme == THEME_ATH or world >= 4:
        for _ in range(3 + world):
            px = rng.randint(16, width - 16)
            py = rng.randint(5, gy - 3)
            for i in range(rng.randint(3, 6)):
                if px + i < width:
                    tiles[py][px + i] = HARD

    for _ in range(8 + world * 2):
        cx = rng.randint(8, width - 8)
        cy = rng.randint(3, gy - 2)
        if tiles[cy][cx] == AIR:
            tiles[cy][cx] = COIN

    if theme == THEME_OVER:
        for _ in range(6):
            cx = rng.randint(0, width - 1)
            cy = rng.randint(1, 4)
            if tiles[cy][cx] == AIR:
                tiles[cy][cx] = CLOUD

    if theme == THEME_CASTLE:
        for _ in range(4 + world):
            sx = rng.randint(12, width - 12)
            if tiles[gy][sx] in SOLID:
                tiles[gy - 1][sx] = SPIKE

    flag_x = width - 7
    for y in range(4, gy):
        tiles[y][flag_x] = FLAG
    for y in range(gy - 4, gy):
        tiles[y][flag_x + 2] = CASTLE
        tiles[y][flag_x + 3] = CASTLE

    enemies = []
    kinds = ["goomba", "goomba", "koopa"]
    if world >= 3:
        kinds.append("flyer")
    for _ in range(4 + world * 2 + stage):
        ex = rng.randint(16, width - 16)
        ey = gy - 1
        if tiles[ey][ex] != AIR:
            continue
        enemies.append({"x": ex * TILE, "y": ey * TILE, "kind": rng.choice(kinds)})

    return {
        "world": world, "stage": stage, "key": stage_key(world, stage),
        "width": width, "height": height, "tiles": tiles, "theme": theme,
        "enemies": enemies, "spawn": (2 * TILE, (gy - 1) * TILE),
        "goal_x": flag_x * TILE, "time": 400, "boss": None,
    }


def build_all_levels() -> dict:
    out = {}
    for w in range(1, 9):
        for s in range(1, 5):
            out[stage_key(w, s)] = generate_level(w, s)
    return out


# ── entities ──────────────────────────────────────────────────────────────
class Player:
    __slots__ = (
        "x", "y", "vx", "vy", "w", "h", "on_ground", "facing", "lives",
        "coins", "score", "invuln", "coyote", "jbuf", "dead", "won",
        "anim", "big", "jump_cut", "p_meter", "jump_chain", "chain_timer",
        "crouch", "slide", "slide_t", "pound", "wall_dir", "spin",
        "spin_t", "stand_h",
    )

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.w, self.h = 24, STAND_H
        self.stand_h = STAND_H
        self.on_ground = False
        self.facing = 1
        self.lives = 5
        self.coins = 0
        self.score = 0
        self.invuln = 0
        self.coyote = 0
        self.jbuf = 0
        self.dead = False
        self.won = False
        self.anim = 0.0
        self.big = False
        self.jump_cut = False
        self.p_meter = 0.0
        self.jump_chain = 0
        self.chain_timer = 0
        self.crouch = False
        self.slide = False
        self.slide_t = 0
        self.pound = False
        self.wall_dir = 0
        self.spin = False
        self.spin_t = 0

    def refresh_height(self):
        if self.crouch and self.on_ground:
            target = CROUCH_H
        elif self.big:
            target = BIG_H
        else:
            target = STAND_H
        if target != self.h:
            dy = self.h - target
            self.h = target
            if dy > 0:
                self.y += dy  # crouch: keep feet planted

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def hurt(self, audio: Audio):
        if self.invuln > 0 or self.dead:
            return
        if self.big:
            self.big = False
            self.refresh_height()
            self.invuln = INVULN
            audio.play("hurt")
            return
        self.dead = True
        self.vy = -8
        self.lives -= 1
        audio.play("hurt")


class Enemy:
    __slots__ = ("x", "y", "vx", "vy", "w", "h", "kind", "alive", "facing")

    def __init__(self, x, y, kind):
        self.x, self.y = float(x), float(y)
        self.vx = -1.05 if kind != "flyer" else -0.85
        self.vy = 0.0
        self.w, self.h = 28, 28
        self.kind = kind
        self.alive = True
        self.facing = -1

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)


class Projectile:
    __slots__ = ("x", "y", "vx", "vy", "life", "hostile")

    def __init__(self, x, y, vx, vy, life=120, hostile=True):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = life
        self.hostile = hostile

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), 12, 12)


class Boss:
    """Bowser Jr (worlds 1–7) or Kamek (world 8)."""

    def __init__(self, kind: str, x: float, y: float):
        self.kind = kind  # "jr" | "kamek"
        self.x, self.y = x, y
        self.vx = -2.0
        self.vy = 0.0
        self.w = 40 if kind == "jr" else 44
        self.h = 44 if kind == "jr" else 48
        self.hp = 3 if kind == "jr" else 6
        self.max_hp = self.hp
        self.alive = True
        self.timer = 0
        self.phase = 0
        self.invuln = 0
        self.ground_y = y

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update(self, level, projectiles: list, audio: Audio):
        if not self.alive:
            return
        self.timer += 1
        if self.invuln > 0:
            self.invuln -= 1
        wpx = level["width"] * TILE
        if self.kind == "jr":
            self.x += self.vx
            if self.x < 64 or self.x > wpx - 80:
                self.vx *= -1
            if self.timer % 90 == 0:
                self.vy = -10
            self.vy += GRAVITY_FALL * 0.9
            self.y += self.vy
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self.vy = 0
            if self.timer % 70 == 35:
                projectiles.append(Projectile(self.x + self.w / 2, self.y + 10, self.vx * 1.5, 0, 100))
                audio.play("bump")
        else:
            # Kamek: teleport + magic
            if self.timer % 100 == 0:
                self.x = random.uniform(80, wpx - 120)
                self.y = random.choice([self.ground_y, self.ground_y - 96, self.ground_y - 160])
                audio.play("power")
            if self.timer % 50 == 20:
                for ang in (-0.4, 0.0, 0.4):
                    projectiles.append(Projectile(
                        self.x + self.w / 2, self.y + 16,
                        math.cos(ang) * -4.5, math.sin(ang) * 3.0, 110,
                    ))
                audio.play("bump")

    def hit(self, audio: Audio) -> bool:
        if self.invuln > 0 or not self.alive:
            return False
        self.hp -= 1
        self.invuln = 45
        audio.play("boss_hit")
        if self.hp <= 0:
            self.alive = False
            audio.play("win")
            return True
        return False


# ── collision helpers ─────────────────────────────────────────────────────
def tile_at(tiles, tx, ty, w, h):
    """Safe tile read — always returns an int tile id (never a row/list).
    Below the map is void (AIR) so actors fall into pits (NSMB2).
    Left/right / above stay solid walls.
    """
    if not tiles:
        return HARD
    if ty >= h or ty >= len(tiles):
        return AIR  # pit void
    if ty < 0:
        return HARD
    if tx < 0 or tx >= w:
        return HARD
    row = tiles[ty]
    if not isinstance(row, (list, tuple)):
        return HARD
    if tx >= len(row):
        return HARD
    t = row[tx]
    if isinstance(t, bool) or not isinstance(t, int):
        return HARD
    return t


def iter_solid_tiles(tiles, x, y, bw, bh, w, h):
    """Yield (tx, ty, kind, tile_x, tile_y) for solids overlapping float AABB."""
    if bw <= 0 or bh <= 0:
        return
    x0 = int(math.floor(x / TILE))
    x1 = int(math.floor((x + bw - 1e-6) / TILE))
    y0 = int(math.floor(y / TILE))
    y1 = int(math.floor((y + bh - 1e-6) / TILE))
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            t = tile_at(tiles, tx, ty, w, h)
            if t in SOLID or t == SPIKE:
                yield tx, ty, t, float(tx * TILE), float(ty * TILE)


# ── game ──────────────────────────────────────────────────────────────────
class Game:
    def __init__(self, screen, audio: Audio):
        self.screen = screen
        self.audio = audio
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Courier New", 22)
        self.font_sm = pygame.font.SysFont("Courier New", 16)
        self.font_big = pygame.font.SysFont("Georgia", 42, bold=True)
        self.levels = build_all_levels()
        self.tile_cache: dict = {}
        self.pframes = player_frames()
        self.jr_img = jr_surf()
        self.kamek_img = kamek_surf()
        self.enemy_img = {
            "goomba": self._enemy(PLAYER_C),
            "koopa": self._enemy(JR_C),
            "flyer": self._enemy((180, 100, 100)),
        }
        self.world = 1
        self.stage = 1
        self.cam_x = 0.0
        self.state = "boot"  # boot splash → menu | help | play | ...
        self.boot_t = BOOT_FRAMES
        self.menu_i = 0
        self.menu_items = ("Play Game", "Help", "Exit")
        self.msg_t = 0
        self.msg = ""
        self.player: Optional[Player] = None
        self.enemies: list = []
        self.boss: Optional[Boss] = None
        self.projectiles: list = []
        self.level = None
        self.time_left = 400
        self.tick = 0

    def _enemy(self, col):
        s = make_surf(28, 28)
        pygame.draw.ellipse(s, col, (2, 6, 24, 20))
        pygame.draw.rect(s, (30, 30, 30), (8, 12, 3, 3))
        pygame.draw.rect(s, (30, 30, 30), (17, 12, 3, 3))
        return s

    def get_tile_surf(self, kind, theme):
        if type(kind) is not int or type(theme) is not int:
            kind, theme = AIR, THEME_OVER
        key = (kind, theme)
        if key not in self.tile_cache:
            self.tile_cache[key] = tile_surf(kind, theme)
        return self.tile_cache[key]

    def start_stage(self, w, s):
        self.world, self.stage = w, s
        self.level = self.levels[stage_key(w, s)]
        # fresh copy of mutable tiles
        tiles = [row[:] for row in self.level["tiles"]]
        self.level = {**self.level, "tiles": tiles}
        sx, sy = self.level["spawn"]
        lives = self.player.lives if self.player else 5
        coins = self.player.coins if self.player else 0
        score = self.player.score if self.player else 0
        self.player = Player(sx, sy)
        self.player.lives = lives
        self.player.coins = coins
        self.player.score = score
        self.enemies = [Enemy(e["x"], e["y"], e["kind"]) for e in self.level["enemies"]]
        self.projectiles = []
        self.boss = None
        if self.level.get("boss"):
            gy = (self.level["height"] - 2) * TILE - 44
            self.boss = Boss(self.level["boss"], self.level["width"] * TILE * 0.55, gy)
            self.audio.set_track("boss")
        else:
            th = self.level["theme"]
            if th == THEME_UNDER:
                self.audio.set_track("under")
            elif th == THEME_CASTLE:
                self.audio.set_track("castle")
            else:
                self.audio.set_track("over")
        self.time_left = self.level["time"]
        self.cam_x = 0.0
        self.state = "play"
        self.tick = 0

    def next_stage(self):
        if self.stage < 4:
            self.start_stage(self.world, self.stage + 1)
        elif self.world < 8:
            self.start_stage(self.world + 1, 1)
        else:
            self.state = "win"
            self.audio.set_track("off")
            self.audio.play("win")

    def _fall_in_pit(self):
        """NSMB2-style pit: lose a life → respawn at stage start, or game over."""
        p = self.player
        p.lives -= 1
        p.dead = False
        p.vx = p.vy = 0.0
        self.audio.play("hurt")
        if p.lives <= 0:
            p.dead = True
            self.state = "gameover"
            self.audio.set_track("off")
            return
        # Respawn at course start; NPCs reset with the stage
        self.start_stage(self.world, self.stage)

    def _pit_y(self) -> float:
        # Just past the bottom row — NSMB2-style void
        return self.level["height"] * TILE + 8

    def _after_death_fall(self):
        p = self.player
        if p.lives <= 0:
            self.state = "gameover"
            self.audio.set_track("off")
        else:
            self.start_stage(self.world, self.stage)

    # ── physics ───────────────────────────────────────────────────────────
    def move_actor(self, ent, tiles, w, h, is_player=False):
        """Axis-separated float AABB. X inset so floors never resolve as walls."""
        world_w = w * TILE

        # --- X ---
        ent.x += ent.vx
        if is_player:
            ent.x = clamp(ent.x, 0.0, float(world_w - ent.w))
        ix = WALL_INSET
        bh = max(1.0, ent.h - ix * 2)
        for tx, ty, t, tl, tt in iter_solid_tiles(tiles, ent.x, ent.y + ix, ent.w, bh, w, h):
            if t == SPIKE and is_player:
                self.player.hurt(self.audio)
            if ent.vx > 0:
                ent.x = tl - ent.w
                ent.vx = 0.0
            elif ent.vx < 0:
                ent.x = tl + TILE
                ent.vx = 0.0

        # --- Y ---
        ent.y += ent.vy
        if is_player:
            self.player.on_ground = False
        pad = 2.0
        bw = max(1.0, ent.w - pad * 2)
        for tx, ty, t, tl, tt in iter_solid_tiles(tiles, ent.x + pad, ent.y, bw, ent.h, w, h):
            if t == SPIKE and is_player:
                self.player.hurt(self.audio)
            feet = ent.y + ent.h
            head = ent.y
            if ent.vy >= 0.0 and feet >= tt and head < tt:
                # land on top (allow slight penetration from gravity step)
                if feet <= tt + max(ent.vy, GRAVITY_FALL) + 6.0:
                    ent.y = tt - ent.h
                    ent.vy = 0.0
                    if is_player:
                        self.player.on_ground = True
            elif ent.vy < 0.0 and head <= tt + TILE and feet > tt + TILE:
                ent.y = tt + TILE
                ent.vy = 0.0
                if is_player and t in (BRICK, QBLOCK):
                    self._bump_block(tx, ty)

        if is_player:
            ent.x = clamp(ent.x, 0.0, float(world_w - ent.w))

    def _bump_block(self, tx, ty):
        tiles = self.level["tiles"]
        h = len(tiles)
        w = len(tiles[0]) if h else 0
        if ty < 0 or tx < 0 or ty >= h or tx >= w:
            return
        t = tiles[ty][tx]
        if not isinstance(t, int):
            return
        if t == BRICK:
            tiles[ty][tx] = AIR
            self.player.score += 50
            self.audio.play("bump")
        elif t == QBLOCK:
            tiles[ty][tx] = QUSED
            self.player.coins += 1
            self.player.score += 200
            self.audio.play("coin")
            if self.player.coins % 5 == 0:
                self.player.big = True
                self.player.refresh_height()
                self.audio.play("power")

    def _probe_wall(self, p, tiles, w, h) -> int:
        """Return -1 if solid on left, +1 on right, else 0 (airborne wall check)."""
        if p.on_ground:
            return 0
        mid_y = p.y + p.h * 0.5
        # left
        if tile_at(tiles, int((p.x - 2) / TILE), int(mid_y / TILE), w, h) in SOLID:
            return -1
        # right
        if tile_at(tiles, int((p.x + p.w + 2) / TILE), int(mid_y / TILE), w, h) in SOLID:
            return 1
        return 0

    def _pound_break(self, p, tiles, w, h):
        """Ground-pound: smash brick under feet."""
        tx = int((p.x + p.w * 0.5) / TILE)
        ty = int((p.y + p.h + 2) / TILE)
        if 0 <= ty < h and 0 <= tx < w and tiles[ty][tx] == BRICK:
            tiles[ty][tx] = AIR
            p.score += 50
            self.audio.play("bump")

    def update_play(self, keys, events):
        p = self.player
        tiles = self.level["tiles"]
        w, h = self.level["width"], self.level["height"]
        self.tick += 1
        if self.tick % 60 == 0:
            self.time_left -= 1
            if self.time_left <= 0:
                p.dead = True
                p.lives -= 1
                self.audio.play("hurt")

        spin_pressed = False
        pound_pressed = False
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = "pause"
                    return
                if e.key in (pygame.K_z, pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    p.jbuf = JUMP_BUF
                if e.key in (pygame.K_c, pygame.K_LCTRL):
                    spin_pressed = True
                    p.jbuf = JUMP_BUF
                if e.key in (pygame.K_DOWN, pygame.K_s) and not p.on_ground:
                    pound_pressed = True
                if e.key == pygame.K_m:
                    self.audio.toggle_mute()

        run = keys[pygame.K_LSHIFT] or keys[pygame.K_x]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        ax = 0.0
        if not (p.crouch and p.on_ground and not p.slide):
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                ax = -1.0
                p.facing = -1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                ax = 1.0
                p.facing = 1

        # ── crouch / slide (NSMB2) ──
        was_ground = p.on_ground
        if p.on_ground and down and not p.slide:
            p.crouch = True
            if abs(p.vx) >= SLIDE_MIN_V:
                p.slide = True
                p.slide_t = 28
                self.audio.play("bump")
        elif not down or not p.on_ground:
            if p.crouch and p.on_ground:
                # standup if ceiling clear
                head = tile_at(tiles, int((p.x + p.w / 2) / TILE), int((p.y - 4) / TILE), w, h)
                if head not in SOLID:
                    p.crouch = False
            elif not p.on_ground:
                p.crouch = False
        if p.slide:
            p.slide_t -= 1
            p.vx *= SLIDE_FRIC
            if p.slide_t <= 0 or abs(p.vx) < 0.4 or not p.on_ground:
                p.slide = False
            p.crouch = p.on_ground
        p.refresh_height()

        # ── P-meter ──
        if p.on_ground and run and abs(p.vx) > MAX_WALK * 0.85 and ax * p.vx > 0:
            p.p_meter = min(P_MAX, p.p_meter + P_BUILD)
        else:
            p.p_meter = max(0.0, p.p_meter - P_DECAY)

        # ── horizontal (skid / run / air) ──
        if p.slide:
            pass  # momentum only
        elif ax != 0.0:
            if p.on_ground and p.vx * ax < 0.0:
                p.vx += ax * SKID_ACC
            elif p.on_ground:
                p.vx += ax * (RUN_ACC if run else WALK_ACC)
            else:
                p.vx += ax * AIR_ACC
        max_v = MAX_WALK
        if run:
            max_v = MAX_P if p.p_meter >= P_MAX else MAX_RUN
        p.vx = clamp(p.vx, -max_v, max_v)
        if ax == 0.0 and not p.slide:
            p.vx *= FRICTION if p.on_ground else AIR_FRIC
            if abs(p.vx) < 0.08:
                p.vx = 0.0

        if p.on_ground:
            p.coyote = COYOTE
            if p.chain_timer > 0:
                p.chain_timer -= 1
            else:
                p.jump_chain = 0
            if p.pound:
                self._pound_break(p, tiles, w, h)
                p.pound = False
                self.audio.play("stomp")
            p.spin = False
        else:
            p.coyote = max(0, p.coyote - 1)
        p.jbuf = max(0, p.jbuf - 1)
        if p.spin_t > 0:
            p.spin_t -= 1
            if p.spin_t <= 0:
                p.spin = False

        # ground pound start
        if pound_pressed and not p.on_ground and not p.pound:
            p.pound = True
            p.vy = 4.0
            p.vx *= 0.3
            p.spin = False
            self.audio.play("bump")

        jump_held = keys[pygame.K_z] or keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]
        # wall probe (pre-move approx from last frame wall_dir + position)
        p.wall_dir = self._probe_wall(p, tiles, w, h)

        # wall jump
        if p.jbuf > 0 and p.wall_dir != 0 and not p.on_ground:
            p.vy = JUMP_WALL
            p.vx = -p.wall_dir * WALL_JUMP_PUSH
            p.facing = -p.wall_dir
            p.jbuf = 0
            p.jump_cut = False
            p.pound = False
            p.spin = False
            self.audio.play("jump")
        # ground / coyote jump (+ triple / long / spin)
        elif p.jbuf > 0 and p.coyote > 0:
            long_j = p.crouch and abs(p.vx) >= SLIDE_MIN_V
            if spin_pressed or keys[pygame.K_c] or keys[pygame.K_LCTRL]:
                p.spin = True
                p.spin_t = 40
                p.vy = JUMP_V
            elif long_j:
                p.vy = JUMP_LONG
                p.vx = p.facing * max(abs(p.vx), MAX_RUN) * 1.15
                p.crouch = False
                p.slide = False
            else:
                # chain: 0→1→2→3
                if p.chain_timer > 0 and abs(p.vx) > MAX_WALK * 0.5:
                    p.jump_chain = min(3, p.jump_chain + 1)
                else:
                    p.jump_chain = 1
                if p.jump_chain >= 3:
                    p.vy = JUMP_V3
                elif p.jump_chain == 2:
                    p.vy = JUMP_V2
                else:
                    p.vy = JUMP_V
                # P-speed jump boost
                if p.p_meter >= P_MAX:
                    p.vy -= 0.6
            p.on_ground = False
            p.coyote = 0
            p.jbuf = 0
            p.jump_cut = False
            p.pound = False
            p.refresh_height()
            self.audio.play("jump")

        if not jump_held and p.vy < 0 and not p.jump_cut and not p.pound:
            p.vy *= JUMP_CUT
            p.jump_cut = True
        if p.on_ground:
            p.jump_cut = False

        # gravity
        if p.pound:
            p.vy += GRAVITY_POUND
            p.vy = min(p.vy, MAX_POUND)
        elif p.wall_dir != 0 and p.vy > 0:
            p.vy += GRAVITY_FALL * 0.35
            p.vy = min(p.vy, WALL_SLIDE_MAX)
        elif p.vy < 0.0 and jump_held and not p.jump_cut:
            p.vy += GRAVITY_UP
            p.vy = min(p.vy, MAX_FALL)
        else:
            p.vy += GRAVITY_FALL
            p.vy = min(p.vy, MAX_FALL)

        if p.invuln > 0:
            p.invuln -= 1

        if not p.dead:
            self.move_actor(p, tiles, w, h, is_player=True)
            # landed → open triple window
            if p.on_ground and not was_ground:
                p.chain_timer = TRIPLE_WINDOW
            p.wall_dir = self._probe_wall(p, tiles, w, h)
            if p.y > self._pit_y():
                self._fall_in_pit()
                return
        else:
            p.vy += GRAVITY_FALL
            p.y += p.vy
            if p.y > self._pit_y() + 120:
                self._after_death_fall()
                return

        # coins pickup
        r = p.rect()
        tx0, ty0 = r.centerx // TILE, r.centery // TILE
        for ty in range(ty0 - 1, ty0 + 2):
            for tx in range(tx0 - 1, tx0 + 2):
                if 0 <= tx < w and 0 <= ty < h and tiles[ty][tx] == COIN:
                    tiles[ty][tx] = AIR
                    p.coins += 1
                    p.score += 100
                    self.audio.play("coin")

        # enemies — walk off ledges (NSMB2); die in pits
        pit_y = self._pit_y()
        for en in self.enemies:
            if not en.alive:
                continue
            if en.kind == "flyer":
                en.y += math.sin(self.tick * 0.08 + en.x) * 0.8
                en.x += en.vx
                en.vy += GRAVITY_FALL * 0.15  # slight drift down over gaps
            else:
                en.vy += GRAVITY_FALL
                # wall bounce only — do NOT turn at cliff edges (fall into pits)
                ahead = int(en.x + en.w / 2 + en.vx * 8) // TILE
                mid_y = int(en.y + en.h / 2) // TILE
                if tile_at(tiles, ahead, mid_y, w, h) in SOLID:
                    en.vx *= -1
                    en.facing *= -1
                en.x += en.vx
                en.y += en.vy
                # Land only if ground is under the enemy's center (no cliff cling)
                mid_x = en.x + en.w * 0.5
                for _tx, _ty, _t, tl, tt in iter_solid_tiles(
                    tiles, en.x + 2, en.y, max(1.0, en.w - 4), en.h, w, h
                ):
                    if not (tl <= mid_x < tl + TILE):
                        continue
                    if en.vy >= 0.0 and en.y + en.h >= tt and en.y < tt:
                        if en.y + en.h <= tt + max(en.vy, GRAVITY_FALL) + 6.0:
                            en.y = tt - en.h
                            en.vy = 0.0
                            break
            # pit death for NPCs
            if en.y > pit_y:
                en.alive = False
                continue
            # stomp / hurt
            if p.invuln > 0 or p.dead:
                continue
            if p.rect().colliderect(en.rect()):
                # ground pound / spin / stomp
                if p.pound or (p.spin and p.vy >= 0) or (p.vy > 0 and p.y + p.h - 8 < en.y + 10):
                    en.alive = False
                    if not p.pound:
                        p.vy = STOMP_BOUNCE
                    p.score += 200
                    self.audio.play("stomp")
                else:
                    p.hurt(self.audio)

        # boss
        if self.boss and self.boss.alive:
            self.boss.update(self.level, self.projectiles, self.audio)
            if p.rect().colliderect(self.boss.rect()) and p.invuln <= 0 and not p.dead:
                if p.vy > 0 and p.y + p.h - 10 < self.boss.y + 16:
                    if self.boss.hit(self.audio):
                        p.score += 5000
                        self.msg = "BOSS CLEAR!"
                        self.msg_t = 90
                        self.state = "clear"
                        self.audio.play("clear")
                    else:
                        p.vy = STOMP_BOUNCE
                else:
                    p.hurt(self.audio)
        elif self.boss and not self.boss.alive and self.state == "play":
            self.msg = "WORLD CLEAR!" if self.world < 8 else "KAMEK DEFEATED!"
            self.msg_t = 90
            self.state = "clear"
            self.audio.play("clear")

        # projectiles
        pr = p.rect()
        for proj in self.projectiles[:]:
            proj.x += proj.vx
            proj.y += proj.vy
            proj.life -= 1
            if proj.life <= 0:
                self.projectiles.remove(proj)
                continue
            if proj.hostile and pr.colliderect(proj.rect()) and p.invuln <= 0 and not p.dead:
                p.hurt(self.audio)
                self.projectiles.remove(proj)

        # goal (non-boss)
        if not self.level.get("boss") and p.x + p.w >= self.level["goal_x"] and not p.dead:
            p.score += 1000 + self.time_left * 10
            self.audio.play("clear")
            self.state = "clear"
            self.msg = f"COURSE CLEAR  {self.world}-{self.stage}"
            self.msg_t = 90

        # camera
        target = p.x - W * 0.35
        self.cam_x += (target - self.cam_x) * 0.12
        self.cam_x = clamp(self.cam_x, 0, max(0, self.level["width"] * TILE - W))

        p.anim += abs(p.vx) * 0.15

    # ── draw ──────────────────────────────────────────────────────────────
    def sky_color(self):
        th = self.level["theme"] if self.level else THEME_OVER
        if th == THEME_UNDER:
            return (20, 24, 28)
        if th == THEME_CASTLE:
            return (28, 24, 32)
        return SKY

    def draw_play(self):
        self.screen.fill(self.sky_color())
        tiles = self.level["tiles"]
        theme = self.level["theme"]
        cam = int(self.cam_x)
        x0 = max(0, cam // TILE - 1)
        x1 = min(self.level["width"], (cam + W) // TILE + 2)
        for ty in range(self.level["height"]):
            for tx in range(x0, x1):
                t = tiles[ty][tx]
                if t == AIR:
                    continue
                surf = self.get_tile_surf(t, theme)
                self.screen.blit(surf, (tx * TILE - cam, ty * TILE))

        for en in self.enemies:
            if not en.alive:
                continue
            img = self.enemy_img.get(en.kind, self.enemy_img["goomba"])
            self.screen.blit(img, (int(en.x) - cam, int(en.y)))

        if self.boss and self.boss.alive:
            img = self.kamek_img if self.boss.kind == "kamek" else self.jr_img
            if self.boss.invuln % 4 < 2:
                self.screen.blit(img, (int(self.boss.x) - cam, int(self.boss.y)))
            # HP bar
            bw = 120
            bx = W // 2 - bw // 2
            pygame.draw.rect(self.screen, (40, 40, 40), (bx, 48, bw, 10))
            frac = self.boss.hp / self.boss.max_hp
            pygame.draw.rect(self.screen, JR_C if self.boss.kind == "jr" else KAMEK_C, (bx, 48, int(bw * frac), 10))
            name = "KAMEK" if self.boss.kind == "kamek" else "BOWSER JR"
            self.screen.blit(self.font_sm.render(name, True, UI_FG), (bx, 30))

        for proj in self.projectiles:
            pygame.draw.circle(self.screen, (240, 200, 80), (int(proj.x) - cam, int(proj.y)), 6)

        p = self.player
        if p and (p.invuln == 0 or p.invuln % 4 < 2):
            fi = int(p.anim) % len(self.pframes)
            img = self.pframes[fi]
            th = max(16, int(p.h))
            tw = 28 if not p.crouch else 26
            if p.big or p.crouch or p.h != 40:
                img = pygame.transform.scale(img, (tw, th))
            if p.facing < 0:
                img = pygame.transform.flip(img, True, False)
            if p.spin and (self.tick % 4 < 2):
                img = pygame.transform.rotate(img, (self.tick * 20) % 360)
            self.screen.blit(img, (int(p.x) - cam, int(p.y)))

        # HUD + P-meter
        hud = f"WORLD {self.world}-{self.stage}   MARIO x{p.lives}   COINS {p.coins:02d}   SCORE {p.score:06d}   TIME {self.time_left:03d}"
        self.screen.blit(self.font_sm.render(hud, True, UI_FG), (12, 8))
        # P meter bar
        pygame.draw.rect(self.screen, (40, 40, 40), (12, 28, 104, 8))
        pw = int(100 * (p.p_meter / P_MAX))
        col = (220, 180, 60) if p.p_meter >= P_MAX else (180, 140, 70)
        pygame.draw.rect(self.screen, col, (14, 30, pw, 4))
        self.screen.blit(self.font_sm.render("P", True, UI_DIM), (120, 24))
        tip = "Z jump · X run · C spin · Down crouch/pound · wall jump · Esc · M"
        self.screen.blit(self.font_sm.render(tip, True, UI_DIM), (12, H - 22))

    def draw_menu(self):
        self.screen.fill(UI_BG)
        # boring decorative strips
        for y in range(0, H, 8):
            a = 30 + (y // 8) % 2 * 8
            pygame.draw.rect(self.screen, (a, a + 2, a + 4), (0, y, W, 4))
        title = self.font_big.render(TITLE, True, UI_FG)
        self.screen.blit(title, title.get_rect(center=(W // 2, 120)))
        sub = self.font.render(f"by {AUTHOR}  ·  {VERSION}", True, ACCENT)
        self.screen.blit(sub, sub.get_rect(center=(W // 2, 175)))
        eng = self.font_sm.render(f"{ENGINE}", True, UI_DIM)
        self.screen.blit(eng, eng.get_rect(center=(W // 2, 210)))

        for i, label in enumerate(self.menu_items):
            sel = i == self.menu_i
            col = ACCENT if sel else UI_FG
            txt = self.font.render(("> " if sel else "  ") + label, True, col)
            self.screen.blit(txt, txt.get_rect(center=(W // 2, 290 + i * 44)))

        foot = self.font_sm.render("[c] 1999-2026  [c] nintendo 1985-2026", True, UI_DIM)
        self.screen.blit(foot, foot.get_rect(center=(W // 2, H - 40)))

    def draw_help(self):
        self.screen.fill(UI_BG)
        lines = [
            "HELP — Mario Forever Boring Edition",
            "",
            "Move: Left/Right or A/D",
            "Jump: Z / Space / Up / W  (hold = higher)",
            "Run: X or Left Shift   ·  Spin jump: C / Ctrl",
            "Crouch / Slide: Down/S  ·  Ground pound: Down in air",
            "Wall jump: jump while sliding on a wall",
            "Pause: Esc   Mute OST: M",
            "",
            "Boring Engine — full NSMB2 homage:",
            "  P-meter · triple jump · long jump · wall jump",
            "  ground pound · crouch/slide · coyote · jump buffer",
            "60 FPS · Worlds 1-1 … 8-4 · Jr bosses · Kamek 8-4",
            "",
            "Press Esc or Enter to return",
        ]
        y = 60
        for line in lines:
            self.screen.blit(self.font_sm.render(line, True, UI_FG), (80, y))
            y += 24

    def draw_overlay(self, title: str, sub: str):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.screen.blit(veil, (0, 0))
        t = self.font_big.render(title, True, UI_FG)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 30)))
        s = self.font.render(sub, True, ACCENT)
        self.screen.blit(s, s.get_rect(center=(W // 2, H // 2 + 30)))

    def draw_boot(self):
        """Startup popup: powered by Boring Engine."""
        self.screen.fill((24, 26, 30))
        # backdrop strips
        for y in range(0, H, 10):
            pygame.draw.rect(self.screen, (32 + (y // 10) % 2 * 6, 34, 38), (0, y, W, 5))
        # popup card
        bw, bh = 520, 200
        bx, by = W // 2 - bw // 2, H // 2 - bh // 2
        pygame.draw.rect(self.screen, (48, 50, 56), (bx, by, bw, bh))
        pygame.draw.rect(self.screen, ACCENT, (bx, by, bw, bh), 3)
        pygame.draw.rect(self.screen, (70, 72, 80), (bx + 8, by + 8, bw - 16, bh - 16), 1)
        title = self.font_big.render(ENGINE_TAG, True, UI_FG)
        self.screen.blit(title, title.get_rect(center=(W // 2, H // 2 - 24)))
        sub = self.font_sm.render("full NSMB2 homage · 60 FPS · FILES=OFF", True, UI_DIM)
        self.screen.blit(sub, sub.get_rect(center=(W // 2, H // 2 + 28)))
        skip = self.font_sm.render("Enter / Z — continue", True, ACCENT)
        self.screen.blit(skip, skip.get_rect(center=(W // 2, H // 2 + 58)))

    # ── main loop ─────────────────────────────────────────────────────────
    def run(self):
        self.audio.set_track("off")  # no OST on boot/menu
        while True:
            dt = self.clock.tick(FPS)
            events = pygame.event.get()
            keys = pygame.key.get_pressed()
            for e in events:
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_m and self.state not in ("play", "boot"):
                    self.audio.toggle_mute()

            if self.state == "boot":
                self.boot_t -= 1
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (
                        pygame.K_RETURN, pygame.K_SPACE, pygame.K_z, pygame.K_ESCAPE
                    ):
                        self.boot_t = 0
                if self.boot_t <= 0:
                    self.state = "menu"
                    self.audio.set_track("off")
                self.draw_boot()

            elif self.state == "menu":
                # OST off — menus stay silent
                for e in events:
                    if e.type == pygame.KEYDOWN:
                        if e.key in (pygame.K_UP, pygame.K_w):
                            self.menu_i = (self.menu_i - 1) % len(self.menu_items)
                        elif e.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_i = (self.menu_i + 1) % len(self.menu_items)
                        elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                            choice = self.menu_items[self.menu_i]
                            if choice == "Play Game":
                                self.player = None
                                self.start_stage(1, 1)
                            elif choice == "Help":
                                self.state = "help"
                            else:
                                return
                        elif e.key == pygame.K_ESCAPE:
                            return
                self.draw_menu()

            elif self.state == "help":
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                        self.state = "menu"
                        self.audio.set_track("off")
                self.draw_help()

            elif self.state == "play":
                self.audio.update(dt)
                self.update_play(keys, events)
                if self.state == "play":
                    self.draw_play()

            elif self.state == "pause":
                self.draw_play()
                self.draw_overlay("PAUSED", "Enter resume · Esc menu")
                for e in events:
                    if e.type == pygame.KEYDOWN:
                        if e.key in (pygame.K_RETURN, pygame.K_z):
                            self.state = "play"
                        elif e.key == pygame.K_ESCAPE:
                            self.state = "menu"
                            self.audio.set_track("off")

            elif self.state == "clear":
                self.draw_play()
                self.draw_overlay(self.msg or "COURSE CLEAR", "Enter — next")
                self.msg_t -= 1
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                        self.next_stage()
                if self.msg_t < -180:
                    self.next_stage()

            elif self.state == "gameover":
                self.screen.fill(UI_BG)
                self.draw_overlay("GAME OVER", "Enter — menu")
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        self.state = "menu"
                        self.audio.set_track("off")

            elif self.state == "win":
                self.screen.fill(UI_BG)
                self.draw_overlay("YOU WIN!", "Kamek defeated · Enter — menu")
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        self.state = "menu"
                        self.audio.set_track("off")

            pygame.display.flip()


def self_test() -> int:
    """Headless smoke: build levels + one physics tick."""
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.mixer.init(22050, -16, 1, 512)
    except Exception:
        pass
    screen = pygame.display.set_mode((W, H))
    audio = Audio()
    g = Game(screen, audio)
    assert len(g.levels) == 32
    assert g.levels["8-4"]["boss"] == "kamek"
    assert g.levels["1-4"]["boss"] == "jr"
    assert g.levels["3-2"]["boss"] is None
    g.start_stage(1, 1)
    g.update_play(pygame.key.get_pressed(), [])
    g.start_stage(8, 4)
    assert g.boss and g.boss.kind == "kamek"
    print("OK", TITLE, VERSION, "levels=32", f"py={sys.version.split()[0]}")
    pygame.quit()
    return 0


def main() -> int:
    if "--test" in sys.argv:
        return self_test()
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.mixer.init(22050, -16, 1, 512)
    except Exception:
        pass
    pygame.display.set_caption(f"{TITLE} by {AUTHOR} {VERSION}")
    screen = pygame.display.set_mode((W, H))
    audio = Audio()
    Game(screen, audio).run()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
