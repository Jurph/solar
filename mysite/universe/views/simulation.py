"""
Views for simulation time control and status.

Contains:
- set_time_scale: Adjust simulation speed (1x to 3600x)
- skip_to_next_event: Fast-forward to the next pending event
- get_simulation_status: Query current simulation time and scale
"""
import json
import logging
import time as time_module

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from mysite.universe.models.event import DialogueEventLog
from mysite.universe.models.simulation import SimulationState, get_simulation_time

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def set_time_scale(request):
    """
    API endpoint to set the simulation time scale.
    
    Time scale controls how fast simulation time advances relative to wall-clock:
    - 1.0 = real-time (1 second real = 1 second simulation)
    - 60.0 = 1 minute real = 1 hour simulation
    - 3600.0 = 1 second real = 1 hour simulation
    
    POST body (JSON):
        time_scale: float - the new time scale multiplier
    
    Returns:
        JSON with status, current simulation_time, and time_scale
    """
    try:
        data = json.loads(request.body) if request.body else {}
        new_scale = float(data.get('time_scale', 1.0))
        
        if new_scale <= 0:
            return JsonResponse({
                'status': 'error',
                'message': 'time_scale must be positive'
            }, status=400)
        
        # Update the simulation state
        state = SimulationState.get_instance()
        state.set_time_scale(new_scale)
        
        return JsonResponse({
            'status': 'success',
            'simulation_time': state.get_simulation_time(),
            'time_scale': state.time_scale,
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid request: {str(e)}'
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def skip_to_next_event(request):
    """
    API endpoint to advance simulation time to the next pending event.
    
    This allows users to "fast forward" to the next event without waiting
    for real-time to pass. Useful for debugging and demonstration.
    
    Returns:
        JSON with status, new simulation_time, and the skipped duration
    """
    current_sim_time = get_simulation_time()
    
    # Find the next pending event
    next_event = DialogueEventLog.objects.filter(
        timestamp__gt=current_sim_time
    ).order_by('timestamp').first()
    
    if not next_event:
        return JsonResponse({
            'status': 'no_events',
            'message': 'No pending events to skip to',
            'simulation_time': current_sim_time,
        })
    
    # Advance simulation time to just after the next event
    # (add a small buffer so the event becomes available immediately)
    new_sim_time = next_event.timestamp + 0.1
    skipped_duration = new_sim_time - current_sim_time
    
    # Update simulation state anchor to the new time
    # This re-anchors the simulation clock at the new time point
    state = SimulationState.get_instance()
    state.anchor_sim_time = new_sim_time
    state.anchor_wall_clock = time_module.time()
    state.time_scale = state.time_scale  # Preserve current time scale
    state.save()
    
    # Verify the update took effect
    actual_sim_time = get_simulation_time()
    
    logger.debug(
        f"skip_to_next: Skipped from {current_sim_time:.1f} to {new_sim_time:.1f} "
        f"(actual: {actual_sim_time:.1f})"
    )
    logger.debug(
        f"skip_to_next: Next event {next_event.actor_name} at {next_event.timestamp:.1f}"
    )
    
    return JsonResponse({
        'status': 'success',
        'simulation_time': actual_sim_time,
        'skipped_seconds': skipped_duration,
        'next_event_actor': next_event.actor_name,
    })


@csrf_exempt
@require_http_methods(["GET"])
def get_simulation_status(request):
    """
    API endpoint to get current simulation time and scale.
    
    Returns:
        JSON with simulation_time, time_scale, and anchor information
    """
    state = SimulationState.get_instance()
    
    return JsonResponse({
        'simulation_time': state.get_simulation_time(),
        'time_scale': state.time_scale,
        'anchor_sim_time': state.anchor_sim_time,
        'anchor_wall_clock': state.anchor_wall_clock,
    })


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    API endpoint to check health of critical services.
    
    Uses OpenAI-compatible endpoints for maximum compatibility with
    different LLM providers (Ollama, LM Studio, OpenAI, etc.).
    
    Returns:
        JSON with health status for each service
    """
    import requests
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Q
    
    health = {}
    
    # Check LLM server using OpenAI-compatible /v1/models endpoint
    # This works with: Ollama, LM Studio, OpenAI API, and other compatible servers
    try:
        resp = requests.get('http://localhost:11434/v1/models', timeout=2)
        if resp.status_code == 200:
            health['llm'] = {
                'status': 'ok',
                'message': 'LLM server responding'
            }
        else:
            health['llm'] = {
                'status': 'error',
                'message': f'LLM server returned {resp.status_code}'
            }
    except requests.exceptions.ConnectionError:
        health['llm'] = {
            'status': 'error',
            'message': 'Cannot connect to LLM server (http://localhost:11434)'
        }
    except Exception as e:
        health['llm'] = {
            'status': 'error',
            'message': f'LLM check failed: {str(e)}'
        }
    
    # Check audio worker activity
    # Look for recent audio generation (within last 2 minutes)
    recent_audio = DialogueEventLog.objects.filter(
        audio_rendered_at__gte=timezone.now() - timedelta(minutes=2)
    ).count()
    
    # Check if there are events needing audio
    pending_audio = DialogueEventLog.objects.filter(
        Q(audio_file='') | Q(audio_file__isnull=True),
        audio_generating=False,
        timestamp__lte=get_simulation_time() + 3600  # Within 1 hour lookahead
    ).count()
    
    if recent_audio > 0:
        health['audio_worker'] = {
            'status': 'ok',
            'message': f'Generated {recent_audio} clips in last 2 minutes'
        }
    elif pending_audio == 0:
        health['audio_worker'] = {
            'status': 'idle',
            'message': 'No events pending audio generation'
        }
    else:
        health['audio_worker'] = {
            'status': 'warning',
            'message': f'{pending_audio} events need audio but no recent generation'
        }
    
    return JsonResponse(health)
