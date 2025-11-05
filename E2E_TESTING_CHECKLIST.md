# End-to-End Browser Testing Checklist

## Setup

### Start the Server
```bash
# Terminal 1: Start Redis
docker run -p 6379:6379 -d redis:7

# Terminal 2: Start Django server
python manage.py runserver 0.0.0.0:8000
```

### Create Test Game
```bash
# Terminal 3: Create test game
python manage.py create_test_game

# Or with auto-start for immediate racing
python manage.py create_test_game --auto-start

# Or with different difficulty
python manage.py create_test_game --difficulty hard
```

## Browser Testing Flow

### Phase 1: Game Creation & Joining ✅

**Test Steps:**
1. [ ] Open two browser windows (or use incognito mode for second)
2. [ ] Window 1: Login as `testplayer1` / `testpass123`
3. [ ] Window 1: Navigate to game URL provided by command
4. [ ] Window 2: Login as `testplayer2` / `testpass123`
5. [ ] Window 2: Navigate to same game URL

**Expected Results:**
- [ ] Both players see the game board
- [ ] Player 1 sees their name in left panel
- [ ] Player 2 sees their name in right panel
- [ ] Game status shows "Waiting for race to start" or similar
- [ ] WebSocket connection established (check DevTools Console)

### Phase 2: Race Start & Timer Sync ✅

**Test Steps:**
1. [ ] Wait for both players to connect
2. [ ] Race should start automatically
3. [ ] Observe timers in both windows

**Expected Results:**
- [ ] Game status changes to "🏁 Racing" or "In Progress"
- [ ] Timers start counting in BOTH windows
- [ ] Timers show synchronized time (within 1 second)
- [ ] Both boards become editable
- [ ] Console shows "race_started" message
- [ ] Start time is logged in console

### Phase 3: Real-Time Move Sync ✅

**Test Steps:**
1. [ ] Window 1: Click on an empty cell
2. [ ] Window 1: Enter a number (1-9)
3. [ ] Window 2: Observe the opponent's board

**Expected Results:**
- [ ] Move appears in Window 1 immediately
- [ ] Move appears in Window 2 within 100ms
- [ ] Valid moves show green flash
- [ ] Invalid moves show red flash and don't persist
- [ ] Opponent's board updates in real-time
- [ ] Console shows move messages in both windows

### Phase 4: Board Validation ✅

**Test Steps:**
1. [ ] Try to enter a number that conflicts with row
2. [ ] Try to enter a number that conflicts with column
3. [ ] Try to enter a number that conflicts with 3x3 box

**Expected Results:**
- [ ] Invalid moves are rejected by server
- [ ] Error message appears in messages area
- [ ] Cell value is cleared after rejection
- [ ] Conflicting cells are highlighted
- [ ] Mistake counter increases
- [ ] Console shows "Invalid move" error

### Phase 5: Puzzle Completion & Auto-Submit ✅

**Test Steps:**
1. [ ] Window 1: Fill in all remaining cells correctly
2. [ ] Observe auto-submission behavior

**Expected Results:**
- [ ] When last cell is filled, auto-submit triggers
- [ ] Board is disabled immediately
- [ ] Timer stops
- [ ] Game status shows "Checking solution..."
- [ ] Console shows "AUTO-SUBMITTING SOLUTION!"
- [ ] Console shows gameFinished = true
- [ ] No "Game already submitted" warnings

### Phase 6: Winner Modal Display ✅

**Test Steps:**
1. [ ] Wait for server to process completion
2. [ ] Observe modal in BOTH windows

**Expected Results:**
- [ ] Winner modal appears in Window 1 (winner)
  - Shows "🏆 You Won!"
  - Shows completion time
  - Shows "Play Again" button
  
- [ ] Winner modal appears in Window 2 (loser/incomplete)
  - Shows "😔 You Lost" or "⏱️ Out of Time"
  - Shows opponent's time
  - Shows "Play Again" button

- [ ] Console logs in both windows:
  - "race_finished message received"
  - Winner ID and username
  - Times for both players
  - Modal display sequence

### Phase 7: Play Again Flow ✅

**Test Steps:**
1. [ ] Window 1: Click "Play Again" button
2. [ ] Observe behavior in both windows

**Expected Results:**
- [ ] Modal closes in Window 1
- [ ] New game is created with same difficulty
- [ ] Window 1 redirects to new game URL
- [ ] Console shows new game code
- [ ] Window 2 receives "new_game_created" message
- [ ] Window 2 can also click Play Again to join

**Alternative Test:**
1. [ ] Window 2: Click "Play Again" before Window 1
2. [ ] Verify same behavior occurs

### Phase 8: WebSocket Stability ✅

**Test Steps:**
1. [ ] During gameplay, check DevTools → Network → WS tab
2. [ ] Monitor connection status
3. [ ] Check for errors or reconnection attempts

**Expected Results:**
- [ ] WebSocket shows "connected" status
- [ ] Messages flow in both directions
- [ ] No connection drops during game
- [ ] No error messages in console
- [ ] Proper WS close on page navigation

## Advanced Testing

### Stress Testing

**Multiple Moves Rapidly:**
1. [ ] Make several moves quickly in succession
2. [ ] Verify all moves sync correctly
3. [ ] No race conditions or lost moves

**Slow Connection Simulation:**
1. [ ] Open DevTools → Network → Throttling
2. [ ] Set to "Slow 3G" or "Fast 3G"
3. [ ] Test if moves still sync (may be delayed)
4. [ ] Timer should still run smoothly

**Page Refresh During Game:**
1. [ ] Refresh one player's window mid-game
2. [ ] Verify game state is restored
3. [ ] WebSocket reconnects
4. [ ] Board shows correct state

### Edge Cases

**Invalid Move Handling:**
- [ ] Server rejects conflicting moves
- [ ] Client clears invalid values from DOM
- [ ] Can continue playing after invalid move
- [ ] Completion works after fixing invalid moves

**Concurrent Completion:**
- [ ] Both players complete at similar time
- [ ] First completion is processed correctly
- [ ] Second completion handled gracefully
- [ ] No database constraint errors

**Single Player Completion:**
- [ ] One player finishes, other doesn't
- [ ] Winner sees victory modal
- [ ] Loser sees defeat modal
- [ ] Both can play again

## Debugging Tips

### Enable Verbose Logging
Open browser console and run:
```javascript
// Show all WebSocket messages
ws.addEventListener('message', (e) => {
  console.log('📨 WS:', JSON.parse(e.data));
});

// Monitor timer updates
setInterval(() => {
  const t1 = document.getElementById('player1-timer');
  const t2 = document.getElementById('player2-timer');
  console.log('⏱️', t1?.textContent, t2?.textContent);
}, 5000);
```

### Common Issues

**Timer not starting:**
- Check console for "race_started" message
- Verify start_time is not null
- Check if timer elements exist in DOM

**Moves not syncing:**
- Check WebSocket connection status
- Verify Redis is running
- Check for JavaScript errors in console

**Winner modal not showing:**
- Check for "race_finished" message
- Verify Bootstrap JS is loaded
- Check for modal initialization errors

**Auto-submit not triggering:**
- Verify all 81 cells are filled
- Check isLocalBoardValid() returns true
- Verify gameFinished flag is false

## Success Criteria

✅ **All phases pass without errors**
✅ **Timers sync within 1 second**
✅ **Moves sync within 100ms**
✅ **Invalid moves are rejected cleanly**
✅ **Auto-submit triggers on completion**
✅ **Winner modal displays correctly**
✅ **Play again creates new game**
✅ **No console errors or warnings**
✅ **WebSocket remains stable throughout**

## Cleanup

After testing:
```bash
# Remove test games
python manage.py shell -c "from game.models import GameSession; GameSession.objects.filter(player1__username='testplayer1').delete()"

# Or keep them for later testing
```
