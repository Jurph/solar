from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Galaxy)
admin.site.register(StarSystem)
admin.site.register(Star)
admin.site.register(Planet)
admin.site.register(Moon)
admin.site.register(Station)