from django.contrib import admin
from .models import (
    Galaxy, StarSystem, Star, 
    Planet, Moon, Station, Ship,
    BerthAssignment
)

admin.site.register(Galaxy)
admin.site.register(StarSystem)
admin.site.register(Star)
admin.site.register(Planet)
admin.site.register(Moon)
admin.site.register(Station)
admin.site.register(Ship)
admin.site.register(BerthAssignment)