from django.urls import path

from ..solarweb.app import views

urlpatterns = [
    path('', views.index, name='index'),
]