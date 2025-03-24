import asyncio
import websockets
import json
import random

async def send_dummy_messages(websocket, path):
    """Simulates a WebSocket server sending test messages to a connected client."""
    
    # Dummy colors assigned to players
    colors = ["red", "orange", "yellow", "blue", "green", "purple", "pink"]
    player1_color = random.choice(colors)
    colors.remove(player1_color)
    player2_color = random.choice(colors)

    # Send color confirmation messages
    await asyncio.sleep(1)
    await websocket.send(json.dumps({"type": "colorConfirmed", "player": "Player1", "color": player1_color}))
    await asyncio.sleep(1)
    await websocket.send(json.dumps({"type": "colorConfirmed", "player": "Player2", "color": player2_color}))

    # Simulate Thaler placements
    placed_positions = set()
    for round_number in range(1, 5):
        await asyncio.sleep(2)  # Simulate time between moves
        pos = random.randint(0, 48)

        while pos in placed_positions:
            pos = random.randint(0, 48)

        placed_positions.add(pos)
        await websocket.send(json.dumps({"type": "thalerPlaced", "position": pos}))

async def start_server():
    server = await websockets.serve(send_dummy_messages, "localhost", 8765)
    print("WebSocket test server started on ws://localhost:8765")
    await server.wait_closed()

# Run the test WebSocket server
asyncio.run(start_server())
