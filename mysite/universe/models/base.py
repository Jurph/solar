from django.db import models
from .scale import Scale, OrderedScale  # Import the enhanced Scale class

_SCALE_TO_MODEL = None


def _scale_to_model():
    """Lazy map from Location.scale code to its concrete model class."""
    global _SCALE_TO_MODEL
    if _SCALE_TO_MODEL is None:
        from .station import Station
        from .celestial import Galaxy, Moon, Planet, Star, StarSystem

        _SCALE_TO_MODEL = {
            Scale.STATION: Station,
            Scale.MOON: Moon,
            Scale.PLANET: Planet,
            Scale.STAR: Star,
            Scale.STARSYSTEM: StarSystem,
            Scale.GALAXY: Galaxy,
        }
    return _SCALE_TO_MODEL


# Contains the base "Location" model that we can use to instantiate other stuff


class Location(models.Model):
    name = models.CharField(max_length=255, unique=True)
    # orbits = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE)

    # Use the enhanced Scale class for assigning and comparing scales.
    # The field stores a two-character string value, with choices defined in Scale.choices.
    scale = models.CharField(
        max_length=2,
        choices=Scale.choices,
        default=Scale.STATION,
    )

    @property
    def ordered_scale(self):
        return OrderedScale(self.scale)

    def __str__(self):
        return self.name

    def get_concrete_instance(self):
        """
        Return the concrete (most specific) instance for this Location.

        Fast path: use `scale` to jump straight to the matching concrete model,
        so the common case is one query instead of probing every subclass.
        Fallback: if legacy or inconsistent rows have a mismatched scale, probe
        the remaining subclasses to preserve historical behavior.
        """
        if self.__class__.__name__ != "Location":
            return self

        model_by_scale = _scale_to_model()
        preferred_model = model_by_scale.get(self.scale)
        tried_models = set()

        if preferred_model is not None:
            tried_models.add(preferred_model)
            try:
                return preferred_model.objects.get(pk=self.pk)
            except preferred_model.DoesNotExist:
                pass

        from .station import Station
        from .celestial import Moon, Planet, Star, StarSystem, Galaxy

        for subclass in (Station, Moon, Planet, Star, StarSystem, Galaxy):
            if subclass in tried_models:
                continue
            try:
                return subclass.objects.get(pk=self.pk)
            except subclass.DoesNotExist:
                continue
        return self

    def get_type_name(self) -> str:
        """
        Returns the real (concrete) class name as a string.
        """
        return self.get_concrete_instance().__class__.__name__

    @classmethod
    def create(cls, **kwargs):
        """
        Factory method to create a new Location (or a subclass thereof). Uses the
        Django model manager to create the new instance and returns
        its concrete instance.
        """
        instance = cls.objects.create(**kwargs)
        return instance.get_concrete_instance()

    def may_have_station(self):
        """
        Determines if this location may have a space station.
        Typically applies for locations at the STAR, PLANET, or MOON scales.
        """
        return self.scale in {Scale.STAR, Scale.PLANET, Scale.MOON}

    def can_dock(self):
        """
        Determines if this location is a space station suitable for docking.
        """
        return self.scale == Scale.STATION

    def can_land(self):
        """
        Determines if this location supports landing, typically for PLANET or MOON scales.
        """
        return self.scale in {Scale.PLANET, Scale.MOON}

    def requires_launch_clearance(self) -> bool:
        """
        Indicates whether leaving this location requires launch clearance.
        (This could be based on special scale values, for example.)
        """
        return self.scale in {Scale.PLANET, Scale.MOON, Scale.STATION}

    def requires_docking_clearance(self) -> bool:
        """
        Indicates whether arriving at this location requires docking clearance.
        """
        return self.scale == Scale.STATION
