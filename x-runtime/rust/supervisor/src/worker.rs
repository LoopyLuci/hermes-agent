use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::sync::Arc;
use std::time::{Duration, Instant};

use hermes_runtime_protocol::v1::{
    Handshake, Ready, ReloadCompleted, ReloadRequest, Shutdown, TaskResult, TaskSubmit,
};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::sync::Mutex;
use uuid::Uuid;
use crate::observability::{SupervisorMetrics, SupervisorObservability};
use crate::protocol_adapter::{FrameKind, VersionedFrame, write_versioned_frame};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MessageEnvelope {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub kind: String,
    pub worker_id: Option<String>,
    pub payload: serde_json::Value,
    pub reload_id: Option<i64>,
    pub path: Option<String>,
    pub checksum: Option<String>,
}

impl MessageEnvelope {
    pub fn handshake(handshake: &Handshake) -> Self {
        Self {
            protocol_version: handshake.protocol_version.clone(),
            message_id: handshake.message_id.clone(),
            timestamp: handshake.timestamp,
            kind: handshake.kind.clone(),
            worker_id: Some(handshake.worker_id.clone()),
            payload: serde_json::to_value(handshake).expect("handshake serialization"),
            ..Default::default()
        }
    }

    pub fn ready(ready: &Ready) -> Self {
        Self {
            protocol_version: ready.protocol_version.clone(),
            message_id: ready.message_id.clone(),
            timestamp: ready.timestamp,
            kind: ready.kind.clone(),
            worker_id: Some(ready.worker_id.clone()),
            payload: serde_json::to_value(ready).expect("ready serialization"),
            ..Default::default()
        }
    }

    pub fn reload_completed(completed: &ReloadCompleted) -> Self {
        Self {
            protocol_version: completed.protocol_version.clone(),
            message_id: completed.message_id.clone(),
            timestamp: completed.timestamp,
            kind: completed.kind.clone(),
            payload: serde_json::to_value(completed).expect("reload completed serialization"),
            reload_id: Some(completed.reload_id),
            checksum: Some(completed.checksum.clone()),
            ..Default::default()
        }
    }

    pub fn reload_request(request: &ReloadRequest) -> Self {
        Self {
            protocol_version: request.protocol_version.clone(),
            message_id: request.message_id.clone(),
            timestamp: request.timestamp,
            kind: request.kind.clone(),
            payload: serde_json::to_value(request).expect("reload request serialization"),
            reload_id: Some(request.reload_id),
            path: Some(request.path.clone()),
            checksum: Some(request.checksum.clone()),
            ..Default::default()
        }
    }

    pub fn shutdown(shutdown: &Shutdown) -> Self {
        Self {
            protocol_version: shutdown.protocol_version.clone(),
            message_id: shutdown.message_id.clone(),
            timestamp: shutdown.timestamp,
            kind: shutdown.kind.clone(),
            payload: serde_json::to_value(shutdown).expect("shutdown serialization"),
            ..Default::default()
        }
    }

    pub fn task_submit(task: &TaskSubmit) -> Self {
        Self {
            protocol_version: task.protocol_version.clone(),
            message_id: task.message_id.clone(),
            timestamp: task.timestamp,
            kind: task.kind.clone(),
            payload: serde_json::to_value(task).expect("task submit serialization"),
            ..Default::default()
        }
    }

    pub fn task_result(result: &TaskResult) -> Self {
        Self {
            protocol_version: result.protocol_version.clone(),
            message_id: result.message_id.clone(),
            timestamp: result.timestamp,
            kind: result.kind.clone(),
            payload: serde_json::to_value(result).expect("task result serialization"),
            ..Default::default()
        }
    }

    pub fn into_handshake(self) -> Option<Handshake> {
        if self.kind != "handshake" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_ready(self) -> Option<Ready> {
        if self.kind != "ready" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_reload_completed(self) -> Option<ReloadCompleted> {
        if self.kind != "reload.completed" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_reload_request(self) -> Option<ReloadRequest> {
        if self.kind != "reload.request" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_shutdown(self) -> Option<Shutdown> {
        if self.kind != "shutdown" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_task_submit(self) -> Option<TaskSubmit> {
        if self.kind != "task.submit" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }

    pub fn into_task_result(self) -> Option<TaskResult> {
        if self.kind != "task.result" {
            return None;
        }
        serde_json::from_value(self.payload).ok()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Capability(pub String);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityGrant {
    pub worker_id: String,
    pub granted: Vec<Capability>,
    pub expires_at_ms: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)] // Retained as part of the public worker heartbeat schema
pub struct Heartbeat {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub worker_id: String,
    pub status: String,
    pub metrics: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum WorkerStatus {
    Healthy,
    Degraded { reason: String },
    Reloading,
    Stopped,
    Error { reason: String },
}

#[derive(Debug, Error)]
pub enum WorkerError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("send failed: {0}")]
    Send(String),
    #[error("worker exited: {0}")]
    Exited(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerSpec {
    pub id: String,
    pub command: String,
    pub args: Vec<String>,
    pub capabilities: Vec<Capability>,
    pub autostart: bool,
}

impl Default for WorkerSpec {
    fn default() -> Self {
        Self {
            id: format!("worker-{}", Uuid::new_v4()),
            command: String::new(),
            args: vec![],
            capabilities: vec![],
            autostart: true,
        }
    }
}

#[derive(Debug)]
pub struct WorkerProcess {
    pub id: String,
    pub spec: WorkerSpec,
    pub status: RwLock<WorkerStatus>,
    pub started_at: Instant,
    pub last_heartbeat: RwLock<Instant>,
    pub capabilities: RwLock<Vec<CapabilityGrant>>,
    pub pending_tasks: RwLock<HashMap<String, Instant>>,
    pub current_reload: RwLock<Option<ReloadState>>,
    inner: Mutex<Option<WorkerInner>>,
    metrics: Arc<RwLock<SupervisorMetrics>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadState {
    pub reload_id: i64,
    pub path: String,
    pub checksum: String,
    pub started_at: i64,
    pub status: ReloadStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReloadStatus {
    Pending,
    InProgress,
    Completed,
    Failed { reason: String },
    RolledBack,
}

#[derive(Debug)]
struct WorkerInner {
    _child: Arc<std::sync::Mutex<std::process::Child>>,
    stdin: std::process::ChildStdin,
    stdout: BufReader<std::process::ChildStdout>,
    line_buf: String,
}

#[derive(Debug, Error)]
pub enum WorkerErrorKind {
    #[error("not found: {0}")]
    NotFound(String),
    #[error("io: {0}")]
    Io(String),
    #[error("protocol: {0}")]
    Protocol(String),
}

impl WorkerProcess {
    pub fn new(
        id: String,
        child: Arc<std::sync::Mutex<std::process::Child>>,
        stdin: std::process::ChildStdin,
        stdout: std::process::ChildStdout,
        metrics: Arc<RwLock<SupervisorMetrics>>,
    ) -> Self {
        let inner = WorkerInner {
            _child: child,
            stdin,
            stdout: BufReader::new(stdout),
            line_buf: String::new(),
        };
        Self {
            id: id.clone(),
            spec: WorkerSpec { id: id.clone(), ..WorkerSpec::default() },
            status: RwLock::new(WorkerStatus::Healthy),
            started_at: Instant::now(),
            last_heartbeat: RwLock::new(Instant::now()),
            capabilities: RwLock::new(vec![]),
            pending_tasks: RwLock::new(HashMap::new()),
            current_reload: RwLock::new(None),
            inner: Mutex::new(Some(inner)),
            metrics,
        }
    }

    pub async fn send(&self, envelope: &MessageEnvelope) -> Result<(), WorkerErrorKind> {
        let mut guard = self.inner.lock().await;
        let inner = guard.as_mut().ok_or_else(|| WorkerErrorKind::Io("worker inner is gone".into()))?;
        let kind = match envelope.kind.as_str() {
            "task.submit" => FrameKind::TaskSubmit,
            "reload.request" => FrameKind::ReloadRequest,
            "capability.grant" => FrameKind::CapabilityGrant,
            _ => FrameKind::Message,
        };
        let payload = serde_json::to_vec(envelope).map_err(|e| WorkerErrorKind::Protocol(e.to_string()))?;
        write_versioned_frame(&mut inner.stdin, kind, 0, &payload).map_err(|e| WorkerErrorKind::Io(e.to_string()))?;
        inner.stdin.flush().map_err(|e| WorkerErrorKind::Io(e.to_string()))?;
        SupervisorObservability::record_transport_send(&self.metrics);
        Ok(())
    }

    pub async fn drain_messages(&self) -> Result<Vec<MessageEnvelope>, WorkerErrorKind> {
        let mut guard = self.inner.lock().await;
        let inner = guard.as_mut().ok_or_else(|| WorkerErrorKind::Io("worker inner is gone".into()))?;
        let mut messages = Vec::new();
        loop {
            inner.line_buf.clear();
            let n = inner.stdout.read_line(&mut inner.line_buf).map_err(|e| WorkerErrorKind::Io(e.to_string()))?;
            if n == 0 {
                break;
            }
            let line = inner.line_buf.trim();
            if line.is_empty() {
                continue;
            }
            if line.starts_with("{") {
                let envelope: MessageEnvelope = serde_json::from_str(line).map_err(|e| WorkerErrorKind::Protocol(e.to_string()))?;
                messages.push(envelope);
            } else {
                let envelope = match VersionedFrame::parse(line.as_bytes()) {
                    Ok(frame) => {
                        let envelope: MessageEnvelope = serde_json::from_slice(&frame.payload).map_err(|e| WorkerErrorKind::Protocol(e.to_string()))?;
                        envelope
                    }
                    Err(_) => continue,
                };
                messages.push(envelope);
            }
        }
        SupervisorObservability::record_transport_receive(&self.metrics);
        Ok(messages)
    }

    pub async fn shutdown(&self, grace: Duration) -> Result<(), WorkerErrorKind> {
        let envelope = MessageEnvelope {
            protocol_version: "1.0".into(),
            message_id: format!("shutdown-{}", Uuid::new_v4()),
            timestamp: now_ms(),
            kind: "shutdown".into(),
            worker_id: Some(self.id.clone()),
            payload: serde_json::json!({"grace_ms": grace.as_millis() as u64}),
            ..MessageEnvelope::default()
        };
        self.send(&envelope).await?;
        Ok(())
    }
}

#[derive(Debug, Default)]
pub struct WorkerRegistry {
    workers: RwLock<HashMap<String, Arc<WorkerProcess>>>,
}

impl WorkerRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub async fn register(&self, worker: Arc<WorkerProcess>) {
        self.workers.write().insert(worker.id.clone(), worker);
    }

    pub async fn get(&self, id: &str) -> Option<Arc<WorkerProcess>> {
        self.workers.read().get(id).cloned()
    }

    pub async fn list(&self) -> Vec<Arc<WorkerProcess>> {
        self.workers.read().values().cloned().collect()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SupervisorConfig {
    pub bind_addr: String,
    pub health_port: u16,
    pub task_timeout: Duration,
    pub reload_timeout: Duration,
    pub heartbeat_interval: Duration,
    pub shutdown_grace: Duration,
}

impl Default for SupervisorConfig {
    fn default() -> Self {
        Self {
            bind_addr: "127.0.0.1:0".into(),
            health_port: 0,
            task_timeout: Duration::from_secs(60),
            reload_timeout: Duration::from_secs(5),
            heartbeat_interval: Duration::from_secs(10),
            shutdown_grace: Duration::from_secs(5),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SupervisorStatusResponse {
    pub supervisor_id: String,
    pub uptime_secs: u64,
    pub worker_count: usize,
    pub workers: Vec<WorkerStatus>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SupervisorHandle {
    pub id: String,
    pub started_at: u64,
}

#[derive(Debug, Error)]
pub enum SupervisorError {
    #[error("worker error: {0}")]
    Worker(String),
    #[error("protocol error: {0}")]
    Protocol(String),
    #[error("state error: {0}")]
    State(String),
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}
