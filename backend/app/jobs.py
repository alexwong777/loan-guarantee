"""In-memory job tracking so the frontend can poll for live per-page progress
instead of blocking on one long request with no feedback until it finishes.

This is intentionally a single-process, in-memory store - fine for a local
demo app with one backend instance. It would need a shared store (Redis, a
DB row) behind more than one backend worker/replica.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

JOB_TTL_SECONDS = 3600


@dataclass
class TrackProgress:
    """Live progress for one OCR pass (e.g. the client letter, or the KYC
    field-extraction pass) - a job can have more than one running concurrently."""

    label: str
    current: int = 0
    total: int = 0
    done: bool = False


@dataclass
class Job:
    id: str
    kind: str  # "compare" | "kyc"
    started_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.time)
    status: str = "running"  # running | done | error | cancelled
    tracks: dict = field(default_factory=dict)  # name -> TrackProgress
    result: Optional[dict] = None
    error: Optional[str] = None
    cancel_requested: bool = False


_JOBS: dict[str, Job] = {}


def new_job(kind: str) -> Job:
    _prune()
    job = Job(id=uuid.uuid4().hex, kind=kind)
    _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _JOBS.get(job_id)


def touch(job: Job) -> None:
    job.updated_at = time.time()


def _prune() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    stale = [jid for jid, j in _JOBS.items() if j.status != "running" and j.updated_at < cutoff]
    for jid in stale:
        del _JOBS[jid]
