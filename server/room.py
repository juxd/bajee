import asyncio
import json
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Self, TypeGuard, cast, get_args

from dataclasses_json import dataclass_json
import game
import websockets

Action = Literal["make_player_choice", "make_player_move", "make_player_guess"]

def is_action(s: Any) -> TypeGuard[Action]:
    return s in get_args(Action)

@dataclass_json
@dataclass(frozen=True, kw_only=True)
class GameStateForClient:
    __magic__: Literal["game_state"] = "game_state"
    pegs: dict[game.Color, game.Coords] = field(
        metadata={
            "dataclasses_json": {
                "encoder": lambda d: {k.to_string(): v.int_repr for k, v in d.items()},
                "decoder": lambda d: {
                    game.Color(int(k)): game.Coords(v) for k, v in d.items()
                },
            }
        }
    )
    thaler_pos: game.Coords
    current_phase: game.WhichPhase

    @classmethod
    def of_game_state(cls, game_state: game.GameState) -> Self:
        return cls(
            pegs=game_state.pegs,
            thaler_pos=game_state.thaler_pos,
            current_phase=game_state.current_phase,
        )


@dataclass
class Room:
    game_state: game.GameState
    p1: websockets.ServerConnection | None = None
    p2: websockets.ServerConnection | None = None

    def connect(
        self, which_player: Literal[1, 2], websocket: websockets.ServerConnection
    ) -> str | None:
        match which_player:
            case 1:
                if self.p1:
                    return "Already taken"
                self.p1 = websocket
            case 2:
                if self.p2:
                    return "Already taken"
                self.p2 = websocket
        if (
            self.p1
            and self.p2
            and self.game_state.current_phase == game.WhichPhase.WAITING_FOR_START
        ):
            self.game_state.current_phase = game.WhichPhase.SELECTING

    async def update_clients(self) -> None:
        state: str = GameStateForClient.of_game_state(self.game_state).to_json()
        _ = await asyncio.gather(*[conn.send(state) for conn in [self.p1, self.p2] if conn])
        return

    async def process_message(
        self, which_player: Literal[1, 2], message: websockets.Data
    ) -> game.InvalidAction | None:
        data: dict[str, Any]
        action, data = json.loads(message)

        if not is_action(action):
            return game.InvalidAction("bruh what is this")

        ws = self.p1 if which_player == 1 else self.p2
        if not ws:
            return
        match action:
            case "make_player_choice":
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                result = self.game_state.make_player_choice(which_player, color)
                await ws.send(json.dumps(["color_confirmed", { "player" : which_player}]))

            case "make_player_move":
                # Handle player move action
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                if not (dst := data.get("dst")):
                    return game.InvalidAction("no dst")
                result = self.game_state.make_player_move(
                    which_player, color, game.Coords(cast(int, dst))
                )

            case "make_player_guess":
                # Handle player guess action
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                result = self.game_state.make_player_guess(which_player, color)
        await self.update_clients()
        return result


# WebSocket server handler
def handler(room: Room) -> Callable[[websockets.ServerConnection], Awaitable[None]]:
    async def handle_connection(ws: websockets.ServerConnection) -> None:
        # Add the client to the room
        print("Player connected", ws.remote_address)

        try:
            while True:
                hello = await ws.recv()
                header: str
                header, content = json.loads(hello)
                if header != "hello":
                    await ws.send(json.dumps(["try_again", f"expected hello but got: {header}"]))
                    continue
                try:
                    which_player = cast(Literal[1, 2], int(content["player"]))
                    print(f"player {which_player} connected!")
                    if bad_conn := room.connect(which_player, ws):
                        # send back to user
                        await ws.send(json.dumps(["try_again", bad_conn]))
                        print("error: ", bad_conn)
                        continue
                    break
                except Exception:
                    continue

            # Listen for messages from the clients
            while True:
                message = await ws.recv()
                response = await room.process_message(which_player, message)
                if response:
                    print(response.message)
                    await ws.send(json.dumps(["invalid_action", response.message]))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Remove the client when they disconnect
            print("Player disconnected", ws.remote_address)
            pass

    return handle_connection


# Main function to start the WebSocket server
async def main():
    room = Room(game_state=game.GameState.create())
    server = await websockets.serve(handler(room), "192.168.1.167", 8765)
    print("WebSocket server started on ws://192.168.1.167:8765")
    await asyncio.Future()  # Keep the server running


if __name__ == "__main__":
    # Run the server
    asyncio.run(main())
