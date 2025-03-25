import random
from dataclasses import dataclass, field
from enum import Enum
from typing import cast, Literal, Self

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(frozen=True)
class Coords:
    int_repr: int

    def to_xy(self) -> tuple[int, int]:
        return (self.int_repr % 7), (self.int_repr // 7)

    def add_xy(self, dx: int, dy: int) -> Self | None:
        x, y = self.to_xy()
        x, y = x + dx, y + dy
        if not (0 <= x < 7 and 0 <= y < 7):
            return None
        return self.__class__(y * 7 + x)

    def distance_from(self, other: Self) -> int:
        x1, y1 = self.to_xy()
        x2, y2 = other.to_xy()
        return max(abs(x1 - x2), abs(y1 - y2))


class Color(Enum):
    RED = 0
    ORANGE = 1
    YELLOW = 2
    GREEN = 3
    BLUE = 4
    PINK = 5
    PURPLE = 6

    def to_string(self):
        match self:
            case self.__class__.RED:
                return "R"
            case self.__class__.ORANGE:
                return "O"
            case self.__class__.YELLOW:
                return "Y"
            case self.__class__.GREEN:
                return "G"
            case self.__class__.BLUE:
                return "B"
            case self.__class__.PINK:
                return "P"
            case self.__class__.PURPLE:
                return "U"

    @classmethod
    def of_string(cls, s: str) -> Self | None:
        mapping = {
            "R": cls.RED,
            "O": cls.ORANGE,
            "Y": cls.YELLOW,
            "G": cls.GREEN,
            "B": cls.BLUE,
            "P": cls.PINK,
            "U": cls.PURPLE,
        }
        return mapping.get(s)


COLOR_CODES = {
    Color.RED: "\033[31m",
    Color.YELLOW: "\033[33m",
    Color.ORANGE: "\033[38;5;214m",  # ANSI code for orange
    Color.GREEN: "\033[32m",
    Color.BLUE: "\033[34m",
    Color.PINK: "\033[38;5;213m",  # ANSI code for pink
    Color.PURPLE: "\033[37m",
}

RESET_CODE = "\033[0m"

THALER_CODE = "\033[47m"


class WhichPhase(Enum):
    WAITING_FOR_START = "Waiting for start"
    SELECTING = "Selecting"
    P1_TURN = "P1 Turn"
    P2_TURN = "P2 Turn"
    GAME_ENDED = "Game ended"


@dataclass
class InvalidAction:
    message: str


Cell = Color | Literal["Thaler"] | None

MaybeGameEnded = Literal["P1_won", "P2_won", "Not_yet"]


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
    current_phase: WhichPhase = WhichPhase.WAITING_FOR_START
    p1_color: Color | None = None
    p2_color: Color | None = None
    game_ended_state: MaybeGameEnded = "Not_yet"

    @classmethod
    def create(cls) -> Self:
        thaler_pos, pegs = generate_peg_positions()
        return cls(
            thaler_pos=thaler_pos,
            pegs=pegs,
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
            case WhichPhase.WAITING_FOR_START:
                return InvalidAction("Not started yet!")
            case WhichPhase.P1_TURN | WhichPhase.P2_TURN | WhichPhase.GAME_ENDED:
                return InvalidAction("Game is already running!")

    def valid_moves(self, color: Color) -> list[Coords]:
        def is_closer_to_thaler_than_current(new_coord: Coords) -> bool:
            return new_coord.distance_from(self.thaler_pos) < self.pegs[
                color
            ].distance_from(self.thaler_pos)

        deltas = [
            (up_down, left_right)
            for up_down in [-1, 0, 1]
            for left_right in [-1, 0, 1]
            if (up_down, left_right) != (0, 0)
        ]
        valid_moves: list[Coords] = []
        for x, y in deltas:
            if (
                (new_coord := self.pegs[color].add_xy(x, y)) is not None
                and new_coord not in self.pegs.values()
                and is_closer_to_thaler_than_current(new_coord)
            ):
                valid_moves.append(new_coord)
            if (
                (new_coord2 := self.pegs[color].add_xy(x * 2, y * 2)) is not None
                and new_coord2 not in self.pegs.values()
                and (skipped := self.pegs[color].add_xy(x, y)) not in self.pegs.values()
                and is_closer_to_thaler_than_current(new_coord2)
            ):
                valid_moves.append(new_coord2)
        return valid_moves

    def progress_game_state(self) -> None:
        match self.game_ended_state:
            case "P1_won" | "P2_won":
                self.current_phase = WhichPhase.GAME_ENDED
            case "Not_yet":
                self.current_phase = (
                    WhichPhase.P1_TURN
                    if self.current_phase == WhichPhase.P2_TURN
                    else WhichPhase.P2_TURN
                )

    def make_player_move(
        self, which_player: Literal[1, 2], color: Color, dst: Coords
    ) -> None | InvalidAction:
        match self.current_phase:
            case WhichPhase.SELECTING | WhichPhase.WAITING_FOR_START:
                return InvalidAction("Can't make move when initializing!")
            case WhichPhase.P1_TURN if which_player == 1:
                pass
            case WhichPhase.P2_TURN if which_player == 2:
                pass
            case _:
                return InvalidAction(f"It's not Player {which_player}'s turn!")
        if dst not in self.valid_moves(color):
            self.pegs[color] = dst
        else:
            return InvalidAction("You bruh'd with an invalid move")
        matching_thaler = [
            color for color, coords in self.pegs.items() if coords == self.thaler_pos
        ]
        if not matching_thaler:
            self.game_ended_state = "Not_yet"
        else:
            matching_thaler = matching_thaler[0]
            match matching_thaler, matching_thaler, self.current_phase:
                case self.p1_color, self.p2_color, WhichPhase.P1_TURN:
                    self.game_ended_state = "P2_won"
                case self.p1_color, _, WhichPhase.P1_TURN:
                    self.game_ended_state = "P1_won"
                case self.p2_color, self.p1_color, WhichPhase.P2_TURN:
                    self.game_ended_state = "P1_won"
                case self.p2_color, _, WhichPhase.P2_TURN:
                    self.game_ended_state = "P2_won"
                case _, _, WhichPhase.P1_TURN:
                    self.game_ended_state = "P2_won"
                case _, _, WhichPhase.P2_TURN:
                    self.game_ended_state = "P1_won"
        self.progress_game_state()
        return

    def make_player_guess(
        self, which_player: Literal[1, 2], guess_of_other: Color
    ) -> None | InvalidAction:
        match self.current_phase:
            case WhichPhase.SELECTING | WhichPhase.WAITING_FOR_START:
                return InvalidAction("Can't make move when initializing!")
            case WhichPhase.P1_TURN if which_player == 1:
                pass
            case WhichPhase.P2_TURN if which_player == 2:
                pass
            case _:
                return InvalidAction(f"It's not Player {which_player}'s turn!")
        other_player_color = cast(
            Color, self.p2_color if which_player == 1 else self.p1_color
        )
        won, lost = ("P1_won", "P2_won") if which_player == 1 else ("P2_won", "P1_won")
        self.game_ended_state = won if other_player_color == guess_of_other else lost
        return


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
