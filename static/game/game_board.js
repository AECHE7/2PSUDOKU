/**
 * Refactored Sudoku Race Game Frontend
 * Uses structured WebSocket messages and centralized state management
 */

document.addEventListener('DOMContentLoaded', () => {
  // Configuration
  const gameDataEl = document.getElementById('game-data');
  const config = {
    gameCode: gameDataEl.dataset.gameCode,
    playerId: parseInt(gameDataEl.dataset.playerId),
    player1Id: parseInt(gameDataEl.dataset.player1Id),
    player2Id: gameDataEl.dataset.player2Id ? parseInt(gameDataEl.dataset.player2Id) : null,
    isPlayer1: gameDataEl.dataset.isPlayer1 === 'true',
    isPlayer2: gameDataEl.dataset.isPlayer2 === 'true',
    difficulty: gameDataEl.dataset.difficulty
  };

  // Game State
  const gameState = {
    connected: false,
    gameStarted: false,
    gameFinished: false,
    raceStartTime: null,
    board: [],
    puzzle: [],
    opponentBoard: [],
    timerInterval: null,
    selectedCell: null,
    selectedNumber: null,
    moveHistory: [],
    statistics: {
      validMoves: 0,
      invalidMoves: 0,
      totalMoves: 0,
      accuracy: 0,
      cellsFilled: 0
    }
  };

  // WebSocket Connection
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${window.location.host}/ws/game/${config.gameCode}/`;
  const ws = new WebSocket(wsUrl);

  // Message Queue for offline handling
  const messageQueue = [];
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 5;

  // DOM Elements
  const elements = {
    messages: document.getElementById('messages'),
    player1Timer: document.getElementById('player1-timer'),
    player2Timer: document.getElementById('player2-timer'),
    elapsedTime: document.getElementById('elapsed-time'),
    gameStatus: document.getElementById('game-status'),
    cellsFilled: document.getElementById('cells-filled'),
    accuracyRate: document.getElementById('accuracy-rate'),
    mistakeCount: document.getElementById('mistake-count')
  };

  // WebSocket Event Handlers
  ws.onopen = () => {
    console.log('WebSocket connected');
    gameState.connected = true;
    reconnectAttempts = 0;
    addMessage('Connected to game server', 'success');

    // Process queued messages
    processMessageQueue();

    // Send join message
    sendMessage({
      type: 'join_game',
      player_id: config.playerId
    });
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleMessage(message);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
      addMessage('Error processing server message', 'error');
    }
  };

  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    gameState.connected = false;

    if (event.code === 1000) {
      addMessage('Connection closed normally', 'info');
    } else {
      addMessage(`Disconnected from server (Code: ${event.code})`, 'error');
      handleReconnection();
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    addMessage('Connection error - please check your internet connection', 'error');
  };

  // Message Handling
  function handleMessage(message) {
    console.log('Received message:', message.type, message);

    const handlers = {
      game_state: handleGameState,
      race_started: handleRaceStarted,
      countdown: handleCountdown,
      move_made: handleMoveMade,
      race_finished: handleRaceFinished,
      new_game_created: handleNewGameCreated,
      player_left_game: handlePlayerLeftGame,
      error: handleError,
      notification: handleNotification
    };

    const handler = handlers[message.type];
    if (handler) {
      handler(message);
    } else {
      console.warn('Unknown message type:', message.type);
    }
  }

  function handleGameState(message) {
    console.log('Handling game state:', message);

    // Update local state
    gameState.puzzle = message.puzzle || [];
    gameState.board = message.board || message.puzzle || [];
    gameState.opponentBoard = message.opponent_board || [];

    // Update UI
    updateBoard(gameState.board, false);
    updateGameInfo(message);

    // Start timers if race is in progress
    if (message.start_time && message.status === 'in_progress') {
      startTimers(new Date(message.start_time));
    }

    // Validate board
    setTimeout(() => validateBoard(), 100);
  }

  function handleRaceStarted(message) {
    console.log('Race started:', message);

    gameState.gameStarted = true;
    gameState.raceStartTime = new Date(message.start_time);

    // Hide countdown
    const countdownElement = document.getElementById('countdown');
    if (countdownElement) {
      countdownElement.style.display = 'none';
    }

    // Update puzzle if provided
    if (message.puzzle) {
      gameState.puzzle = message.puzzle;
      updateBoard(gameState.board, false);
    }

    // Start timers
    startTimers(gameState.raceStartTime);

    // Update UI
    if (elements.gameStatus) {
      elements.gameStatus.innerHTML = '🏁 Racing';
      elements.gameStatus.style.color = 'green';
    }

    addMessage('🏁 Race started — good luck!', 'success');
  }

  function handleMoveMade(message) {
    console.log('Move made:', message);

    // Update board if it's opponent's move
    if (message.player_id !== config.playerId) {
      updateOpponentMove(message.row, message.col, message.value);
      addMessage(`${message.username} made a move`, 'info');
    }

    // Update statistics
    updateStatistics();
  }

  function handleRaceFinished(message) {
    console.log('Race finished:', message);

    gameState.gameFinished = true;
    stopTimers();

    // Disable all inputs
    disableAllInputs();

    // Update UI
    if (elements.gameStatus) {
      elements.gameStatus.innerHTML = '🏆 Finished';
      elements.gameStatus.style.color = 'gold';
    }

    // Show results
    const isWinner = message.winner_id === config.playerId;
    const resultMessage = isWinner
      ? `🏆 YOU WON! Completed in ${message.winner_time}`
      : `${message.winner_username} won in ${message.winner_time}. You: ${message.loser_time || 'Did not finish'}`;

    addMessage(resultMessage, isWinner ? 'success' : 'info');

    // Show winner modal
    showWinnerModal(message, isWinner);
  }

  function handleNewGameCreated(message) {
    addMessage(`New game created! Redirecting...`, 'success');

    setTimeout(() => {
      window.location.href = `/game/${message.game_code}/`;
    }, 1500);
  }

  function handlePlayerLeftGame(message) {
    addMessage(`${message.leaving_player} left the game`, 'warning');

    if (message.leaving_player !== config.username) {
      showGameEndModal('Opponent Left', 'Your opponent has left the game.');
    }
  }

  function handleError(message) {
    addMessage(`Error: ${message.error}`, 'error');
  }

  function handleNotification(message) {
    addMessage(message.message, message.level || 'info');
  }

  function handleCountdown(message) {
    const countdownElement = document.getElementById('countdown');
    if (countdownElement) {
      countdownElement.textContent = `Race starts in ${message.seconds}...`;
      countdownElement.style.display = 'block';
    }

    // Also show countdown in game status
    if (elements.gameStatus) {
      elements.gameStatus.innerHTML = `⏱️ Race starts in ${message.seconds}...`;
      elements.gameStatus.style.color = 'orange';
    }

    addMessage(`⏱️ Race starts in ${message.seconds}...`, 'info');
  }

  // UI Update Functions
  function updateBoard(board, isOpponent = false) {
    const boardElement = isOpponent
      ? document.getElementById('opponent-board')
      : document.getElementById('player-board');

    if (!boardElement) return;

    const cells = boardElement.querySelectorAll('.cell-input');

    cells.forEach((cell, index) => {
      const row = Math.floor(index / 9);
      const col = index % 9;
      const value = board[row] && board[row][col];

      if (value && value !== 0) {
        cell.value = value;
        cell.classList.add('filled');
        if (isOpponent) {
          cell.classList.add('opponent-move');
        }
      }
    });

    if (!isOpponent) {
      updateStatistics();
    }
  }

  function updateOpponentMove(row, col, value) {
    // Update opponent board display
    const opponentBoard = document.getElementById('opponent-board');
    if (opponentBoard) {
      const cell = opponentBoard.querySelector(`[data-row="${row}"][data-col="${col}"] .cell-input`);
      if (cell) {
        cell.value = value;
        cell.classList.add('opponent-move');
      }
    }
  }

  function updateGameInfo(message) {
    // Update player info display
    const player1El = document.getElementById('player1-name');
    const player2El = document.getElementById('player2-name');

    if (player1El && message.player1) {
      player1El.textContent = message.player1;
    }
    if (player2El && message.player2) {
      player2El.textContent = message.player2 || 'Waiting...';
    }

    // Update game status
    if (elements.gameStatus) {
      const statusText = {
        waiting: '⏳ Waiting for players',
        ready: '✅ Ready to start',
        in_progress: '🏁 Racing',
        finished: '🏆 Finished',
        abandoned: '❌ Abandoned'
      }[message.status] || message.status;

      elements.gameStatus.innerHTML = statusText;
    }
  }

  function updateStatistics() {
    // Count filled cells
    const playerBoard = document.getElementById('player-board');
    if (playerBoard) {
      const filledCells = playerBoard.querySelectorAll('.cell-input[value]:not([value=""])').length;
      gameState.statistics.cellsFilled = filledCells;

      if (elements.cellsFilled) {
        elements.cellsFilled.textContent = `${filledCells}/81`;
      }
    }

    // Update accuracy
    if (gameState.statistics.totalMoves > 0) {
      gameState.statistics.accuracy = Math.round(
        (gameState.statistics.validMoves / gameState.statistics.totalMoves) * 100
      );

      if (elements.accuracyRate) {
        elements.accuracyRate.textContent = `${gameState.statistics.accuracy}%`;
      }
    }
  }

  // Timer Functions
  function startTimers(startTime) {
    console.log('Starting timers from:', startTime);

    stopTimers(); // Clear any existing timer

    gameState.timerInterval = setInterval(() => {
      const now = new Date();
      const elapsed = Math.max(0, Math.floor((now - startTime) / 1000));
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

      // Update all timer displays
      if (elements.player1Timer) elements.player1Timer.textContent = timeString;
      if (elements.player2Timer) elements.player2Timer.textContent = timeString;
      if (elements.elapsedTime) elements.elapsedTime.textContent = timeString;
    }, 500);
  }

  function stopTimers() {
    if (gameState.timerInterval) {
      clearInterval(gameState.timerInterval);
      gameState.timerInterval = null;
    }
  }

  // Input Handling
  document.addEventListener('change', (e) => {
    if (!e.target.classList.contains('cell-input') || e.target.disabled) return;

    const cell = e.target.closest('.sudoku-cell');
    if (!cell) return;

    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    const value = parseInt(e.target.value);

    if (value >= 1 && value <= 9) {
      handlePlayerMove(row, col, value, e.target);
    } else if (e.target.value === '') {
      // Clear cell
      e.target.classList.remove('correct', 'incorrect', 'invalid');
    }
  });

  function handlePlayerMove(row, col, value, cellElement) {
    // Clear previous validation
    cellElement.classList.remove('correct', 'incorrect', 'invalid');

    // Validate move
    const isValid = validateMove(row, col, value);

    // Update statistics
    gameState.statistics.totalMoves++;
    if (isValid) {
      gameState.statistics.validMoves++;
      cellElement.classList.add('correct');
    } else {
      gameState.statistics.invalidMoves++;
      cellElement.classList.add('incorrect');
    }

    // Record move
    gameState.moveHistory.push({
      row, col, value, isValid,
      timestamp: new Date().toISOString()
    });

    // Send to server
    sendMessage({
      type: 'move',
      row: row,
      col: col,
      value: value
    });

    // Update UI
    updateStatistics();

    // Check for completion
    setTimeout(() => {
      if (isBoardComplete() && isBoardValid()) {
        autoSubmitSolution();
      }
    }, 100);

    // Clear validation classes after animation
    setTimeout(() => {
      cellElement.classList.remove('correct', 'incorrect');
    }, 500);
  }

  // Validation Functions
  function validateMove(row, col, value) {
    // Check row
    for (let c = 0; c < 9; c++) {
      if (c !== col && getCellValue(row, c) === value) {
        return false;
      }
    }

    // Check column
    for (let r = 0; r < 9; r++) {
      if (r !== row && getCellValue(r, col) === value) {
        return false;
      }
    }

    // Check 3x3 box
    const boxRow = Math.floor(row / 3) * 3;
    const boxCol = Math.floor(col / 3) * 3;

    for (let r = boxRow; r < boxRow + 3; r++) {
      for (let c = boxCol; c < boxCol + 3; c++) {
        if ((r !== row || c !== col) && getCellValue(r, c) === value) {
          return false;
        }
      }
    }

    return true;
  }

  function getCellValue(row, col) {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return 0;

    const cell = playerBoard.querySelector(`[data-row="${row}"][data-col="${col}"] .cell-input`);
    return cell ? parseInt(cell.value) || 0 : 0;
  }

  function isBoardComplete() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return false;

    const inputs = playerBoard.querySelectorAll('.cell-input');
    return Array.from(inputs).every(input => input.value && input.value !== '');
  }

  function isBoardValid() {
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 9; col++) {
        const value = getCellValue(row, col);
        if (value && !validateMove(row, col, value)) {
          return false;
        }
      }
    }
    return true;
  }

  function validateBoard() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;

    const cells = playerBoard.querySelectorAll('.cell-input');

    cells.forEach((cell, index) => {
      const row = Math.floor(index / 9);
      const col = index % 9;
      const value = parseInt(cell.value);

      cell.classList.remove('invalid');

      if (value && !validateMove(row, col, value)) {
        cell.classList.add('invalid');
      }
    });
  }

  // Auto-submit when puzzle is complete
  function autoSubmitSolution() {
    if (gameState.gameFinished) return;

    gameState.gameFinished = true;
    addMessage('🎉 Puzzle completed! Submitting solution...', 'success');

    // Disable inputs
    disableAllInputs();

    // Stop timers
    stopTimers();

    // Calculate completion time
    const completionTime = gameState.raceStartTime
      ? new Date() - gameState.raceStartTime
      : 0;

    // Send completion
    sendMessage({
      type: 'complete',
      completion_time: completionTime
    });
  }

  function disableAllInputs() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;

    const inputs = playerBoard.querySelectorAll('.cell-input');
    inputs.forEach(input => {
      input.disabled = true;
      input.classList.add('game-finished');
    });
  }

  // Message Sending
  function sendMessage(message) {
    if (ws.readyState === WebSocket.OPEN && gameState.connected) {
      try {
        ws.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Error sending message:', error);
        return false;
      }
    } else {
      console.log('WebSocket not connected, queuing message');
      messageQueue.push(message);
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

  // UI Helper Functions
  function addMessage(text, className = '') {
    if (!elements.messages) return;

    const div = document.createElement('div');
    div.className = `message ${className}`;
    div.textContent = text;
    elements.messages.appendChild(div);
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  function showWinnerModal(data, isWinner) {
    const modal = document.getElementById('winner-modal');
    const winnerContent = document.getElementById('winner-content');
    const gameStats = document.getElementById('game-stats');

    if (!modal) {
      console.error('Winner modal not found');
      return;
    }

    // Update content
    if (winnerContent) {
      winnerContent.innerHTML = isWinner
        ? '<h4 class="text-success">🏆 Congratulations!</h4><p class="lead">You won the race!</p>'
        : `<h4 class="text-info">Good Game!</h4><p class="lead">${data.winner_username} won this round</p>`;
    }

    if (gameStats) {
      gameStats.innerHTML = `
        <div class="row">
          <div class="col-6"><strong>Winner:</strong></div>
          <div class="col-6">${data.winner_username}</div>
        </div>
        <div class="row">
          <div class="col-6"><strong>Time:</strong></div>
          <div class="col-6">${data.winner_time}</div>
        </div>
      `;
    }

    // Show modal
    try {
      const bsModal = new bootstrap.Modal(modal, { backdrop: 'static', keyboard: false });
      bsModal.show();
    } catch (error) {
      console.error('Error showing modal:', error);
      modal.style.display = 'block';
      modal.classList.add('show');
    }
  }

  function showGameEndModal(title, message) {
    const modalHtml = `
      <div class="modal fade show" style="display: block;">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">${title}</h5>
            </div>
            <div class="modal-body">
              <p>${message}</p>
            </div>
            <div class="modal-footer">
              <button class="btn btn-primary" onclick="location.reload()">Play Again</button>
              <button class="btn btn-secondary" onclick="window.location.href='/'">Return to Lobby</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop fade show"></div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

  // Reconnection Handling
  function handleReconnection() {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      addMessage('❌ Connection failed. Please refresh the page manually.', 'error');
      showGameEndModal('Connection Lost', 'Unable to reconnect to the game server. Please refresh the page.');
      return;
    }

    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);

    addMessage(`Reconnecting in ${Math.floor(delay/1000)}s... (Attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`, 'info');

    setTimeout(() => {
      if (!gameState.connected) {
        location.reload();
      }
    }, delay);
  }

  // Event Listeners
  document.addEventListener('click', (e) => {
    // Number pad
    if (e.target.classList.contains('number-btn')) {
      const number = e.target.dataset.number;
      if (gameState.selectedCell && !gameState.selectedCell.disabled) {
        gameState.selectedCell.value = number;
        gameState.selectedCell.dispatchEvent(new Event('change'));
      }
    }

    // Play again button
    if (e.target.id === 'play-again-btn') {
      sendMessage({
        type: 'play_again',
        difficulty: config.difficulty
      });
    }

    // Leave game button
    if (e.target.id === 'leave-game-btn') {
      if (confirm('Are you sure you want to leave the game?')) {
        sendMessage({ type: 'leave_game' });
      }
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (gameState.selectedCell && !gameState.selectedCell.disabled) {
      if (e.key >= '1' && e.key <= '9') {
        gameState.selectedCell.value = e.key;
        gameState.selectedCell.dispatchEvent(new Event('change'));
        e.preventDefault();
      } else if (e.key === 'Backspace' || e.key === 'Delete') {
        gameState.selectedCell.value = '';
        gameState.selectedCell.dispatchEvent(new Event('change'));
        e.preventDefault();
      }
    }

    // Ctrl+Enter to finish
    if (e.ctrlKey && e.key === 'Enter') {
      if (isBoardComplete() && isBoardValid() && !gameState.gameFinished) {
        autoSubmitSolution();
      }
      e.preventDefault();
    }
  });

  // Cell selection
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell-input')) {
      const playerBoard = document.getElementById('player-board');
      if (playerBoard.contains(e.target)) {
        selectCell(e.target);
      }
    }
  });

  function selectCell(cellElement) {
    // Remove previous selection
    if (gameState.selectedCell) {
      gameState.selectedCell.classList.remove('selected');
    }

    // Select new cell
    gameState.selectedCell = cellElement;
    cellElement.classList.add('selected');

    // Highlight related cells
    highlightRelatedCells(
      parseInt(cellElement.closest('.sudoku-cell').dataset.row),
      parseInt(cellElement.closest('.sudoku-cell').dataset.col)
    );
  }

  function highlightRelatedCells(row, col) {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;

    const cells = playerBoard.querySelectorAll('.cell-input');

    cells.forEach((cell, index) => {
      const cellRow = Math.floor(index / 9);
      const cellCol = index % 9;

      if (cellRow === row || cellCol === col ||
          (Math.floor(cellRow / 3) === Math.floor(row / 3) &&
           Math.floor(cellCol / 3) === Math.floor(col / 3))) {
        cell.classList.add('highlighted');
      }
    });
  }

  // Initialize
  console.log('Sudoku Race game initialized with config:', config);
});
