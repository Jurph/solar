from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .universe import views

urlpatterns = [
    # The administrator page for adding elements 
    path('admin/', admin.site.urls),
    # The "Universe Browser"
    path('universe/', views.universe_view, name='universe'),
    # API endpoint for object details (baseball card)
    path('api/universe/<str:object_type>/<int:object_id>/', views.object_details, name='object_details'),
    # The event scroller wrapper with control panel (main page):
    path("events/", views.event_scroller_wrapper, name="event_scroller_wrapper"),
    # The event scroller page (iframe content):
    path("events/scroller/", views.event_scroller, name="event_scroller"),
    # The JSON API endpoint for polling events:
    path("api/events/", views.event_feed, name="event_feed"),
    # API endpoint to run the dialogue demo:
    path("api/run-demo/", views.run_demo, name="run_demo"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

