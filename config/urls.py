from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static

def health_check(request):
    return JsonResponse({"status": "healthy", "service": "2PSUDOKU"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check),
    path('', include('game.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
