from django.shortcuts import render
from .models import Galaxy

def universe_view(request):
    galaxies = Galaxy.objects.all()
    
    # Debug output
    print(f"Found {galaxies.count()} galaxies")
    for galaxy in galaxies:
        print(f"Galaxy: {galaxy.name}")
    
    return render(request, 'universe/index.html', {'galaxies': galaxies})