"""
URL configuration for game app
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('lobby/', views.lobby, name='lobby'),
    path('create/', views.create_game, name='create_game'),
    path('join/<str:session_code>/', views.join_game, name='join_game'),
    path('game/<str:session_code>/', views.game_room, name='game_room'),
    path('history/', views.game_history, name='game_history'),
]
