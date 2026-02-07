"""
Format negotiation utilities.

Provides format capability negotiation between producers and consumers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from enum import Enum

from voice_soundboard.formats.converter import AudioFormat


@dataclass
class FormatCapabilities:
    """
    Describes format capabilities of a component.
    
    Attributes:
        supported_formats: Set of supported audio formats
        sample_rates: Supported sample rates
        bit_depths: Supported bit depths
        channels: Supported channel counts
        max_duration: Maximum duration in seconds (None = unlimited)
        preferred_format: Preferred output format
        preferred_sample_rate: Preferred sample rate
    """
    supported_formats: Set[AudioFormat] = field(default_factory=lambda: {AudioFormat.WAV})
    sample_rates: Set[int] = field(default_factory=lambda: {22050, 44100, 48000})
    bit_depths: Set[int] = field(default_factory=lambda: {16, 32})
    channels: Set[int] = field(default_factory=lambda: {1, 2})
    max_duration: Optional[float] = None
    preferred_format: AudioFormat = AudioFormat.WAV
    preferred_sample_rate: int = 22050
    
    def supports(self, format: AudioFormat) -> bool:
        """Check if format is supported."""
        return format in self.supported_formats
    
    def supports_sample_rate(self, rate: int) -> bool:
        """Check if sample rate is supported."""
        return rate in self.sample_rates
    
    def common_formats(self, other: "FormatCapabilities") -> Set[AudioFormat]:
        """Get formats supported by both capabilities."""
        return self.supported_formats & other.supported_formats
    
    def common_sample_rates(self, other: "FormatCapabilities") -> Set[int]:
        """Get sample rates supported by both capabilities."""
        return self.sample_rates & other.sample_rates
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "formats": [f.value for f in self.supported_formats],
            "sample_rates": list(self.sample_rates),
            "bit_depths": list(self.bit_depths),
            "channels": list(self.channels),
            "max_duration": self.max_duration,
            "preferred_format": self.preferred_format.value,
            "preferred_sample_rate": self.preferred_sample_rate,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FormatCapabilities":
        """Create from dictionary."""
        return cls(
            supported_formats={AudioFormat(f) for f in data.get("formats", ["wav"])},
            sample_rates=set(data.get("sample_rates", [22050])),
            bit_depths=set(data.get("bit_depths", [16])),
            channels=set(data.get("channels", [1])),
            max_duration=data.get("max_duration"),
            preferred_format=AudioFormat(data.get("preferred_format", "wav")),
            preferred_sample_rate=data.get("preferred_sample_rate", 22050),
        )


@dataclass
class NegotiatedFormat:
    """
    Result of format negotiation.
    
    Attributes:
        format: Negotiated audio format
        sample_rate: Negotiated sample rate
        bit_depth: Negotiated bit depth
        channels: Negotiated channel count
        conversion_needed: Whether conversion is needed
        notes: Notes about the negotiation
    """
    format: AudioFormat
    sample_rate: int
    bit_depth: int
    channels: int
    conversion_needed: bool = False
    notes: List[str] = field(default_factory=list)


class NegotiationStrategy(Enum):
    """Strategy for format negotiation."""
    PREFER_PRODUCER = "producer"  # Prefer producer's format
    PREFER_CONSUMER = "consumer"  # Prefer consumer's format
    PREFER_QUALITY = "quality"    # Prefer highest quality
    PREFER_SPEED = "speed"        # Prefer fastest processing


class FormatNegotiator:
    """
    Negotiates format between producer and consumer.
    
    Finds common ground between what a producer can output
    and what a consumer can accept.
    """
    
    def __init__(self, strategy: NegotiationStrategy = NegotiationStrategy.PREFER_QUALITY):
        """
        Initialize negotiator.
        
        Args:
            strategy: Negotiation strategy to use
        """
        self.strategy = strategy
    
    def negotiate(
        self,
        producer: FormatCapabilities,
        consumer: FormatCapabilities,
    ) -> Optional[NegotiatedFormat]:
        """
        Negotiate format between producer and consumer.
        
        Args:
            producer: Producer's capabilities
            consumer: Consumer's capabilities
            
        Returns:
            NegotiatedFormat if successful, None if incompatible
        """
        notes = []
        
        # Find common formats
        common_formats = producer.common_formats(consumer)
        if not common_formats:
            # No common formats - check if conversion is possible
            if AudioFormat.WAV in producer.supported_formats or AudioFormat.PCM in producer.supported_formats:
                # Producer can output WAV/PCM, we can convert
                common_formats = {AudioFormat.WAV}
                notes.append("Format conversion required")
            else:
                return None
        
        # Select format based on strategy
        format = self._select_format(common_formats, producer, consumer)
        
        # Find common sample rates
        common_rates = producer.common_sample_rates(consumer)
        if not common_rates:
            # No common rates - will need resampling
            common_rates = producer.sample_rates
            notes.append("Sample rate conversion required")
        
        # Select sample rate
        sample_rate = self._select_sample_rate(common_rates, producer, consumer)
        
        # Find common bit depths
        common_depths = producer.bit_depths & consumer.bit_depths
        if not common_depths:
            common_depths = {16}  # Default to 16-bit
            notes.append("Bit depth conversion required")
        
        bit_depth = self._select_bit_depth(common_depths)
        
        # Find common channels
        common_channels = producer.channels & consumer.channels
        if not common_channels:
            common_channels = {1}  # Default to mono
            notes.append("Channel conversion required")
        
        channels = max(common_channels) if self.strategy == NegotiationStrategy.PREFER_QUALITY else min(common_channels)
        
        conversion_needed = len(notes) > 0
        
        return NegotiatedFormat(
            format=format,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            conversion_needed=conversion_needed,
            notes=notes,
        )
    
    def _select_format(
        self,
        common: Set[AudioFormat],
        producer: FormatCapabilities,
        consumer: FormatCapabilities,
    ) -> AudioFormat:
        """Select best format from common formats."""
        # Priority order based on strategy
        if self.strategy == NegotiationStrategy.PREFER_PRODUCER:
            if producer.preferred_format in common:
                return producer.preferred_format
        elif self.strategy == NegotiationStrategy.PREFER_CONSUMER:
            if consumer.preferred_format in common:
                return consumer.preferred_format
        elif self.strategy == NegotiationStrategy.PREFER_QUALITY:
            # Quality priority: FLAC > WAV > OGG > OPUS > MP3
            quality_order = [AudioFormat.FLAC, AudioFormat.WAV, AudioFormat.OGG, AudioFormat.OPUS, AudioFormat.MP3]
            for fmt in quality_order:
                if fmt in common:
                    return fmt
        else:  # PREFER_SPEED
            # Speed priority: PCM > WAV > MP3 > OGG > OPUS > FLAC
            speed_order = [AudioFormat.PCM, AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG, AudioFormat.OPUS, AudioFormat.FLAC]
            for fmt in speed_order:
                if fmt in common:
                    return fmt
        
        # Default to first available
        return list(common)[0]
    
    def _select_sample_rate(
        self,
        common: Set[int],
        producer: FormatCapabilities,
        consumer: FormatCapabilities,
    ) -> int:
        """Select best sample rate from common rates."""
        if self.strategy == NegotiationStrategy.PREFER_PRODUCER:
            if producer.preferred_sample_rate in common:
                return producer.preferred_sample_rate
        elif self.strategy == NegotiationStrategy.PREFER_CONSUMER:
            if consumer.preferred_sample_rate in common:
                return consumer.preferred_sample_rate
        elif self.strategy == NegotiationStrategy.PREFER_QUALITY:
            return max(common)  # Higher rate = better quality
        else:  # PREFER_SPEED
            return min(common)  # Lower rate = faster processing
        
        return list(common)[0]
    
    def _select_bit_depth(self, common: Set[int]) -> int:
        """Select bit depth."""
        if self.strategy in (NegotiationStrategy.PREFER_QUALITY, NegotiationStrategy.PREFER_PRODUCER):
            return max(common)
        else:
            return min(common)


def negotiate_format(
    producer: FormatCapabilities,
    consumer: FormatCapabilities,
    strategy: NegotiationStrategy = NegotiationStrategy.PREFER_QUALITY,
) -> Optional[NegotiatedFormat]:
    """
    Negotiate format between producer and consumer.
    
    Convenience function for quick negotiation.
    
    Args:
        producer: Producer's capabilities
        consumer: Consumer's capabilities
        strategy: Negotiation strategy
        
    Returns:
        NegotiatedFormat if successful, None if incompatible
        
    Example:
        producer_caps = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.MP3},
            sample_rates={22050, 44100},
        )
        
        consumer_caps = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.OPUS},
            sample_rates={48000},
        )
        
        result = negotiate_format(producer_caps, consumer_caps)
        # result.format = WAV, result.sample_rate = 44100
        # result.conversion_needed = True (sample rate conversion)
    """
    negotiator = FormatNegotiator(strategy)
    return negotiator.negotiate(producer, consumer)


# Common capability profiles
CAPABILITIES_MINIMAL = FormatCapabilities(
    supported_formats={AudioFormat.WAV},
    sample_rates={22050},
    bit_depths={16},
    channels={1},
)

CAPABILITIES_STANDARD = FormatCapabilities(
    supported_formats={AudioFormat.WAV, AudioFormat.MP3},
    sample_rates={22050, 44100, 48000},
    bit_depths={16},
    channels={1, 2},
)

CAPABILITIES_FULL = FormatCapabilities(
    supported_formats={AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG, AudioFormat.OPUS, AudioFormat.FLAC},
    sample_rates={8000, 16000, 22050, 44100, 48000, 96000},
    bit_depths={16, 24, 32},
    channels={1, 2},
)
