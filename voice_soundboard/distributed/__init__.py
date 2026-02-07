"""
Voice Soundboard v2.4 - Distributed Module

Horizontal scaling infrastructure for production deployments.

Components:
    SynthesisCluster - Multi-node distributed synthesis
    ModelShard       - Model sharding across GPUs
    SynthesisQueue   - Async request queue with Redis backend

Usage:
    from voice_soundboard.distributed import SynthesisCluster

    cluster = SynthesisCluster(
        nodes=["gpu-node-1:8080", "gpu-node-2:8080"],
        load_balancing="round_robin",
    )

    results = cluster.batch_synthesize(texts)
"""

from voice_soundboard.distributed.cluster import (
    SynthesisCluster,
    ClusterConfig,
    ClusterNode,
    LoadBalancingStrategy,
)

from voice_soundboard.distributed.shard import (
    ModelShard,
    ShardConfig,
    ShardingStrategy,
)

from voice_soundboard.distributed.queue import (
    SynthesisQueue,
    QueueConfig,
    QueueStatus,
    QueueJob,
)

__all__ = [
    # Cluster
    "SynthesisCluster",
    "ClusterConfig",
    "ClusterNode",
    "LoadBalancingStrategy",
    # Sharding
    "ModelShard",
    "ShardConfig",
    "ShardingStrategy",
    # Queue
    "SynthesisQueue",
    "QueueConfig",
    "QueueStatus",
    "QueueJob",
]
