# v3.2 Spatial Audio Documentation

## Overview

Version 3.2 adds **Spatial Audio & Acoustic Context** to the Voice Soundboard audio graph system. This enables listener-centric spatialization, binaural HRTF rendering, and explicit spatial-to-stereo downmix.

## Coordinate System (Frozen)

The spatial coordinate system follows standard conventions and is **frozen** for v3.2:

```
         +Y (Up)
          |
          |
          +---- +X (Right)
         /
        /
       +Z (Distance from listener, always positive)
```

- **X**: Left (-1) to Right (+1) - horizontal position
- **Y**: Down (-1) to Up (+1) - vertical position  
- **Z**: Distance from listener in meters (must be > 0)

### Position Examples

```python
from voice_soundboard.v3 import Position3D

# Directly in front, 2 meters away
front = Position3D(x=0, y=0, z=2)

# To the right, 1 meter away
right = Position3D(x=1, y=0, z=1)

# Slightly left and above, 3 meters away
left_up = Position3D(x=-0.5, y=0.3, z=3)
```

## Quick Start

### Creating a Spatial Scene

```python
from voice_soundboard.v3 import create_spatial_scene, Position3D

# Create a scene with defaults (listener, downmix, HRTF engine)
scene = create_spatial_scene()

# Add positioned sources
voice1 = scene.add_source("speaker1", Position3D(x=-0.5, y=0, z=2))
voice2 = scene.add_source("speaker2", Position3D(x=0.5, y=0, z=2))

# Validate the graph
result = scene.validate()
assert result.is_valid
```

### Processing Audio

```python
from voice_soundboard.v3 import HRTFEngine

# Get audio data (from your audio pipeline)
audio1 = [...]  # Float samples for source 1
audio2 = [...]  # Float samples for source 2

# Create HRTF engine
engine = HRTFEngine()

# Process sources to binaural stereo
source_data = [
    (voice1, audio1),
    (voice2, audio2),
]
left, right = engine.process_graph(source_data, scene.listener, scene.downmix)
```

## Core Components

### Position3D

Immutable (frozen) position in 3D space:

```python
@dataclass(frozen=True)
class Position3D:
    x: float = 0.0  # Left/Right
    y: float = 0.0  # Down/Up
    z: float = 1.0  # Distance (always positive)
```

Key methods:
- `distance_to(other)` - Euclidean distance
- `to_spherical()` - Convert to (azimuth, elevation, distance)
- `from_spherical(azimuth, elevation, distance)` - Create from spherical
- `interpolate(other, t)` - Linear interpolation

### SpatialNode

A positioned audio source:

```python
source = SpatialNode(
    name="voice",
    position=Position3D(x=0.5, y=0, z=1),
    distance_model="inverse",  # "linear", "inverse", "exponential"
    ref_distance=1.0,          # Distance where gain = 1.0
    max_distance=10.0,         # Maximum attenuation distance
)

# Update position
source.set_position(x=0.3, y=0, z=2)

# Calculate distance attenuation
gain = source.calculate_gain(listener_distance=2.0)
```

### ListenerNode

The single listener in the scene:

```python
listener = ListenerNode(
    name="listener",
    position=Position3D(x=0, y=0, z=0),  # Usually at origin
    orientation=Orientation3D(yaw=0, pitch=0, roll=0),
)

# Calculate ITD (Interaural Time Difference)
itd = listener.calculate_itd(source_position)

# Calculate ILD (Interaural Level Difference)
left_gain, right_gain = listener.calculate_ild(source_position)
```

### SpatialDownmixNode

Explicit spatial-to-stereo conversion:

```python
downmix = SpatialDownmixNode(
    limiter_enabled=True,         # Apply output limiter
    limiter_threshold_db=-0.1,    # Limiter threshold
)

# Apply limiting
left_out, right_out = downmix.apply_limiter(left_in, right_in)
```

### HRTFEngine

Binaural rendering engine:

```python
from voice_soundboard.v3 import HRTFEngine, HRTFParameters, HRTFProfile

# Default configuration
engine = HRTFEngine()

# Custom configuration
params = HRTFParameters(
    profile=HRTFProfile.WIDE,  # COMPACT, DEFAULT, WIDE, INTIMATE, CUSTOM
    filter_length=128,          # HRTF filter taps
    max_sources=16,             # Maximum concurrent sources
)
engine = HRTFEngine(params)

# Process single source
left, right = engine.process_source(source, listener, samples)

# Process multiple sources with mixing
source_data = [(source1, samples1), (source2, samples2)]
left, right = engine.process_graph(source_data, listener, downmix)
```

## Movement Automation

### MovementPath

Define movement over time:

```python
from voice_soundboard.v3 import MovementPath, MovementKeyframe, InterpolationMode

# Create path
path = MovementPath()
path.add_keyframe(0, Position3D(x=-1, y=0, z=1))          # Start left
path.add_keyframe(1000, Position3D(x=0, y=0, z=1))        # Center at 1s
path.add_keyframe(2000, Position3D(x=1, y=0, z=1))        # End right at 2s

# Or use fluent API
path = (MovementPath()
    .add_keyframe(0, Position3D(x=-1, y=0, z=1))
    .add_keyframe(1000, Position3D(x=1, y=0, z=1), InterpolationMode.SMOOTHSTEP))

# Get position at time (milliseconds)
pos = path.position_at(500)  # Returns interpolated position
```

### Interpolation Modes

- `LINEAR` - Simple linear interpolation
- `SMOOTHSTEP` - Smooth start and end
- `EASE_IN` - Slow start
- `EASE_OUT` - Slow end

### Attaching to Sources

```python
graph = create_spatial_scene()
source = graph.add_source("moving_voice")

path = MovementPath(keyframes=[
    MovementKeyframe(time_ms=0, position=Position3D(x=-1, y=0, z=1)),
    MovementKeyframe(time_ms=2000, position=Position3D(x=1, y=0, z=1)),
])

graph.add_movement("moving_voice", path)
```

## Safety Features

### Loudness Safety

The system enforces loudness invariants:

1. **No gain stacking from panning** - Constant power panning
2. **Loudness bounded after HRTF** - Output never exceeds threshold
3. **Limiter after spatial mix** - Final safety stage

### Distance Safety

```python
from voice_soundboard.v3 import validate_spatial_safety, SpatialSafetyLimits

limits = SpatialSafetyLimits(
    min_source_distance=0.1,    # Minimum distance (meters)
    max_source_distance=100.0,  # Maximum distance (meters)
    max_combined_gain=10.0,     # Maximum gain
)

sources = [source1, source2, source3]
violations = validate_spatial_safety(sources, limits)

for v in violations:
    print(f"Safety violation: {v}")
```

### Movement Validation

```python
path = MovementPath(
    max_speed=10.0,             # Max meters per second
    teleport_threshold=5.0,     # Distance requiring crossfade
    crossfade_duration_ms=50.0, # Fade time for teleports
)

errors = path.validate()
for err in errors:
    print(f"Movement error: {err}")
```

## HRTF Profiles

| Profile | Description | Use Case |
|---------|-------------|----------|
| `COMPACT` | Narrow stereo image | Headphones, intimate spaces |
| `DEFAULT` | Standard HRTF | General purpose |
| `WIDE` | Wide stereo image | Spacious environments |
| `INTIMATE` | Close, present sound | Voice chat, podcasts |
| `CUSTOM` | User-provided HRTF | Custom measurements |

## Performance Considerations

### CPU Bounds

- HRTF processing scales linearly with source count
- Filter length affects quality vs. performance
- Position updates are very fast (<10µs)

### Recommended Limits

```python
HRTFParameters(
    max_sources=16,      # Real-time safe
    filter_length=128,   # Good quality/performance balance
    update_rate_hz=60,   # Smooth movement
)
```

### Performance Guidelines

1. **Buffer sizes**: 256-1024 samples for real-time
2. **Source count**: 8-16 for real-time, up to 32 with careful budgeting
3. **Movement paths**: Pre-calculate where possible
4. **Distance models**: `inverse` is fastest, `exponential` is smoothest

## Registrar Independence

Per Section 10, spatial audio is **completely independent** of the Registrar control plane:

- No registrar state for spatial data
- No spatial invariants in registrar
- No agent-visible spatial authority
- All spatial behavior is AudioGraph-local

Position changes do not require attestation or mediation.

## API Reference

### Main Exports

```python
from voice_soundboard.v3 import (
    # Coordinates
    Position3D,
    Orientation3D,
    
    # Nodes
    SpatialNode,
    ListenerNode,
    SpatialDownmixNode,
    
    # HRTF
    HRTFProfile,
    HRTFParameters,
    HRTFEngine,
    
    # Movement
    InterpolationMode,
    MovementKeyframe,
    MovementPath,
    
    # Graph
    SpatialGraph,
    SpatialGraphValidation,
    create_spatial_scene,
    
    # Safety
    SpatialSafetyLimits,
    validate_spatial_safety,
)
```

## Troubleshooting

### Common Issues

**"No listener node" error**
- Ensure `set_listener()` is called or use `create_spatial_scene()`

**"No downmix node" error**  
- Explicit downmix is required; call `set_downmix()` or use `create_spatial_scene()`

**"Source too close" warning**
- Z coordinate must be > 0.1m for safety

**"Speed exceeds maximum" error**
- Movement path has teleportation; increase crossfade duration or slow down

### Debug Tips

```python
# Validate graph before processing
result = graph.validate()
if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
```
