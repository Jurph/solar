from django.urls import path

from . import views

urlpatterns = [
    path('', views.universe_view, name='universe'),
    ]