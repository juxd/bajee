let lastPickedColor = null;
let connected = false;
let player = 1;
let selectedColor = null;

// Generate a unique player ID (e.g., using localStorage to persist across sessions)
let playerId = localStorage.getItem("playerId");
if (!playerId) {
    playerId = `player-${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem("playerId", playerId);
}

const ws = new WebSocket(`ws://${window.location.hostname}:8765`);

function generateBoard() {
    const board = document.getElementById('board');
    for (let i = 0; i < 49; i++) {
        const cell = document.createElement('div');
        cell.classList.add('cell');
        cell.id = `cell-${i}`;
        cell.dataset.index = i;
        cell.dataset.piece = "";
        cell.addEventListener("click", (evt) => {
            if (lastPickedColor && connected && !cell.dataset.piece) {
                ws.send(JSON.stringify(["make_player_move", { color: lastPickedColor, dst: i, playerId }]));
                removeBoardHighlights();
                return;
            }
            if (!cell.dataset.piece || cell.dataset.piece == "thaler") {
                return;
            }
            lastPickedColor = cell.dataset.piece;
            ws.send(JSON.stringify(["request_moves", { color: lastPickedColor, playerId }]));
        });
        board.appendChild(cell);
    }
}

generateBoard();

const colors = {
    "R": "red",
    "O": "orange",
    "Y": "yellow",
    "G": "green",
    "B": "blue",
    "P": "pink",
    "U": "purple",
};

function populateBoard(pegs, thaler) {
    for (const cell of document.getElementById('board').children) {
        delete cell.dataset.piece;
        cell.style.removeProperty("background-color");
    }

    let cell = undefined;

    Object.entries(pegs).forEach(([color, index]) => {
        cell = document.getElementById('board').children[index];
        if (cell) {
            cell.style.backgroundColor = colors[color];
            cell.dataset.piece = color;
        }
    });
    // thaler
    cell = document.getElementById('board').children[thaler];
    if (cell) {
        cell.style.backgroundColor = "gray";
        cell.dataset.filled = "true";
    }
}

function removeBoardHighlights() {
    for (const cell of document.getElementById('board').children) {
        cell.classList.remove("highlighted");
    }
}

function highlightSuggestedBoard(highlighted) {
    for (const cell of document.getElementById('board').children) {
        cell.classList.remove("highlighted");
    }

    highlighted.forEach((index) => {
        document.getElementById('board').children[index].classList.add("highlighted");
    });
}

ws.onopen = (event) => {
    connected = true;
    // Send a reconnect message with the player ID
    ws.send(JSON.stringify(["reconnect", { playerId }]));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);

    if (data[0] == "error") {
        console.log("error", data[1]);
    }

    if (data[0] == "try_again") {
        player += 1;
        if (player > 2) {
            console.log("room full :(");
            return;
        }
        ws.send(JSON.stringify(["hello", { player, playerId }]));
    }

    if (data.__magic__ == "game_state") {
        populateBoard(data.pegs, data.thaler_pos.int_repr);
    }

    if (data[0] == "hello_okay") {
        if (data[1].you_are === 1) {
            document.getElementById("player-label").innerText = "Player 1";
        } else {
            document.getElementById("player-label").innerText = "Player 2";
        }
    }

    if (data[0] === 'color_confirmed' && data[0].player === player) {
        document.getElementById("subtitle").innerText = "Waiting for other player...";
        document.getElementById("player-color").innerText = colors[selectedColor];
    }

    if (data[0] == "valid_moves") {
        highlightSuggestedBoard(data[1].moves);
    }

    if (data[0] == "reconnect_success") {
        // Restore game state after reconnecting
        populateBoard(data[1].pegs, data[1].thaler);
        document.getElementById("subtitle").innerText = data[1].subtitle || "Reconnected!";
        selectedColor = data[1].selectedColor || null;
    }
};

function chooseColor(color) {
    if (selectedColor) return alert("You've already picked a color!");
    selectedColor = color;
    document.getElementById("subtitle").innerText = "Waiting for other player...";
    ws.send(JSON.stringify(["make_player_choice", { player, color, playerId }]));
}
