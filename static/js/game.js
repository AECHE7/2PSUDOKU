// Game WebSocket and UI Logic
let gameSocket = null;
let selectedCell = null;
let gameState = null;

// Initialize the game when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeBoard();
    connectWebSocket();
});

// Connect to WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/game/${sessionCode}/`;
    
    gameSocket = new WebSocket(wsUrl);
    
    gameSocket.onopen = function(e) {
        console.log('WebSocket connected');
        showMessage('Connected to game!', 'success');
    };
    
    gameSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        handleWebSocketMessage(data);
    };
    
    gameSocket.onclose = function(e) {
        console.error('WebSocket closed');
        showMessage('Connection lost. Refresh to reconnect.', 'error');
    };
    
    gameSocket.onerror = function(e) {
        console.error('WebSocket error:', e);
        showMessage('Connection error!', 'error');
    };
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'game_state':
            gameState = data.data;
            updateGameState(gameState);
            break;
        case 'move_made':
            handleMoveMade(data);
            break;
        case 'chat_message':
            showMessage(`${data.player}: ${data.message}`, 'info');
            break;
        case 'error':
            showMessage(data.message, 'error');
            break;
    }
}

// Initialize the Sudoku board
function initializeBoard() {
    const board = document.getElementById('sudoku-board');
    board.innerHTML = '';
    
    for (let i = 0; i < 9; i++) {
        for (let j = 0; j < 9; j++) {
            const cell = document.createElement('div');
            cell.className = 'sudoku-cell';
            cell.dataset.row = i;
            cell.dataset.col = j;
            
            const value = currentBoard[i][j];
            if (value !== 0) {
                cell.textContent = value;
                if (initialBoard[i][j] !== 0) {
                    cell.classList.add('initial');
                } else {
                    cell.classList.add('filled');
                }
            }
            
            if (initialBoard[i][j] === 0) {
                cell.addEventListener('click', function() {
                    selectCell(cell);
                });
            }
            
            board.appendChild(cell);
        }
    }
    
    // Setup number pad
    const numButtons = document.querySelectorAll('.num-btn');
    numButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            if (selectedCell) {
                const value = parseInt(btn.dataset.value);
                makeMove(selectedCell, value);
            } else {
                showMessage('Please select a cell first!', 'info');
            }
        });
    });
}

// Update board with current state
function updateBoard(board) {
    const cells = document.querySelectorAll('.sudoku-cell');
    
    for (let i = 0; i < 9; i++) {
        for (let j = 0; j < 9; j++) {
            const cell = cells[i * 9 + j];
            const value = board[i][j];
            
            if (value !== 0 && initialBoard[i][j] === 0) {
                cell.textContent = value;
                cell.classList.add('filled');
            }
        }
    }
}

// Select a cell
function selectCell(cell) {
    // Remove previous selection
    if (selectedCell) {
        selectedCell.classList.remove('selected');
    }
    
    // Select new cell
    selectedCell = cell;
    cell.classList.add('selected');
}

// Make a move
function makeMove(cell, value) {
    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    
    // Check if it's player's turn
    if (!gameState) {
        showMessage('Game state not loaded yet!', 'error');
        return;
    }
    
    if (gameState.status !== 'active') {
        showMessage('Game is not active!', 'error');
        return;
    }
    
    if (gameState.current_turn !== currentUser) {
        showMessage('Not your turn!', 'error');
        return;
    }
    
    // Send move to server
    gameSocket.send(JSON.stringify({
        type: 'make_move',
        row: row,
        col: col,
        value: value
    }));
    
    showMessage('Move sent...', 'info');
}

// Handle move made by any player
function handleMoveMade(data) {
    const cells = document.querySelectorAll('.sudoku-cell');
    const cellIndex = data.row * 9 + data.col;
    const cell = cells[cellIndex];
    
    if (data.is_valid) {
        cell.textContent = data.value;
        cell.classList.add('filled');
        cell.classList.remove('invalid');
        
        if (data.player === currentUser) {
            showMessage('Valid move! +10 points', 'success');
        } else {
            showMessage(`${data.player} made a valid move!`, 'info');
        }
    } else {
        // Show invalid move briefly
        cell.classList.add('invalid');
        setTimeout(() => {
            cell.classList.remove('invalid');
        }, 1000);
        
        if (data.player === currentUser) {
            showMessage('Invalid move! Turn passed.', 'error');
        } else {
            showMessage(`${data.player} made an invalid move!`, 'info');
        }
    }
    
    // Update game state
    if (data.game_state) {
        gameState = data.game_state;
        updateGameState(gameState);
    }
    
    // Deselect cell
    if (selectedCell) {
        selectedCell.classList.remove('selected');
        selectedCell = null;
    }
}

// Update game state UI
function updateGameState(state) {
    // Update scores
    document.getElementById('player1-score').textContent = `Score: ${state.player1_score}`;
    document.getElementById('player2-score').textContent = `Score: ${state.player2_score}`;
    
    // Update turn indicators
    const player1Turn = document.getElementById('player1-turn');
    const player2Turn = document.getElementById('player2-turn');
    
    player1Turn.classList.remove('active');
    player2Turn.classList.remove('active');
    
    if (state.current_turn === state.player1) {
        player1Turn.classList.add('active');
    } else if (state.current_turn === state.player2) {
        player2Turn.classList.add('active');
    }
    
    // Update board if provided
    if (state.board) {
        updateBoard(state.board);
    }
    
    // Check if game completed
    if (state.status === 'completed') {
        if (state.winner) {
            showMessage(`🎉 Game Over! Winner: ${state.winner}!`, 'success');
        } else {
            showMessage('🤝 Game Over! It\'s a draw!', 'info');
        }
        
        // Reload page to show results
        setTimeout(() => {
            location.reload();
        }, 2000);
    }
}

// Show message to user
function showMessage(message, type = 'info') {
    const messageArea = document.getElementById('message-area');
    messageArea.textContent = message;
    messageArea.className = 'message-area';
    
    if (type === 'success') {
        messageArea.style.background = '#d4edda';
        messageArea.style.color = '#155724';
    } else if (type === 'error') {
        messageArea.style.background = '#f8d7da';
        messageArea.style.color = '#721c24';
    } else {
        messageArea.style.background = '#d1ecf1';
        messageArea.style.color = '#0c5460';
    }
    
    // Clear message after 3 seconds
    setTimeout(() => {
        if (messageArea.textContent === message) {
            messageArea.textContent = '';
            messageArea.style.background = '#f8f9fa';
        }
    }, 3000);
}
