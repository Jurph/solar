from models import *
from django.db import models
from django.core.files import File
import xml.etree.ElementTree as ET
from django.core import serializers

def exportXML():
    Universe = Galaxy.objects.all()
    data = serializers.serialize('xml', Universe, fields = 'fieldName')
    f = open('export.xml')
    myfile = File(f)
    myfile.write(data)
    myfile.close()