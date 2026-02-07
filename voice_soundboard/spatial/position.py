"""
Spatial Position - 3D position and orientation.

Features:
    - 3D coordinate system
    - Distance calculation
    - Direction vectors
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Coordinates:
    """3D coordinates in meters."""
    
    x: float = 0.0  # Left (-) / Right (+)
    y: float = 0.0  # Down (-) / Up (+)
    z: float = 0.0  # Behind (-) / Front (+)
    
    def distance_to(self, other: "Coordinates") -> float:
        """Calculate distance to another point."""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )
    
    def direction_to(self, other: "Coordinates") -> Tuple[float, float]:
        """
        Calculate direction to another point.
        
        Returns:
            Tuple of (azimuth, elevation) in radians
        """
        dx = other.x - self.x
        dy = other.y - self.y
        dz = other.z - self.z
        
        # Azimuth (horizontal angle)
        azimuth = math.atan2(dx, dz)
        
        # Elevation (vertical angle)
        distance_horizontal = math.sqrt(dx ** 2 + dz ** 2)
        elevation = math.atan2(dy, distance_horizontal)
        
        return azimuth, elevation
    
    def normalized(self) -> "Coordinates":
        """Return normalized unit vector."""
        length = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
        if length == 0:
            return Coordinates(0, 0, 1)  # Default forward
        return Coordinates(
            x=self.x / length,
            y=self.y / length,
            z=self.z / length,
        )
    
    def __add__(self, other: "Coordinates") -> "Coordinates":
        return Coordinates(
            x=self.x + other.x,
            y=self.y + other.y,
            z=self.z + other.z,
        )
    
    def __sub__(self, other: "Coordinates") -> "Coordinates":
        return Coordinates(
            x=self.x - other.x,
            y=self.y - other.y,
            z=self.z - other.z,
        )
    
    def __mul__(self, scalar: float) -> "Coordinates":
        return Coordinates(
            x=self.x * scalar,
            y=self.y * scalar,
            z=self.z * scalar,
        )


@dataclass
class SpatialPosition:
    """
    Position of an audio source in 3D space.
    
    Coordinate system:
        x: Left (-) / Right (+)
        y: Down (-) / Up (+)
        z: Behind (-) / Front (+)
    
    Example:
        # Source 2 meters to the right
        pos = SpatialPosition(x=2.0, y=0.0, z=0.0)
        
        # Source behind and to the left
        pos = SpatialPosition(x=-1.0, y=0.0, z=-2.0)
    """
    
    # Position
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    # Orientation (for directional sources)
    facing_x: float = 0.0
    facing_y: float = 0.0
    facing_z: float = 1.0  # Default facing forward
    
    # Source properties
    spread: float = 0.0  # 0 = point source, 1 = omnidirectional
    rolloff: float = 1.0  # Distance rolloff factor
    min_distance: float = 0.5  # Distance at full volume
    max_distance: float = 50.0  # Maximum audible distance
    
    @property
    def coordinates(self) -> Coordinates:
        """Get position as Coordinates."""
        return Coordinates(self.x, self.y, self.z)
    
    @property
    def facing(self) -> Coordinates:
        """Get facing direction as Coordinates."""
        return Coordinates(self.facing_x, self.facing_y, self.facing_z)
    
    @classmethod
    def from_polar(
        cls,
        azimuth: float,
        distance: float,
        elevation: float = 0.0,
    ) -> "SpatialPosition":
        """
        Create position from polar coordinates.
        
        Args:
            azimuth: Horizontal angle in radians (0 = front, positive = right)
            distance: Distance in meters
            elevation: Vertical angle in radians (0 = level, positive = up)
            
        Returns:
            SpatialPosition
        """
        # Convert to Cartesian
        x = distance * math.sin(azimuth) * math.cos(elevation)
        y = distance * math.sin(elevation)
        z = distance * math.cos(azimuth) * math.cos(elevation)
        
        return cls(x=x, y=y, z=z)
    
    def to_polar(self) -> Tuple[float, float, float]:
        """
        Convert to polar coordinates.
        
        Returns:
            Tuple of (azimuth, distance, elevation)
        """
        distance = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
        azimuth = math.atan2(self.x, self.z)
        elevation = math.atan2(self.y, math.sqrt(self.x ** 2 + self.z ** 2))
        
        return azimuth, distance, elevation
    
    # Convenience factories
    @classmethod
    def center(cls) -> "SpatialPosition":
        """Create position at center (front)."""
        return cls(x=0.0, y=0.0, z=1.0)
    
    @classmethod
    def left(cls, distance: float = 1.0) -> "SpatialPosition":
        """Create position to the left."""
        return cls(x=-distance, y=0.0, z=1.0)
    
    @classmethod
    def right(cls, distance: float = 1.0) -> "SpatialPosition":
        """Create position to the right."""
        return cls(x=distance, y=0.0, z=1.0)
    
    @classmethod
    def behind(cls, distance: float = 1.0) -> "SpatialPosition":
        """Create position behind."""
        return cls(x=0.0, y=0.0, z=-distance)
    
    @classmethod
    def above(cls, distance: float = 1.0) -> "SpatialPosition":
        """Create position above."""
        return cls(x=0.0, y=distance, z=1.0)


@dataclass
class ListenerPosition:
    """
    Position and orientation of the listener.
    
    The listener represents the "camera" for spatial audio,
    typically at the origin facing forward.
    """
    
    # Position
    position: Coordinates = None
    
    # Orientation
    forward: Coordinates = None  # Direction facing
    up: Coordinates = None       # Up vector
    
    def __post_init__(self):
        if self.position is None:
            self.position = Coordinates(0, 0, 0)
        if self.forward is None:
            self.forward = Coordinates(0, 0, 1)  # Facing forward
        if self.up is None:
            self.up = Coordinates(0, 1, 0)  # Y is up
    
    @property
    def right(self) -> Coordinates:
        """Calculate right vector from forward and up."""
        # Cross product: forward × up
        return Coordinates(
            x=self.forward.y * self.up.z - self.forward.z * self.up.y,
            y=self.forward.z * self.up.x - self.forward.x * self.up.z,
            z=self.forward.x * self.up.y - self.forward.y * self.up.x,
        )
    
    def look_at(self, target: Coordinates) -> "ListenerPosition":
        """
        Create new listener looking at target.
        
        Args:
            target: Point to look at
            
        Returns:
            New ListenerPosition
        """
        forward = (target - self.position).normalized()
        
        return ListenerPosition(
            position=self.position,
            forward=forward,
            up=self.up,
        )
    
    def relative_position(self, world_pos: Coordinates) -> Coordinates:
        """
        Convert world position to listener-relative coordinates.
        
        Args:
            world_pos: Position in world space
            
        Returns:
            Position relative to listener
        """
        # Translate to listener position
        relative = world_pos - self.position
        
        # Rotate to listener orientation
        right = self.right
        
        # Project onto listener axes
        return Coordinates(
            x=relative.x * right.x + relative.y * right.y + relative.z * right.z,
            y=relative.x * self.up.x + relative.y * self.up.y + relative.z * self.up.z,
            z=relative.x * self.forward.x + relative.y * self.forward.y + relative.z * self.forward.z,
        )
