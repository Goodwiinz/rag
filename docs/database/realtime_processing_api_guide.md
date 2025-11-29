# Real-Time Document Processing API Integration Guide

This guide demonstrates how to use the enhanced real-time document processing schema in your FastAPI backend and WebSocket implementation.

## Overview

The enhanced schema provides comprehensive real-time tracking for:
- Document processing pipeline stages
- WebSocket-based status updates
- Performance monitoring and analytics
- Error tracking and recovery
- Resource usage monitoring

## Core Components

### 1. Document Processing Models

```python
# backend/src/models/realtime_document.py
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone as dt_timezone
from typing import Optional, List, Dict, Any
import uuid

class DocumentProcessingStage(BaseModel):
    """Processing stage configuration and tracking"""

    __tablename__ = "document_processing_stages"

    stage_key = Column(String(100), nullable=False, unique=True, index=True)
    stage_name = Column(String(200), nullable=False)
    stage_order = Column(Integer, nullable=False)
    stage_type = Column(String(50), nullable=False)  # extraction, transformation, analysis, indexing
    description = Column(Text, nullable=True)
    default_config = Column(JSON, nullable=True)
    timeout_seconds = Column(Integer, default=300)

class ProcessingJobExecution(BaseModel):
    """Real-time processing job execution tracking"""

    __tablename__ = "processing_job_executions"

    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False)
    execution_id = Column(String(255), nullable=False, unique=True)
    execution_status = Column(String(50), nullable=False, default="pending")
    overall_progress = Column(Float, default=0.0)
    current_stage = Column(String(100), nullable=True)
    total_stages = Column(Integer, default=0)
    completed_stages = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True), nullable=True)
    estimated_remaining_seconds = Column(Integer, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="processing_executions")
    stage_executions = relationship("StageExecution", back_populates="job_execution")

class StageExecution(BaseModel):
    """Individual stage execution tracking"""

    __tablename__ = "stage_executions"

    job_execution_id = Column(GUID(), ForeignKey("processing_job_executions.id"), nullable=False)
    stage_key = Column(String(100), nullable=False)
    stage_status = Column(String(50), nullable=False, default="pending")
    progress_percentage = Column(Float, default=0.0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    worker_id = Column(String(255), nullable=True)

    # Performance metrics
    cpu_time_ms = Column(Integer, nullable=True)
    memory_peak_mb = Column(Integer, nullable=True)
    output_quality_score = Column(Float, nullable=True)
```

### 2. Real-Time Status Update Service

```python
# backend/src/services/realtime_status_service.py
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json
import asyncio
from datetime import datetime, timedelta

class RealtimeStatusService:
    """Service for managing real-time document processing status updates"""

    def __init__(self, db: Session):
        self.db = db

    async def create_processing_job(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> ProcessingJobExecution:
        """Create new processing job execution"""

        execution_id = f"job_{uuid.uuid4().hex[:12]}"

        job = ProcessingJobExecution(
            document_id=document_id,
            organization_id=organization_id,
            execution_id=execution_id,
            execution_status="queued",
            queued_at=datetime.utcnow()
        )

        # Update document with current execution
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.current_execution_id = execution_id
            document.processing_status = "queued"
            document.last_status_update = datetime.utcnow()

        self.db.add(job)
        self.db.commit()

        # Create initial status update
        await self._create_status_update(
            job_id=job.id,
            document_id=document_id,
            update_type="status_change",
            title="Document queued for processing",
            data={"execution_id": execution_id}
        )

        return job

    async def start_processing_stage(
        self,
        job_execution_id: uuid.UUID,
        stage_key: str,
        worker_id: Optional[str] = None
    ) -> StageExecution:
        """Start a new processing stage"""

        # Get stage configuration
        stage = self.db.query(DocumentProcessingStage).filter(
            DocumentProcessingStage.stage_key == stage_key
        ).first()

        if not stage:
            raise ValueError(f"Unknown processing stage: {stage_key}")

        # Create stage execution
        stage_execution = StageExecution(
            job_execution_id=job_execution_id,
            stage_key=stage_key,
            stage_name=stage.stage_name,
            stage_order=stage.stage_order,
            stage_status="running",
            started_at=datetime.utcnow(),
            worker_id=worker_id
        )

        # Update job execution
        job = self.db.query(ProcessingJobExecution).filter(
            ProcessingJobExecution.id == job_execution_id
        ).first()

        if job:
            job.current_stage = stage_key
            job.current_stage_started_at = datetime.utcnow()
            job.execution_status = "running"
            if job.started_at is None:
                job.started_at = datetime.utcnow()

        self.db.add(stage_execution)
        self.db.commit()

        # Create status update
        await self._create_status_update(
            job_id=job.id,
            stage_execution_id=stage_execution.id,
            update_type="progress_update",
            title=f"Starting {stage.stage_name}",
            data={
                "stage_key": stage_key,
                "stage_name": stage.stage_name,
                "worker_id": worker_id
            }
        )

        return stage_execution

    async def update_stage_progress(
        self,
        stage_execution_id: uuid.UUID,
        progress_percentage: float,
        current_step: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Update progress of current stage"""

        stage = self.db.query(StageExecution).filter(
            StageExecution.id == stage_execution_id
        ).first()

        if not stage:
            return

        stage.progress_percentage = max(0.0, min(100.0, progress_percentage))
        stage.last_progress_update = datetime.utcnow()

        if current_step:
            # This would require additional column for current_step_name
            pass

        # Update overall job progress
        await self._update_job_progress(stage.job_execution_id)

        self.db.commit()

        # Create progress update
        await self._create_status_update(
            job_id=stage.job_execution_id,
            stage_execution_id=stage_execution_id,
            update_type="progress_update",
            progress_percentage=stage.progress_percentage,
            title=f"Progress: {stage.progress_percentage:.1f}% - {stage.stage_name}",
            data=details or {}
        )

    async def complete_stage(
        self,
        stage_execution_id: uuid.UUID,
        result_data: Optional[Dict[str, Any]] = None,
        quality_score: Optional[float] = None
    ):
        """Mark stage as completed"""

        stage = self.db.query(StageExecution).filter(
            StageExecution.id == stage_execution_id
        ).first()

        if not stage:
            return

        stage.stage_status = "completed"
        stage.completed_at = datetime.utcnow()

        if stage.started_at:
            stage.duration_ms = int(
                (stage.completed_at - stage.started_at).total_seconds() * 1000
            )

        if result_data:
            stage.output_data = result_data

        if quality_score is not None:
            stage.output_quality_score = quality_score

        # Update job progress
        await self._update_job_progress(stage.job_execution_id)

        self.db.commit()

        # Create completion update
        await self._create_status_update(
            job_id=stage.job_execution_id,
            stage_execution_id=stage_execution_id,
            update_type="stage_complete",
            progress_percentage=stage.progress_percentage,
            title=f"Completed {stage.stage_name}",
            data={
                "stage_key": stage.stage_key,
                "duration_ms": stage.duration_ms,
                "quality_score": quality_score
            }
        )

    async def complete_processing_job(
        self,
        job_execution_id: uuid.UUID,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Complete processing job"""

        job = self.db.query(ProcessingJobExecution).filter(
            ProcessingJobExecution.id == job_execution_id
        ).first()

        if not job:
            return

        job.execution_status = "completed" if success else "failed"
        job.completed_at = datetime.utcnow()
        job.overall_progress = 100.0 if success else job.overall_progress

        if error_message:
            job.error_message = error_message

        # Update document status
        document = self.db.query(Document).filter(
            Document.id == job.document_id
        ).first()

        if document:
            document.processing_status = "completed" if success else "failed"
            document.processing_completed_at = datetime.utcnow()
            document.processing_progress = 100.0 if success else 0.0
            if error_message:
                document.processing_error = error_message

        self.db.commit()

        # Create final status update
        await self._create_status_update(
            job_id=job.id,
            update_type="completion",
            title="Document processing completed" if success else "Document processing failed",
            data={
                "success": success,
                "error_message": error_message,
                "total_duration_seconds": (
                    int((job.completed_at - job.started_at).total_seconds())
                    if job.started_at and job.completed_at else None
                )
            }
        )

    async def _update_job_progress(self, job_execution_id: uuid.UUID):
        """Update overall job progress based on stage completion"""

        job = self.db.query(ProcessingJobExecution).filter(
            ProcessingJobExecution.id == job_execution_id
        ).first()

        if not job:
            return

        # Count total and completed stages
        total_stages = self.db.query(StageExecution).filter(
            StageExecution.job_execution_id == job_execution_id
        ).count()

        completed_stages = self.db.query(StageExecution).filter(
            and_(
                StageExecution.job_execution_id == job_execution_id,
                StageExecution.stage_status == "completed"
            )
        ).count()

        failed_stages = self.db.query(StageExecution).filter(
            and_(
                StageExecution.job_execution_id == job_execution_id,
                StageExecution.stage_status == "failed"
            )
        ).count()

        job.total_stages = total_stages
        job.completed_stages = completed_stages
        job.failed_stages = failed_stages

        if total_stages > 0:
            job.overall_progress = (completed_stages * 100.0) / total_stages

        # Update document progress
        document = self.db.query(Document).filter(
            Document.id == job.document_id
        ).first()

        if document:
            document.processing_progress = job.overall_progress
            document.last_status_update = datetime.utcnow()

    async def _create_status_update(
        self,
        job_id: uuid.UUID,
        update_type: str,
        title: str,
        stage_execution_id: Optional[uuid.UUID] = None,
        progress_percentage: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """Create real-time status update for WebSocket broadcasting"""

        from .models.websocket_status import DocumentProcessingUpdate

        update = DocumentProcessingUpdate(
            update_id=f"update_{uuid.uuid4().hex[:12]}",
            job_execution_id=job_id,
            update_type=update_type,
            title=title,
            update_data=data or {},
            progress_percentage=progress_percentage
        )

        self.db.add(update)
        self.db.commit()

        # Trigger WebSocket broadcast (would be implemented in WebSocket manager)
        await self._broadcast_update(update)

    async def _broadcast_update(self, update: 'DocumentProcessingUpdate'):
        """Broadcast update to WebSocket connections"""
        # This would integrate with your WebSocket manager
        pass
```

### 3. WebSocket Integration

```python
# backend/src/websocket/processing_manager.py
from typing import Dict, List, Set
import asyncio
import json
from datetime import datetime

class ProcessingWebSocketManager:
    """WebSocket manager for real-time processing updates"""

    def __init__(self):
        # Active connections by user and organization
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.document_subscriptions: Dict[str, Set[str]] = {}  # document_id -> connection_ids

    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str, org_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Store connection metadata
        await self._store_connection(connection_id, user_id, org_id, websocket)

    async def disconnect(self, websocket: WebSocket, connection_id: str):
        """Handle WebSocket disconnection"""
        # Remove from active connections
        for user_id, connections in self.active_connections.items():
            if websocket in connections:
                connections.remove(websocket)
                if not connections:
                    del self.active_connections[user_id]
                break

        # Update connection status in database
        await self._update_connection_status(connection_id, "disconnected")

    async def subscribe_to_document(
        self,
        connection_id: str,
        document_id: str
    ):
        """Subscribe connection to document updates"""
        if document_id not in self.document_subscriptions:
            self.document_subscriptions[document_id] = set()
        self.document_subscriptions[document_id].add(connection_id)

        # Store subscription in database
        await self._create_subscription(connection_id, document_id, "document_processing")

    async def broadcast_document_update(
        self,
        document_id: str,
        update_data: Dict[str, Any]
    ):
        """Broadcast update to all subscribers of a document"""
        if document_id not in self.document_subscriptions:
            return

        message = {
            "type": "document_processing_update",
            "document_id": document_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": update_data
        }

        connection_ids = self.document_subscriptions[document_id].copy()

        for connection_id in connection_ids:
            try:
                websocket = await self._get_websocket_by_connection_id(connection_id)
                if websocket:
                    await websocket.send_text(json.dumps(message))
                    await self._record_delivery(connection_id, message["update_id"])
            except Exception as e:
                print(f"Error broadcasting to connection {connection_id}: {e}")

    async def get_processing_queue_status(self, org_id: str) -> Dict[str, Any]:
        """Get real-time processing queue status"""
        from .services.realtime_status_service import get_realtime_queue_status

        queue_status = get_realtime_queue_status(org_id)

        return {
            "type": "queue_status",
            "organization_id": org_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": queue_status
        }

    async def get_document_progress(
        self,
        document_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get detailed document processing progress"""
        # Query database for current progress
        # This would use the document_processing_dashboard view
        pass
```

### 4. FastAPI Integration

```python
# backend/src/api/realtime_processing.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Any, List
import uuid
import json

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime-processing"])

@router.get("/queue/status")
async def get_queue_status(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get real-time processing queue status"""
    if current_user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    status = await websocket_manager.get_processing_queue_status(organization_id)
    return status

@router.get("/documents/{document_id}/progress")
async def get_document_progress(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed processing progress for a document"""

    # Check user has access to document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    progress = await websocket_manager.get_document_progress(
        document_id, current_user.id
    )

    return progress

@router.get("/processing/metrics")
async def get_processing_metrics(
    organization_id: str = None,
    time_window_minutes: int = 5,
    current_user: User = Depends(get_current_user)
):
    """Get processing performance metrics"""
    org_id = organization_id or current_user.organization_id

    # Use the performance monitoring function
    metrics = get_realtime_performance_metrics(org_id, time_window_minutes)

    return {
        "organization_id": org_id,
        "time_window_minutes": time_window_minutes,
        "metrics": [dict(m) for m in metrics]
    }

@router.post("/documents/{document_id}/subscribe")
async def subscribe_to_document_updates(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Subscribe to real-time updates for a document"""

    # Check document access
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Create subscription record
    subscription_id = f"sub_{uuid.uuid4().hex[:12]}"

    return {
        "subscription_id": subscription_id,
        "document_id": document_id,
        "message": "Subscribed to document updates"
    }

@router.websocket("/ws/{connection_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_id: str,
    token: str = None
):
    """WebSocket endpoint for real-time updates"""

    # Authenticate user from token
    user = await authenticate_websocket_token(token)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    try:
        await websocket_manager.connect(
            websocket,
            connection_id,
            str(user.id),
            str(user.organization_id)
        )

        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "connection_id": connection_id,
            "user_id": str(user.id),
            "organization_id": str(user.organization_id),
            "timestamp": datetime.utcnow().isoformat()
        }))

        # Handle messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            await handle_websocket_message(websocket, connection_id, message, user)

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, connection_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket, connection_id)

async def handle_websocket_message(
    websocket: WebSocket,
    connection_id: str,
    message: Dict[str, Any],
    user: User
):
    """Handle incoming WebSocket messages"""

    message_type = message.get("type")

    if message_type == "subscribe_document":
        document_id = message.get("document_id")
        if document_id:
            await websocket_manager.subscribe_to_document(connection_id, document_id)
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "document_id": document_id
            }))

    elif message_type == "get_queue_status":
        status = await websocket_manager.get_processing_queue_status(str(user.organization_id))
        await websocket.send_text(json.dumps(status))

    elif message_type == "ping":
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        }))

    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))
```

## Usage Examples

### 1. Processing a Document with Real-Time Updates

```python
# Example: Process a PDF document with real-time status tracking
async def process_document_with_realtime_updates(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    organization_id: uuid.UUID
):
    """Process document with real-time status updates"""

    status_service = RealtimeStatusService(db)

    # Create processing job
    job = await status_service.create_processing_job(
        document_id=document_id,
        user_id=user_id,
        organization_id=organization_id
    )

    try:
        # Stage 1: Text Extraction
        stage = await status_service.start_processing_stage(
            job_execution_id=job.id,
            stage_key="text_extraction",
            worker_id="ocr_worker_001"
        )

        # Update progress during extraction
        for progress in [25, 50, 75, 100]:
            await status_service.update_stage_progress(
                stage_execution_id=stage.id,
                progress_percentage=progress,
                current_step=f"Extracting page {progress//25}"
            )
            await asyncio.sleep(1)  # Simulate processing time

        await status_service.complete_stage(
            stage_execution_id=stage.id,
            result_data={"pages_processed": 10, "text_length": 5000},
            quality_score=0.95
        )

        # Stage 2: Entity Extraction
        stage = await status_service.start_processing_stage(
            job_execution_id=job.id,
            stage_key="entity_extraction",
            worker_id="nlp_worker_001"
        )

        # Update progress during entity extraction
        for progress in [20, 40, 60, 80, 100]:
            await status_service.update_stage_progress(
                stage_execution_id=stage.id,
                progress_percentage=progress,
                current_step=f"Extracting entities ({progress}%)"
            )
            await asyncio.sleep(0.5)

        await status_service.complete_stage(
            stage_execution_id=stage.id,
            result_data={"entities": 25, "relationships": 15},
            quality_score=0.88
        )

        # Stage 3: Vector Embedding
        stage = await status_service.start_processing_stage(
            job_execution_id=job.id,
            stage_key="vector_embedding",
            worker_id="embedding_worker_001"
        )

        for progress in [33, 66, 100]:
            await status_service.update_stage_progress(
                stage_execution_id=stage.id,
                progress_percentage=progress,
                current_step=f"Generating embeddings ({progress}%)"
            )
            await asyncio.sleep(2)

        await status_service.complete_stage(
            stage_execution_id=stage.id,
            result_data={"embedding_id": "vec_12345", "dimensions": 768},
            quality_score=0.92
        )

        # Complete processing
        await status_service.complete_processing_job(
            job_execution_id=job.id,
            success=True
        )

    except Exception as e:
        await status_service.complete_processing_job(
            job_execution_id=job.id,
            success=False,
            error_message=str(e)
        )
```

### 2. Frontend WebSocket Integration

```javascript
// Frontend WebSocket client for real-time updates
class DocumentProcessingWebSocket {
    constructor() {
        this.ws = null;
        this.connectionId = null;
        this.subscriptions = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    async connect(token) {
        this.connectionId = `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const wsUrl = `ws://localhost:8000/api/v1/realtime/ws/${this.connectionId}?token=${token}`;

        this.ws = new WebSocket(wsUrl);

        return new Promise((resolve, reject) => {
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                resolve();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.handleReconnect();
            };

            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };
        });
    }

    handleMessage(message) {
        console.log('Received message:', message);

        switch (message.type) {
            case 'connection_established':
                this.onConnectionEstablished(message);
                break;

            case 'document_processing_update':
                this.onDocumentUpdate(message);
                break;

            case 'queue_status':
                this.onQueueStatusUpdate(message);
                break;

            case 'subscription_confirmed':
                this.onSubscriptionConfirmed(message);
                break;

            case 'pong':
                // Handle ping/pong for connection health
                break;

            default:
                console.warn('Unknown message type:', message.type);
        }
    }

    onConnectionEstablished(message) {
        console.log('Connection established:', message);
        this.connectionId = message.connection_id;

        // Subscribe to queue status
        this.sendMessage({
            type: 'get_queue_status'
        });
    }

    onDocumentUpdate(message) {
        // Update UI with document processing progress
        const documentId = message.document_id;
        const updateData = message.data;

        // Update progress bar
        if (updateData.progress_percentage !== undefined) {
            this.updateProgressBar(documentId, updateData.progress_percentage);
        }

        // Update status message
        if (updateData.title) {
            this.updateStatusMessage(documentId, updateData.title);
        }

        // Handle completion
        if (message.update_type === 'completion') {
            this.handleProcessingComplete(documentId, updateData);
        }
    }

    subscribeToDocument(documentId) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('WebSocket not connected');
        }

        this.subscriptions.set(documentId, true);

        this.sendMessage({
            type: 'subscribe_document',
            document_id: documentId
        });
    }

    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not ready, message not sent:', message);
        }
    }

    ping() {
        this.sendMessage({ type: 'ping' });
    }

    async handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(async () => {
                try {
                    await this.connect(this.token);
                    // Resubscribe to documents
                    this.subscriptions.forEach((_, documentId) => {
                        this.subscribeToDocument(documentId);
                    });
                } catch (error) {
                    console.error('Reconnection failed:', error);
                }
            }, Math.pow(2, this.reconnectAttempts) * 1000); // Exponential backoff
        }
    }

    updateProgressBar(documentId, progress) {
        const progressBar = document.querySelector(`[data-document-id="${documentId}"] .progress-bar`);
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }

    updateStatusMessage(documentId, message) {
        const statusElement = document.querySelector(`[data-document-id="${documentId}"] .status-message`);
        if (statusElement) {
            statusElement.textContent = message;
        }
    }

    handleProcessingComplete(documentId, data) {
        if (data.success) {
            this.updateStatusMessage(documentId, 'Processing completed successfully');
            this.markDocumentAsComplete(documentId);
        } else {
            this.updateStatusMessage(documentId, `Processing failed: ${data.error_message}`);
            this.markDocumentAsFailed(documentId, data.error_message);
        }
    }
}

// Usage example
const wsClient = new DocumentProcessingWebSocket();

async function initializeWebSocket(token) {
    try {
        await wsClient.connect(token);

        // Subscribe to updates for specific documents
        const documentIds = ['doc1', 'doc2', 'doc3'];
        documentIds.forEach(docId => {
            wsClient.subscribeToDocument(docId);
        });

        // Start ping interval for connection health
        setInterval(() => {
            wsClient.ping();
        }, 30000); // Ping every 30 seconds

    } catch (error) {
        console.error('Failed to initialize WebSocket:', error);
    }
}
```

## Performance Considerations

### 1. Database Optimization
- Use materialized views for dashboard queries
- Implement connection pooling for WebSocket database queries
- Partition high-volume tables by time
- Use appropriate indexing for real-time queries

### 2. WebSocket Optimization
- Implement message batching to reduce network overhead
- Use connection pooling for database operations
- Implement proper cleanup for stale connections
- Use compression for large message payloads

### 3. Scaling Considerations
- Use Redis pub/sub for cross-instance WebSocket communication
- Implement horizontal scaling with multiple WebSocket servers
- Use database read replicas for reporting queries
- Implement rate limiting for WebSocket connections

This comprehensive integration guide provides the foundation for implementing real-time document processing status updates in your Multimodal Enterprise RAG System.