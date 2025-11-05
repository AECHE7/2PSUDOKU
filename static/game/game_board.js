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
      handleGameFinished(data);
    } else if (data.type === 'new_game_created') {
      handleNewGameCreated(data);
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

    // After each input, check if puzzle is complete and auto-submit
    if (isLocalBoardComplete() && isLocalBoardValid()) {
      // Auto-submit the completed puzzle
      autoSubmitSolution();
    }
  });

  // Ready UI
  const readyBtn = document.getElementById('ready-btn');
  if (readyBtn) {
    readyBtn.style.display = 'inline-block';
    readyBtn.addEventListener('click', () => {
      safeSend({ type: 'ready' });
      readyBtn.disabled = true;
      readyBtn.textContent = 'Waiting for opponent...';
    });
  }

  // Finish button (kept for manual submission if needed)
  const finishBtn = document.getElementById('finish-btn');
  if (finishBtn) {
    finishBtn.addEventListener('click', () => {
      if (!gameFinished && isLocalBoardComplete() && isLocalBoardValid()) {
        autoSubmitSolution();
      } else if (!isLocalBoardComplete()) {
        addMessage('Please complete the puzzle before submitting!', 'error');
      } else if (!isLocalBoardValid()) {
        addMessage('Please fix the errors in your solution!', 'error');
      }
    });
  }

  // Play Again button
  document.addEventListener('click', (e) => {
    if (e.target.id === 'play-again-btn') {
      handlePlayAgain();
    }
  });

  function handlePlayAgain() {
    addMessage('Creating new game...', 'info');
    
    // Request a new game with the same players
    safeSend({ 
      type: 'play_again', 
      difficulty: gameDataEl.dataset.difficulty 
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



  function isLocalBoardComplete() {
    const inputs = document.querySelectorAll('.cell-input');
    for (const input of inputs) {
      if (!input.value || input.value === '') return false;
    }
    return true;
  }

  function isLocalBoardValid() {
    // Basic validation - check for duplicates in rows, columns, and boxes
    const inputs = document.querySelectorAll('.cell-input');
    const board = [];
    
    // Convert inputs to 9x9 array
    for (let row = 0; row < 9; row++) {
      board[row] = [];
      for (let col = 0; col < 9; col++) {
        const input = inputs[row * 9 + col];
        board[row][col] = parseInt(input.value) || 0;
      }
    }
    
    return validateSudokuBoard(board);
  }

  function validateSudokuBoard(board) {
    // Check rows
    for (let row = 0; row < 9; row++) {
      const seen = new Set();
      for (let col = 0; col < 9; col++) {
        const val = board[row][col];
        if (val !== 0) {
          if (seen.has(val)) return false;
          seen.add(val);
        }
      }
    }
    
    // Check columns
    for (let col = 0; col < 9; col++) {
      const seen = new Set();
      for (let row = 0; row < 9; row++) {
        const val = board[row][col];
        if (val !== 0) {
          if (seen.has(val)) return false;
          seen.add(val);
        }
      }
    }
    
    // Check 3x3 boxes
    for (let boxRow = 0; boxRow < 3; boxRow++) {
      for (let boxCol = 0; boxCol < 3; boxCol++) {
        const seen = new Set();
        for (let row = boxRow * 3; row < boxRow * 3 + 3; row++) {
          for (let col = boxCol * 3; col < boxCol * 3 + 3; col++) {
            const val = board[row][col];
            if (val !== 0) {
              if (seen.has(val)) return false;
              seen.add(val);
            }
          }
        }
      }
    }
    
    return true;
  }

  let gameFinished = false;
  
  function autoSubmitSolution() {
    if (gameFinished) return; // Prevent multiple submissions
    
    gameFinished = true;
    addMessage('🎉 Puzzle completed! Submitting solution...', 'success');
    
    // Hide finish button since we're auto-submitting
    const finishBtn = document.getElementById('finish-btn');
    if (finishBtn) {
      finishBtn.style.display = 'none';
    }
    
    // Disable all inputs
    disableAllInputs();
    
    // Submit the solution
    safeSend({ type: 'complete' });
  }

  function disableAllInputs() {
    const inputs = document.querySelectorAll('.cell-input');
    inputs.forEach(input => {
      input.disabled = true;
      input.classList.add('game-finished');
    });
  }

  function handleGameFinished(data) {
    gameFinished = true;
    stopTimers();
    disableAllInputs();
    
    // Hide race controls
    const raceControls = document.querySelector('.race-controls');
    if (raceControls) {
      raceControls.style.display = 'none';
    }
    
    // Show winner message in chat
    const isWinner = data.winner_id == playerId;
    const winnerMessage = isWinner ? 
      `🏆 Congratulations! You won in ${data.winner_time}!` :
      `${data.winner_username} won in ${data.winner_time}. Better luck next time!`;
    
    addMessage(winnerMessage, isWinner ? 'success' : 'info');
    
    // Show winner modal
    showWinnerModal(data, isWinner);
  }

  function showWinnerModal(data, isWinner) {
    const modal = document.getElementById('winner-modal');
    const winnerContent = document.getElementById('winner-content');
    const gameStats = document.getElementById('game-stats');
    
    // Populate winner content
    if (isWinner) {
      winnerContent.innerHTML = `
        <h4 class="text-success">🏆 Congratulations!</h4>
        <p class="lead">You won the race!</p>
      `;
    } else {
      winnerContent.innerHTML = `
        <h4 class="text-info">Good Game!</h4>
        <p class="lead">${data.winner_username} won this round</p>
      `;
    }
    
    // Populate game stats
    const difficulty = gameDataEl.dataset.difficulty;
    gameStats.innerHTML = `
      <div class="row">
        <div class="col-6"><strong>Winner:</strong></div>
        <div class="col-6">${data.winner_username}</div>
      </div>
      <div class="row">
        <div class="col-6"><strong>Time:</strong></div>
        <div class="col-6">${formatTime(data.winner_time)}</div>
      </div>
      <div class="row">
        <div class="col-6"><strong>Difficulty:</strong></div>
        <div class="col-6">${difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}</div>
      </div>
    `;
    
    // Show modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
  }

  function formatTime(timeString) {
    // Parse time string and format nicely
    try {
      const parts = timeString.split(':');
      if (parts.length >= 2) {
        const minutes = parseInt(parts[1]);
        const seconds = parseFloat(parts[2]);
        return `${minutes}:${seconds.toFixed(1).padStart(4, '0')}`;
      }
    } catch (e) {
      // Fallback
    }
    return timeString;
  }

  function handleNewGameCreated(data) {
    addMessage(`New game created! Redirecting to game ${data.game_code}...`, 'success');
    
    // Close the modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('winner-modal'));
    if (modal) {
      modal.hide();
    }
    
    // Redirect to new game after a short delay
    setTimeout(() => {
      window.location.href = `/game/${data.game_code}/`;
    }, 1500);
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
