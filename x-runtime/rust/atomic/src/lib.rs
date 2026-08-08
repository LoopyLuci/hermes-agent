use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use serde_json::Value;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize, PartialEq, Eq, Hash)]
pub struct ReloadId(pub u64);

impl ReloadId {
    pub fn next(seq: &AtomicU64) -> Self {
        Self(seq.fetch_add(1, Ordering::Relaxed))
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum ReloadStatus {
    Pending,
    Reloading,
    Active,
    Failed(String),
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ReloadEvent {
    pub id: ReloadId,
    pub worker_id: String,
    pub path: String,
    pub checksum: String,
    pub status: ReloadStatus,
    pub started_at: u64,
}

impl ReloadEvent {
    pub fn new(worker_id: impl Into<String>, path: impl Into<String>, checksum: impl Into<String>) -> Self {
        static SEQ: AtomicU64 = AtomicU64::new(1);
        Self {
            id: ReloadId::next(&SEQ),
            worker_id: worker_id.into(),
            path: path.into(),
            checksum: checksum.into(),
            status: ReloadStatus::Pending,
            started_at: now_ms(),
        }
    }

    pub fn with_status(mut self, status: ReloadStatus) -> Self {
        self.status = status;
        self
    }
}

#[derive(Debug, Error)]
pub enum AtomicError {
    #[error("invalid transition: {0}")]
    InvalidTransition(String),
    #[error("state missing")]
    MissingState,
    #[error("compare-and-swap failed")]
    CasFailed,
}

pub trait HotReloadable: Send + Sync + 'static {
    fn reload(&mut self, event: &ReloadEvent) -> Result<(), String>;
    fn kind(&self) -> &'static str;
}

#[derive(Debug, Default)]
pub struct ReloadRegistry {
    seq: AtomicU64,
}

impl ReloadRegistry {
    pub fn next_id(&self) -> ReloadId {
        ReloadId::next(&self.seq)
    }
}

#[derive(Debug, Default)]
pub struct AtomicState {
    inner: RwLock<HashMap<String, Value>>,
}

impl AtomicState {
    pub fn new() -> Self {
        Self::default()
    }

    pub async fn put(&self, key: impl Into<String>, value: Value) {
        self.inner.write().await.insert(key.into(), value);
    }

    pub async fn get(&self, key: &str) -> Option<Value> {
        self.inner.read().await.get(key).cloned()
    }

    pub async fn compare_swap(
        &self,
        key: impl Into<String>,
        expected: Option<Value>,
        new: Option<Value>,
    ) -> Result<(), AtomicError> {
        let key = key.into();
        let mut state = self.inner.write().await;
        let current = state.get(&key).cloned();
        if current == expected {
            if new.is_some() {
                state.insert(key.clone(), new.unwrap());
            } else {
                state.remove(&key);
            }
            Ok(())
        } else {
            Err(AtomicError::CasFailed)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn atomic_state_put_get() {
        let store = AtomicState::new();
        store.put("x", Value::from(1)).await;
        assert_eq!(store.get("x").await, Some(Value::from(1)));
    }

    #[tokio::test]
    async fn atomic_state_compare_swap() {
        let store = AtomicState::new();
        store.put("x", Value::from("a")).await;
        assert!(store.compare_swap("x", Some(Value::from("a")), Some(Value::from("b"))).await.is_ok());
        assert_eq!(store.get("x").await, Some(Value::from("b")));
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}
