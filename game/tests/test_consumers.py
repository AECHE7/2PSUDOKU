import json
import pytest
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import re_path
from asgiref.sync import sync_to_async
from ..consumers import GameConsumer
from ..models import GameSession
from ..game_state import GameStatus

User = get_user_model()

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_game_consumer_connect():
    """Test websocket connection and basic game flow."""
    # Create test users
    player1 = await sync_to_async(User.objects.create_user)(
        username='testplayer1', password='testpass123'
    )
    player2 = await sync_to_async(User.objects.create_user)(
        username='testplayer2', password='testpass123'
    )
    
    # Create game session
    game_code = 'TEST123'
    game = await sync_to_async(GameSession.objects.create)(
        code=game_code,
        player1=player1,
        status='waiting'
    )

    # Setup application
    application = URLRouter([
        re_path(r'ws/game/(?P<code>\w+)/$', GameConsumer.as_asgi()),
    ])

    # Connect player 1
    communicator1 = WebsocketCommunicator(
        application,
        f'/ws/game/{game_code}/',
        headers=[(b'user', str(player1.id).encode())]
    )
    connected1, _ = await communicator1.connect()
    assert connected1

    # Connect player 2
    communicator2 = WebsocketCommunicator(
        application,
        f'/ws/game/{game_code}/',
        headers=[(b'user', str(player2.id).encode())]
    )
    connected2, _ = await communicator2.connect()
    assert connected2

    # Send join game messages
    await communicator1.send_json_to({
        'type': 'join_game',
        'player_id': player1.id
    })
    
    await communicator2.send_json_to({
        'type': 'join_game',
        'player_id': player2.id
    })

    # Validate game status changes
    response1 = await communicator1.receive_json_from()
    assert response1['type'] == 'game_state'
    
    response2 = await communicator2.receive_json_from()
    assert response2['type'] == 'game_state'

    # Make a move
    await communicator1.send_json_to({
        'type': 'move',
        'row': 0,
        'col': 0,
        'value': 5
    })

    # Check move broadcast
    move_response = await communicator1.receive_json_from()
    assert move_response['type'] == 'move_made'
    assert move_response['row'] == 0
    assert move_response['col'] == 0
    assert move_response['value'] == 5

    # Clean up
    await communicator1.disconnect()
    await communicator2.disconnect()