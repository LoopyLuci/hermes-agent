use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::sync::{Mutex, RwLock};
use tracing::{debug, info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    pub id: String,
    pub version: String,
    pub entry: String,
    pub language: PluginLanguage,
    pub capabilities: Vec<String>,
    pub route_hint: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PluginLanguage {
    Rust,
    Python,
    Clojure,
    TypeScript,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginRegistration {
    pub id: String,
    pub manifest: PluginManifest,
    pub loaded_at: u64,
}

#[derive(Debug, Error)]
pub enum PluginHostError {
    #[error("plugin already loaded: {0}")]
    AlreadyLoaded(String),
    #[error("plugin not found: {0}")]
    NotFound(String),
    #[error("plugin load failed: {0}")]
    LoadFailed(String),
}

#[derive(Default)]
pub struct PluginHostRegistry {
    registrations: RwLock<HashMap<String, PluginRegistration>>,
}

impl PluginHostRegistry {
    pub async fn register(&self, registration: PluginRegistration) -> Result<(), PluginHostError> {
        let mut guard = self.registrations.write().await;
        if guard.contains_key(&registration.id) {
            return Err(PluginHostError::AlreadyLoaded(registration.id));
        }
        debug!(plugin_id = %registration.id, "register plugin");
        guard.insert(registration.id.clone(), registration);
        Ok(())
    }

    pub async fn get(&self, id: &str) -> Option<PluginRegistration> {
        self.registrations.read().await.get(id).cloned()
    }

    pub async fn list(&self) -> Vec<PluginRegistration> {
        self.registrations.read().await.values().cloned().collect()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerCallEnvelope {
    pub worker_id: String,
    pub method: String,
    pub params: serde_json::Value,
    pub request_id: String,
    pub timeout_ms: Option<u64>,
}

impl WorkerCallEnvelope {
    pub fn new(worker_id: impl Into<String>, method: impl Into<String>, params: serde_json::Value) -> Self {
        Self {
            worker_id: worker_id.into(),
            method: method.into(),
            params,
            request_id: format!("call-{}", uuid()),
            timeout_ms: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerCallResponse {
    pub request_id: String,
    pub ok: bool,
    pub body: serde_json::Value,
    pub latency_ms: u64,
}

#[derive(Debug, Default)]
pub struct PluginProcessPool {
    next_pid: AtomicU64,
}

impl PluginProcessPool {
    pub fn spawn_placeholder(&self, _id: &str) -> u64 {
        self.next_pid.fetch_add(1, Ordering::Relaxed)
    }
}

fn uuid() -> u64 {
    static SEQ: AtomicU64 = AtomicU64::new(1);
    SEQ.fetch_add(1, Ordering::Relaxed)
}
