import json
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Callable, Literal, Self, cast

import websockets
from . import game

Action = Literal["make_player_choice", "make_player_move", "make_player_guess"]


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

    async def process_message(
        self, which_player: Literal[1, 2], message: str
    ) -> game.InvalidAction | None:
        data: dict[str, Any]
        action, data = json.loads(message)

        if not isinstance(action, Action):
            return game.InvalidAction("bruh what is this")

        match action:
            case "make_player_choice":
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                result = self.game_state.make_player_choice(which_player, color)

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
        hello = await ws.recv()
        header, content = json.loads(hello)
        if header != "Hello":
            print("expected hello")
            return

        which_player = cast(Literal[1, 2], content["player"])
        try:
            # Start the game when there are 2 players
            if len(room.clients) == 2:
                await room.start_game()

            # Listen for messages from the clients
            while True:
                message = await websocket.recv()
                response = await room.process_message(which_player, message)
                if response:
                    await websocket.send(json.dumps({"response": response}))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Remove the client when they disconnect
            await room.remove_client(websocket)

    return handle_connection


# Main function to start the WebSocket server
async def main():
    room = Room(game_state=game.GameState())
    server = await websockets.serve(handler(room), "localhost", 8765)
    print("WebSocket server started on ws://localhost:8765")
    await asyncio.Future()  # Keep the server running


# Run the server
asyncio.run(main())
