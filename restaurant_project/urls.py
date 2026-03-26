from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views

urlpatterns = [
    path('', include('core.urls')),
    path('admin/', admin.site.urls),
    path('owner/', include('core.owner_urls')),
    path('api/place-order/', core_views.place_order, name='place_order'),
    path('restaurant/<slug:slug>/', core_views.restaurant_public, name='restaurant_public'),
]

# Only serve media files through Django in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
