from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...models.ship import Ship
import random 

@dataclass
class MaintenanceEvent:
    """Basic representation of a ship maintenance issue"""
    ship: Ship
    occurred_at: datetime = datetime.now()
    resolved_at: Optional[datetime] = None
    repair_time: int = 1  # Default 1 time unit for now
    
    def mark_resolved(self):
        """Mark the maintenance event as resolved"""
        self.resolved_at = datetime.now()

class MaintenanceManager:
    """Basic manager for ship maintenance events"""
    
    def __init__(self, env):
        self.env = env
        self.active_events = []
    
    def check_for_failure(self, ship: Ship) -> Optional[MaintenanceEvent]:
        """Simple random check for generic failure"""
        # For now, just a 1% chance of failure per tick
        if random.random() < 0.01:
            return MaintenanceEvent(ship=ship)
        return None
    
    async def handle_maintenance_event(self, event: MaintenanceEvent):
        """Handle a basic maintenance event"""
        self.active_events.append(event)
        
        # Basic status update
        event.ship.status = 'HOLD'
        event.ship.save()
        
        # Simple delay
        yield self.env.timeout(event.repair_time)
        
        # Resolve
        event.mark_resolved()
        self.active_events.remove(event)
        
        # Resume normal operation
        event.ship.status = 'TRAN'
        event.ship.save()