// Auto-generated from x-runtime/protocol/v1/schema/*.json
// Run `python x-runtime/protocol/v1/generate.py` to regenerate.
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvelopeError {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Handshake {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub worker_id: String,
    pub worker_type: String,
    pub capabilities: Vec<String>,
    pub config: Option<serde_json::Value>,
    pub abi_version: Option<String>,
    pub language_host: Option<String>,
    pub features: Option<serde_json::Value>,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Ready {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub worker_id: String,
    pub status: String,
    pub features: Vec<String>,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadCompleted {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub reload_id: i64,
    pub status: String,
    pub checksum: String,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadRequest {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub reload_id: i64,
    pub path: String,
    pub checksum: String,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Shutdown {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub grace_ms: i64,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub task_id: String,
    pub ok: bool,
    pub result: serde_json::Value,
    pub latency_ms: i64,
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskSubmit {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub task_id: String,
    pub method: String,
    pub params: Option<serde_json::Value>,
    pub timeout_ms: Option<i64>,
    #[serde(rename = "type")]
    pub kind: String,
}
