"""LLM Mock Response Generators for Docker Tests.

These functions generate mock ATC-style dialogue that the container will use
when no real LLM endpoint is available.
"""

# Launch request from ship to control
def generate_launch_request() -> dict:
    return {
        "id": "launch-req-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "qwen2.5:1.5b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Commercial tanker PULP NOVELLA, this is Houston Ground Control. Launch clearance granted. Confirm visual on tower."
            }
        }],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}
    }


# ATC radio response to ship
def generate_radio_response() -> dict:
    return {
        "id": "radio-resp-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "qwen2.5:1.5b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "PULP NOVELLA read back heading zero-niner-zero, passing through outer marker at altitude five-thousand."
            }
        }],
        "usage": {"prompt_tokens": 45, "completion_tokens": 35, "total_tokens": 80}
    }


# Maneuver clearance from controller
def generate_maneuver_clearance() -> dict:
    return {
        "id": "maneuver-cleared-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "qwen2.5:1.5b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Free to execute burn for trans-Mars injection. Thrust vector nominal."
            }
        }],
        "usage": {"prompt_tokens": 48, "completion_tokens": 32, "total_tokens": 80}
    }


# Landing approach scenario
def generate_landing_approach() -> dict:
    return {
        "id": "landing-approach-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "qwen2.5:1.5b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Mineralia Approach, CASSITER you are cleared for final approach runway sector three-alpha."
            }
        }],
        "usage": {"prompt_tokens": 52, "completion_tokens": 28, "total_tokens": 80}
    }


# Emergency beacon reception
def generate_emergency_beacon() -> dict:
    return {
        "id": "emergency-mock",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "qwen2.5:1.5b",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Houston Ground Control, we are receiving distress beacon from vessel IRON HORNET requesting immediate extraction."
            }
        }],
        "usage": {"prompt_tokens": 55, "completion_tokens": 30, "total_tokens": 85}
    }


if __name__ == "__main__":
    # Quick test to verify generators work
    print(generate_launch_request())
    print(generate_radio_response())
