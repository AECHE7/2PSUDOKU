document.addEventListener('DOMContentLoaded', () => {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${window.location.host}/ws/game/${gameCode}/`;
  const ws = new WebSocket(wsUrl);
  
  const messageDiv = document.getElementById('messages');
  let cellInputs = document.querySelectorAll('.cell-input');
  let currentTurnPlayerId = currentPlayerId;
  
  ws.onopen = () => {
    console.log('WebSocket connected');
    addMessage('Connected to game server');
    updateInputDisabledState();
    
    // Send join message
    ws.send(JSON.stringify({
      type: 'join_game',
      playerId: playerId,
    }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    if (data.type === 'notification') {
      addMessage(data.message);
    } else if (data.type === 'game_state') {
      updateBoardFromState(data.board);
      addMessage(`Game started! Players: ${data.player1} vs ${data.player2 || 'Waiting...'}`);
    } else if (data.type === 'move') {
      addMessage(`${data.username} placed ${data.value} at row ${data.row + 1}, col ${data.col + 1}`);
      updateCellDisplay(data.row, data.col, data.value);
    } else if (data.type === 'board') {
      updateBoardFromState(data.board);
    } else if (data.type === 'current_turn_updated') {
      currentTurnPlayerId = data.player_id;
      addMessage(`${data.username}'s turn`);
      updateInputDisabledState();
    } else if (data.error) {
      addMessage(`Error: ${data.error}`, 'error');
    }
  };
  
  ws.onclose = () => {
    console.log('WebSocket closed');
    addMessage('Disconnected from server', 'error');
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    addMessage('WebSocket error', 'error');
  };
  
  // Handle cell input
  document.addEventListener('change', (e) => {
    if (!e.target.classList.contains('cell-input')) return;
    if (e.target.disabled) return;
    
    // Check if it's player's turn
    if (currentTurnPlayerId !== playerId) {
      addMessage('It is not your turn!', 'error');
      e.target.value = '';
      return;
    }
    
    const cell = e.target.closest('.sudoku-cell');
    if (!cell) return;
    
    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    const value = parseInt(e.target.value);
    
    if (value && value >= 1 && value <= 9) {
      ws.send(JSON.stringify({
        type: 'move',
        row: row,
        col: col,
        value: value,
      }));
    } else if (e.target.value === '') {
      // Allow clearing, but don't send empty move
      return;
    }
  });
  
  // Request current board state
  setTimeout(() => {
    ws.send(JSON.stringify({ type: 'get_board' }));
  }, 500);
  
  function addMessage(text, className = '') {
    const div = document.createElement('div');
    div.className = `message ${className}`;
    div.textContent = text;
    messageDiv.appendChild(div);
    messageDiv.scrollTop = messageDiv.scrollHeight;
  }
  
  function updateBoardFromState(board) {
    cellInputs = document.querySelectorAll('.cell-input');
    cellInputs.forEach((input, index) => {
      const row = Math.floor(index / 9);
      const col = index % 9;
      const value = board[row] ? board[row][col] : 0;
      if (value !== 0) {
        input.value = value;
        input.disabled = true;
        input.classList.add('prefilled');
      }
    });
  }
  
  function updateCellDisplay(row, col, value) {
    const input = document.querySelector(`.sudoku-cell[data-row="${row}"][data-col="${col}"] .cell-input`);
    if (input) {
      input.value = value;
      input.disabled = true;
    }
  }
  
  function updateInputDisabledState() {
    cellInputs = document.querySelectorAll('.cell-input');
    const isMyTurn = currentTurnPlayerId === playerId;
    
    cellInputs.forEach(input => {
      // Don't override prefilled cells
      if (!input.classList.contains('prefilled')) {
        input.disabled = !isMyTurn;
        if (isMyTurn) {
          input.classList.add('active');
        } else {
          input.classList.remove('active');
        }
      }
    });
  }
});
