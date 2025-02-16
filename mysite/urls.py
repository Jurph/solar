from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .universe import views
# from mysite.universe.views.event_scroller import event_scroller
# from mysite.universe.views.event_feed import event_feed

urlpatterns = [
    # The administrator page for adding elements 
    path('admin/', admin.site.urls),
    # The "Universe Browser"
    path('universe/', views.universe_view, name='universe'),
    # The event scroller page:
    # path("events/", event_scroller, name="event_scroller"),
    # The JSON API endpoint for polling events:
    # path("api/events/", event_feed, name="event_feed"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

