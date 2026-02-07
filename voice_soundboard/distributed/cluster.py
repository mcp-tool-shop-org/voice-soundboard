"""
Synthesis Cluster - Multi-node distributed synthesis.

Features:
    - Multiple load balancing strategies
    - Automatic failover
    - Health checking
    - Request routing
"""

from __future__ import annotations

import time
import random
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


class LoadBalancingStrategy(Enum):
    """Load balancing strategies for cluster."""
    
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_LATENCY = "least_latency"
    WEIGHTED = "weighted"


class NodeStatus(Enum):
    """Health status of cluster nodes."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ClusterNode:
    """A node in the synthesis cluster."""
    
    address: str
    port: int = 8080
    weight: float = 1.0
    
    # Status
    status: NodeStatus = NodeStatus.UNKNOWN
    last_health_check: float = 0.0
    
    # Metrics
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    average_latency_ms: float = 0.0
    
    @property
    def url(self) -> str:
        """Get node URL."""
        return f"http://{self.address}:{self.port}"
    
    @classmethod
    def from_string(cls, node_str: str) -> "ClusterNode":
        """Create node from 'host:port' string."""
        if ":" in node_str:
            host, port = node_str.rsplit(":", 1)
            return cls(address=host, port=int(port))
        return cls(address=node_str)
    
    def update_latency(self, latency_ms: float) -> None:
        """Update average latency with new measurement."""
        if self.average_latency_ms == 0:
            self.average_latency_ms = latency_ms
        else:
            # Exponential moving average
            self.average_latency_ms = 0.9 * self.average_latency_ms + 0.1 * latency_ms


@dataclass
class ClusterConfig:
    """Configuration for synthesis cluster."""
    
    # Load balancing
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    
    # Health checking
    health_check_interval_seconds: int = 10
    health_check_timeout_seconds: float = 5.0
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    
    # Failover
    failover_enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 0.5
    
    # Connections
    max_connections_per_node: int = 100
    connection_timeout_seconds: float = 30.0
    
    # Batch processing
    batch_size: int = 10
    max_parallel_requests: int = 50


@dataclass
class SynthesisResult:
    """Result from cluster synthesis."""
    
    success: bool
    audio_path: str | None = None
    audio_data: bytes | None = None
    duration: float = 0.0
    
    # Metadata
    node_address: str | None = None
    latency_ms: float = 0.0
    retries: int = 0
    
    # Error
    error: str | None = None


class SynthesisCluster:
    """
    Multi-node distributed synthesis cluster.
    
    Example:
        cluster = SynthesisCluster(
            nodes=[
                "gpu-node-1:8080",
                "gpu-node-2:8080",
                "gpu-node-3:8080",
            ],
            load_balancing="round_robin",
        )
        
        # Distributed synthesis
        results = cluster.batch_synthesize(texts)
        
        # Single request with failover
        result = cluster.synthesize("Hello world!")
    """
    
    def __init__(
        self,
        nodes: list[str] | list[ClusterNode],
        load_balancing: str | LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        config: ClusterConfig | None = None,
    ):
        self.config = config or ClusterConfig()
        
        if isinstance(load_balancing, str):
            self.config.strategy = LoadBalancingStrategy(load_balancing)
        else:
            self.config.strategy = load_balancing
        
        # Initialize nodes
        self._nodes: list[ClusterNode] = []
        for node in nodes:
            if isinstance(node, str):
                self._nodes.append(ClusterNode.from_string(node))
            else:
                self._nodes.append(node)
        
        # State
        self._round_robin_index = 0
        self._lock = threading.Lock()
        self._health_check_thread: threading.Thread | None = None
        self._stop_health_check = threading.Event()
        
        # Start health checking
        self._start_health_checks()
    
    def _start_health_checks(self) -> None:
        """Start background health checking."""
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
        )
        self._health_check_thread.start()
    
    def _health_check_loop(self) -> None:
        """Background health check loop."""
        consecutive_failures: dict[str, int] = {n.address: 0 for n in self._nodes}
        consecutive_successes: dict[str, int] = {n.address: 0 for n in self._nodes}
        
        while not self._stop_health_check.wait(self.config.health_check_interval_seconds):
            for node in self._nodes:
                try:
                    healthy = self._check_node_health(node)
                    
                    if healthy:
                        consecutive_failures[node.address] = 0
                        consecutive_successes[node.address] += 1
                        
                        if consecutive_successes[node.address] >= self.config.healthy_threshold:
                            node.status = NodeStatus.HEALTHY
                    else:
                        consecutive_successes[node.address] = 0
                        consecutive_failures[node.address] += 1
                        
                        if consecutive_failures[node.address] >= self.config.unhealthy_threshold:
                            node.status = NodeStatus.UNHEALTHY
                        else:
                            node.status = NodeStatus.DEGRADED
                    
                    node.last_health_check = time.time()
                    
                except Exception:
                    consecutive_failures[node.address] += 1
                    if consecutive_failures[node.address] >= self.config.unhealthy_threshold:
                        node.status = NodeStatus.UNHEALTHY
    
    def _check_node_health(self, node: ClusterNode) -> bool:
        """Check if a node is healthy."""
        import urllib.request
        import urllib.error
        
        try:
            url = f"{node.url}/health"
            req = urllib.request.Request(url, method="GET")
            
            with urllib.request.urlopen(
                req,
                timeout=self.config.health_check_timeout_seconds,
            ) as response:
                return response.status == 200
                
        except (urllib.error.URLError, TimeoutError):
            return False
    
    def _select_node(self) -> ClusterNode | None:
        """Select a node based on load balancing strategy."""
        healthy_nodes = [n for n in self._nodes if n.status == NodeStatus.HEALTHY]
        
        if not healthy_nodes:
            # Fall back to all nodes if none healthy
            healthy_nodes = self._nodes
        
        if not healthy_nodes:
            return None
        
        with self._lock:
            if self.config.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                node = healthy_nodes[self._round_robin_index % len(healthy_nodes)]
                self._round_robin_index += 1
                return node
            
            elif self.config.strategy == LoadBalancingStrategy.RANDOM:
                return random.choice(healthy_nodes)
            
            elif self.config.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return min(healthy_nodes, key=lambda n: n.active_connections)
            
            elif self.config.strategy == LoadBalancingStrategy.LEAST_LATENCY:
                return min(healthy_nodes, key=lambda n: n.average_latency_ms or float('inf'))
            
            elif self.config.strategy == LoadBalancingStrategy.WEIGHTED:
                # Weighted random selection
                total_weight = sum(n.weight for n in healthy_nodes)
                r = random.uniform(0, total_weight)
                cumulative = 0
                for node in healthy_nodes:
                    cumulative += node.weight
                    if r <= cumulative:
                        return node
                return healthy_nodes[-1]
        
        return healthy_nodes[0]
    
    def synthesize(
        self,
        text: str,
        voice: str = "af_bella",
        **kwargs: Any,
    ) -> SynthesisResult:
        """
        Synthesize text using the cluster.
        
        Args:
            text: Text to synthesize
            voice: Voice to use
            **kwargs: Additional synthesis parameters
            
        Returns:
            SynthesisResult with audio or error
        """
        retries = 0
        last_error = None
        tried_nodes: set[str] = set()
        
        while retries <= self.config.max_retries:
            node = self._select_node()
            
            if not node:
                return SynthesisResult(
                    success=False,
                    error="No available nodes",
                )
            
            # Skip if already tried
            if node.address in tried_nodes and len(tried_nodes) < len(self._nodes):
                continue
            
            tried_nodes.add(node.address)
            
            try:
                node.active_connections += 1
                start_time = time.time()
                
                result = self._send_request(node, text, voice, **kwargs)
                
                latency_ms = (time.time() - start_time) * 1000
                node.update_latency(latency_ms)
                node.total_requests += 1
                
                result.node_address = node.address
                result.latency_ms = latency_ms
                result.retries = retries
                
                return result
                
            except Exception as e:
                last_error = str(e)
                node.total_errors += 1
                
                if self.config.failover_enabled:
                    retries += 1
                    time.sleep(self.config.retry_delay_seconds)
                else:
                    break
                    
            finally:
                node.active_connections -= 1
        
        return SynthesisResult(
            success=False,
            error=last_error or "Synthesis failed",
            retries=retries,
        )
    
    def _send_request(
        self,
        node: ClusterNode,
        text: str,
        voice: str,
        **kwargs: Any,
    ) -> SynthesisResult:
        """Send synthesis request to a node."""
        import urllib.request
        import json
        
        url = f"{node.url}/synthesize"
        
        data = json.dumps({
            "text": text,
            "voice": voice,
            **kwargs,
        }).encode()
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(
            req,
            timeout=self.config.connection_timeout_seconds,
        ) as response:
            result = json.loads(response.read())
            
            return SynthesisResult(
                success=result.get("success", True),
                audio_data=result.get("audio"),
                duration=result.get("duration", 0),
            )
    
    def batch_synthesize(
        self,
        texts: list[str],
        voice: str = "af_bella",
        **kwargs: Any,
    ) -> list[SynthesisResult]:
        """
        Synthesize multiple texts in parallel across the cluster.
        
        Args:
            texts: List of texts to synthesize
            voice: Voice to use
            **kwargs: Additional parameters
            
        Returns:
            List of SynthesisResults in same order as input
        """
        results: list[SynthesisResult | None] = [None] * len(texts)
        
        with ThreadPoolExecutor(max_workers=self.config.max_parallel_requests) as executor:
            futures = {}
            
            for i, text in enumerate(texts):
                future = executor.submit(self.synthesize, text, voice, **kwargs)
                futures[future] = i
            
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    results[index] = SynthesisResult(
                        success=False,
                        error=str(e),
                    )
        
        return [r or SynthesisResult(success=False, error="Unknown error") for r in results]
    
    def get_cluster_status(self) -> dict[str, Any]:
        """Get current cluster status."""
        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": sum(1 for n in self._nodes if n.status == NodeStatus.HEALTHY),
            "nodes": [
                {
                    "address": n.address,
                    "status": n.status.value,
                    "active_connections": n.active_connections,
                    "total_requests": n.total_requests,
                    "total_errors": n.total_errors,
                    "average_latency_ms": n.average_latency_ms,
                }
                for n in self._nodes
            ],
        }
    
    def add_node(self, node: str | ClusterNode) -> None:
        """Add a node to the cluster."""
        if isinstance(node, str):
            node = ClusterNode.from_string(node)
        
        with self._lock:
            self._nodes.append(node)
    
    def remove_node(self, address: str) -> bool:
        """Remove a node from the cluster."""
        with self._lock:
            for i, node in enumerate(self._nodes):
                if node.address == address:
                    del self._nodes[i]
                    return True
        return False
    
    def shutdown(self) -> None:
        """Shutdown the cluster and stop health checks."""
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5.0)
