import pygame
import sys
from dataclasses import dataclass
from typing import List, Tuple, Optional

# -----------------------------
# Chess — Single-file pygame app
# -----------------------------
# Features
# - 100% legal move validation (incl. check, checkmate, stalemate)
# - Castling, en passant, promotion
# - Move highlighting & undo (Ctrl+Z)
# - Simple status text (turn, check, result)
# - No external assets: uses Unicode chess symbols
#
# Run:
#   pip install pygame
#   python main.py

# Board/pixel config
TILE_SIZE = 80
BOARD_SIZE = TILE_SIZE * 8
PADDING = 16
INFO_HEIGHT = 56
WIN_W, WIN_H = BOARD_SIZE, BOARD_SIZE + INFO_HEIGHT
FPS = 60

# Colors
C_LIGHT = (240, 217, 181)
C_DARK = (181, 136, 99)
C_SELECT = (246, 246, 105)
C_HINT = (106, 162, 214)
C_LAST = (246, 246, 105)
C_TEXT = (30, 30, 30)
C_OVER = (
