"""
v3.2 Spatial Audio — Graph-Native Spatial Sound.

Spatial audio for Voice Soundboard with strict invariants:
- Listener-centric spatialization
- Headphone / stereo output
- Binaural HRTF rendering
- Static or slowly-moving sources

NOT in v3.2 (explicitly excluded):
- Ambisonics (FOA/HOA)
- Multi-listener rendering
- Speaker array output
- Dynamic room impulse simulation

Design Principles:
1. Spatialization is ALWAYS explicit (never implicit)
2. Temporal order is ALWAYS preserved
3. Loudness is ALWAYS bounded
4. Movement is audio-domain, not control-domain

Coordinate System (Frozen):
- X: Left (-1) to Right (+1)
- Y: Down (-1) to Up (+1)  
- Z: Distance from listener (>0, typically 0.1 to 10)
- Origin: Listener position
- Units: Meters (for distance), normalized for X/Y
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, Protocol
import hashlib
import json


# =============================================================================
# Coordinate System (Section 7: Coordinate system frozen)
# =============================================================================

@dataclass(frozen=True)
class Position3D:
    """
    3D position in listener-centric coordinates.
    
    Coordinate System:
        X: Left-Right axis. -1 = full left, +1 = full right, 0 = center
        Y: Up-Down axis. -1 = below, +1 = above, 0 = ear level  
        Z: Distance from listener in meters. Must be > 0.
    
    The listener is always at origin (0, 0, 0).
    All source positions are relative to the listener.
    """
    x: float = 0.0  # Left (-1) to Right (+1)
    y: float = 0.0  # Down (-1) to Up (+1)
    z: float = 1.0  # Distance in meters (must be > 0)
    
    def __post_init__(self):
        if self.z <= 0:
            raise ValueError(f"Distance (z) must be positive, got {self.z}")
    
    @classmethod
    def from_spherical(cls, azimuth: float, elevation: float, distance: float) -> Position3D:
        """
        Create position from spherical coordinates.
        
        Args:
            azimuth: Horizontal angle in degrees. 0=front, 90=right, -90=left, 180=behind
            elevation: Vertical angle in degrees. 0=ear level, 90=above, -90=below
            distance: Distance in meters (must be > 0)
        """
        if distance <= 0:
            raise ValueError(f"Distance must be positive, got {distance}")
        
        # Convert to radians
        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        
        # Spherical to Cartesian
        x = math.sin(az_rad) * math.cos(el_rad)
        y = math.sin(el_rad)
        z_unit = math.cos(az_rad) * math.cos(el_rad)
        
        # Scale by distance (z is the actual distance, x/y are normalized)
        return cls(x=x, y=y, z=distance)
    
    def to_spherical(self) -> tuple[float, float, float]:
        """
        Convert to spherical coordinates.
        
        Returns:
            (azimuth, elevation, distance) in degrees and meters
        """
        # Distance is just z in our coordinate system
        distance = self.z
        
        # Azimuth from x (assuming unit sphere projection)
        azimuth = math.degrees(math.atan2(self.x, 1.0))  # Assuming z=1 for direction
        
        # Elevation from y
        elevation = math.degrees(math.asin(max(-1, min(1, self.y))))
        
        return (azimuth, elevation, distance)
    
    def distance_to(self, other: Position3D) -> float:
        """Calculate Euclidean distance to another position."""
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )
    
    def interpolate(self, target: Position3D, t: float) -> Position3D:
        """
        Linear interpolation to target position.
        
        Args:
            target: Target position
            t: Interpolation factor (0=self, 1=target)
        """
        t = max(0.0, min(1.0, t))  # Clamp to [0, 1]
        return Position3D(
            x=self.x + (target.x - self.x) * t,
            y=self.y + (target.y - self.y) * t,
            z=self.z + (target.z - self.z) * t,
        )


@dataclass(frozen=True)
class Orientation3D:
    """
    3D orientation for listener head tracking.
    
    Uses Euler angles in degrees:
        yaw: Rotation around vertical axis. 0=forward, +90=right, -90=left
        pitch: Rotation around lateral axis. 0=level, +90=looking up, -90=looking down
        roll: Rotation around forward axis. 0=level, +90=tilted right
    
    For v3.2, only yaw is fully supported (horizontal head rotation).
    Pitch and roll are tracked but have limited HRTF support.
    """
    yaw: float = 0.0    # Horizontal rotation in degrees
    pitch: float = 0.0  # Vertical tilt in degrees
    roll: float = 0.0   # Head tilt in degrees
    
    @classmethod
    def facing(cls, direction: Position3D) -> Orientation3D:
        """Create orientation facing toward a position."""
        azimuth, elevation, _ = direction.to_spherical()
        return cls(yaw=azimuth, pitch=elevation, roll=0.0)
    
    def rotate_position(self, pos: Position3D) -> Position3D:
        """
        Transform a world position to listener-relative coordinates.
        
        This applies the inverse of the listener's rotation to convert
        world coordinates to head-relative coordinates for HRTF lookup.
        """
        # Only apply yaw for v3.2 (horizontal rotation)
        yaw_rad = math.radians(-self.yaw)  # Negative because we're transforming world->head
        
        cos_y = math.cos(yaw_rad)
        sin_y = math.sin(yaw_rad)
        
        new_x = pos.x * cos_y - pos.z * sin_y
        new_z = pos.x * sin_y + pos.z * cos_y
        
        return Position3D(x=new_x, y=pos.y, z=max(0.1, new_z))


# =============================================================================
# Spatial Nodes (Section 2: AudioGraph Spatial Extensions)
# =============================================================================

class SpatialNodeType(str, Enum):
    """Types of spatial nodes in the graph."""
    SOURCE = "source"       # A positioned audio source
    LISTENER = "listener"   # The listener (exactly one per graph)
    DOWNMIX = "downmix"     # Spatial to stereo conversion


@dataclass
class SpatialNode:
    """
    A spatial audio source node.
    
    Represents a positioned sound source in the spatial field.
    Position and movement are explicit graph properties.
    
    Invariants:
    - Position is always defined
    - Distance is always positive
    - Movement is bounded (no teleportation)
    """
    name: str
    position: Position3D = field(default_factory=Position3D)
    
    # Source properties
    distance_model: str = "inverse"  # "linear", "inverse", "exponential"
    ref_distance: float = 1.0        # Distance where gain = 1.0
    max_distance: float = 10.0       # Maximum distance for attenuation
    rolloff_factor: float = 1.0      # How quickly sound attenuates
    
    # Directivity (cone for directional sources)
    inner_cone_angle: float = 360.0  # Full volume within this cone (degrees)
    outer_cone_angle: float = 360.0  # Attenuated beyond this (degrees)
    outer_cone_gain: float = 0.0     # Gain outside outer cone (0-1)
    
    # Node identity
    node_type: SpatialNodeType = SpatialNodeType.SOURCE
    id: str = field(default_factory=lambda: "")
    
    # Movement automation (Section 6)
    _movement_path: list[tuple[float, Position3D]] | None = field(default=None, repr=False)
    
    def __post_init__(self):
        if not self.id:
            content = f"{self.name}:{self.position.x},{self.position.y},{self.position.z}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:8]
    
    def set_position(self, x: float = 0.0, y: float = 0.0, z: float = 1.0) -> SpatialNode:
        """
        Set position explicitly. Returns self for chaining.
        
        This is the ergonomic API for positioning (Section 7).
        """
        self.position = Position3D(x=x, y=y, z=z)
        return self
    
    def calculate_gain(self, listener_distance: float) -> float:
        """
        Calculate distance-based gain attenuation.
        
        Ensures no gain stacking (Section 4).
        """
        if listener_distance <= self.ref_distance:
            return 1.0
        
        if listener_distance >= self.max_distance:
            if self.distance_model == "linear":
                return 0.0
            # For inverse/exponential, cap at max_distance calculation
            listener_distance = self.max_distance
        
        if self.distance_model == "linear":
            return 1.0 - self.rolloff_factor * (listener_distance - self.ref_distance) / (self.max_distance - self.ref_distance)
        elif self.distance_model == "inverse":
            return self.ref_distance / (self.ref_distance + self.rolloff_factor * (listener_distance - self.ref_distance))
        elif self.distance_model == "exponential":
            return (listener_distance / self.ref_distance) ** (-self.rolloff_factor)
        
        return 1.0
    
    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class ListenerNode:
    """
    The listener node — exactly one per spatial graph.
    
    Represents the listener's position and orientation.
    All spatial calculations are relative to the listener.
    
    Invariants:
    - Exactly one listener per graph (enforced by SpatialGraph)
    - Listener is always at origin in head-relative space
    - Orientation affects HRTF selection
    """
    name: str = "listener"
    orientation: Orientation3D = field(default_factory=Orientation3D)
    
    # Listener properties
    speed_of_sound: float = 343.0  # m/s at 20°C (for ITD calculation)
    head_radius: float = 0.0875    # Average human head radius in meters
    
    # HRTF selection
    hrtf_profile: str = "default"  # HRTF dataset to use
    
    # Node identity
    node_type: SpatialNodeType = SpatialNodeType.LISTENER
    id: str = "listener"
    
    def set_orientation(self, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0) -> ListenerNode:
        """
        Set head orientation. Returns self for chaining.
        
        Ergonomic API (Section 7).
        """
        self.orientation = Orientation3D(yaw=yaw, pitch=pitch, roll=roll)
        return self
    
    def calculate_itd(self, source_position: Position3D) -> float:
        """
        Calculate Interaural Time Difference for a source position.
        
        Returns the time difference in seconds between sound arriving
        at the left and right ears.
        
        Positive = right ear leads (source on right)
        Negative = left ear leads (source on left)
        """
        # Apply listener orientation to get head-relative position
        rel_pos = self.orientation.rotate_position(source_position)
        
        # Simplified ITD model: Woodworth formula
        # ITD = (head_radius / speed_of_sound) * (azimuth + sin(azimuth))
        azimuth_rad = math.atan2(rel_pos.x, rel_pos.z)
        itd = (self.head_radius / self.speed_of_sound) * (azimuth_rad + math.sin(azimuth_rad))
        
        return itd
    
    def calculate_ild(self, source_position: Position3D) -> tuple[float, float]:
        """
        Calculate Interaural Level Difference.
        
        Returns (left_gain, right_gain) as multipliers.
        This is a simplified head shadow model.
        """
        rel_pos = self.orientation.rotate_position(source_position)
        
        # Simple panning law based on azimuth
        azimuth = math.atan2(rel_pos.x, rel_pos.z)
        
        # Constant power panning
        left_gain = math.cos(azimuth / 2 + math.pi / 4)
        right_gain = math.sin(azimuth / 2 + math.pi / 4)
        
        # Apply elevation-based attenuation (simplified)
        elevation_factor = 1.0 - abs(rel_pos.y) * 0.1
        
        return (left_gain * elevation_factor, right_gain * elevation_factor)


@dataclass
class SpatialDownmixNode:
    """
    Explicit spatial-to-stereo downmix node.
    
    Required in every spatial graph to convert 3D positioned
    audio to stereo output. Spatialization is NEVER implicit.
    
    This node applies:
    1. HRTF filtering (binaural encoding)
    2. Distance attenuation
    3. Final limiter (safety, Section 4)
    """
    name: str = "spatial_downmix"
    
    # Downmix settings
    hrtf_enabled: bool = True
    apply_distance_attenuation: bool = True
    
    # Safety (Section 4: Loudness & Safety)
    output_gain: float = 1.0
    limiter_threshold_db: float = -1.0  # dBFS
    limiter_enabled: bool = True
    
    # Node identity
    node_type: SpatialNodeType = SpatialNodeType.DOWNMIX
    id: str = "spatial_downmix"
    
    def apply_limiter(self, left: float, right: float) -> tuple[float, float]:
        """
        Apply output limiter for safety.
        
        Ensures no clipping from spatialization (Section 4).
        """
        if not self.limiter_enabled:
            return (left * self.output_gain, right * self.output_gain)
        
        threshold = 10 ** (self.limiter_threshold_db / 20)
        
        def limit(sample: float) -> float:
            sample *= self.output_gain
            if abs(sample) > threshold:
                return math.copysign(threshold, sample)
            return sample
        
        return (limit(left), limit(right))


# =============================================================================
# HRTF Engine (Section 5)
# =============================================================================

class HRTFProfile(str, Enum):
    """Available HRTF profiles."""
    DEFAULT = "default"       # Generic HRTF (KEMAR-derived)
    COMPACT = "compact"       # Low-latency, reduced quality
    WIDE = "wide"            # Enhanced stereo width
    INTIMATE = "intimate"    # Enhanced proximity
    CUSTOM = "custom"        # User-provided HRTF


@dataclass
class HRTFParameters:
    """
    HRTF configuration parameters.
    
    Section 5 Requirements:
    - Deterministic HRTF selection
    - No external mutable state
    - Bounded CPU cost
    - Hot-path safe (no allocations)
    """
    profile: HRTFProfile = HRTFProfile.DEFAULT
    
    # Filter parameters
    filter_length: int = 128       # HRTF filter taps (bounded)
    interpolation: bool = True     # Interpolate between measured positions
    
    # Performance bounds
    max_sources: int = 16          # Maximum concurrent spatial sources
    update_rate_hz: float = 60.0   # Position update rate
    
    # Custom HRTF (Section 5: Optional custom HRTF, validated)
    custom_hrtf_path: str | None = None
    
    def validate(self) -> list[str]:
        """Validate HRTF configuration. Returns list of errors."""
        errors = []
        
        if self.filter_length not in {64, 128, 256, 512}:
            errors.append(f"Invalid filter_length: {self.filter_length}. Must be 64, 128, 256, or 512.")
        
        if self.max_sources < 1 or self.max_sources > 64:
            errors.append(f"max_sources must be between 1 and 64, got {self.max_sources}")
        
        if self.update_rate_hz < 1.0 or self.update_rate_hz > 1000.0:
            errors.append(f"update_rate_hz must be between 1 and 1000, got {self.update_rate_hz}")
        
        if self.profile == HRTFProfile.CUSTOM and not self.custom_hrtf_path:
            errors.append("custom_hrtf_path required when using CUSTOM profile")
        
        return errors


class HRTFEngine:
    """
    HRTF rendering engine for binaural audio.
    
    Processes positioned audio sources into binaural stereo output
    using Head-Related Transfer Functions.
    
    Design constraints (Section 5):
    - Deterministic: Same input always produces same output
    - No external mutable state
    - Bounded CPU cost
    - Hot-path safe: No allocations during processing
    """
    
    def __init__(self, params: HRTFParameters | None = None):
        self.params = params or HRTFParameters()
        
        # Validate on construction
        errors = self.params.validate()
        if errors:
            raise ValueError(f"Invalid HRTF config: {errors}")
        
        # Pre-allocate processing buffers (hot-path safe)
        self._left_buffer: list[float] = [0.0] * self.params.filter_length
        self._right_buffer: list[float] = [0.0] * self.params.filter_length
        
        # Load HRTF data (simplified - real impl would load from file)
        self._hrtf_data = self._load_hrtf_data()
    
    def _load_hrtf_data(self) -> dict[str, Any]:
        """
        Load HRTF data for the selected profile.
        
        Returns pre-computed filter coefficients for various angles.
        In a real implementation, this would load from SOFA files.
        """
        # Simplified: Return placeholder coefficients
        # Real implementation would load from bundled HRTF database
        return {
            "sample_rate": 48000,
            "filter_length": self.params.filter_length,
            "profile": self.params.profile.value,
            # Coefficients would be indexed by (azimuth, elevation)
            "coefficients": {},
        }
    
    def process_source(
        self,
        source: SpatialNode,
        listener: ListenerNode,
        input_samples: list[float],
    ) -> tuple[list[float], list[float]]:
        """
        Process a single spatial source to binaural stereo.
        
        This is the main processing function. It:
        1. Transforms source position to head-relative
        2. Calculates ITD and ILD
        3. Applies HRTF filtering
        4. Returns (left_channel, right_channel)
        
        Invariants (Section 3):
        - No sample reordering
        - No duration change
        - Bounded buffer size
        """
        # Transform to listener-relative coordinates
        rel_pos = listener.orientation.rotate_position(source.position)
        
        # Calculate spatial cues
        itd = listener.calculate_itd(source.position)
        left_gain, right_gain = listener.calculate_ild(source.position)
        
        # Calculate distance attenuation
        distance = source.position.z  # z is distance in our coordinate system
        distance_gain = source.calculate_gain(distance)
        
        # Apply gains (simplified - real HRTF would convolve with filters)
        num_samples = len(input_samples)
        left_output = [0.0] * num_samples
        right_output = [0.0] * num_samples
        
        for i, sample in enumerate(input_samples):
            # Apply distance and panning
            left_output[i] = sample * left_gain * distance_gain
            right_output[i] = sample * right_gain * distance_gain
        
        return (left_output, right_output)
    
    def process_graph(
        self,
        sources: list[tuple[SpatialNode, list[float]]],
        listener: ListenerNode,
        downmix: SpatialDownmixNode,
    ) -> tuple[list[float], list[float]]:
        """
        Process all spatial sources to final stereo output.
        
        This is the graph-level processing function:
        1. Process each source through HRTF
        2. Sum all sources
        3. Apply downmix settings (limiter, etc.)
        
        Section 4: Loudness bounded after HRTF, limiter applied.
        """
        if not sources:
            return ([], [])
        
        # Determine output length (all sources should match)
        output_length = max(len(samples) for _, samples in sources)
        
        # Pre-allocate output (hot-path safe)
        left_mix = [0.0] * output_length
        right_mix = [0.0] * output_length
        
        # Process and mix all sources
        for source, samples in sources:
            left_ch, right_ch = self.process_source(source, listener, samples)
            
            for i, (l, r) in enumerate(zip(left_ch, right_ch)):
                left_mix[i] += l
                right_mix[i] += r
        
        # Apply limiter for safety (Section 4)
        for i in range(output_length):
            left_mix[i], right_mix[i] = downmix.apply_limiter(left_mix[i], right_mix[i])
        
        return (left_mix, right_mix)


# =============================================================================
# Movement & Automation (Section 6)
# =============================================================================

class InterpolationMode(str, Enum):
    """Movement interpolation modes."""
    LINEAR = "linear"           # Simple linear interpolation
    SMOOTHSTEP = "smoothstep"   # Smooth start and end
    EASE_IN = "ease_in"        # Slow start
    EASE_OUT = "ease_out"      # Slow end


@dataclass
class MovementKeyframe:
    """A keyframe in a movement path."""
    time_ms: float              # Time in milliseconds
    position: Position3D        # Target position
    interpolation: InterpolationMode = InterpolationMode.LINEAR
    
    def __post_init__(self):
        if self.time_ms < 0:
            raise ValueError("time_ms must be non-negative")


@dataclass
class MovementPath:
    """
    Explicit movement path for a spatial source.
    
    Section 6 Rules:
    - Movement is explicit in graph
    - Position interpolation bounded
    - No teleportation without fade
    - Registrar does NOT mediate position changes
    
    Movement is audio-domain, not control-domain.
    """
    keyframes: list[MovementKeyframe] = field(default_factory=list)
    
    # Safety bounds
    max_speed: float = 10.0  # Maximum meters per second
    teleport_threshold: float = 5.0  # Distance requiring crossfade
    crossfade_duration_ms: float = 50.0  # Fade duration for teleports
    
    def add_keyframe(self, time_ms: float, position: Position3D, 
                     interpolation: InterpolationMode = InterpolationMode.LINEAR) -> MovementPath:
        """Add a keyframe. Returns self for chaining."""
        kf = MovementKeyframe(time_ms, position, interpolation)
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.time_ms)
        return self
    
    def validate(self) -> list[str]:
        """
        Validate movement path.
        
        Checks:
        - No teleportation without proper handling
        - Speed bounds respected
        - Keyframes properly ordered
        """
        errors = []
        
        if len(self.keyframes) < 2:
            return errors  # No movement to validate
        
        for i in range(1, len(self.keyframes)):
            prev = self.keyframes[i - 1]
            curr = self.keyframes[i]
            
            # Check time ordering
            if curr.time_ms <= prev.time_ms:
                errors.append(f"Keyframes must be time-ordered: {prev.time_ms} >= {curr.time_ms}")
            
            # Check distance/speed
            distance = prev.position.distance_to(curr.position)
            duration_s = (curr.time_ms - prev.time_ms) / 1000.0
            
            if duration_s > 0:
                speed = distance / duration_s
                if speed > self.max_speed:
                    errors.append(
                        f"Speed exceeds maximum: {speed:.2f} m/s > {self.max_speed} m/s "
                        f"between {prev.time_ms}ms and {curr.time_ms}ms"
                    )
            
            # Check for teleportation
            if distance > self.teleport_threshold:
                # Teleportation requires crossfade handling
                if duration_s * 1000 < self.crossfade_duration_ms:
                    errors.append(
                        f"Teleportation detected without sufficient crossfade: "
                        f"{distance:.2f}m in {duration_s * 1000:.0f}ms"
                    )
        
        return errors
    
    def position_at(self, time_ms: float) -> Position3D:
        """
        Get interpolated position at a given time.
        
        Section 6: Position interpolation bounded.
        """
        if not self.keyframes:
            return Position3D()
        
        if time_ms <= self.keyframes[0].time_ms:
            return self.keyframes[0].position
        
        if time_ms >= self.keyframes[-1].time_ms:
            return self.keyframes[-1].position
        
        # Find surrounding keyframes
        for i in range(1, len(self.keyframes)):
            if self.keyframes[i].time_ms >= time_ms:
                prev = self.keyframes[i - 1]
                curr = self.keyframes[i]
                
                # Calculate interpolation factor
                duration = curr.time_ms - prev.time_ms
                elapsed = time_ms - prev.time_ms
                t = elapsed / duration if duration > 0 else 0
                
                # Apply interpolation mode
                t = self._apply_interpolation(t, curr.interpolation)
                
                return prev.position.interpolate(curr.position, t)
        
        return self.keyframes[-1].position
    
    def _apply_interpolation(self, t: float, mode: InterpolationMode) -> float:
        """Apply interpolation curve."""
        if mode == InterpolationMode.LINEAR:
            return t
        elif mode == InterpolationMode.SMOOTHSTEP:
            return t * t * (3 - 2 * t)
        elif mode == InterpolationMode.EASE_IN:
            return t * t
        elif mode == InterpolationMode.EASE_OUT:
            return 1 - (1 - t) ** 2
        return t


# =============================================================================
# Spatial Graph (Section 2: Full graph implementation)
# =============================================================================

@dataclass
class SpatialGraphValidation:
    """Validation results for a spatial graph."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def add_error(self, message: str) -> None:
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class SpatialGraph:
    """
    Graph container for spatial audio.
    
    Enforces spatial audio invariants:
    - Exactly one listener per graph
    - Explicit spatial → stereo downmix
    - All sources must be connected
    - Movement paths validated
    
    Section 2: Spatial audio must be graph-native.
    """
    
    MAX_SOURCES = 64  # Hard limit on concurrent sources
    
    def __init__(self, name: str = "spatial_graph"):
        self.name = name
        self._listener: ListenerNode | None = None
        self._sources: dict[str, SpatialNode] = {}
        self._downmix: SpatialDownmixNode | None = None
        self._movement_paths: dict[str, MovementPath] = {}
        self._hrtf_params: HRTFParameters = HRTFParameters()
        self._metadata: dict[str, Any] = {}
    
    # =========================================================================
    # Listener (exactly one)
    # =========================================================================
    
    def set_listener(self, listener: ListenerNode | None = None) -> ListenerNode:
        """
        Set the listener node. Creates default if not provided.
        
        There can only be one listener per graph.
        """
        self._listener = listener or ListenerNode()
        return self._listener
    
    @property
    def listener(self) -> ListenerNode | None:
        """Get the listener node."""
        return self._listener
    
    # =========================================================================
    # Sources
    # =========================================================================
    
    def add_source(self, name: str, position: Position3D | None = None) -> SpatialNode:
        """Add a spatial source to the graph."""
        if len(self._sources) >= self.MAX_SOURCES:
            raise ValueError(f"Maximum sources ({self.MAX_SOURCES}) exceeded")
        
        if name in self._sources:
            raise ValueError(f"Source '{name}' already exists")
        
        source = SpatialNode(name=name, position=position or Position3D())
        self._sources[name] = source
        return source
    
    def get_source(self, name: str) -> SpatialNode | None:
        """Get a source by name."""
        return self._sources.get(name)
    
    def remove_source(self, name: str) -> bool:
        """Remove a source. Returns True if removed."""
        if name in self._sources:
            del self._sources[name]
            if name in self._movement_paths:
                del self._movement_paths[name]
            return True
        return False
    
    @property
    def sources(self) -> list[SpatialNode]:
        """Get all sources."""
        return list(self._sources.values())
    
    @property
    def source_count(self) -> int:
        """Number of sources."""
        return len(self._sources)
    
    # =========================================================================
    # Downmix (required)
    # =========================================================================
    
    def set_downmix(self, downmix: SpatialDownmixNode | None = None) -> SpatialDownmixNode:
        """
        Set the downmix node. Creates default if not provided.
        
        The downmix node is required for explicit stereo conversion.
        """
        self._downmix = downmix or SpatialDownmixNode()
        return self._downmix
    
    @property
    def downmix(self) -> SpatialDownmixNode | None:
        """Get the downmix node."""
        return self._downmix
    
    # =========================================================================
    # Movement
    # =========================================================================
    
    def add_movement(self, source_name: str, path: MovementPath) -> None:
        """Add a movement path to a source."""
        if source_name not in self._sources:
            raise ValueError(f"Source '{source_name}' not found")
        self._movement_paths[source_name] = path
    
    def get_movement(self, source_name: str) -> MovementPath | None:
        """Get movement path for a source."""
        return self._movement_paths.get(source_name)
    
    # =========================================================================
    # HRTF Configuration
    # =========================================================================
    
    def configure_hrtf(self, params: HRTFParameters) -> None:
        """
        Configure HRTF parameters.
        
        Section 5: HRTF changes require graph rebuild.
        """
        errors = params.validate()
        if errors:
            raise ValueError(f"Invalid HRTF config: {errors}")
        self._hrtf_params = params
    
    @property
    def hrtf_params(self) -> HRTFParameters:
        """Get HRTF parameters."""
        return self._hrtf_params
    
    # =========================================================================
    # Validation (Section 8)
    # =========================================================================
    
    def validate(self) -> SpatialGraphValidation:
        """
        Validate the spatial graph.
        
        Checks:
        - Exactly one listener
        - Downmix node present
        - All sources valid
        - Movement paths valid
        - HRTF configuration valid
        """
        result = SpatialGraphValidation()
        
        # Check listener (required)
        if self._listener is None:
            result.add_error("No listener node. Call set_listener() first.")
        
        # Check downmix (required)
        if self._downmix is None:
            result.add_error("No downmix node. Call set_downmix() for explicit stereo conversion.")
        
        # Check source count
        if len(self._sources) == 0:
            result.add_warning("No spatial sources in graph.")
        
        if len(self._sources) > self.MAX_SOURCES:
            result.add_error(f"Too many sources: {len(self._sources)} > {self.MAX_SOURCES}")
        
        # Validate each source
        for name, source in self._sources.items():
            if source.position.z <= 0:
                result.add_error(f"Source '{name}' has invalid distance: {source.position.z}")
        
        # Validate movement paths
        for source_name, path in self._movement_paths.items():
            errors = path.validate()
            for err in errors:
                result.add_error(f"Movement path '{source_name}': {err}")
        
        # Validate HRTF
        hrtf_errors = self._hrtf_params.validate()
        for err in hrtf_errors:
            result.add_error(f"HRTF: {err}")
        
        return result
    
    # =========================================================================
    # Processing
    # =========================================================================
    
    def create_engine(self) -> HRTFEngine:
        """Create an HRTF engine configured for this graph."""
        return HRTFEngine(self._hrtf_params)


# =============================================================================
# Ergonomic API (Section 7)
# =============================================================================

def create_spatial_scene(
    name: str = "scene",
    hrtf_profile: HRTFProfile = HRTFProfile.DEFAULT,
) -> SpatialGraph:
    """
    Create a spatial scene with sensible defaults.
    
    This is the simple entry point for spatial audio (Section 7).
    
    Example:
        scene = create_spatial_scene()
        scene.add_source("voice", Position3D(x=0.5, y=0, z=1.5))
        scene.listener.set_orientation(yaw=30)
    """
    graph = SpatialGraph(name=name)
    
    # Set up defaults
    graph.set_listener()
    graph.set_downmix()
    graph.configure_hrtf(HRTFParameters(profile=hrtf_profile))
    
    return graph


# =============================================================================
# Safety Invariants (Section 4)
# =============================================================================

@dataclass
class SpatialSafetyLimits:
    """
    Safety limits for spatial audio processing.
    
    Section 4: Loudness & Safety Invariants.
    """
    # Maximum combined gain from distance + panning
    max_combined_gain: float = 2.0
    
    # Output ceiling (dBFS)
    output_ceiling_db: float = -0.1
    
    # Maximum distance for any source
    max_source_distance: float = 100.0
    
    # Minimum distance (to prevent infinite gain)
    min_source_distance: float = 0.1


def validate_spatial_safety(
    sources: list[SpatialNode],
    limits: SpatialSafetyLimits | None = None,
) -> list[str]:
    """
    Validate spatial sources against safety limits.
    
    Returns list of violations.
    """
    limits = limits or SpatialSafetyLimits()
    violations = []
    
    for source in sources:
        # Check distance bounds
        if source.position.z < limits.min_source_distance:
            violations.append(
                f"Source '{source.name}' too close: {source.position.z}m < {limits.min_source_distance}m"
            )
        
        if source.position.z > limits.max_source_distance:
            violations.append(
                f"Source '{source.name}' too far: {source.position.z}m > {limits.max_source_distance}m"
            )
        
        # Check potential gain stacking
        max_gain = source.calculate_gain(limits.min_source_distance)
        if max_gain > limits.max_combined_gain:
            violations.append(
                f"Source '{source.name}' max gain too high: {max_gain:.2f} > {limits.max_combined_gain}"
            )
    
    return violations


# =============================================================================
# Public API Exports
# =============================================================================

__all__ = [
    # Coordinates
    "Position3D",
    "Orientation3D",
    # Nodes
    "SpatialNode",
    "SpatialNodeType",
    "ListenerNode",
    "SpatialDownmixNode",
    # HRTF
    "HRTFProfile",
    "HRTFParameters",
    "HRTFEngine",
    # Movement
    "InterpolationMode",
    "MovementKeyframe",
    "MovementPath",
    # Graph
    "SpatialGraph",
    "SpatialGraphValidation",
    "create_spatial_scene",
    # Safety
    "SpatialSafetyLimits",
    "validate_spatial_safety",
]
