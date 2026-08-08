use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;
use tokio::sync::{mpsc, oneshot, RwLock};
use tracing::debug;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct AgenticTaskId(pub String);

impl AgenticTaskId {
    pub fn new() -> Self {
        Self(format!("task-{}", Uuid::new_v4()))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum TaskStatus {
    Queued,
    Running,
    Completed,
    Failed(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgenticTask {
    pub id: AgenticTaskId,
    pub owner: String,
    pub kind: String,
    pub input: serde_json::Value,
    pub output: Option<serde_json::Value>,
    pub status: TaskStatus,
    pub created_at: u64,
    pub updated_at: u64,
}

impl AgenticTask {
    pub fn new(owner: impl Into<String>, kind: impl Into<String>, input: serde_json::Value) -> Self {
        let now = now_ms();
        Self {
            id: AgenticTaskId::new(),
            owner: owner.into(),
            kind: kind.into(),
            input,
            output: None,
            status: TaskStatus::Queued,
            created_at: now,
            updated_at: now,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskOutcome {
    pub task_id: AgenticTaskId,
    pub status: TaskStatus,
    pub output: Option<serde_json::Value>,
}

#[derive(Debug, Error)]
pub enum AgenticError {
    #[error("queue error: {0}")]
    Queue(String),
}

#[derive(Debug, Default)]
pub struct TaskQueue {
    pending: RwLock<Vec<AgenticTask>>,
    in_flight: RwLock<HashMap<AgenticTaskId, AgenticTask>>,
}

impl TaskQueue {
    pub async fn enqueue(&self, task: AgenticTask) -> Result<oneshot::Receiver<TaskOutcome>, AgenticError> {
        let mut pending = self.pending.write().await;
        pending.push(task.clone());
        let (tx, rx) = oneshot::channel();
        debug!(task_id=%task.id.0, "task enqueued");
        let _ = tx.send(TaskOutcome {
            task_id: task.id.clone(),
            status: task.status.clone(),
            output: None,
        });
        Ok(rx)
    }

    pub async fn drain_pending(&self) -> Vec<AgenticTask> {
        let mut pending = self.pending.write().await;
        std::mem::take(&mut *pending)
    }
}

#[derive(Debug, Default)]
pub struct TaskRegistry {
    inner: std::sync::RwLock<HashMap<AgenticTaskId, AgenticTask>>,
}

impl TaskRegistry {
    pub fn insert(&self, task: AgenticTask) {
        self.inner.write().unwrap().insert(task.id.clone(), task);
    }

    pub fn get(&self, id: &AgenticTaskId) -> Option<AgenticTask> {
        self.inner.read().unwrap().get(id).cloned()
    }
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}
