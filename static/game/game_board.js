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
  
  // UI State Management
  let selectedCell = null;
  let selectedNumber = null;
  let mistakeCount = 0;
  let startTime = null;
  let elapsedInterval = null;

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
    console.log('WebSocket message received:', data);
    
    if (data.type === 'notification') {
      addMessage(data.message);
    } else if (data.type === 'game_state') {
      // Initial state: puzzle + both player boards
      updateBoardFromState(data.board, false); // Player's board
      if (data.opponent_board) {
        updateBoardFromState(data.opponent_board, true); // Opponent's board
      }
      addMessage(`Room: players ${data.player1} vs ${data.player2 || 'Waiting...'}`);
      // If race already started, start timers
      if (data.start_time) {
        startTimers(new Date(data.start_time));
        startElapsedTimer();
      }
    } else if (data.type === 'move') {
      // Show move in chat
      addMessage(`${data.username} placed ${data.value} at row ${data.row + 1}, col ${data.col + 1}`);
      
      // Update the appropriate board in real-time
      if (data.player_id == playerId) {
        // Update player's own board (shouldn't be needed but for consistency)
        updatePlayerBoard(data.row, data.col, data.value);
      } else {
        // Update opponent's board display
        updateOpponentBoard(data.row, data.col, data.value);
        addMessage(`${data.username} is making progress...`, 'info');
      }
    } else if (data.type === 'board') {
      updateBoardFromState(data.board);
    } else if (data.type === 'race_started') {
      // Start timers and ensure both boards have the puzzle
      const startTime = new Date(data.start_time);
      startTimers(startTime);
      startElapsedTimer();
      
      if (data.puzzle) {
        updateBoardFromState(data.board || data.puzzle);
      }
      
      // Update game status
      document.getElementById('game-status').innerHTML = '🏁 Racing';
      
      addMessage('Race started — good luck!');
    } else if (data.type === 'race_finished') {
      handleGameFinished(data);
    } else if (data.type === 'game_progress_update') {
      // Real-time board state update
      if (data.player_id != playerId) {
        // Update opponent's board with their current progress
        updateBoardFromState(data.board, true);
      }
    } else if (data.type === 'player_ready_status') {
      // Live status updates
      handlePlayerReadyStatus(data);
    } else if (data.type === 'new_game_created') {
      handleNewGameCreated(data);
    } else if (data.type === 'player_left_game') {
      handlePlayerLeftGame(data);
    } else if (data.type === 'leave_game_confirmed') {
      handleLeaveConfirmed(data);
    } else if (data.error) {
      addMessage(`Error: ${data.error}`, 'error');
      
      // If completion failed, reset game state so player can try again
      if (data.error.includes('not a valid completed solution')) {
        gameFinished = false;
        addMessage('Please check your solution and try again.', 'info');
        
        // Re-enable finish button
        const finishBtn = document.getElementById('finish-btn');
        if (finishBtn) {
          finishBtn.style.display = 'inline-block';
        }
      }
    }
  };
  
  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    isConnected = false;
    
    if (event.code === 1000) {
      addMessage('Connection closed normally', 'info');
    } else {
      addMessage(`Disconnected from server (Code: ${event.code})`, 'error');
      
      // Attempt to reconnect after a delay if not a normal closure
      if (event.code !== 1000 && !gameFinished) {
        setTimeout(() => {
          addMessage('Attempting to reconnect...', 'info');
          location.reload(); // Simple reconnection strategy
        }, 3000);
      }
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    addMessage('Connection error - please check your internet connection', 'error');
  };
  
  // Enhanced Cell Input Handling
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('cell-input') && !e.target.disabled) {
      // Only allow selection on player's own board
      const playerBoard = document.getElementById('player-board');
      if (playerBoard.contains(e.target)) {
        selectCell(e.target);
      }
    }
  });

  document.addEventListener('change', (e) => {
    if (!e.target.classList.contains('cell-input')) return;
    if (e.target.disabled) return;
    
    const cell = e.target.closest('.sudoku-cell');
    if (!cell) return;
    
    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    const value = parseInt(e.target.value);
    
    if (value && value >= 1 && value <= 9) {
      // Validate move immediately
      const isValidMove = validateMove(row, col, value);
      
      if (isValidMove) {
        e.target.classList.add('correct');
        e.target.classList.remove('incorrect');
        setTimeout(() => e.target.classList.remove('correct'), 500);
      } else {
        e.target.classList.add('incorrect');
        e.target.classList.remove('correct');
        mistakeCount++;
        updateMistakeCount();
        setTimeout(() => e.target.classList.remove('incorrect'), 500);
      }

      safeSend({
        type: 'move',
        row: row,
        col: col,
        value: value,
      });
      
      updateCellsFilledCount();
      highlightRelatedCells(row, col, value);
      
    } else if (e.target.value === '') {
      updateCellsFilledCount();
      clearHighlights();
      return;
    }

    // After each input, check if puzzle is complete and auto-submit
    const isComplete = isLocalBoardComplete();
    const isValid = isLocalBoardValid();
    console.log('Board check:', { isComplete, isValid });
    
    if (isComplete && isValid) {
      console.log('Auto-submitting solution...');
      autoSubmitSolution();
    }
  });

  // Number Pad Integration
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('number-btn')) {
      const number = e.target.dataset.number;
      selectNumber(number);
      
      if (selectedCell && !selectedCell.disabled) {
        selectedCell.value = number;
        selectedCell.dispatchEvent(new Event('change'));
      }
    }
  });

  // Keyboard Support
  document.addEventListener('keydown', (e) => {
    if (selectedCell && !selectedCell.disabled) {
      if (e.key >= '1' && e.key <= '9') {
        selectedCell.value = e.key;
        selectedCell.dispatchEvent(new Event('change'));
        e.preventDefault();
      } else if (e.key === 'Backspace' || e.key === 'Delete') {
        selectedCell.value = '';
        selectedCell.dispatchEvent(new Event('change'));
        e.preventDefault();
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        navigateGrid(e.key);
        e.preventDefault();
      }
    }
  });

  // Ready UI
  const readyBtn = document.getElementById('ready-btn');
  if (readyBtn) {
    readyBtn.addEventListener('click', () => {
      console.log('Ready button clicked');
      safeSend({ type: 'ready' });
      readyBtn.disabled = true;
      readyBtn.textContent = 'Waiting for opponent...';
      readyBtn.classList.remove('btn-success', 'btn-primary');
      readyBtn.classList.add('btn-secondary');
    });
  }

  // Finish button (kept for manual submission if needed)
  const finishBtn = document.getElementById('finish-btn');
  if (finishBtn) {
    finishBtn.addEventListener('click', () => {
      console.log('Finish button clicked');
      const isComplete = isLocalBoardComplete();
      const isValid = isLocalBoardValid();
      console.log('Manual finish check:', { isComplete, isValid, gameFinished });
      
      if (!gameFinished && isComplete && isValid) {
        autoSubmitSolution();
      } else if (!isComplete) {
        addMessage('Please complete the puzzle before submitting!', 'error');
      } else if (!isValid) {
        addMessage('Please fix the errors in your solution!', 'error');
      } else if (gameFinished) {
        addMessage('Game already finished!', 'info');
      }
    });
  }

  // Play Again button
  document.addEventListener('click', (e) => {
    if (e.target.id === 'play-again-btn') {
      handlePlayAgain();
    }
  });

  // Leave Game button
  const leaveGameBtn = document.getElementById('leave-game-btn');
  if (leaveGameBtn) {
    leaveGameBtn.addEventListener('click', () => {
      handleLeaveGame();
    });
  }

  // Enhanced keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl+Enter to submit solution
    if (e.ctrlKey && e.key === 'Enter') {
      const finishBtn = document.getElementById('finish-btn');
      if (finishBtn && !finishBtn.disabled) {
        finishBtn.click();
      }
      e.preventDefault();
    }
    
    // Ctrl+Q to leave game
    if (e.ctrlKey && e.key === 'q') {
      handleLeaveGame();
      e.preventDefault();
    }
    
    // Escape to deselect cell
    if (e.key === 'Escape') {
      if (selectedCell) {
        selectedCell.classList.remove('selected');
        selectedCell = null;
        clearHighlights();
      }
      e.preventDefault();
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
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return false;
    const inputs = playerBoard.querySelectorAll('.cell-input');
    for (const input of inputs) {
      if (!input.value || input.value === '') return false;
    }
    return true;
  }

  function isLocalBoardValid() {
    // Basic validation - check for duplicates in rows, columns, and boxes
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return false;
    const inputs = playerBoard.querySelectorAll('.cell-input');
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
    
    console.log('Auto-submitting solution!');
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
    const success = safeSend({ type: 'complete' });
    console.log('Complete message sent:', success);
    
    if (!success) {
      addMessage('❌ Failed to submit solution. Check connection.', 'error');
      gameFinished = false; // Allow retry
    }
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

  function handleGameFinished(data) {
    gameFinished = true;
    stopTimers();
    stopElapsedTimer();
    disableAllInputs();
    clearHighlights();
    
    // Update game status
    document.getElementById('game-status').innerHTML = '🏆 Finished';
    
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
    console.log('Showing winner modal:', { data, isWinner });
    const modal = document.getElementById('winner-modal');
    const winnerContent = document.getElementById('winner-content');
    const gameStats = document.getElementById('game-stats');
    
    if (!modal) {
      console.error('Winner modal element not found!');
      return;
    }
    
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
    try {
      if (typeof bootstrap !== 'undefined') {
        const bootstrapModal = new bootstrap.Modal(modal, {
          backdrop: 'static',
          keyboard: false
        });
        bootstrapModal.show();
        console.log('Bootstrap modal shown');
      } else {
        console.error('Bootstrap not loaded!');
        // Fallback: show modal manually with backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop fade show';
        backdrop.id = 'modal-backdrop';
        document.body.appendChild(backdrop);
        
        modal.style.display = 'block';
        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('modal-open');
        
        // Add backdrop click handling
        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) {
            // Don't close modal on backdrop click (game finished state)
          }
        });
      }
    } catch (error) {
      console.error('Error showing modal:', error);
      // Simple fallback
      alert(`Game Over! ${isWinner ? 'You won!' : data.winner_username + ' won!'}`);
    }
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
    try {
      const modalElement = document.getElementById('winner-modal');
      const modal = bootstrap.Modal.getInstance(modalElement);
      if (modal) {
        modal.hide();
      } else {
        // Fallback manual close
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');
        const backdrop = document.getElementById('modal-backdrop');
        if (backdrop) backdrop.remove();
      }
    } catch (error) {
      console.error('Error closing modal:', error);
    }
    
    // Redirect to new game after a short delay
    setTimeout(() => {
      window.location.href = `/game/${data.game_code}/`;
    }, 1500);
  }

  function handlePlayerLeftGame(data) {
    // Handle when a player leaves the game
    const { leaving_player, remaining_player, reason, game_status } = data;
    
    if (leaving_player === username) {
      // This player left - shouldn't happen since we redirect
      addMessage('You have left the game.', 'info');
    } else {
      // Opponent left
      addMessage(`${leaving_player} has left the game.`, 'warning');
      
      if (reason === 'user_request') {
        addMessage('You win by forfeit! 🎉', 'success');
      } else {
        addMessage('Game abandoned due to disconnection.', 'warning');
      }
      
      // Show options to player
      showGameEndOptions({
        type: 'forfeit',
        winner: remaining_player,
        message: `${leaving_player} left the game`,
      });
      
      // Disable game controls
      disableGameControls();
    }
  }

  function handleLeaveConfirmed(data) {
    // Handle leave game confirmation
    addMessage(data.message, 'success');
    
    // Show leaving message
    const gameBoard = document.getElementById('game-board');
    if (gameBoard) {
      gameBoard.innerHTML = `
        <div class="text-center py-5">
          <div class="spinner-border text-primary mb-3" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
          <h4>Leaving game...</h4>
          <p class="text-muted">Redirecting to main page...</p>
        </div>
      `;
    }
  }

  function disableGameControls() {
    // Disable all game interaction elements
    const inputs = document.querySelectorAll('.cell-input');
    inputs.forEach(input => {
      input.disabled = true;
      input.style.opacity = '0.6';
    });
    
    const buttons = document.querySelectorAll('.game-controls button');
    buttons.forEach(button => {
      if (!button.classList.contains('btn-secondary')) { // Keep leave button enabled
        button.disabled = true;
      }
    });
    
    // Update game status
    const statusEl = document.getElementById('game-status');
    if (statusEl) {
      statusEl.innerHTML = '❌ Game Ended';
    }
  }

  function showGameEndOptions(result) {
    // Create or update modal for game end
    let modal = document.getElementById('gameEndModal');
    
    if (!modal) {
      // Create modal if it doesn't exist
      modal = document.createElement('div');
      modal.className = 'modal fade';
      modal.id = 'gameEndModal';
      modal.innerHTML = `
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Game Ended</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div id="gameEndContent"></div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              <button type="button" class="btn btn-primary" onclick="window.location.href = '/'">
                Return to Lobby
              </button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
    
    // Update modal content
    const content = document.getElementById('gameEndContent');
    content.innerHTML = `
      <div class="text-center">
        <i class="fas fa-trophy text-warning fa-3x mb-3"></i>
        <h4>${result.type === 'forfeit' ? 'Victory by Forfeit!' : 'Game Over'}</h4>
        <p class="lead">${result.message}</p>
        <p class="text-muted">The game has ended and cannot be continued.</p>
      </div>
    `;
    
    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
  }

  // Interactive UI Functions
  function selectCell(cellInput) {
    // Remove previous selection
    if (selectedCell) {
      selectedCell.classList.remove('selected');
    }
    
    // Select new cell
    selectedCell = cellInput;
    selectedCell.classList.add('selected');
    
    // Highlight related cells
    const row = parseInt(selectedCell.dataset.row);
    const col = parseInt(selectedCell.dataset.col);
    const value = selectedCell.value;
    
    clearHighlights();
    highlightRelatedCells(row, col, value);
  }

  function selectNumber(number) {
    // Remove previous number selection
    document.querySelectorAll('.number-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Select new number
    const numberBtn = document.querySelector(`[data-number="${number}"]`);
    if (numberBtn) {
      numberBtn.classList.add('active');
      selectedNumber = number;
    }
  }

  function highlightRelatedCells(row, col, value) {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    const cells = playerBoard.querySelectorAll('.cell-input');

    cells.forEach((cell, index) => {
      const cellRow = Math.floor(index / 9);
      const cellCol = index % 9;

      // Highlight same row, column, or 3x3 box
      if (cellRow === row || cellCol === col || 
          (Math.floor(cellRow / 3) === Math.floor(row / 3) && 
           Math.floor(cellCol / 3) === Math.floor(col / 3))) {
        cell.classList.add('highlighted');
      }

      // Highlight cells with same value
      if (value && cell.value === value) {
        cell.classList.add('highlighted');
      }
    });
  }

  function clearHighlights() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    playerBoard.querySelectorAll('.cell-input').forEach(cell => {
      cell.classList.remove('highlighted');
    });
  }

  function navigateGrid(key) {
    if (!selectedCell) return;
    
    const currentRow = parseInt(selectedCell.dataset.row);
    const currentCol = parseInt(selectedCell.dataset.col);
    let newRow = currentRow;
    let newCol = currentCol;
    
    switch (key) {
      case 'ArrowUp': newRow = Math.max(0, currentRow - 1); break;
      case 'ArrowDown': newRow = Math.min(8, currentRow + 1); break;
      case 'ArrowLeft': newCol = Math.max(0, currentCol - 1); break;
      case 'ArrowRight': newCol = Math.min(8, currentCol + 1); break;
    }
    
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    const newCell = playerBoard.querySelector(`[data-row="${newRow}"][data-col="${newCol}"]`);
    if (newCell && !newCell.disabled) {
      selectCell(newCell.querySelector('.cell-input') || newCell);
      const focusEl = newCell.querySelector('.cell-input') || newCell;
      if (focusEl && typeof focusEl.focus === 'function') focusEl.focus();
    }
  }

  function validateMove(row, col, value) {
    // Basic client-side validation on player's board only
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return true; // if no player board in DOM, skip strict checks
    const cells = playerBoard.querySelectorAll('.cell-input');
    
    // Check row
    for (let c = 0; c < 9; c++) {
      if (c !== col) {
        const cell = cells[row * 9 + c];
        if (cell.value == value) return false;
      }
    }
    
    // Check column
    for (let r = 0; r < 9; r++) {
      if (r !== row) {
        const cell = cells[r * 9 + col];
        if (cell.value == value) return false;
      }
    }
    
    // Check 3x3 box
    const boxRow = Math.floor(row / 3) * 3;
    const boxCol = Math.floor(col / 3) * 3;
    
    for (let r = boxRow; r < boxRow + 3; r++) {
      for (let c = boxCol; c < boxCol + 3; c++) {
        if (r !== row || c !== col) {
          const cell = cells[r * 9 + c];
          if (cell && cell.value == value) return false;
        }
      }
    }
    
    return true;
  }

  // Statistics Functions
  function updateMistakeCount() {
    document.getElementById('mistake-count').textContent = mistakeCount;
  }

  function updateCellsFilledCount() {
    const playerBoard = document.getElementById('player-board');
    const filledCells = playerBoard.querySelectorAll('.cell-input[value]:not([value=""])').length;
    document.getElementById('cells-filled').textContent = `${filledCells}/81`;
  }

  function startElapsedTimer() {
    if (elapsedInterval) clearInterval(elapsedInterval);
    
    startTime = new Date();
    elapsedInterval = setInterval(() => {
      if (startTime) {
        const elapsed = new Date() - startTime;
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        document.getElementById('elapsed-time').textContent = 
          `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      }
    }, 1000);
  }

  function stopElapsedTimer() {
    if (elapsedInterval) {
      clearInterval(elapsedInterval);
      elapsedInterval = null;
    }
  }

  // Initialize UI
  function initializeUI() {
    updateCellsFilledCount();
    updateMistakeCount();
    
    // Add click handlers for navigation buttons
    window.copyGameCode = function() {
      navigator.clipboard.writeText(gameCode).then(() => {
        addMessage('Game code copied to clipboard!', 'success');
      });
    };
    
    window.showRules = function() {
      addMessage('Rules: First player to complete the Sudoku puzzle wins! Use number pad or keyboard to fill cells.', 'info');
    };
    
    window.toggleFullscreen = function() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    };
  }

  // Initialize on load
  initializeUI();
  
  function addMessage(text, className = '') {
    const div = document.createElement('div');
    div.className = `message ${className}`;
    div.textContent = text;
    messageDiv.appendChild(div);
    messageDiv.scrollTop = messageDiv.scrollHeight;
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

  // Board Update Functions
  function updatePlayerBoard(row, col, value) {
    const playerBoard = document.getElementById('player-board');
    const cell = playerBoard.querySelector(`[data-row="${row}"][data-col="${col}"]`);
    if (cell) {
      const input = cell.querySelector('.cell-input');
      if (input && !input.classList.contains('prefilled')) {
        input.value = value;
        input.classList.add('filled');
        updateCellsFilledCount();
      }
    }
  }

  function updateOpponentBoard(row, col, value) {
    const opponentBoard = document.getElementById('opponent-board');
    const cells = opponentBoard.querySelectorAll('.cell-input');
    const cellIndex = row * 9 + col;
    
    if (cells[cellIndex] && !cells[cellIndex].classList.contains('prefilled')) {
      cells[cellIndex].value = value;
      cells[cellIndex].classList.add('filled');
      
      // Add visual effect for opponent move
      cells[cellIndex].style.animation = 'opponentMove 0.5s ease';
      setTimeout(() => {
        cells[cellIndex].style.animation = '';
      }, 500);
    }
  }

  // Enhanced board state management
  function updateBoardFromState(board, isOpponent = false) {
    console.log('Updating board state:', { board, isOpponent });
    const targetBoard = isOpponent ? document.getElementById('opponent-board') : document.getElementById('player-board');
    if (!targetBoard) {
      console.error('Target board not found:', isOpponent ? 'opponent-board' : 'player-board');
      return;
    }
    
    const cellInputs = targetBoard.querySelectorAll('.cell-input');
    console.log('Found cells:', cellInputs.length);
    
    cellInputs.forEach((input, index) => {
      const row = Math.floor(index / 9);
      const col = index % 9;
      const value = board[row] ? board[row][col] : 0;
      
      if (value !== 0) {
        // Always update the display value, regardless of prefilled status for opponent board
        if (isOpponent || !input.classList.contains('prefilled')) {
          input.value = value;
          input.classList.add('filled');
          if (isOpponent) {
            input.classList.add('opponent-move');
          }
        }
      }
    });
    
    if (!isOpponent) {
      updateCellsFilledCount();
    }
  }

  function handlePlayerReadyStatus(data) {
    // Update live status without refresh
    addMessage(`${data.username} is ready!`, 'success');
    
    if (data.both_ready) {
      // Update game status
      document.getElementById('game-status').innerHTML = '🏁 Starting...';
      addMessage('Both players ready! Race starting soon...', 'success');
    } else {
      // Update game status  
      document.getElementById('game-status').innerHTML = '⏳ Waiting for opponent';
    }
  }

  function handleLeaveGame() {
    // Confirm before leaving
    const isRacing = document.getElementById('game-status').textContent.includes('Racing');
    const confirmMessage = isRacing 
      ? 'Are you sure you want to leave the race? This will forfeit the game.' 
      : 'Are you sure you want to leave this game?';
    
    if (confirm(confirmMessage)) {
      // Send leave message to server
      safeSend({ 
        type: 'leave_game',
        reason: 'user_request'
      });
      
      // Show leaving message
      addMessage('Leaving game...', 'info');
      
      // Disable all controls
      const buttons = document.querySelectorAll('button');
      buttons.forEach(btn => btn.disabled = true);
      
      // Redirect after a delay
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);
    }
  }

  // Auto-save game state to prevent data loss
  function autoSaveGameState() {
    if (typeof Storage !== 'undefined') {
      const gameState = {
        gameCode: gameCode,
        board: Array.from(document.querySelectorAll('#player-board .cell-input')).map(input => input.value || ''),
        timestamp: Date.now()
      };
      localStorage.setItem('sudoku_race_autosave', JSON.stringify(gameState));
    }
  }

  // Auto-save every 30 seconds during active play
  if (typeof Storage !== 'undefined') {
    setInterval(autoSaveGameState, 30000);
  }

  // Page visibility API for better performance
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      // Page is hidden, reduce activity
      console.log('Page hidden - reducing background activity');
    } else {
      // Page is visible, resume normal activity
      console.log('Page visible - resuming normal activity');
    }
  });

  // Connection status indicator
  function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
      statusEl.className = connected ? 'connection-good' : 'connection-poor';
      statusEl.textContent = connected ? 'Connected' : 'Reconnecting...';
    }
  }

  // Enhanced error handling with retry
  function handleConnectionError() {
    updateConnectionStatus(false);
    addMessage('Connection lost. Attempting to reconnect...', 'error');
    
    // Try to reconnect after a delay
    setTimeout(() => {
      if (ws.readyState === WebSocket.CLOSED) {
        location.reload();
      }
    }, 5000);
  }
  

});
