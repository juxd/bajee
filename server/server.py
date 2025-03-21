import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from dataclasses_json import dataclass_json


@dataclass_json
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
    Color.PINK: "\033[38;5;213m",  # ANSI code for pink
    Color.WHITE: "\033[37m",
}

RESET_CODE = "\033[0m"

THALER_CODE = "\033[47m"


class WhichPhase(Enum):
    SELECTING = "Selecting"
    P1_TURN = "P1 Turn"
    P2_TURN = "P2 Turn"


class InvalidAction:
    message: str

    def __init__(self, message: str):
        self.message = message


Cell = Color | Literal["Thaler"] | None


@dataclass_json
@dataclass
class GameState:
    pegs: dict[Color, Coords] = field(
        metadata={
            "dataclasses_json": {
                "encoder": lambda d: {k.value: v.int_repr for k, v in d.items()},
                "decoder": lambda d: {Color(int(k)): Coords(v) for k, v in d.items()},
            }
        }
    )
    thaler_pos: Coords
    current_player: int
    current_phase: WhichPhase
    p1_color: Color | None = None
    p2_color: Color | None = None

    @classmethod
    def create(cls):
        thaler_pos, pegs = generate_peg_positions()
        current_player = 0
        current_phase = WhichPhase.SELECTING
        return cls(
            thaler_pos=thaler_pos,
            pegs=pegs,
            current_player=current_player,
            current_phase=current_phase,
        )

    def to_board(self) -> str:
        board = [
            color_cell("  ", [RESET_CODE, "\033[100m"][idx % 2]) for idx in range(0, 49)
        ]
        for color, peg in self.pegs.items():
            board[peg.int_repr] = color_cell(
                f"{color.to_string()} ", COLOR_CODES[color]
            )
        board[self.thaler_pos.int_repr] = color_cell(f"T ", THALER_CODE)
        rows = [row(board[r : r + 7]) for r in range(0, 49, 7)]
        return "\n".join(rows)

    def make_player_choice(
        self, which_player: Literal[1, 2], which_color: Color
    ) -> None | InvalidAction:
        match self.current_phase:
            case WhichPhase.SELECTING:
                if which_player == 1 and self.p1_color is None:
                    self.p1_color = which_color
                elif which_player == 2 and self.p2_color is None:
                    self.p2_color = which_color
                if self.p1_color is not None and self.p2_color is not None:
                    self.current_phase = WhichPhase.P1_TURN
            case WhichPhase.P1_TURN | WhichPhase.P2_TURN:
                return InvalidAction("Game is already running!")

    def move_is_valid(self, color: Color, dst: Coords):


    def make_player_move(
        self, which_player: Literal[1, 2], color: Color, dst: Coords
    ) -> None | InvalidAction:
        match self.current_phase:
            case WhichPhase.SELECTING:
                return InvalidAction("Can't make move when initializing!")
            case WhichPhase.P1_TURN if which_player == 1:
                if self.move_is_valid(color, dst):
                    self.pegs[color] = dst
            case WhichPhase.P2_TURN if which_player == 2:
                if self.move_is_valid(color, dst):
                    self.pegs[color] = dst
            case _:
                return InvalidAction(f"It's not Player {which_player}'s turn!")

    def make_player_guess(self):
        pass


def color_cell(cell_content: str, color: Color | str) -> str:
    esc = color if isinstance(color, str) else COLOR_CODES[color]
    return RESET_CODE + esc + cell_content


def row(cells: list[str]) -> str:
    return "".join(cells) + RESET_CODE


def generate_peg_positions() -> tuple[Coords, dict[Color, Coords]]:
    all_pos = random.sample(list(range(0, 49)), k=8)
    color_pos = {Color(idx): Coords(pos) for idx, pos in enumerate(all_pos[:7])}
    thaler_pos = Coords(all_pos[7])
    return thaler_pos, color_pos


if __name__ == "__main__":
    init_state = GameState.create()
    print(init_state)
    print(init_state.to_board())
    print(init_state.to_json())
    print(init_state.from_json(init_state.to_json()))
