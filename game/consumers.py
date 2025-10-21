"""
WebSocket consumer for real-time Sudoku gameplay
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import GameSession, Move
from .sudoku_logic import validate_move, is_board_complete, check_board_correct


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_code = self.scope['url_route']['kwargs']['session_code']
        self.room_group_name = f'game_{self.session_code}'
        self.user = self.scope['user']
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial game state
        game_state = await self.get_game_state()
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'data': game_state
        }))
    
    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'make_move':
            await self.handle_move(data)
        elif message_type == 'chat_message':
            await self.handle_chat(data)
    
    async def handle_move(self, data):
        row = data.get('row')
        col = data.get('col')
        value = data.get('value')
        
        # Validate and process move
        result = await self.process_move(row, col, value)
        
        if result['success']:
            # Broadcast move to all players in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'move_made',
                    'row': row,
                    'col': col,
                    'value': value,
                    'player': self.user.username,
                    'is_valid': result['is_valid'],
                    'game_state': result['game_state']
                }
            )
        else:
            # Send error to this player only
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': result.get('error', 'Invalid move')
            }))
    
    async def handle_chat(self, data):
        message = data.get('message', '')
        
        # Broadcast chat message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'player': self.user.username
            }
        )
    
    async def move_made(self, event):
        """Send move to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'move_made',
            'row': event['row'],
            'col': event['col'],
            'value': event['value'],
            'player': event['player'],
            'is_valid': event['is_valid'],
            'game_state': event['game_state']
        }))
    
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'player': event['player']
        }))
    
    @database_sync_to_async
    def get_game_state(self):
        """Get current game state from database"""
        try:
            game = GameSession.objects.get(session_code=self.session_code)
            return {
                'session_code': game.session_code,
                'board': game.get_current_board(),
                'initial_board': game.get_initial_board(),
                'status': game.status,
                'player1': game.player1.username,
                'player2': game.player2.username if game.player2 else None,
                'current_turn': game.current_turn.username if game.current_turn else None,
                'player1_score': game.player1_score,
                'player2_score': game.player2_score,
                'winner': game.winner.username if game.winner else None
            }
        except GameSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def process_move(self, row, col, value):
        """Process a move and update game state"""
        try:
            game = GameSession.objects.select_for_update().get(session_code=self.session_code)
            
            # Check if game is active
            if game.status != 'active':
                return {'success': False, 'error': 'Game is not active'}
            
            # Check if it's player's turn
            if game.current_turn != self.user:
                return {'success': False, 'error': 'Not your turn'}
            
            # Get current board and solution
            board = game.get_current_board()
            solution = game.get_solution()
            
            # Validate move
            is_valid = validate_move(board, solution, row, col, value)
            
            if not is_valid:
                # Invalid move - switch turn but don't update board
                if game.current_turn == game.player1:
                    game.current_turn = game.player2
                else:
                    game.current_turn = game.player1
                game.save()
                
                # Record invalid move
                Move.objects.create(
                    game=game,
                    player=self.user,
                    row=row,
                    col=col,
                    value=value,
                    is_valid=False
                )
                
                return {
                    'success': True,
                    'is_valid': False,
                    'game_state': self._get_game_state_dict(game)
                }
            
            # Valid move - update board
            board[row][col] = value
            game.set_current_board(board)
            
            # Update score
            if game.current_turn == game.player1:
                game.player1_score += 10
                game.current_turn = game.player2
            else:
                game.player2_score += 10
                game.current_turn = game.player1
            
            # Record valid move
            Move.objects.create(
                game=game,
                player=self.user,
                row=row,
                col=col,
                value=value,
                is_valid=True
            )
            
            # Check if board is complete
            if is_board_complete(board):
                game.status = 'completed'
                # Winner is player with higher score
                if game.player1_score > game.player2_score:
                    game.winner = game.player1
                elif game.player2_score > game.player1_score:
                    game.winner = game.player2
                # else: draw (no winner)
                
                from django.utils import timezone
                game.completed_at = timezone.now()
            
            game.save()
            
            return {
                'success': True,
                'is_valid': True,
                'game_state': self._get_game_state_dict(game)
            }
            
        except GameSession.DoesNotExist:
            return {'success': False, 'error': 'Game not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_game_state_dict(self, game):
        """Helper to convert game to dict"""
        return {
            'session_code': game.session_code,
            'board': game.get_current_board(),
            'initial_board': game.get_initial_board(),
            'status': game.status,
            'player1': game.player1.username,
            'player2': game.player2.username if game.player2 else None,
            'current_turn': game.current_turn.username if game.current_turn else None,
            'player1_score': game.player1_score,
            'player2_score': game.player2_score,
            'winner': game.winner.username if game.winner else None
        }
