from django.shortcuts import render
from django.http import HttpResponse
from .models import *

# Create your views here.
def index(request):
    response = "Fiat Lux! There is now a universe.<BR>"
    for g in Galaxy.objects.all():
        response += "[O] {}<br>".format(g)
        for ss in StarSystem.objects.all():
            if ss.orbits == g:
                response += "  [o] {}<BR>".format(ss)
            for s in Star.objects.all():
                if s.orbits == ss:
                    response += "   * {}<BR>".format(s)
                for p in Planet.objects.all():
                    if p.orbits == s:
                        response += "    - {}<BR>".format(p)
                    for obj in Location.objects.all():
                        if obj.orbits == p:
                            response += "    -- {}<BR>".format(obj)
                        else:
                            pass
                    for m in Moon.objects.all():
                        if m.orbits == p:
                            response += "    -- {}<BR>".format(m)
                        for obj in Location.objects.all():
                            if obj.orbits == m:
                                response += "    --- {}<BR>".format(obj)
    return HttpResponse(response)
