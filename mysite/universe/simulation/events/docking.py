from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...models.ship import Ship
from ...models.station import Station

@dataclass
class DockingRequest:
    """Represents a request to dock at a station"""
    ship: Ship
    station: Station
    requested_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    status: str = 'PENDING'  # PENDING, APPROVED, REJECTED, COMPLETED

    def approve(self):
        self.status = 'APPROVED'
        
    def reject(self):
        self.status = 'REJECTED'
        
    def complete(self):
        self.status = 'COMPLETED'
        self.completed_at = datetime.now()