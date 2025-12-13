from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Atmosphere(models.Model):
    """
    Atmospheric properties for planets and moons.
    Only created when a celestial body actually has an atmosphere.
    """
    
    class AtmosphereType(models.TextChoices):
        NONE = 'NONE', _('None')
        CO2_THIN = 'CO2_THIN', _('CO₂ Thin')
        CO2_THICK = 'CO2_THICK', _('CO₂ Thick')
        N2_O2 = 'N2_O2', _('N₂/O₂ (Earth-like)')
        N2 = 'N2', _('Nitrogen')
        H2_HE = 'H2_HE', _('H₂/He (Gas Giant)')
        N2_CH4 = 'N2_CH4', _('N₂/CH₄ (Titan-like)')
        SO2 = 'SO2', _('SO₂ (Volcanic)')
        H2O = 'H2O', _('H₂O (Steam)')
    
    # Use ContentType for generic relationship to Planet or Moon
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    parent_body = GenericForeignKey('content_type', 'object_id')
    
    atmosphere_type = models.CharField(
        max_length=10,
        choices=AtmosphereType.choices,
        default=AtmosphereType.NONE
    )
    
    atmosphere_height_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Height of atmosphere above surface in kilometers"
    )
    
    surface_pressure_bar = models.FloatField(
        null=True,
        blank=True,
        help_text="Surface atmospheric pressure in bars"
    )
    
    scale_height_km = models.FloatField(
        null=True,
        blank=True,
        help_text="Atmospheric scale height (density falloff) in kilometers"
    )
    
    class Meta:
        unique_together = ['content_type', 'object_id']
    
    def __str__(self):
        return f"{self.atmosphere_type} atmosphere for {self.parent_body}"

