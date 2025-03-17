import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import websockets

@dataclass(frozen=True, kw_only=True)
class Coords:
    int_repr: int

    def to_xy(self) -> tuple[int, int]:
        return (self.int_repr // 8), (self.int_repr % 8)


class Color(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2
    ORANGE = 3
    YELLOW = 4
    PINK = 5
    WHITE = 6


class WhichPhase(Enum):
    SELECTING = "Selecting"
    P1_TURN = "P1 Turn"
    P2_TURN = "P2 Turn"


@dataclass
class GameState:
    pegs: dict[Color, Coords]
    thaler_pos: Coords
    current_player: int
    p1_color: Optional[Color] = None
    p2_color: Optional[Color] = None
    current_phase: Optional[WhichPhase] = None

    def __init__(self):
        self.thaler_pos, self.pegs = generate_peg_positions()
        self.current_player = 0


def generate_peg_positions() -> tuple[Coords, dict[Color, Coords]]:
    all_pos = random.sample(list(range(0, 64)), k=8)
    color_pos = dict(enumerate(all_pos[:7]))
    thaler_pos = all_pos[7]
    return thaler_pos, color_pos


if __name__ == "__main__":
    init_state = GameState()
    print(init_state)
