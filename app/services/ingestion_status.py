"""
Ingestion Status Service - Track progress for long-running policy ingestion.

This addresses the production risk of ingestion latency:
- 100-page policies can take 30-60+ seconds to process
- Users need feedback on progress, not a spinning loading indicator

Features:
- In-memory status tracking (can be extended to Redis for multi-instance)
- Progress updates at each stage (OCR, chunking, classification, embedding)
- Estimated time remaining based on chunk count
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Callable, Any
from threading import Lock

logger = logging.getLogger(__name__)


class IngestionStage(str, Enum):
    """Stages of the ingestion pipeline."""
    PENDING = "pending"
    READING_PDF = "reading_pdf"
    EXTRACTING_TEXT = "extracting_text"  # OCR/text extraction
    CHUNKING = "chunking"
    CLASSIFYING = "classifying"  # LLM classification (the slow part)
    EMBEDDING = "embedding"
    STORING = "storing"  # Vector store insertion
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionProgress:
    """Progress information for a single ingestion job."""
    job_id: str
    policy_id: str
    stage: IngestionStage = IngestionStage.PENDING
    progress_percent: float = 0.0
    current_step: str = "Initializing..."
    total_chunks: int = 0
    processed_chunks: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    estimated_seconds_remaining: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "job_id": self.job_id,
            "policy_id": self.policy_id,
            "stage": self.stage.value,
            "progress_percent": round(self.progress_percent, 1),
            "current_step": self.current_step,
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "estimated_seconds_remaining": self.estimated_seconds_remaining,
        }


class IngestionStatusService:
    """
    Service for tracking ingestion job progress.
    
    Thread-safe in-memory implementation.
    For production with multiple API instances, extend to use Redis.
    """
    
    _instance: Optional["IngestionStatusService"] = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern for global status tracking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._jobs: Dict[str, IngestionProgress] = {}
        return cls._instance
    
    def create_job(self, job_id: str, policy_id: str) -> IngestionProgress:
        """Create a new ingestion job."""
        progress = IngestionProgress(job_id=job_id, policy_id=policy_id)
        self._jobs[job_id] = progress
        logger.info(f"[INGESTION] Created job {job_id} for policy {policy_id}")
        return progress
    
    def update_progress(
        self,
        job_id: str,
        stage: Optional[IngestionStage] = None,
        progress_percent: Optional[float] = None,
        current_step: Optional[str] = None,
        total_chunks: Optional[int] = None,
        processed_chunks: Optional[int] = None,
    ) -> Optional[IngestionProgress]:
        """Update job progress."""
        if job_id not in self._jobs:
            return None
        
        progress = self._jobs[job_id]
        progress.updated_at = datetime.utcnow()
        
        if stage:
            progress.stage = stage
        if progress_percent is not None:
            progress.progress_percent = min(progress_percent, 100.0)
        if current_step:
            progress.current_step = current_step
        if total_chunks is not None:
            progress.total_chunks = total_chunks
        if processed_chunks is not None:
            progress.processed_chunks = processed_chunks
            
        # Calculate estimated time remaining
        if progress.total_chunks > 0 and progress.processed_chunks > 0:
            elapsed = (progress.updated_at - progress.started_at).total_seconds()
            rate = progress.processed_chunks / elapsed if elapsed > 0 else 1
            remaining_chunks = progress.total_chunks - progress.processed_chunks
            progress.estimated_seconds_remaining = int(remaining_chunks / rate) if rate > 0 else None
        
        return progress
    
    def complete_job(self, job_id: str) -> Optional[IngestionProgress]:
        """Mark job as completed."""
        if job_id not in self._jobs:
            return None
        
        progress = self._jobs[job_id]
        progress.stage = IngestionStage.COMPLETED
        progress.progress_percent = 100.0
        progress.current_step = "Completed!"
        progress.completed_at = datetime.utcnow()
        progress.estimated_seconds_remaining = 0
        
        logger.info(f"[INGESTION] Completed job {job_id}")
        return progress
    
    def fail_job(self, job_id: str, error: str) -> Optional[IngestionProgress]:
        """Mark job as failed."""
        if job_id not in self._jobs:
            return None
        
        progress = self._jobs[job_id]
        progress.stage = IngestionStage.FAILED
        progress.current_step = "Failed"
        progress.error_message = error
        progress.completed_at = datetime.utcnow()
        
        logger.error(f"[INGESTION] Failed job {job_id}: {error}")
        return progress
    
    def get_progress(self, job_id: str) -> Optional[IngestionProgress]:
        """Get current progress for a job."""
        return self._jobs.get(job_id)
    
    def get_job_by_policy(self, policy_id: str) -> Optional[IngestionProgress]:
        """Get the most recent job for a policy."""
        matching = [j for j in self._jobs.values() if j.policy_id == policy_id]
        if matching:
            return max(matching, key=lambda j: j.started_at)
        return None
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove completed jobs older than max_age_hours."""
        cutoff = datetime.utcnow()
        to_remove = []
        
        for job_id, progress in self._jobs.items():
            if progress.completed_at:
                age_hours = (cutoff - progress.completed_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(job_id)
        
        for job_id in to_remove:
            del self._jobs[job_id]
        
        if to_remove:
            logger.info(f"[INGESTION] Cleaned up {len(to_remove)} old jobs")


def get_ingestion_status_service() -> IngestionStatusService:
    """Get the singleton ingestion status service."""
    return IngestionStatusService()


# =============================================================================
# Progress Callback for Vectorizer
# =============================================================================

class IngestionProgressCallback:
    """
    Callback class for reporting progress during vectorization.
    
    Pass this to PolicyVectorizer to get progress updates.
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.service = get_ingestion_status_service()
    
    def on_stage_change(self, stage: IngestionStage, message: str):
        """Called when entering a new stage."""
        # Calculate approximate progress based on stage
        stage_progress = {
            IngestionStage.READING_PDF: 5,
            IngestionStage.EXTRACTING_TEXT: 15,
            IngestionStage.CHUNKING: 25,
            IngestionStage.CLASSIFYING: 50,  # This is the slow stage
            IngestionStage.EMBEDDING: 80,
            IngestionStage.STORING: 95,
        }
        
        progress = stage_progress.get(stage, 0)
        self.service.update_progress(
            job_id=self.job_id,
            stage=stage,
            progress_percent=progress,
            current_step=message,
        )
    
    def on_chunk_progress(self, processed: int, total: int, message: str = ""):
        """Called during chunk processing (classification/embedding)."""
        # Classification is 25-80%, embedding is 80-95%
        current_progress = self.service.get_progress(self.job_id)
        if not current_progress:
            return
        
        if current_progress.stage == IngestionStage.CLASSIFYING:
            # 25% to 80% during classification
            percent = 25 + (55 * processed / total) if total > 0 else 25
        elif current_progress.stage == IngestionStage.EMBEDDING:
            # 80% to 95% during embedding
            percent = 80 + (15 * processed / total) if total > 0 else 80
        else:
            percent = current_progress.progress_percent
        
        step_message = message or f"Processing chunk {processed}/{total}"
        self.service.update_progress(
            job_id=self.job_id,
            progress_percent=percent,
            current_step=step_message,
            total_chunks=total,
            processed_chunks=processed,
        )
    
    def on_complete(self):
        """Called when ingestion is complete."""
        self.service.complete_job(self.job_id)
    
    def on_error(self, error: str):
        """Called on failure."""
        self.service.fail_job(self.job_id, error)

