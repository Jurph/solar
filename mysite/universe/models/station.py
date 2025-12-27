from django.db import models
from django.core.exceptions import ValidationError
from .base import Location
from .ship import Ship

class Station(Location):
    large_berths = models.PositiveSmallIntegerField(default=1)
    medium_berths = models.PositiveSmallIntegerField(default=2)
    small_berths = models.PositiveSmallIntegerField(default=8)
    orbital_distance_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Orbital distance from parent body surface in km"
    )
    orbits = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='orbiting_stations'
    )

class BerthAssignment(models.Model):
    station = models.ForeignKey(
        'Station', 
        on_delete=models.CASCADE,
        related_name='current_berths'
    )
    ship = models.OneToOneField(
        'Ship',
        on_delete=models.CASCADE,
        related_name='current_berth'
    )
    berth_size = models.CharField(
        max_length=1,
        choices=[('L', 'Large'), ('M', 'Medium'), ('S', 'Small')]
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['station', 'ship']

    def get_available_berths(self, size: str) -> int:
        """Return number of available berths of given size"""
        total = getattr(self, f"{size.lower()}_berths")
        used = self.current_berths.filter(berth_size=size).count()
        return total - used

    def assign_berth(self, ship: 'Ship') -> 'BerthAssignment':
        """Attempt to assign a berth to a ship"""
        if self.get_available_berths(ship.size) <= 0:
            raise ValidationError(f"No available {ship.get_size_display()} berths")
            
        return self.BerthAssignment.objects.create(
            station=self,
            ship=ship,
            berth_size=ship.size
        )