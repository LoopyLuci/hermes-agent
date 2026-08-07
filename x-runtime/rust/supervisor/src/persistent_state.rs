use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::PathBuf;
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

const MAX_PERSISTED_WORKERS: usize = 512;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SupervisorState {
    pub workers: HashMap<String, WorkerStateRecord>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkerStateRecord {
    pub spec: WorkerSpecRecord,
    pub status: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkerSpecRecord {
    pub id: String,
    pub command: String,
    pub args: Vec<String>,
    pub capabilities: Vec<String>,
}

#[derive(Debug, thiserror::Error)]
pub enum PersistentStateError {
    #[error("io error: {0}")]
    Io(#[from] io::Error),
    #[error("serde error: {0}")]
    Serde(#[from] serde_json::Error),
}

#[derive(Debug)]
pub struct PersistentSupervisorState {
    path: PathBuf,
    state: Arc<RwLock<SupervisorState>>,
}

impl PersistentSupervisorState {
    pub fn open(path: impl Into<PathBuf>) -> Result<Self, PersistentStateError> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let state = if path.exists() {
            let bytes = fs::read(&path)?;
            serde_json::from_slice(&bytes).unwrap_or_default()
        } else {
            SupervisorState::default()
        };
        Ok(Self {
            path,
            state: Arc::new(RwLock::new(state)),
        })
    }

    pub async fn snapshot(&self) -> SupervisorState {
        self.state.read().await.clone()
    }

    pub async fn register_worker(&self, record: WorkerStateRecord) -> Result<(), PersistentStateError> {
        self.state.write().await.workers.insert(record.spec.id.clone(), record);
        self.maybe_compact().await;
        self.persist().await
    }

    pub async fn update_worker_status(&self, worker_id: &str, status: &str) -> Result<(), PersistentStateError> {
        if let Some(entry) = self.state.write().await.workers.get_mut(worker_id) {
            entry.status = status.to_string();
        }
        self.maybe_compact().await;
        self.persist().await
    }

    pub async fn remove_worker(&self, worker_id: &str) -> Result<(), PersistentStateError> {
        self.state.write().await.workers.remove(worker_id);
        self.persist().await
    }

    pub async fn recover_worker_specs(&self) -> Vec<WorkerSpecRecord> {
        self.state
            .read()
            .await
            .workers
            .values()
            .map(|entry| entry.spec.clone())
            .collect()
    }

    pub async fn flush(&self) -> Result<(), PersistentStateError> {
        self.persist().await
    }

    async fn maybe_compact(&self) {
        let mut guard = self.state.write().await;
        if guard.workers.len() > MAX_PERSISTED_WORKERS {
            let mut keys: Vec<_> = guard.workers.keys().cloned().collect();
            keys.sort();
            let excess = keys.len() - MAX_PERSISTED_WORKERS;
            for key in keys.into_iter().take(excess) {
                guard.workers.remove(&key);
            }
            #[allow(clippy::let_underscore_future)]
            let _ = self.persist_locked(&guard).await;
        }
    }

    async fn persist_locked(&self, state: &SupervisorState) -> Result<(), PersistentStateError> {
        let payload = serde_json::to_vec_pretty(state)?;
        let tmp = self.path.with_extension("json.tmp");
        {
            let mut file = File::create(&tmp)?;
            file.write_all(&payload)?;
            file.sync_all()?;
        }
        fs::rename(&tmp, &self.path)?;
        Ok(())
    }

    async fn persist(&self) -> Result<(), PersistentStateError> {
        let guard = self.state.read().await;
        self.persist_locked(&guard).await?;
        Ok(())
    }
}
