from django.db import models
from django.utils.translation import gettext_lazy as _
from .base import Location

class Ship(models.Model):
    name = models.CharField(max_length=100)
    
    class Size(models.TextChoices):
        SMALL = 'S', _('small')
        MEDIUM = 'M', _('medium')
        LARGE = 'L', _('large')
    
    size = models.CharField(
        max_length=1,
        choices=Size.choices,
        default=Size.MEDIUM
    )
    
    current_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='ships_present'
    )
    
    cargo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Current cargo being transported'
    )
    
    status = models.CharField(
        max_length=5,
        choices=[
            ('DOCK', 'Docked'),
            ('TRAN', 'In Transit'),
            ('APRCH', 'Approaching'),
            ('HOLD', 'Holding Pattern'),
            ('DEPT', 'Departing')
        ],
        default='DOCK'
    )

    def __str__(self):
        return f"{self.name} ({self.get_status_display()} at {self.current_location.name})"