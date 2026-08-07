use crate::{AtomicError, ReloadEvent, ReloadStatus};

use std::collections::VecDeque;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicU64;
use tokio::sync::RwLock;
use tracing::{debug, warn};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct WalEntry {
    pub key: String,
    pub prev: Option<serde_json::Value>,
    pub next: Option<serde_json::Value>,
    pub checksum: String,
    pub timestamp: u64,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AtomicStateSnapshot {
    pub state: std::collections::HashMap<String, serde_json::Value>,
    pub checksum: String,
    pub timestamp: u64,
}

#[derive(Debug, Default)]
pub struct DurableAtomicState {
    wal_path: PathBuf,
    state: RwLock<std::collections::HashMap<String, serde_json::Value>>,
    wal: RwLock<VecDeque<WalEntry>>,
    seq: AtomicU64,
}

impl DurableAtomicState {
    pub fn new(wal_path: impl Into<PathBuf>) -> Self {
        let wal_path = wal_path.into();
        let mut state = Self {
            wal_path: wal_path.clone(),
            state: RwLock::new(std::collections::HashMap::new()),
            wal: RwLock::new(VecDeque::new()),
            seq: AtomicU64::new(0),
        };
        let _ = state.recover();
        state
    }

    pub async fn put(&self, key: impl Into<String>, value: serde_json::Value) {
        let key = key.into();
        let checksum = format!("{:x}", md5::compute(format!("{key}:{value}")));
        let entry = WalEntry {
            key: key.clone(),
            prev: self.state.read().await.get(&key).cloned(),
            next: Some(value.clone()),
            checksum,
            timestamp: now_ms(),
        };
        self.wal.write().await.push_back(entry.clone());
        self.state.write().await.insert(key.clone(), value);
        let _ = self.persist_wal_entry(&entry);
    }

    pub async fn compare_swap(
        &self,
        key: impl Into<String>,
        expected: Option<serde_json::Value>,
        new: Option<serde_json::Value>,
    ) -> Result<(), AtomicError> {
        let key = key.into();
        let state = self.state.read().await;
        let current = state.get(&key).cloned();
        drop(state);
        if current == expected {
            let checksum = format!("{:x}", md5::compute(format!("{key}:{:?}", new)));
            let entry = WalEntry {
                key: key.clone(),
                prev: current.clone(),
                next: new.clone(),
                checksum,
                timestamp: now_ms(),
            };
            self.wal.write().await.push_back(entry.clone());
            self.state.write().await.insert(key.clone(), new.unwrap_or(serde_json::Value::Null));
            let _ = self.persist_wal_entry(&entry);
            Ok(())
        } else {
            Err(AtomicError::CasFailed)
        }
    }

    pub async fn get(&self, key: &str) -> Option<serde_json::Value> {
        self.state.read().await.get(key).cloned()
    }

    pub fn recover(&mut self) -> Result<(), String> {
        if !self.wal_path.exists() {
            return Ok(());
        }
        let mut file = File::open(&self.wal_path).map_err(|e| e.to_string())?;
        let mut text = String::new();
        file.read_to_string(&mut text).map_err(|e| e.to_string())?;
        let mut wal = VecDeque::new();
        for line in text.lines() {
            if line.trim().is_empty() { continue; }
            let entry: WalEntry = serde_json::from_str(line).map_err(|e| e.to_string())?;
            wal.push_back(entry);
        }
        let mut state = std::collections::HashMap::new();
        for entry in &wal {
            if let Some(next) = &entry.next {
                state.insert(entry.key.clone(), next.clone());
            } else if entry.next.is_none() {
                state.remove(&entry.key);
            }
        }
        *self.state.get_mut() = RwLock::new(state);
        *self.wal.get_mut() = RwLock::new(wal);
        Ok(())
    }

    pub async fn checkpoint(&self) -> Result<(), String> {
        let snapshot = AtomicStateSnapshot {
            state: self.state.read().await.clone(),
            checksum: "".into(),
            timestamp: now_ms(),
        };
        let json = serde_json::to_vec(&snapshot).map_err(|e| e.to_string())?;
        let dir = self.wal_path.parent().map(Path::new).filter(|p| p.exists()).ok_or_else(|| "missing wal dir".to_string())?;
        let temp = dir.join(format!("{}.tmp", self.wal_path.file_name().unwrap().to_str().unwrap()));
        fs::write(&temp, json).map_err(|e| e.to_string())?;
        fs::rename(&temp, &self.wal_path).map_err(|e| e.to_string())?;
        Ok(())
    }

    fn persist_wal_entry(&self, entry: &WalEntry) -> Result<(), String> {
        if let Some(parent) = self.wal_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let mut file = OpenOptions::new().create(true).append(true).open(&self.wal_path).map_err(|e| e.to_string())?;
        let line = serde_json::to_string(entry).map_err(|e| e.to_string())?;
        file.write_all(line.as_bytes()).map_err(|e| e.to_string())?;
        file.write_all(b"\n").map_err(|e| e.to_string())?;
        Ok(())
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn durable_put_get_and_recover() {
        let dir = std::env::temp_dir().join("hermes-durable-tests");
        let _ = fs::create_dir_all(&dir);
        let wal = dir.join("wal.jsonl");
        let _ = fs::remove_file(&wal);
        {
            let state = DurableAtomicState::new(&wal);
            state.put("x", serde_json::Value::from(1)).await;
        }
        let mut recovered = DurableAtomicState::new(&wal);
        let value = recovered.get("x").await;
        assert_eq!(value, Some(serde_json::Value::from(1)));
    }

    #[tokio::test]
    async fn durable_compare_swap_persists() {
        let dir = std::env::temp_dir().join("hermes-durable-tests");
        let wal = dir.join("wal-cas.jsonl");
        let _ = fs::remove_file(&wal);
        {
            let state = DurableAtomicState::new(&wal);
            state.put("x", serde_json::Value::from("a")).await;
            state.compare_swap("x", Some(serde_json::Value::from("a")), Some(serde_json::Value::from("b"))).await.unwrap();
        }
        let recovered = DurableAtomicState::new(&wal);
        assert_eq!(recovered.get("x").await, Some(serde_json::Value::from("b")));
    }
}
