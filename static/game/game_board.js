document.addEventListener('DOMContentLoaded', () => {
  // Read configuration from data attributes
  const gameDataEl = document.getElementById('game-data');
  const gameCode = gameDataEl.dataset.gameCode;
  const playerId = parseInt(gameDataEl.dataset.playerId);
  const player1Id = parseInt(gameDataEl.dataset.player1Id);
  const player2Id = gameDataEl.dataset.player2Id ? parseInt(gameDataEl.dataset.player2Id) : null;
  const isPlayer1 = gameDataEl.dataset.isPlayer1 === 'true';
  const isPlayer2 = gameDataEl.dataset.isPlayer2 === 'true';

  
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${window.location.host}/ws/game/${gameCode}/`;
  const ws = new WebSocket(wsUrl);
  
  const messageDiv = document.getElementById('messages');
  let cellInputs = document.querySelectorAll('.cell-input');

  // Helper function to safely send WebSocket messages
  let messageQueue = [];
  let isConnected = false;

  function safeSend(message) {
    if (ws.readyState === WebSocket.OPEN && isConnected) {
      try {
        ws.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    } else if (ws.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket still connecting, queuing message');
      messageQueue.push(message);
      return false;
    } else {
      console.log('WebSocket is not connected, cannot send message');
      addMessage('Connection lost. Please refresh the page.', 'error');
      return false;
    }
  }

  function processMessageQueue() {
    while (messageQueue.length > 0 && ws.readyState === WebSocket.OPEN) {
      const message = messageQueue.shift();
      try {
        ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error sending queued message:', error);
        break;
      }
    }
  }
  
  ws.onopen = () => {
    console.log('WebSocket connected');
    isConnected = true;
    addMessage('Connected to game server');
    
    // Process any queued messages
    processMessageQueue();
    
    // Send join message
    safeSend({
      type: 'join_game',
      playerId: playerId,
    });

    // Request current board state after connection is established
    setTimeout(() => {
      safeSend({ type: 'get_board' });
    }, 500);
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    if (data.type === 'notification') {
      addMessage(data.message);
    } else if (data.type === 'game_state') {
      // Initial state: puzzle + player's board
      updateBoardFromState(data.board);
      addMessage(`Room: players ${data.player1} vs ${data.player2 || 'Waiting...'}`);
      // If race already started, start timer
      if (data.start_time) {
        startTimers(new Date(data.start_time));
      }
    } else if (data.type === 'move') {
      addMessage(`${data.username} placed ${data.value} at row ${data.row + 1}, col ${data.col + 1}`);
      // Update appropriate player's board cell
      updateCellDisplay(data.row, data.col, data.value, data.player_id);
    } else if (data.type === 'board') {
      updateBoardFromState(data.board);
    } else if (data.type === 'race_started') {
      // Start timers and ensure both boards have the puzzle
      const startTime = new Date(data.start_time);
      startTimers(startTime);
      if (data.puzzle) {
        updateBoardFromState(data.board || data.puzzle);
      }
      addMessage('Race started — good luck!');
    } else if (data.type === 'race_finished') {
      addMessage(`${data.winner_username} finished the puzzle in ${data.winner_time}`);
      stopTimers();
    } else if (data.error) {
      addMessage(`Error: ${data.error}`, 'error');
    }
  };
  
  ws.onclose = () => {
    console.log('WebSocket closed');
    isConnected = false;
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
    // Race mode: allow simultaneous input
    
    const cell = e.target.closest('.sudoku-cell');
    if (!cell) return;
    
    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    const value = parseInt(e.target.value);
    
    if (value && value >= 1 && value <= 9) {
      safeSend({
        type: 'move',
        row: row,
        col: col,
        value: value,
      });
    } else if (e.target.value === '') {
      // Allow clearing, but don't send empty move
      return;
    }

    // After each input, check if board is fully filled locally and show finish button
    if (isLocalBoardComplete()) {
      showFinishButton();
    }
  });

  // Ready/start UI
  const readyBtn = document.getElementById('ready-btn');
  const startRaceBtn = document.getElementById('start-race-btn');
  if (readyBtn) {
    readyBtn.style.display = 'inline-block';
    readyBtn.addEventListener('click', () => {
      safeSend({ type: 'ready' });
      readyBtn.disabled = true;
      readyBtn.textContent = 'Waiting for opponent...';
    });
  }
  if (startRaceBtn && isPlayer1) {
    // Optionally allow host to force start
    startRaceBtn.style.display = 'inline-block';
    startRaceBtn.addEventListener('click', () => {
      safeSend({ type: 'ready' });
    });
  }

  // Finish button
  const finishBtn = document.getElementById('finish-btn');
  if (finishBtn) {
    finishBtn.addEventListener('click', () => {
      // Check if puzzle is complete before submitting
      if (isLocalBoardComplete()) {
        safeSend({ type: 'complete' });
        finishBtn.disabled = true;
        finishBtn.textContent = 'Submitted!';
        addMessage('Solution submitted!');
      } else {
        addMessage('Please complete the puzzle before submitting!', 'error');
      }
    });
  }

  // Timers
  let timerInterval = null;
  let raceStartTime = null;

  function startTimers(startTime) {
    raceStartTime = startTime;
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      const now = new Date();
      const elapsed = Math.max(0, Math.floor((now - raceStartTime) / 1000));
      const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const ss = String(elapsed % 60).padStart(2, '0');
      document.getElementById('player1-timer').textContent = `${mm}:${ss}`;
      document.getElementById('player2-timer').textContent = `${mm}:${ss}`;
    }, 500);
  }

  function stopTimers() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function showFinishButton() {
    const finishBtn = document.getElementById('finish-btn');
    if (finishBtn && finishBtn.style.display === 'none') {
      finishBtn.style.display = 'inline-block';
      addMessage('Puzzle complete! Click "Submit Solution" to finish.');
    }
  }

  function isLocalBoardComplete() {
    const inputs = document.querySelectorAll('.cell-input');
    for (const input of inputs) {
      if (!input.value || input.value === '') return false;
    }
    return true;
  }
  
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
  
  function updateCellDisplay(row, col, value, player_id) {
    const input = document.querySelector(`.sudoku-cell[data-row="${row}"][data-col="${col}"] .cell-input`);
    if (input) {
      input.value = value;
      // Only disable if the move was from this client; otherwise keep editable for local player
      if (player_id !== playerId) {
        // show opponent move but keep inputs enabled for local edits
        input.classList.add('opponent-move');
      } else {
        input.disabled = true;
        input.classList.add('prefilled');
      }
    }
  }
  

});
