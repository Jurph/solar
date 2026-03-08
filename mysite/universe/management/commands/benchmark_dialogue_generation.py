import time
from typing import Optional

from django.core.management.base import BaseCommand

from mysite.universe.models.base import Location
from mysite.universe.models.ship import Ship
from mysite.universe.models.actor import Pilot
from mysite.universe.services.llm_service import LLMService
from mysite.universe.services.route_server import RouteService
from mysite.universe.services.script_server import ScriptService


class Command(BaseCommand):
    help = "Benchmark LLM-backed dialogue generation latency for a planned route."

    def add_arguments(self, parser):
        parser.add_argument("--origin", type=str, default="Mars", help="Origin Location.name")
        parser.add_argument("--destination", type=str, default="Earth", help="Destination Location.name")
        parser.add_argument("--temperature", type=float, default=0.25, help="LLM temperature")
        parser.add_argument(
            "--physics-delays",
            action="store_true",
            help="Use physics-based delays between navigation-event chains (default: off)",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=1,
            help="Number of times to generate dialogue for the same planned route",
        )

    def handle(self, *args, **options):
        origin_name = options["origin"]
        dest_name = options["destination"]
        temperature = options["temperature"]
        use_physics_delays = bool(options["physics_delays"])
        iterations = int(options["iterations"])

        origin = self._get_location_by_name(origin_name)
        destination = self._get_location_by_name(dest_name)

        route_service = RouteService()
        t0 = time.perf_counter()
        route_events = route_service.plan_route(origin=origin, destination=destination)
        t1 = time.perf_counter()

        if not route_events:
            self.stderr.write(self.style.ERROR("No route events generated; cannot benchmark dialogue generation."))
            return

        llm = LLMService(quiet_mode=True)
        llm.temperature = temperature
        script_service = ScriptService(llm=llm)

        ship = Ship.create(location=origin)
        Pilot.create(ship=ship)

        self.stdout.write(self.style.SUCCESS("Benchmark: Dialogue generation"))
        self.stdout.write(f"- Origin: {origin.name}")
        self.stdout.write(f"- Destination: {destination.name}")
        self.stdout.write(f"- Navigation events: {len(route_events)}")
        self.stdout.write(f"- Plan route time: {(t1 - t0):.3f}s")
        self.stdout.write(f"- Iterations: {iterations}")
        self.stdout.write(f"- use_physics_delays: {use_physics_delays}")
        self.stdout.write(f"- temperature: {temperature}")

        per_iter = []
        first_event_latencies = []
        event_counts = []

        for i in range(iterations):
            start = time.perf_counter()
            first_event_time: Optional[float] = None
            count = 0

            for event in script_service.iter_navigation_events(
                route_events, ship, use_physics_delays=use_physics_delays
            ):
                if first_event_time is None:
                    first_event_time = time.perf_counter()
                count += 1

            end = time.perf_counter()
            per_iter.append(end - start)
            event_counts.append(count)
            if first_event_time is not None:
                first_event_latencies.append(first_event_time - start)

            self.stdout.write(
                f"iter {i+1}/{iterations}: {count} events, "
                f"first_event={(first_event_time - start):.3f}s, total={(end - start):.3f}s"
                if first_event_time is not None
                else f"iter {i+1}/{iterations}: {count} events, total={(end - start):.3f}s (no events)"
            )

        if per_iter:
            avg_total = sum(per_iter) / len(per_iter)
            self.stdout.write(self.style.SUCCESS(f"avg total: {avg_total:.3f}s"))
        if first_event_latencies:
            avg_first = sum(first_event_latencies) / len(first_event_latencies)
            self.stdout.write(self.style.SUCCESS(f"avg time-to-first-event: {avg_first:.3f}s"))
        if event_counts:
            avg_count = sum(event_counts) / len(event_counts)
            self.stdout.write(self.style.SUCCESS(f"avg events per run: {avg_count:.1f}"))

    def _get_location_by_name(self, name: str) -> Location:
        try:
            return Location.objects.get(name=name)
        except Location.DoesNotExist:
            raise SystemExit(f"Location '{name}' not found. Have you imported universe XML?") from None


