from django.http import HttpResponse

def index(request):
    return HttpResponse("You have created a galaxy. Hello, galaxy.")