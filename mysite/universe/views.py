from inspect import Attribute
from django.shortcuts import render
from django.http import HttpResponse
from .models import *

def orbitsAround(hub, orbiter):
    for a in Location.objects.all():
        try:
            if orbiter.orbits_id == None:
                return False
            elif orbiter.orbits_id == hub.id:
                return True
        except AttributeError:
            return False

# Create your views here.
def index(request):
    response = "Fiat Lux! There is now a universe.<BR>"
    for g in Galaxy.objects.all():
        response += "GALAXY: {} //  ID: {}<BR>".format(g, g.id)
        for ss in StarSystem.objects.all():
            if orbitsAround(g, ss):
                response += "..{}<BR>".format(ss)
                for s in Star.objects.all():
                    if orbitsAround(ss, s):
                        response += "...o {}<BR>".format(s)
                        for p in Planet.objects.all():
                            if orbitsAround(s, p):
                                response += ".....*{}<BR>".format(p)
                                for stat in Station.objects.all():
                                    if orbitsAround(p, stat):
                                        response += ".......-{}<BR>".format(stat)
                                for m in Moon.objects.all():
                                    if orbitsAround(p, m):
                                        response += ".......-{}<BR>".format(m)
                                        for obj in Station.objects.all():
                                            if orbitsAround(m, obj):
                                                response += "........--{}<BR>".format(obj)
                        for solarstation in Station.objects.all():
                            if orbitsAround(s, solarstation):
                                response += ".....*{}<BR>".format(stat)

    return HttpResponse(response)

# def later(request):
#    for g in Galaxy.objects.all():
#        response += "[O] {}<br>".format(g)
#            for s in Star.objects.all():
#                if s.orbits_id == ss:
#                    response += "   * {}<BR>".format(s)
#                for p in Planet.objects.all():
#                    if p.orbits == s:
#                        response += "    - {}<BR>".format(p)
#                    for obj in Location.objects.all():
#                        if obj.orbits == p:
#                            response += "    -- {}<BR>".format(obj)
#                        else:
#                            pass
#                    for m in Moon.objects.all():
#                        if m.orbits == p:
#                             response += "    -- {}<BR>".format(m)
#                        for obj in Location.objects.all():
#                            if obj.orbits == m:
#                                response += "    --- {}<BR>".format(obj)
