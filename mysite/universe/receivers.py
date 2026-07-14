"""Signal receivers for the universe app.

Only live receiver kept here: ensure newly created actors always get an
AudioProfile, even when callers bypass the canonical `.create()` helpers.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver

from mysite.universe.models.actor import Actor, Controller, Pilot, Satellite


@receiver(post_save, sender=Actor)
@receiver(post_save, sender=Pilot)
@receiver(post_save, sender=Controller)
@receiver(post_save, sender=Satellite)
def ensure_actor_audio_profile(sender, instance, created, **kwargs):
    """
    Ensure actors have audio profiles assigned after save.

    This catches any actors created via .objects.create() that bypass .create()
    methods. Idempotent - only assigns if profile is missing or incomplete.
    """
    if not created:
        return

    try:
        profile = instance.audio_profile
        vp = profile.get_voice_params() or {}
        if vp.get("voice_template"):
            return
    except ObjectDoesNotExist:
        pass

    if isinstance(instance, Pilot):
        Pilot.assign_audio_profile(instance)
    elif isinstance(instance, Controller):
        Controller.assign_audio_profile(instance)
    elif isinstance(instance, Satellite):
        Satellite.assign_audio_profile(instance)
    else:
        Actor.assign_audio_profile(instance)
