from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Check if any superuser exists'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            exit(0)
        exit(1)