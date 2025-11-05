import pytest
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from ..consumers import GameConsumer
from ..models import GameSession
from ..game_state import GameStateManager, GameStatus

User = get_user_model()

@pytest.mark.asyncio
@pytest.mark.django_db
class TestAsyncSafety:
    async def test_async_state_access(self):
        # Create test user
        user = await sync_to_async(User.objects.create_user)(
            username='testuser',
            password='testpass123'
        )
        
        # Create game session
        game = await sync_to_async(GameSession.objects.create)(
            code='TEST123',
            player1=user,
            status='waiting'
        )
        
        # Setup application
        application = URLRouter([
            re_path(r'ws/game/(?P<code>\w+)/$', GameConsumer.as_asgi()),
        ])
        
        # Connect client
        communicator = WebsocketCommunicator(
            application,
            f'/ws/game/{game.code}/',
            headers=[(b'user', str(user.id).encode())]
        )
        
        connected, _ = await communicator.connect()
        assert connected
        
        try:
            # Send join game message
            await communicator.send_json_to({
                'type': 'join_game',
                'player_id': user.id
            })
            
            # Should receive game state without errors
            response = await communicator.receive_json_from()
            assert response['type'] == 'game_state'
            assert 'puzzle' in response
            assert 'board' in response
            
            # Test move
            await communicator.send_json_to({
                'type': 'move',
                'row': 0,
                'col': 0,
                'value': 5
            })
            
            # Should receive move confirmation
            response = await communicator.receive_json_from()
            assert response['type'] == 'move_made'
            assert response['row'] == 0
            assert response['col'] == 0
            assert response['value'] == 5
            
        finally:
            await communicator.disconnect()
            
    async def test_state_manager_async_safety(self):
        # Create test user and game
        user = await sync_to_async(User.objects.create_user)(
            username='testuser2',
            password='testpass123'
        )
        
        game = await sync_to_async(GameSession.objects.create)(
            code='TEST456',
            player1=user,
            status='waiting'
        )
        
        # Create state manager
        manager = GameStateManager(game)
        
        # Test async state access
        state = await manager.get_current_state_async()
        assert state is not None
        assert hasattr(state, 'puzzle')
        assert hasattr(state, 'solution')
        
        # Test async move validation
        valid = await manager.validate_move_async(user.id, 0, 0, 5)
        assert isinstance(valid, bool)
        
        # Test async move recording
        if valid:
            success = await manager.record_move_async(user.id, 0, 0, 5)
            assert success
            
    async def test_error_handling(self):
        # Test with invalid game code
        application = URLRouter([
            re_path(r'ws/game/(?P<code>\w+)/$', GameConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/game/INVALID/',
            headers=[(b'user', b'999')]
        )
        
        connected, _ = await communicator.connect()
        assert not connected  # Should reject invalid connection