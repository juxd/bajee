import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import websockets

@dataclass(frozen=True)
class Coords:
    int_repr: int

    def to_xy(self) -> tuple[int, int]:
        return (self.int_repr // 7), (self.int_repr % 7)


class Color(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2
    ORANGE = 3
    YELLOW = 4
    PINK = 5
    WHITE = 6

    def to_string(self):
        match self:
            case self.__class__.RED:
                return "R"
            case self.__class__.GREEN:
                return "G"
            case self.__class__.BLUE:
                return "B"
            case self.__class__.ORANGE:
                return "O"
            case self.__class__.YELLOW:
                return "Y"
            case self.__class__.PINK:
                return "P"
            case self.__class__.WHITE:
                return "W"

COLOR_CODES = {
    Color.RED: "\033[31m",
    Color.BLUE: "\033[34m",
    Color.GREEN: "\033[32m",
    Color.YELLOW: "\033[33m",
    Color.ORANGE: "\033[38;5;214m",  # ANSI code for orange
    Color.PINK: "\033[38;5;213m",    # ANSI code for pink
    Color.WHITE: "\033[37m",
}

RESET_CODE = "\033[0m"

class WhichPhase(Enum):
    SELECTING = "Selecting"
    P1_TURN = "P1 Turn"
    P2_TURN = "P2 Turn"


def color_cell(cell_content: str, color: Color | str) -> str:
    esc = RESET_CODE + (color if isinstance(color, str) else COLOR_CODES[color])
    return esc + cell_content

def row(cells: list[str]) -> str:
    return "".join(cells) + RESET_CODE

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

    def to_board(self):
        board = [color_cell("  ", [RESET_CODE, "\033[100m"][idx % 2]) for idx in range(0, 49)]
        for color, peg in self.pegs.items():
            board[peg.int_repr] = color_cell(f"{color.to_string()} ", COLOR_CODES[color])
        rows = [row(board[r:r+7]) for r in range(0, 49, 7)]
        return "\n".join(rows)


def generate_peg_positions() -> tuple[Coords, dict[Color, Coords]]:
    all_pos = random.sample(list(range(0, 49)), k=8)
    color_pos = { Color(idx): Coords(pos) for idx, pos in enumerate(all_pos[:7]) }
    thaler_pos = Coords(all_pos[7])
    return thaler_pos, color_pos


if __name__ == "__main__":
    init_state = GameState()
    print(init_state)
    print(init_state.to_board())
