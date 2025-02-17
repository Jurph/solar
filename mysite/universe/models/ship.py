from django.db import models
from django.utils.translation import gettext_lazy as _
import random
from .base import Location
from .scale import Scale

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

    # Expose the list of name templates as a class variable.
    NAME_TEMPLATES = [
        "{COLOR} {MATERIAL}",
        "{GIVEN} {SURNAME}'s {ANIMAL}",
        "{GIVEN}'s {MATERIAL} {ANIMAL}",
        "{CITY} {MATERIAL}",
        "{MATERIAL} {NUMBER}",
        "{ANIMAL} {NUMBER}",
        "{SURNAME} {NUMBER}",
        "{MATERIAL} {ANIMAL}",
        "The {AVATAR} of {CITY}",
        "{MATERIAL} {AVATAR}",
        "{COLOR} {AVATAR}",
        "{AVATAR} {NUMBER}"
    ]

    @classmethod
    def generate_name(cls) -> str:
        """Generate a random ship name using the dictionary service."""
        from ..services.dictionary import DictionaryService
        dictionary = DictionaryService()
        template = random.choice(cls.NAME_TEMPLATES)
        # Use string.Formatter to extract placeholder names robustly.
        import string
        formatter = string.Formatter()
        field_names = [
            field_name for _, field_name, _, _ in formatter.parse(template) if field_name
        ]
        # Build replacements by asking the dictionary for each placeholder.
        replacements = {field: dictionary.get_random(field) for field in field_names}
        return template.format(**replacements)

    @classmethod
    def create(cls, *, name: str = None, location: Location = None, 
            size: str = None, cargo: str = None) -> 'Ship':
        """
        Create a new Ship instance with sensible defaults.
        
        Args:
            name: Ship name (generated via generate_name() if not provided)
            location: Starting location (random station if not provided)
            size: Ship size (randomly selected if not provided)
            cargo: Cargo to be transported (generated if not provided)
            
        Returns:
            The created and saved Ship instance with a valid name, cargo, and status.
        """
        if name is None:
            name = cls.generate_name()
        if location is None:
            location = cls.get_random_station()
        if size is None:
            size = random.choice(cls.Size.choices)[0]
        # Generate cargo using a temporary unsaved Ship instance to supply its characteristics.
        if cargo is None:
            from ..services.cargo_server import CargoService
            cargo_service = CargoService()
            temp_ship = cls(name=name, current_location=location, size=size, status='DOCK')
            cargo = cargo_service.generate_cargo(temp_ship)
        
        ship = cls(
            name=name,
            current_location=location,
            size=size,
            cargo=cargo,
            status='DOCK'
        )
        ship.save()
        return ship

    @classmethod
    def get_random_station(cls) -> Location:
        """Get a random station from available stations."""
        station = Location.objects.filter(
            scale=Scale.STATION
        ).order_by('?').first()
        if station is None:
            raise ValueError("No station locations available in the database.")
        return station

    def __str__(self):
        return f"{self.name} ({self.get_status_display()} at {self.current_location.name})"