from django.shortcuts import render
from .models import Galaxy

def universe_view(request):
    galaxies = Galaxy.objects.all()
    return render(request, 'universe/index.html', {'galaxies': galaxies})