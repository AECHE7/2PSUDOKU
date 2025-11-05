document.addEventListener('DOMContentLoaded', () => {
  // Ensure Logger is available, fallback to console if not
  if (typeof Logger === 'undefined') {
    window.Logger = {
      debug: console.log.bind(console),
      info: console.info.bind(console),
      warn: console.warn.bind(console),
      error: console.error.bind(console),
      critical: console.error.bind(console)
    };
  }
  
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

  // Sudoku validation state
  let currentBoard = [];
  let puzzleBoard = [];
  let validationEnabled = true;

  // Move tracking and analysis
  let moveHistory = [];
  let validMoves = 0;
  let invalidMoves = 0;
  let totalMoves = 0;
  let gameStatistics = {
    startTime: null,
    endTime: null,
    totalTime: 0,
    moveCount: 0,
    validMoveCount: 0,
    invalidMoveCount: 0,
    cellsCompleted: 0,
    accuracyRate: 0
  };

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
        console.log('✅ Fallback modal shown manually!');
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
    console.log('📤 Sending join_game message with playerId:', playerId);
    safeSend({
      type: 'join_game',
      playerId: playerId,
    });

    // Request current board state after connection is established
    setTimeout(() => {
      console.log('📤 Requesting board state...');
      safeSend({ type: 'get_board' });
    }, 500);
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('📨 WebSocket message received:', data.type, data);
    
    if (data.type === 'notification') {
      addMessage(data.message);
    } else if (data.type === 'game_state') {
      console.log('🎮 GAME_STATE received:', {
        player1: data.player1,
        player2: data.player2,
        status: data.status,
        start_time: data.start_time,
        has_puzzle: !!data.puzzle,
        has_board: !!data.board
      });
      
      // Initial state: focus on player's board only
      updateBoardFromState(data.board, false); // Player's board
      
      // Simple game info display
      addMessage(`Room: ${data.player1} vs ${data.player2 || 'Waiting...'}`);
      
      // Update game focus status
      const gameFocusStatus = document.getElementById('game-focus-status');
      if (gameFocusStatus) {
        if (data.player2 && data.player2 !== 'None') {
          gameFocusStatus.innerHTML = `<p class="text-success">✓ Ready to race! Focus on your puzzle.</p>`;
        } else {
          gameFocusStatus.innerHTML = '<p class="text-muted">Waiting for opponent... Practice while you wait!</p>';
        }
      }
      
      // Validate the board after it's loaded
      setTimeout(() => {
        if (typeof validateEntireBoard === 'function') {
          validateEntireBoard();
        }
      }, 500);
      
      // If race already started, start timers
      if (data.start_time) {
        console.log('⏱️ game_state has start_time, starting timers...');
        startTimers(new Date(data.start_time));
      } else {
        console.log('⏱️ game_state has NO start_time yet, waiting for race_started...');
      }
    } else if (data.type === 'move') {
      // Simple move notification - focus on player's own game
      if (data.player_id == playerId) {
        // Update player's own board (shouldn't be needed but for consistency)
        updatePlayerBoard(data.row, data.col, data.value);
        
        // Validate after move update
        setTimeout(() => {
          if (typeof validateEntireBoard === 'function') {
            validateEntireBoard();
          }
        }, 100);
      } else {
        // Simple opponent move notification
        addMessage(`${data.username} made a move`, 'info');
      }
    } else if (data.type === 'board') {
      updateBoardFromState(data.board);
    } else if (data.type === 'race_started') {
      console.log('');
      console.log('═══════════════════════════════════════');
      console.log('🏁 RACE STARTED MESSAGE RECEIVED!');
      console.log('═══════════════════════════════════════');
      console.log('📊 Full race data:', JSON.stringify(data, null, 2));
      console.log('📅 Start time from server:', data.start_time);
      console.log('📅 Start time type:', typeof data.start_time);
      console.log('⏰ Current time:', new Date().toISOString());
      console.log('═══════════════════════════════════════');
      console.log('');
      
      // Initialize game statistics
      gameStatistics.startTime = data.start_time;
      gameStatistics.moveCount = 0;
      gameStatistics.validMoveCount = 0;
      gameStatistics.invalidMoveCount = 0;
      gameStatistics.accuracyRate = 0;
      totalMoves = 0;
      validMoves = 0;
      invalidMoves = 0;
      moveHistory = [];
      
      // Start timers and ensure both boards have the puzzle
      const startTime = new Date(data.start_time);
      console.log('⏰ Parsed start time as Date:', startTime);
      console.log('⏰ Start time is valid?', !isNaN(startTime.getTime()));
      
      // Force timer start
      console.log('🔄 About to call startTimers()...');
      startTimers(startTime);
      console.log('✅ startTimers() call completed');
      
      if (data.puzzle) {
        console.log('🧩 Updating board with puzzle data');
        updateBoardFromState(data.board || data.puzzle);
      }
      
      // Update game status
      const gameStatusEl = document.getElementById('game-status');
      if (gameStatusEl) {
        gameStatusEl.innerHTML = '🏁 Racing';
        gameStatusEl.style.color = 'green';
        gameStatusEl.style.fontWeight = 'bold';
        console.log('✅ Updated game status to Racing');
      } else {
        console.error('❌ Could not find game-status element!');
      }
      
      addMessage('🏁 Race started — good luck!', 'success');
      
      // Force a UI refresh
      setTimeout(() => {
        console.log('');
        console.log('─────────────────────────────────');
        console.log('🔄 UI Refresh Check (1 second later)');
        console.log('─────────────────────────────────');
        const timer1El = document.getElementById('player1-timer');
        const timer2El = document.getElementById('player2-timer');
        if (timer1El && timer2El) {
          console.log('✅ Timer1 element:', timer1El);
          console.log('✅ Timer1 text:', timer1El.textContent);
          console.log('✅ Timer2 element:', timer2El);
          console.log('✅ Timer2 text:', timer2El.textContent);
        } else {
          console.error('❌ Timer elements still not found after 1 second!');
          console.error('❌ timer1El:', timer1El);
          console.error('❌ timer2El:', timer2El);
        }
        console.log('─────────────────────────────────');
        console.log('');
      }, 1000);
    } else if (data.type === 'race_finished') {
      console.log('');
      console.log('═══════════════════════════════════════');
      console.log('🏁 RACE FINISHED MESSAGE RECEIVED!');
      console.log('═══════════════════════════════════════');
      console.log('📊 Full finish data:', JSON.stringify(data, null, 2));
      console.log('🏆 Winner ID:', data.winner_id);
      console.log('🏆 Winner Username:', data.winner_username);
      console.log('⏱️ Winner Time:', data.winner_time);
      console.log('⏱️ Loser Time:', data.loser_time);
      console.log('👤 Current Player ID:', playerId);
      console.log('🎯 Is Winner?', data.winner_id == playerId);
      console.log('═══════════════════════════════════════');
      console.log('');
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
      // Show user-friendly error messages
      let errorMessage = data.error;
      if (errorMessage === 'Game is full. Please create a new game.') {
        errorMessage = '🎮 This game is full. Please create or join another game.';
      } else if (errorMessage === 'Cannot join this game') {
        errorMessage = '❌ Unable to join this game. It may be full or have connection issues.';
      }
      addMessage(`Error: ${errorMessage}`, 'error');
      
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
  
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 5;
  
  ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    isConnected = false;
    
    if (event.code === 1000) {
      addMessage('Connection closed normally', 'info');
    } else {
      addMessage(`Disconnected from server (Code: ${event.code})`, 'error');
      
      // Implement exponential backoff for reconnection
      if (event.code !== 1000 && !gameFinished && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
        
        addMessage(`Reconnecting in ${Math.floor(backoffDelay/1000)}s... (Attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`, 'info');
        
        setTimeout(() => {
          location.reload();
        }, backoffDelay);
      } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        addMessage('❌ Connection failed. Please refresh the page manually.', 'error');
        // Show user-friendly error modal
        showConnectionErrorModal();
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
    
    Logger.debug('🎯 CHANGE EVENT TRIGGERED ON CELL INPUT!');
    Logger.debug('📝 Target element:', e.target);
    Logger.debug('📝 Target value:', e.target.value);
    
    // Get row/col from parent td element's data attributes
    const cell = e.target.closest('.sudoku-cell');
    if (!cell) {
      Logger.error('Could not find parent sudoku-cell');
      return;
    }
    
    const row = parseInt(cell.dataset.row);
    const col = parseInt(cell.dataset.col);
    
    Logger.debug(`Got row/col from data attributes: row=${row}, col=${col}`);
    
    const value = parseInt(e.target.value);
    Logger.debug(`🎯 Input change detected: Row ${row}, Col ${col}, Value ${value}`);
    
    // Check if we have valid row/col values
    if (isNaN(row) || isNaN(col)) {
      Logger.error('Invalid row/col values:', { row, col });
      return;
    }
    
    if (value && value >= 1 && value <= 9) {
      // Clear any previous validation classes for this cell
      e.target.classList.remove('correct', 'incorrect', 'invalid');
      
      // Validate move immediately
      Logger.debug('🔍 Calling validateMove...');
      const isValidMove = validateMove(row, col, value);
      Logger.debug('🔍 Validation result:', isValidMove);
      
      // Track this move for analysis
      trackMove(row, col, value, isValidMove);
      
      if (isValidMove) {
        Logger.debug('✅ Valid move - adding correct class');
        e.target.classList.add('correct');
        validMoves++;
        gameStatistics.validMoveCount++;
        
        setTimeout(() => {
          e.target.classList.remove('correct');
        }, 500);
        // Clear any conflict highlights when a valid move is made
        clearConflictHighlights();
      } else {
        Logger.debug('❌ Invalid move - adding incorrect class');
        // Show immediate feedback with shake animation
        e.target.classList.add('incorrect');
        invalidMoves++;
        gameStatistics.invalidMoveCount++;
        
        // Highlight conflicting cells like Sudoku.com
        highlightConflictingCells(row, col, value);
        
        mistakeCount++;
        updateMistakeCount();
        
        // After animation, change to permanent invalid state
        setTimeout(() => {
          e.target.classList.remove('incorrect');
          e.target.classList.add('invalid'); // Permanent red state like Sudoku.com
        }, 500);
        
        // Keep conflict highlights visible longer
        setTimeout(() => {
          clearConflictHighlights();
        }, 2000);
      }

      safeSend({
        type: 'move',
        row: row,
        col: col,
        value: value,
      });

      // Validate entire board after move to catch any other invalid states
      setTimeout(() => {
        validateEntireBoard();
        
        // Check for game completion after validation
        setTimeout(() => {
          checkGameCompletion();
        }, 50);
      }, 100);
      
      updateCellsFilledCount();
      highlightRelatedCells(row, col, value);
      
    } else if (e.target.value === '') {
      // Clear validation states when cell is emptied
      e.target.classList.remove('correct', 'incorrect', 'invalid');
      updateCellsFilledCount();
      clearHighlights();
      clearConflictHighlights();
      return;
    }

    // After each input, check if puzzle is complete and auto-submit
    const isComplete = isLocalBoardComplete();
    const isValid = isLocalBoardValid();
    console.log('Board check:', { isComplete, isValid, gameFinished });

    if (isComplete && isValid && !gameFinished) {
      console.log('Auto-submitting solution...');
      autoSubmitSolution();
    }
  });

  // Also listen for 'input' events for immediate validation (as user types)
  document.addEventListener('input', (e) => {
    if (!e.target.classList.contains('cell-input')) return;
    if (e.target.disabled) return;
    
    console.log('Input event triggered (immediate)');
    
    // Trigger the same validation logic as change event
    const changeEvent = new Event('change');
    e.target.dispatchEvent(changeEvent);
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

  // Auto-start: Race begins automatically when second player joins
  // No manual ready button needed - game starts when player2 connects

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
  let cachedTimerElements = null;  // Cache timer DOM elements

  function startTimers(startTime) {
    console.log('🔥 startTimers() CALLED!');
    console.log('📅 Start time received:', startTime);

    Logger.info(`Starting timers from: ${startTime}`);
    raceStartTime = startTime;

    // Function to check and start timer
    const initTimer = () => {
      console.log('🔍 Attempting to find timer elements...');

      // Always get fresh references to ensure DOM is ready
      const timer1 = document.getElementById('player1-timer');
      const timer2 = document.getElementById('player2-timer');
      const elapsedTimer = document.getElementById('elapsed-time');

      console.log('🔍 player1-timer:', timer1);
      console.log('🔍 player2-timer:', timer2);
      console.log('🔍 elapsed-time:', elapsedTimer);

      if (!timer1 || !timer2 || !elapsedTimer) {
        console.warn('⚠️ Timer elements not found yet, retrying...');
        return false;
      }

      // Cache the elements for faster access
      cachedTimerElements = { timer1, timer2, elapsedTimer };
      console.log('✅ Timer elements cached!');

      // Clear any existing interval
      if (timerInterval) {
        clearInterval(timerInterval);
      }

      timerInterval = setInterval(() => {
        const now = new Date();
        const elapsed = Math.max(0, Math.floor((now - raceStartTime) / 1000));
        const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const ss = String(elapsed % 60).padStart(2, '0');
        const timeString = `${mm}:${ss}`;

        // Update ALL three timer displays using cached elements
        cachedTimerElements.timer1.textContent = timeString;
        cachedTimerElements.timer2.textContent = timeString;
        cachedTimerElements.elapsedTimer.textContent = timeString;
      }, 500);

      console.log('✅ Timer interval started successfully!');
      return true;
    };

    // Try immediately first
    if (initTimer()) {
      return;
    }

    // Retry mechanism with exponential backoff
    const maxRetries = 10;
    let retryIndex = 0;

    const retryTimer = setInterval(() => {
      console.log(`🔄 Retry ${retryIndex + 1}/${maxRetries}`);
      if (initTimer() || retryIndex >= maxRetries) {
        clearInterval(retryTimer);
        if (retryIndex >= maxRetries) {
          console.error('❌ Failed to start timer after maximum retries');
          addMessage('Timer failed to start. Please refresh the page.', 'error');
        }
      } else {
        retryIndex++;
      }
    }, 200); // Check every 200ms
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
    
    console.log('🏁 AUTO-SUBMITTING SOLUTION!');
    console.log('⏰ Timestamp:', new Date().toISOString());
    
    gameFinished = true;
    addMessage('🎉 Puzzle completed! Submitting solution...', 'success');
    
    // Hide finish button since we're auto-submitting
    const finishBtn = document.getElementById('finish-btn');
    if (finishBtn) {
      finishBtn.style.display = 'none';
    }
    
    // Disable all inputs immediately
    disableAllInputs();
    
    // Stop timer immediately
    stopTimers();
    
    // Show immediate feedback
    const gameStatusEl = document.getElementById('game-status');
    if (gameStatusEl) {
      gameStatusEl.innerHTML = '⏳ Checking solution...';
      gameStatusEl.style.color = 'orange';
    }
    
    // Calculate completion time
    const completionTime = raceStartTime ? new Date() - raceStartTime : 0;
    
    console.log('📤 Sending completion message to server...');
    // Submit the solution with completion time
    const success = safeSend({ 
      type: 'complete',
      completion_time: completionTime
    });
    console.log('✅ Complete message sent:', success);
    
    if (!success) {
      console.error('❌ Failed to send completion message');
      addMessage('❌ Failed to submit solution. Check connection.', 'error');
      gameFinished = false; // Allow retry
      
      // Re-enable if failed
      const inputs = document.querySelectorAll('.cell-input');
      inputs.forEach(input => input.disabled = false);
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
    console.log('🎮 handleGameFinished() called with data:', data);
    
    gameFinished = true;
    console.log('⏹️ Stopping timers...');
    stopTimers();
    
    console.log('🔒 Disabling all inputs...');
    disableAllInputs();
    
    console.log('✨ Clearing highlights...');
    clearHighlights();
    
    // Hide submit button
    console.log('👻 Hiding submit button...');
    hideSubmitButton();
    
    // Update game status
    const gameStatusEl = document.getElementById('game-status');
    if (gameStatusEl) {
      gameStatusEl.innerHTML = '🏆 Finished';
      console.log('✅ Game status updated to Finished');
    }
    
    // Hide race controls
    const raceControls = document.querySelector('.race-controls');
    if (raceControls) {
      raceControls.style.display = 'none';
      console.log('✅ Race controls hidden');
    }
    
    // Determine winner and show results
    const isWinner = data.winner_id == playerId;
    const loserTime = data.loser_time || 'Did not finish';
    
    console.log('🏆 Winner determination:', {
      winner_id: data.winner_id,
      playerId: playerId,
      isWinner: isWinner
    });
    
    let winnerMessage;
    if (isWinner) {
      winnerMessage = `🏆 YOU WON! Completed in ${data.winner_time}. Opponent: ${loserTime}`;
    } else {
      winnerMessage = `${data.winner_username} won in ${data.winner_time}. You: ${loserTime}`;
    }
    
    console.log('📢 Winner message:', winnerMessage);
    addMessage(winnerMessage, isWinner ? 'success' : 'info');
    
    // Show winner modal
    console.log('🎉 Calling showWinnerModal...');
    showWinnerModal(data, isWinner);
  }

  function showWinnerModal(data, isWinner) {
    console.log('');
    console.log('═══════════════════════════════════════');
    console.log('🎊 showWinnerModal() called');
    console.log('═══════════════════════════════════════');
    console.log('Data:', data);
    console.log('Is Winner:', isWinner);

    const modal = document.getElementById('winner-modal');
    const winnerContent = document.getElementById('winner-content');
    const gameStats = document.getElementById('game-stats');

    console.log('🔍 DOM Elements:');
    console.log('  - modal:', modal);
    console.log('  - winnerContent:', winnerContent);
    console.log('  - gameStats:', gameStats);

    if (!modal) {
      console.error('❌ Winner modal element not found!');
      alert(`Game Over! ${isWinner ? 'You won!' : data.winner_username + ' won!'} Time: ${data.winner_time}`);
      return;
    }

    // Populate winner content
    console.log('📝 Populating winner content...');
    if (winnerContent) {
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
      console.log('✅ Winner content populated');
    }

    // Populate game stats
    console.log('📊 Populating game stats...');
    if (gameStats) {
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
      console.log('✅ Game stats populated');
    }

    // Show modal
    console.log('🎭 Attempting to show modal...');
    try {
      if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        console.log('✅ Bootstrap found, creating modal instance...');
        const bootstrapModal = new bootstrap.Modal(modal, {
          backdrop: 'static',
          keyboard: false
        });
        bootstrapModal.show();
        console.log('✅ Bootstrap modal shown!');
      } else {
        console.warn('⚠️ Bootstrap not loaded, using fallback...');
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
      console.error('❌ Error showing modal:', error);
      console.error('Stack trace:', error.stack);
      // Simple fallback
      const message = `Game Over! ${isWinner ? '🏆 YOU WON!' : data.winner_username + ' won!'} Time: ${data.winner_time}`;
      alert(message);
    }

    console.log('═══════════════════════════════════════');
    console.log('✅ showWinnerModal() completed');
    console.log('═══════════════════════════════════════');
    console.log('');
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
    console.log('🎮 New game created:', data);
    addMessage(`New game created! Redirecting to game ${data.game_code}...`, 'success');

    // Close the modal if open
    try {
      const modalElement = document.getElementById('winner-modal');
      if (modalElement) {
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
    // Get all cells from player's board
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) {
      Logger.warn('No player board found for validation');
      return true;
    }
    
    // Build a 9x9 array of current values
    const board = [];
    for (let r = 0; r < 9; r++) {
      board[r] = [];
      for (let c = 0; c < 9; c++) {
        const cellElement = playerBoard.querySelector(`.sudoku-cell[data-row="${r}"][data-col="${c}"] .cell-input`);
        if (cellElement) {
          // For the current cell being validated, use the new value
          if (r === row && c === col) {
            board[r][c] = value;
          } else {
            board[r][c] = parseInt(cellElement.value) || 0;
          }
        } else {
          board[r][c] = 0;
        }
      }
    }
    
    Logger.debug(`Validating: Row ${row}, Col ${col}, Value ${value}`);
    
    // Check row for conflicts
    for (let c = 0; c < 9; c++) {
      if (c !== col && board[row][c] === value) {
        Logger.debug(`❌ Row conflict at col ${c}`);
        return false;
      }
    }
    
    // Check column for conflicts
    for (let r = 0; r < 9; r++) {
      if (r !== row && board[r][col] === value) {
        Logger.debug(`❌ Column conflict at row ${r}`);
        return false;
      }
    }
    
    // Check 3x3 box for conflicts
    const boxRow = Math.floor(row / 3) * 3;
    const boxCol = Math.floor(col / 3) * 3;
    
    for (let r = boxRow; r < boxRow + 3; r++) {
      for (let c = boxCol; c < boxCol + 3; c++) {
        if ((r !== row || c !== col) && board[r][c] === value) {
          Logger.debug(`❌ Box conflict at (${r}, ${c})`);
          return false;
        }
      }
    }
    
    Logger.debug('✅ Move is valid');
    return true;
  }

  function highlightConflictingCells(row, col, value) {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    const cells = playerBoard.querySelectorAll('.cell-input');
    
    // Highlight conflicting cells in row
    for (let c = 0; c < 9; c++) {
      if (c !== col) {
        const cell = cells[row * 9 + c];
        if (cell.value == value) {
          cell.classList.add('conflict');
        }
      }
    }
    
    // Highlight conflicting cells in column
    for (let r = 0; r < 9; r++) {
      if (r !== row) {
        const cell = cells[r * 9 + col];
        if (cell.value == value) {
          cell.classList.add('conflict');
        }
      }
    }
    
    // Highlight conflicting cells in 3x3 box
    const boxRow = Math.floor(row / 3) * 3;
    const boxCol = Math.floor(col / 3) * 3;
    
    for (let r = boxRow; r < boxRow + 3; r++) {
      for (let c = boxCol; c < boxCol + 3; c++) {
        if (r !== row || c !== col) {
          const cell = cells[r * 9 + c];
          if (cell && cell.value == value) {
            cell.classList.add('conflict');
          }
        }
      }
    }
  }

  function clearConflictHighlights() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    const conflictCells = playerBoard.querySelectorAll('.cell-input.conflict');
    conflictCells.forEach(cell => cell.classList.remove('conflict'));
  }

  // Removed unused clearValidationHighlights and validateAllCells functions

  // Test function for validation - can be called from browser console
  window.testValidation = function() {
    console.log('🧪 Testing Sudoku validation...');
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) {
      console.error('❌ Player board not found!');
      return;
    }
    
    const cells = playerBoard.querySelectorAll('.cell-input');
    console.log(`✅ Found ${cells.length} cells`);
    
    // Show current board state
    console.log('📋 Current board state:');
    for (let i = 0; i < 81; i++) {
      const row = Math.floor(i / 9);
      const col = i % 9;
      const cell = cells[i];
      if (cell && cell.value) {
        console.log(`Cell [${row}, ${col}]: ${cell.value}`);
      }
    }
    
    // Test case 1: Find first empty cell and test validation
    let testCell = null;
    let testRow = -1, testCol = -1;
    
    for (let i = 0; i < cells.length; i++) {
      if (cells[i] && !cells[i].disabled && !cells[i].value) {
        testCell = cells[i];
        testRow = Math.floor(i / 9);
        testCol = i % 9;
        break;
      }
    }
    
    if (testCell) {
      console.log(`🎯 Testing on empty cell at [${testRow}, ${testCol}]`);
      
      // Try to put a number that should conflict
      let conflictValue = '1';
      // Check if '1' already exists in this row, column, or box
      for (let c = 0; c < 9; c++) {
        const rowCell = cells[testRow * 9 + c];
        if (rowCell && rowCell.value === '1') {
          console.log(`📍 Found existing '1' in row at col ${c} - this should trigger validation`);
          break;
        }
      }
      
      // Set the test value and trigger validation
      testCell.value = conflictValue;
      const event = new Event('input');
      testCell.dispatchEvent(event);
      
      console.log('🔍 Test completed - check cell styling');
      console.log('Cell classes:', testCell.className);
    } else {
      console.log('⚠️ No empty cells found for testing');
    }
    
    return 'Check console and visual feedback in the game board';
  };

  // Debug function to show board state
  window.showBoardState = function() {
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) {
      console.error('❌ Player board not found!');
      return;
    }
    
    const cells = playerBoard.querySelectorAll('.cell-input');
    console.log('📋 Current 9x9 Sudoku Board:');
    
    for (let row = 0; row < 9; row++) {
      let rowStr = '';
      for (let col = 0; col < 9; col++) {
        const cell = cells[row * 9 + col];
        const value = cell && cell.value ? cell.value : '.';
        rowStr += value + ' ';
        if (col === 2 || col === 5) rowStr += '| ';
      }
      console.log(rowStr);
      if (row === 2 || row === 5) console.log('------+-------+------');
    }
  };

  // Function to validate entire board and highlight invalid cells
  function validateEntireBoard() {
    console.log('🔍 Validating entire board...');
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) return;
    
    const cells = playerBoard.querySelectorAll('.cell-input');
    let invalidCount = 0;
    
    // Clear existing validation states
    cells.forEach(cell => {
      cell.classList.remove('invalid', 'conflict');
    });
    
    // Check each filled cell
    cells.forEach((cell, index) => {
      if (cell && cell.value && cell.value !== '') {
        const row = Math.floor(index / 9);
        const col = index % 9;
        const value = parseInt(cell.value);
        
        if (!validateMove(row, col, value)) {
          cell.classList.add('invalid');
          invalidCount++;
          console.log(`❌ Invalid cell found at [${row}, ${col}] with value ${value}`);
        }
      }
    });
    
    console.log(`📊 Board validation complete: ${invalidCount} invalid cells found`);
    return invalidCount === 0;
  }

  // Function to trigger validation on board load/update
  window.validateBoard = validateEntireBoard;

  // Make validateEntireBoard function available globally
  window.validateEntireBoard = validateEntireBoard;

  // Move tracking and analysis functions
  function trackMove(row, col, value, isValid) {
    totalMoves++;
    gameStatistics.moveCount++;
    
    const moveData = {
      timestamp: new Date().toISOString(),
      row: row,
      col: col,
      value: value,
      isValid: isValid,
      moveNumber: totalMoves
    };
    
    moveHistory.push(moveData);
    
    // Update accuracy rate
    gameStatistics.accuracyRate = ((gameStatistics.validMoveCount / gameStatistics.moveCount) * 100).toFixed(1);
    
    console.log(`📊 Move ${totalMoves}: [${row},${col}]=${value} ${isValid ? '✅' : '❌'} | Accuracy: ${gameStatistics.accuracyRate}%`);
    
    // Update statistics display
    updateGameStatistics();
  }

  function updateGameStatistics() {
    // Update cells filled count
    const playerBoard = document.getElementById('player-board');
    const filledCells = playerBoard.querySelectorAll('.cell-input[value]:not([value=""])').length;
    gameStatistics.cellsCompleted = filledCells;
    
    // Update UI elements if they exist
    const cellsFilledEl = document.getElementById('cells-filled');
    if (cellsFilledEl) {
      cellsFilledEl.textContent = `${filledCells}/81`;
    }
    
    const accuracyEl = document.getElementById('accuracy-rate');
    if (accuracyEl) {
      accuracyEl.textContent = `${gameStatistics.accuracyRate}%`;
    }
    
    console.log('📈 Game Statistics:', gameStatistics);
  }

  function getMoveAnalysis() {
    return {
      totalMoves: totalMoves,
      validMoves: validMoves,
      invalidMoves: invalidMoves,
      accuracyRate: gameStatistics.accuracyRate,
      moveHistory: moveHistory,
      gameStatistics: gameStatistics
    };
  }

  // Game completion detection function
  function checkGameCompletion() {
    Logger.debug('Checking game completion...');
    const playerBoard = document.getElementById('player-board');
    if (!playerBoard) {
      Logger.error('Player board not found!');
      return false;
    }
    
    // Build complete board state
    let filledCells = 0;
    let allValid = true;
    
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        const cellElement = playerBoard.querySelector(`.sudoku-cell[data-row="${r}"][data-col="${c}"] .cell-input`);
        if (cellElement) {
          const value = parseInt(cellElement.value);
          if (value >= 1 && value <= 9) {
            filledCells++;
            // Validate this cell
            if (!validateMove(r, c, value)) {
              allValid = false;
            }
          } else {
            allValid = false;
          }
        } else {
          allValid = false;
        }
      }
    }
    
    Logger.debug(`Completion check: ${filledCells}/81 filled, valid=${allValid}`);
    
    // Show submit button if all cells filled
    if (filledCells === 81) {
      showSubmitButton(allValid);
      return allValid;
    } else {
      hideSubmitButton();
    }
    
    return false;
  }

  // Show submit button
  function showSubmitButton(isValid) {
    let submitBtn = document.getElementById('submit-puzzle-btn');
    
    if (!submitBtn) {
      // Create submit button if it doesn't exist
      const playerBoard = document.getElementById('player-board');
      if (!playerBoard) return;
      
      submitBtn = document.createElement('button');
      submitBtn.id = 'submit-puzzle-btn';
      submitBtn.className = 'btn btn-lg mt-3 w-100';
      submitBtn.style.fontSize = '1.2rem';
      submitBtn.style.fontWeight = 'bold';
      
      submitBtn.addEventListener('click', () => {
        handleManualSubmit();
      });
      
      playerBoard.parentElement.appendChild(submitBtn);
    }
    
    if (isValid) {
      submitBtn.className = 'btn btn-success btn-lg mt-3 w-100';
      submitBtn.innerHTML = '✓ Submit Puzzle';
      submitBtn.disabled = false;
    } else {
      submitBtn.className = 'btn btn-warning btn-lg mt-3 w-100';
      submitBtn.innerHTML = '⚠ Puzzle has errors (click to submit anyway)';
      submitBtn.disabled = false;
    }
    
    submitBtn.style.display = 'block';
  }

  // Hide submit button
  function hideSubmitButton() {
    const submitBtn = document.getElementById('submit-puzzle-btn');
    if (submitBtn) {
      submitBtn.style.display = 'none';
    }
  }

  // Handle manual submit
  function handleManualSubmit() {
    if (gameFinished) {
      Logger.warn('Game already submitted');
      return;
    }
    
    console.log('🏁 MANUAL SUBMIT CLICKED!');
    console.log('⏰ Timestamp:', new Date().toISOString());
    
    Logger.info('Manual puzzle submission');
    gameFinished = true;
    
    // Disable submit button immediately
    const submitBtn = document.getElementById('submit-puzzle-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '⏳ Submitting...';
    }
    
    // Disable all inputs immediately
    disableAllInputs();
    
    // Stop timer immediately
    stopTimers();
    
    // Show immediate feedback
    const gameStatusEl = document.getElementById('game-status');
    if (gameStatusEl) {
      gameStatusEl.innerHTML = '⏳ Checking solution...';
      gameStatusEl.style.color = 'orange';
    }
    
    addMessage('📤 Submitting your solution...', 'info');
    
    // Calculate completion time
    const completionTime = raceStartTime ? new Date() - raceStartTime : 0;
    
    console.log('📤 Sending completion message to server...');
    // Send completion to server
    const success = safeSend({ 
      type: 'complete',
      completion_time: completionTime
    });
    
    console.log('✅ Complete message sent:', success);
    
    if (success) {
      addMessage('🎉 Puzzle submitted! Waiting for results...', 'success');
    } else {
      console.error('❌ Failed to send completion message');
      addMessage('❌ Failed to submit solution. Check connection.', 'error');
      gameFinished = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '✓ Submit Puzzle';
      }
      // Re-enable inputs
      const inputs = document.querySelectorAll('.cell-input');
      inputs.forEach(input => input.disabled = false);
    }
  }

  // Handle successful game completion
  function handleGameCompletion() {
    console.log('🏆 Player completed the puzzle!');
    
    // Record completion time
    gameStatistics.endTime = new Date().toISOString();
    gameStatistics.totalTime = startTime ? new Date() - startTime : 0;
    
    // Stop the timer
    stopTimers();
    
    // Get final move analysis
    const finalAnalysis = getMoveAnalysis();
    
    // Send completion notification to server with statistics
    safeSend({
      type: 'puzzle_complete',
      completion_time: gameStatistics.endTime,
      game_statistics: gameStatistics,
      move_analysis: finalAnalysis
    });
    
    // Update UI to show completion
    const gameStatus = document.getElementById('game-status');
    if (gameStatus) {
      gameStatus.innerHTML = '🏆 Puzzle Complete!';
      gameStatus.classList.add('text-success');
    }
    
    // Show completion message with statistics
    const completionTime = gameStatistics.totalTime ? Math.floor(gameStatistics.totalTime / 1000) : 0;
    const minutes = Math.floor(completionTime / 60);
    const seconds = completionTime % 60;
    
    addMessage(`🎉 Congratulations! You completed the puzzle in ${minutes}:${seconds.toString().padStart(2, '0')} with ${gameStatistics.accuracyRate}% accuracy!`, 'success');
    
    // Log final statistics
    console.log('📊 Final Game Statistics:', finalAnalysis);
    
    // Add visual celebration effect
    const playerBoard = document.getElementById('player-board');
    if (playerBoard) {
      playerBoard.classList.add('puzzle-complete');
      setTimeout(() => {
        playerBoard.classList.remove('puzzle-complete');
      }, 3000);
    }
  }

  // Auto-validate board when page loads (already inside DOMContentLoaded, no need for another listener)
  setTimeout(() => {
    if (typeof validateEntireBoard === 'function') {
      validateEntireBoard();
    }
  }, 1000);

  // Statistics Functions
  function updateMistakeCount() {
    document.getElementById('mistake-count').textContent = mistakeCount;
  }

  function updateCellsFilledCount() {
    const playerBoard = document.getElementById('player-board');
    const filledCells = playerBoard.querySelectorAll('.cell-input[value]:not([value=""])').length;
    document.getElementById('cells-filled').textContent = `${filledCells}/81`;
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
    // Function removed - focusing on player's board only
    // Opponent moves are now just shown as simple notifications
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
      // Validate the entire board after update
      setTimeout(() => {
        validateEntireBoard();
      }, 100);
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
  function showConnectionErrorModal() {
    const modalHtml = `
      <div class="modal fade show" id="connectionErrorModal" style="display: block;" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header bg-danger text-white">
              <h5 class="modal-title">Connection Lost</h5>
            </div>
            <div class="modal-body">
              <p>Unable to maintain connection to the game server.</p>
              <p>Your game progress may not be saved.</p>
              <p><strong>Please check your internet connection and refresh the page.</strong></p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" onclick="location.reload()">
                Refresh Page
              </button>
              <button type="button" class="btn btn-secondary" onclick="window.location.href='/'">
                Return to Lobby
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop fade show"></div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

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
