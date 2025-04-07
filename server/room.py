import asyncio
import json
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Self, TypeGuard, cast, get_args

from dataclasses_json import dataclass_json
import game
import websockets
from websockets import WebSocketServerProtocol
from collections import defaultdict
from game import GameState, Color

Action = Literal[
    "make_player_choice", "make_player_move", "make_player_guess", "request_moves"
]


def is_action(s: Any) -> TypeGuard[Action]:
    return s in get_args(Action)


@dataclass_json
@dataclass(frozen=True, kw_only=True)
class GameStateForClient:
    __magic__: Literal["game_state"] = "game_state"
    you_are: Literal[1, 2]
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
    def of_game_state(cls, game_state: game.GameState, you_are: Literal[1, 2]) -> Self:
        return cls(
            you_are=you_are,
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
        def state(you_are: Literal[1, 2]) -> str:
            return GameStateForClient.of_game_state(
                self.game_state, you_are=you_are
            ).to_json()

        _ = await asyncio.gather(
            *[
                conn.send(state(cast(Literal[1, 2], you_are)))
                for (you_are, conn) in [(1, self.p1), (2, self.p2)]
                if conn
            ]
        )
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
                await ws.send(json.dumps(["color_confirmed", {"player": which_player}]))

            case "make_player_move":
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
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                result = self.game_state.make_player_guess(which_player, color)

            case "request_moves":
                if not (color := data.get("color")) or not (
                    color := game.Color.of_string(color)
                ):
                    return game.InvalidAction("no valid color")
                moves = [c.int_repr for c in self.game_state.valid_moves(color)]
                await ws.send(json.dumps(["valid_moves", {"moves": moves}]))
                result = None
        await self.update_clients()
        return result


# WebSocket server handler
def handler(room: Room) -> Callable[[websockets.ServerConnection], Awaitable[None]]:
    async def handle_connection(ws: websockets.ServerConnection) -> None:
        print("Player connected", ws.remote_address)
        which_player = None  # Initialize which_player to None

        try:
            while True:
                hello = await ws.recv()
                header: str
                header, content = json.loads(hello)

                if header == "hello":
                    # Automatically assign the player to the first available slot
                    which_player = 1 if not room.p1 else 2
                    error = room.connect(which_player, ws)
                    if error:
                        await ws.send(json.dumps(["try_again", error]))
                        print(error)
                        return

                    print(f"Assigned Player {which_player}")
                    await ws.send(json.dumps(["hello_okay", {"you_are": which_player}]))

                    # Transition to SELECTING phase if both players are connected
                    if room.p1 and room.p2:
                        print("Both players connected. Transitioning to 'SELECTING' phase.")
                        room.game_state.current_phase = game.WhichPhase.SELECTING
                        await room.update_clients()
                    break

                elif header == "reconnect":
                    player_id = content.get("playerId")
                    if player_id == "player1" and room.p1:
                        room.p1 = ws
                        which_player = 1  # Reassign Player 1
                        print(f"Player 1 reconnected with ID {player_id}")
                        await ws.send(json.dumps(["reconnect_success", {"you_are": 1}]))
                        break
                    elif player_id == "player2" and room.p2:
                        room.p2 = ws
                        which_player = 2  # Reassign Player 2
                        print(f"Player 2 reconnected with ID {player_id}")
                        await ws.send(json.dumps(["reconnect_success", {"you_are": 2}]))
                        break
                    else:
                        await ws.send(json.dumps(["try_again", "Invalid reconnect attempt"]))
                        continue

                else:
                    await ws.send(json.dumps(["try_again", f"expected hello but got: {header}"]))
                    continue

            # Listen for messages from the clients
            while True:
                if which_player is None:
                    print("Player not assigned, skipping message processing.")
                    break

                message = await ws.recv()
                response = await room.process_message(which_player, message)
                if response:
                    print(response.message)
                    await ws.send(json.dumps(["invalid_action", response.message]))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            print("Player disconnected", ws.remote_address)
            if room.p1 == ws:
                room.p1 = None
            elif room.p2 == ws:
                room.p2 = None

    return handle_connection


# Main function to start the WebSocket server
async def main():
    room = Room(game.GameState.create())  # Use the create method to initialize the GameState
    server = await websockets.serve(handler(room), "0.0.0.0", 8765)  # Bind to all network interfaces
    print("WebSocket server running on port 8765")
    await server.wait_closed()

asyncio.run(main())

# Track game rooms and player connections
rooms = {}  # {room_id: GameState}
player_rooms = {}  # {player_id: room_id}
player_connections = {}  # {player_id: WebSocketServerProtocol}

class RoomManager:
    def __init__(self):
        self.rooms = rooms
        self.player_rooms = player_rooms
        self.player_connections = player_connections

    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        data = json.loads(message)
        action = data[0]
        payload = data[1]

        if action == "reconnect":
            await self.handle_reconnect(websocket, payload)
        elif action == "make_player_choice":
            await self.handle_player_choice(websocket, payload)
        elif action == "make_player_move":
            await self.handle_player_move(websocket, payload)
        elif action == "request_moves":
            await self.handle_request_moves(websocket, payload)

    async def handle_reconnect(self, websocket: WebSocketServerProtocol, payload: dict):
        player_id = payload["playerId"]

        # Check if the player was in a game
        if player_id in self.player_rooms:
            room_id = self.player_rooms[player_id]
            game_state = self.rooms.get(room_id)

            if game_state:
                # Reconnect the player and send the game state
                self.player_connections[player_id] = websocket
                await websocket.send(json.dumps([
                    "reconnect_success",
                    {
                        "pegs": {color.to_string(): coord.int_repr for color, coord in game_state.pegs.items()},
                        "thaler": game_state.thaler_pos.int_repr,
                        "subtitle": f"Welcome back, {player_id}!",
                        "selectedColor": game_state.p1_color.to_string() if game_state.p1_color else None,
                    }
                ]))
                return

        # If no game state is found, send an error
        await websocket.send(json.dumps(["error", "No active game found for this player."]))

    async def handle_player_choice(self, websocket: WebSocketServerProtocol, payload: dict):
        player_id = payload["playerId"]
        color = Color.of_string(payload["color"])
        room_id = self.player_rooms.get(player_id)

        if room_id and room_id in self.rooms:
            game_state = self.rooms[room_id]
            if game_state.current_phase == "Selecting":
                if player_id not in game_state.pegs:
                    game_state.make_player_choice(1 if player_id == "player1" else 2, color)
                    await websocket.send(json.dumps(["color_confirmed", {"player": player_id, "color": color.to_string()}]))

    async def handle_player_move(self, websocket: WebSocketServerProtocol, payload: dict):
        player_id = payload["playerId"]
        color = Color.of_string(payload["color"])
        dst = payload["dst"]
        room_id = self.player_rooms.get(player_id)

        if room_id and room_id in self.rooms:
            game_state = self.rooms[room_id]
            result = game_state.make_player_move(1 if player_id == "player1" else 2, color, dst)
            if isinstance(result, str):  # InvalidAction
                await websocket.send(json.dumps(["error", result]))
            else:
                # Broadcast the updated game state to all players in the room
                for pid, ws in self.player_connections.items():
                    if self.player_rooms.get(pid) == room_id:
                        await ws.send(json.dumps([
                            "game_state",
                            {
                                "pegs": {color.to_string(): coord.int_repr for color, coord in game_state.pegs.items()},
                                "thaler": game_state.thaler_pos.int_repr,
                                "current_phase": game_state.current_phase.value,
                            }
                        ]))

    async def handle_request_moves(self, websocket: WebSocketServerProtocol, payload: dict):
        player_id = payload["playerId"]
        color = Color.of_string(payload["color"])
        room_id = self.player_rooms.get(player_id)

        if room_id and room_id in self.rooms:
            game_state = self.rooms[room_id]
            valid_moves = game_state.valid_moves(color)
            await websocket.send(json.dumps(["valid_moves", {"moves": [move.int_repr for move in valid_moves]}]))

# Example of starting the WebSocket server
async def main(websocket: WebSocketServerProtocol, path: str):
    manager = RoomManager()
    async for message in websocket:
        await manager.handle_message(websocket, message)
