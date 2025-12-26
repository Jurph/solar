from typing import List

from mysite.universe.models.navigation import NavigationEvent


def pretty_print_events(events: List[NavigationEvent], include_headers: bool = True) -> str:
    """
    Creates a readable table of navigation events with key information.

    This is presentation/diagnostics, not core route logic.
    """
    if not events:
        return "No navigation events to display"

    origins = []
    for i, event in enumerate(events):
        if i == 0:
            origins.append("STARTING POINT")
        else:
            origins.append(events[i - 1].destination.name if events[i - 1].destination else "Unknown")

    origin_width = max(len("Origin"), max(len(str(o)) for o in origins))
    next_stop_width = max(
        len("Next Stop"),
        max(len(str(e.destination.name)) if e.destination else 0 for e in events),
    )
    maneuver_width = max(len("Maneuver Type"), max(len(str(e.maneuver.name)) for e in events))
    controller_width = max(
        len("Effective Controller"),
        max(len(str(e.controller.name)) if e.controller else len("None") for e in events),
    )

    row_template = f"{{:{origin_width}}} | {{:{next_stop_width}}} | {{:{maneuver_width}}} | {{:{controller_width}}}"

    result = []
    if include_headers:
        result.append(row_template.format("Origin", "Next Stop", "Maneuver Type", "Effective Controller"))
        result.append("-" * (origin_width + next_stop_width + maneuver_width + controller_width + 9))

    for i, event in enumerate(events):
        origin = origins[i]
        next_stop = event.destination.name if event.destination else "Unknown"
        maneuver_type = event.maneuver.name
        controller = event.controller.name if event.controller else "None"
        result.append(row_template.format(origin, next_stop, maneuver_type, controller))

    return "\n".join(result)


