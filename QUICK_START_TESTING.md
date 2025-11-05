# Quick Start: Browser Testing

## 1. Start Services (3 commands)

```bash
# Terminal 1: Redis
docker run -p 6379:6379 -d redis:7

# Terminal 2: Django
python manage.py runserver 0.0.0.0:8000

# Terminal 3: Create test game
python manage.py create_test_game
```

## 2. Open Two Browsers

The `create_test_game` command will output URLs and credentials like:

```
Game URL: http://localhost:8000/game/ABC123/

Window 1 (Player 1):
  - Login: testplayer1 / testpass123
  - Go to game URL

Window 2 (Player 2):
  - Login: testplayer2 / testpass123
  - Go to game URL
```

## 3. Test the Flow

The complete cycle is automatic:

1. **Join** → Both players navigate to game URL
2. **Start** → Race starts automatically when both connected
3. **Play** → Fill in numbers, see real-time updates
4. **Complete** → Auto-submits when all cells filled
5. **Win** → Modal shows winner/loser
6. **Restart** → Click "Play Again" for new game

## What You'll See

✅ **Timers** sync between browsers in real-time  
✅ **Moves** appear instantly in opponent's board  
✅ **Validation** rejects invalid moves with feedback  
✅ **Auto-submit** triggers when puzzle is complete  
✅ **Winner modal** displays results and stats  
✅ **Play again** creates new game seamlessly  

## Check DevTools Console

Press F12 and watch for:
- `🏁 RACE STARTED!` when game begins
- `📨 WebSocket message received` for all updates
- `🎉 PUZZLE COMPLETE!` when auto-submitting
- `🏆 WINNER` or `😔 LOSER` modal display

## Advanced Options

```bash
# Hard difficulty
python manage.py create_test_game --difficulty hard

# Auto-start immediately (no waiting for players)
python manage.py create_test_game --auto-start

# Combined
python manage.py create_test_game --difficulty medium --auto-start
```

## Full Testing Checklist

See `E2E_TESTING_CHECKLIST.md` for comprehensive testing phases and expected results.

## Cleanup

```bash
# Remove test games when done
python manage.py shell -c "from game.models import GameSession; GameSession.objects.filter(player1__username='testplayer1').delete()"
```
