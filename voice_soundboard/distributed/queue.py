"""
Synthesis Queue - Async request queue with Redis backend.

Features:
    - Priority queues
    - Webhook callbacks
    - Job status tracking
    - Rate limiting integration
"""

from __future__ import annotations

import json
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum
from datetime import datetime, timezone


class JobState(Enum):
    """State of a queue job."""
    
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueConfig:
    """Configuration for synthesis queue."""
    
    # Redis connection
    backend: str = "redis://localhost:6379"
    key_prefix: str = "voice_soundboard:queue"
    
    # Queue settings
    max_concurrent: int = 10
    priority_levels: int = 3
    default_priority: int = 2
    
    # Job settings
    job_timeout_seconds: int = 300
    job_ttl_seconds: int = 86400  # 1 day
    max_retries: int = 3
    
    # Worker settings
    worker_poll_interval: float = 0.1
    batch_size: int = 1
    
    # Callbacks
    enable_webhooks: bool = True
    webhook_timeout_seconds: float = 10.0


@dataclass
class QueueJob:
    """A job in the synthesis queue."""
    
    job_id: str
    text: str
    voice: str = "af_bella"
    priority: int = 2
    
    # State
    state: JobState = JobState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Options
    callback_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Result
    result_path: str | None = None
    error: str | None = None
    retries: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "text": self.text,
            "voice": self.voice,
            "priority": self.priority,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "callback_url": self.callback_url,
            "metadata": self.metadata,
            "result_path": self.result_path,
            "error": self.error,
            "retries": self.retries,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueJob":
        """Create job from dictionary."""
        return cls(
            job_id=data["job_id"],
            text=data["text"],
            voice=data.get("voice", "af_bella"),
            priority=data.get("priority", 2),
            state=JobState(data.get("state", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            callback_url=data.get("callback_url"),
            metadata=data.get("metadata", {}),
            result_path=data.get("result_path"),
            error=data.get("error"),
            retries=data.get("retries", 0),
        )


@dataclass
class QueueStatus:
    """Status of a queued job."""
    
    job_id: str
    state: JobState
    position: int | None = None
    eta_seconds: float | None = None
    progress: float | None = None
    
    # Result (if completed)
    result_path: str | None = None
    error: str | None = None


class InMemoryBackend:
    """In-memory queue backend for testing/development."""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self._queues: dict[int, list[QueueJob]] = {
            p: [] for p in range(config.priority_levels)
        }
        self._jobs: dict[str, QueueJob] = {}
        self._lock = threading.Lock()
    
    def enqueue(self, job: QueueJob) -> None:
        """Add job to queue."""
        with self._lock:
            self._jobs[job.job_id] = job
            self._queues[job.priority].append(job)
            job.state = JobState.QUEUED
    
    def dequeue(self) -> QueueJob | None:
        """Get next job from queue (highest priority first)."""
        with self._lock:
            for priority in range(self.config.priority_levels):
                if self._queues[priority]:
                    job = self._queues[priority].pop(0)
                    job.state = JobState.PROCESSING
                    job.started_at = datetime.now(timezone.utc)
                    return job
        return None
    
    def get_job(self, job_id: str) -> QueueJob | None:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def update_job(self, job: QueueJob) -> None:
        """Update job state."""
        with self._lock:
            self._jobs[job.job_id] = job
    
    def get_position(self, job_id: str) -> int | None:
        """Get job position in queue."""
        job = self._jobs.get(job_id)
        if not job or job.state != JobState.QUEUED:
            return None
        
        position = 0
        for priority in range(job.priority + 1):
            position += len(self._queues[priority])
        
        try:
            position += self._queues[job.priority].index(job)
        except ValueError:
            return None
        
        return position
    
    def get_queue_length(self) -> int:
        """Get total queue length."""
        return sum(len(q) for q in self._queues.values())


class RedisBackend:
    """Redis-based queue backend for production."""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self._redis = None
    
    def _get_redis(self):
        """Lazy-load Redis client."""
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self.config.backend)
        return self._redis
    
    def enqueue(self, job: QueueJob) -> None:
        """Add job to Redis queue."""
        r = self._get_redis()
        
        # Store job data
        job_key = f"{self.config.key_prefix}:job:{job.job_id}"
        r.set(job_key, json.dumps(job.to_dict()), ex=self.config.job_ttl_seconds)
        
        # Add to priority queue
        queue_key = f"{self.config.key_prefix}:queue:{job.priority}"
        r.rpush(queue_key, job.job_id)
        
        job.state = JobState.QUEUED
        r.set(job_key, json.dumps(job.to_dict()), ex=self.config.job_ttl_seconds)
    
    def dequeue(self) -> QueueJob | None:
        """Get next job from Redis queue."""
        r = self._get_redis()
        
        # Check queues from highest to lowest priority
        for priority in range(self.config.priority_levels):
            queue_key = f"{self.config.key_prefix}:queue:{priority}"
            job_id = r.lpop(queue_key)
            
            if job_id:
                job_id = job_id.decode() if isinstance(job_id, bytes) else job_id
                job = self.get_job(job_id)
                
                if job:
                    job.state = JobState.PROCESSING
                    job.started_at = datetime.now(timezone.utc)
                    self.update_job(job)
                    return job
        
        return None
    
    def get_job(self, job_id: str) -> QueueJob | None:
        """Get job by ID from Redis."""
        r = self._get_redis()
        job_key = f"{self.config.key_prefix}:job:{job_id}"
        
        data = r.get(job_key)
        if data:
            return QueueJob.from_dict(json.loads(data))
        return None
    
    def update_job(self, job: QueueJob) -> None:
        """Update job in Redis."""
        r = self._get_redis()
        job_key = f"{self.config.key_prefix}:job:{job.job_id}"
        r.set(job_key, json.dumps(job.to_dict()), ex=self.config.job_ttl_seconds)
    
    def get_position(self, job_id: str) -> int | None:
        """Get job position in queue."""
        job = self.get_job(job_id)
        if not job or job.state != JobState.QUEUED:
            return None
        
        r = self._get_redis()
        position = 0
        
        for priority in range(job.priority + 1):
            queue_key = f"{self.config.key_prefix}:queue:{priority}"
            queue_len = r.llen(queue_key)
            
            if priority < job.priority:
                position += queue_len
            else:
                # Find position in this queue
                items = r.lrange(queue_key, 0, -1)
                for i, item in enumerate(items):
                    item_id = item.decode() if isinstance(item, bytes) else item
                    if item_id == job_id:
                        return position + i
        
        return None
    
    def get_queue_length(self) -> int:
        """Get total queue length."""
        r = self._get_redis()
        total = 0
        
        for priority in range(self.config.priority_levels):
            queue_key = f"{self.config.key_prefix}:queue:{priority}"
            total += r.llen(queue_key)
        
        return total


class SynthesisQueue:
    """
    Async request queue for synthesis jobs.
    
    Example:
        queue = SynthesisQueue(
            backend="redis://localhost:6379",
            max_concurrent=10,
            priority_levels=3,
        )
        
        # Submit request
        job_id = queue.submit(
            text="Hello world!",
            priority=1,  # High priority
            callback_url="https://my-app/webhook",
        )
        
        # Check status
        status = queue.status(job_id)
        # QueueStatus(position=0, state="processing", eta_seconds=2)
    """
    
    def __init__(
        self,
        backend: str = "redis://localhost:6379",
        max_concurrent: int = 10,
        priority_levels: int = 3,
        config: QueueConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = QueueConfig(
                backend=backend,
                max_concurrent=max_concurrent,
                priority_levels=priority_levels,
            )
        
        # Initialize backend
        if backend.startswith("redis://"):
            self._backend = RedisBackend(self.config)
        else:
            self._backend = InMemoryBackend(self.config)
        
        # Worker state
        self._workers: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._active_jobs = 0
        self._lock = threading.Lock()
        self._engine = None
        
        # Callbacks
        self._completion_callbacks: list[Callable[[QueueJob], None]] = []
    
    def submit(
        self,
        text: str,
        voice: str = "af_bella",
        priority: int | None = None,
        callback_url: str | None = None,
        **metadata: Any,
    ) -> str:
        """
        Submit a synthesis job to the queue.
        
        Args:
            text: Text to synthesize
            voice: Voice to use
            priority: Job priority (0=highest)
            callback_url: URL for completion webhook
            **metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = QueueJob(
            job_id=job_id,
            text=text,
            voice=voice,
            priority=priority if priority is not None else self.config.default_priority,
            callback_url=callback_url,
            metadata=metadata,
        )
        
        self._backend.enqueue(job)
        
        return job_id
    
    def status(self, job_id: str) -> QueueStatus | None:
        """
        Get status of a queued job.
        
        Args:
            job_id: Job ID
            
        Returns:
            QueueStatus or None if not found
        """
        job = self._backend.get_job(job_id)
        
        if not job:
            return None
        
        position = None
        eta = None
        
        if job.state == JobState.QUEUED:
            position = self._backend.get_position(job_id)
            if position is not None:
                # Estimate based on average processing time
                eta = position * 2.0  # Placeholder - would track actual times
        
        return QueueStatus(
            job_id=job_id,
            state=job.state,
            position=position,
            eta_seconds=eta,
            result_path=job.result_path,
            error=job.error,
        )
    
    def cancel(self, job_id: str) -> bool:
        """
        Cancel a queued job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if cancelled, False if not found or already processing
        """
        job = self._backend.get_job(job_id)
        
        if not job:
            return False
        
        if job.state in (JobState.PENDING, JobState.QUEUED):
            job.state = JobState.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            self._backend.update_job(job)
            return True
        
        return False
    
    def get_queue_info(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_length": self._backend.get_queue_length(),
            "active_jobs": self._active_jobs,
            "max_concurrent": self.config.max_concurrent,
        }
    
    def start_workers(self, num_workers: int | None = None) -> None:
        """
        Start worker threads to process jobs.
        
        Args:
            num_workers: Number of workers (default: max_concurrent)
        """
        num_workers = num_workers or self.config.max_concurrent
        self._stop_event.clear()
        
        for _ in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)
    
    def stop_workers(self) -> None:
        """Stop all worker threads."""
        self._stop_event.set()
        
        for worker in self._workers:
            worker.join(timeout=5.0)
        
        self._workers.clear()
    
    def _worker_loop(self) -> None:
        """Worker loop to process jobs."""
        while not self._stop_event.is_set():
            # Check if we can process more jobs
            with self._lock:
                if self._active_jobs >= self.config.max_concurrent:
                    time.sleep(self.config.worker_poll_interval)
                    continue
                
                self._active_jobs += 1
            
            try:
                job = self._backend.dequeue()
                
                if not job:
                    with self._lock:
                        self._active_jobs -= 1
                    time.sleep(self.config.worker_poll_interval)
                    continue
                
                # Process job
                self._process_job(job)
                
            finally:
                with self._lock:
                    self._active_jobs -= 1
    
    def _process_job(self, job: QueueJob) -> None:
        """Process a single job."""
        try:
            # Initialize engine if needed
            if self._engine is None:
                from voice_soundboard import VoiceEngine
                self._engine = VoiceEngine()
            
            # Synthesize
            result = self._engine.speak(job.text, voice=job.voice)
            
            job.state = JobState.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result_path = str(result.audio_path)
            
        except Exception as e:
            job.retries += 1
            
            if job.retries < self.config.max_retries:
                # Re-queue for retry
                job.state = JobState.QUEUED
                job.started_at = None
                self._backend.enqueue(job)
            else:
                job.state = JobState.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error = str(e)
        
        self._backend.update_job(job)
        
        # Send webhook if configured
        if job.callback_url and self.config.enable_webhooks:
            self._send_webhook(job)
        
        # Call completion callbacks
        for callback in self._completion_callbacks:
            try:
                callback(job)
            except Exception:
                pass
    
    def _send_webhook(self, job: QueueJob) -> None:
        """Send completion webhook."""
        import urllib.request
        
        try:
            data = json.dumps(job.to_dict()).encode()
            
            req = urllib.request.Request(
                job.callback_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            urllib.request.urlopen(
                req,
                timeout=self.config.webhook_timeout_seconds,
            )
        except Exception:
            pass
    
    def add_completion_callback(self, callback: Callable[[QueueJob], None]) -> None:
        """Add a callback for job completion."""
        self._completion_callbacks.append(callback)
