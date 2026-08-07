use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Capability(pub String);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Handshake {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub worker_id: String,
    pub worker_type: String,
    pub capabilities: Vec<Capability>,
    pub config: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadyMessage {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub worker_id: String,
    pub status: String,
    pub features: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskSubmit {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub task_id: String,
    pub method: String,
    pub params: serde_json::Value,
    pub timeout_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub task_id: String,
    pub ok: bool,
    pub result: serde_json::Value,
    pub latency_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadRequest {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub reload_id: u64,
    pub path: String,
    pub checksum: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReloadCompleted {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub reload_id: u64,
    pub status: String,
    pub checksum: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShutdownMessage {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: u64,
    #[serde(rename = "type")]
    pub kind: String,
    pub grace_ms: u64,
}
