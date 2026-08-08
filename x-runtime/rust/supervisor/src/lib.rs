mod auto_restart;
mod observability;
mod persistent_state;
mod protocol_adapter;
mod worker;

pub use auto_restart::maybe_restart_unhealthy_workers;
pub use observability::{CapabilityToken, SupervisorMetrics, SupervisorObservability};
pub use persistent_state::{PersistentSupervisorState, SupervisorState, WorkerStateRecord, WorkerSpecRecord};
pub use worker::{
    Capability, CapabilityGrant, MessageEnvelope, SupervisorConfig, SupervisorError, SupervisorHandle,
    SupervisorStatusResponse, WorkerError, WorkerErrorKind, WorkerProcess, WorkerRegistry, WorkerSpec, WorkerStatus,
};

use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;

use axum::{
    extract::State,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use serde_json::json;
use tracing::info;
use uuid::Uuid;
use hermes_runtime_protocol::ReloadRequest;

#[derive(Debug)]
pub struct Supervisor {
    pub id: String,
    pub config: SupervisorConfig,
    pub registry: Arc<WorkerRegistry>,
    pub started_at: Instant,
    pub persistent_state: PersistentSupervisorState,
    pub metrics: Arc<RwLock<SupervisorMetrics>>,
}

impl Supervisor {
    pub async fn new(config: SupervisorConfig, state_path: std::path::PathBuf) -> Result<Self, SupervisorError> {
        Self::new_with_registry(config, state_path, Arc::new(WorkerRegistry::new())).await
    }

    pub async fn new_with_registry(
        config: SupervisorConfig,
        state_path: std::path::PathBuf,
        registry: Arc<WorkerRegistry>,
    ) -> Result<Self, SupervisorError> {
        let persistent_state = PersistentSupervisorState::open(state_path)
            .map_err(|e| SupervisorError::State(e.to_string()))?;
        let id = format!("supervisor-{}", Uuid::new_v4());
        Ok(Self {
            id,
            config,
            registry,
            started_at: Instant::now(),
            persistent_state,
            metrics: Arc::new(RwLock::new(SupervisorMetrics::default())),
        })
    }

    pub fn record_restart(&self, success: bool) {
        SupervisorObservability::record_restart(&self.metrics, success);
    }

    pub fn record_backoff(&self) {
        SupervisorObservability::record_backoff(&self.metrics);
    }

    pub async fn spawn_worker(&self, mut spec: WorkerSpec) -> Result<Arc<WorkerProcess>, SupervisorError> {
        if spec.id.is_empty() || spec.id == "worker" {
            spec.id = format!("worker-{}", Uuid::new_v4());
        }
        let mut cmd = std::process::Command::new(&spec.command);
        cmd.args(&spec.args)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::inherit());
        let mut child = cmd.spawn().map_err(|e| SupervisorError::Worker(e.to_string()))?;
        let stdin = child.stdin.take().ok_or_else(|| SupervisorError::Worker("missing stdin".into()))?;
        let stdout = child.stdout.take().ok_or_else(|| SupervisorError::Worker("missing stdout".into()))?;
        let process = Arc::new(WorkerProcess::new(
            spec.id.clone(),
            Arc::new(std::sync::Mutex::new(child)),
            stdin,
            stdout,
            self.metrics.clone(),
        ));
        self.registry.register(process.clone()).await;
        Ok(process)
    }
}

#[derive(Debug, Serialize)]
struct RestStatusResponse {
    status: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[allow(dead_code)] // Struct reserved for path-extracted worker ID contract
struct WorkerPathParam {
    pub id: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct RenewCapabilitiesRequest {
    ttl_ms: i64,
}

#[derive(Debug, Serialize)]
struct RenewCapabilitiesResponse {
    status: String,
    expires_at_ms: i64,
}

fn supervisor_router(state: Arc<Supervisor>) -> Router {
    Router::new()
        .route("/status", get(status_handler))
        .route("/healthz", get(health_handler))
        .route("/workers", post(spawn_handler))
        .route("/workers/{id}", get(worker_status_handler))
        .route("/workers/{id}/reload", post(reload_handler))
        .route("/workers/{id}/shutdown", post(shutdown_handler))
        .route("/workers/{id}/capabilities/renew", post(capability_renew_handler))
        .route("/metrics", get(metrics_handler))
        .with_state(state)
}

async fn spawn_handler(
    State(supervisor): State<Arc<Supervisor>>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let id = payload.get("id").and_then(|v| v.as_str()).unwrap_or("worker");
    let command = payload.get("command").and_then(|v| v.as_str()).unwrap_or("");
    let args = payload.get("args").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let raw_capabilities: Vec<_> = payload.get("capabilities").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let capabilities: Vec<Capability> = raw_capabilities.into_iter().map(Capability).collect();
    let autostart = payload.get("autostart").and_then(|v| v.as_bool()).unwrap_or(true);
    let spec = WorkerSpec {
        id: id.into(),
        command: command.into(),
        args,
        capabilities,
        autostart,
    };
    let worker = supervisor.spawn_worker(spec).await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(json!({"id": worker.id, "status": "spawned"})))
}

async fn worker_status_handler(
    State(supervisor): State<Arc<Supervisor>>,
    axum::extract::Path(param): axum::extract::Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let worker = supervisor.registry.get(&param).await.ok_or(StatusCode::NOT_FOUND)?;
    let status = worker.status.read().clone();
    Ok(Json(json!({"id": param, "status": status})))
}

async fn reload_handler(
    State(supervisor): State<Arc<Supervisor>>,
    axum::extract::Path(param): axum::extract::Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let worker = supervisor.registry.get(&param).await.ok_or(StatusCode::NOT_FOUND)?;
    let reload_id: i64 = payload.get("reload_id").and_then(|v| v.as_i64()).unwrap_or(0);
    let checksum = payload.get("checksum").and_then(|v| v.as_str()).unwrap_or("");
    let path = payload.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let request = ReloadRequest {
        protocol_version: "1.0".into(),
        message_id: format!("reload-{}", Uuid::new_v4()),
        timestamp: now_ms(),
        kind: "reload.request".into(),
        reload_id,
        path: path.into(),
        checksum: checksum.into(),
    };
    let envelope = MessageEnvelope::reload_request(&request);
    worker.send(&envelope).await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(RestStatusResponse { status: "reload_requested".into() }))
}

async fn shutdown_handler(
    State(supervisor): State<Arc<Supervisor>>,
    axum::extract::Path(param): axum::extract::Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let worker = supervisor.registry.get(&param).await.ok_or(StatusCode::NOT_FOUND)?;
    worker
        .shutdown(supervisor.config.shutdown_grace)
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(RestStatusResponse { status: "shutdown_sent".into() }))
}

async fn capability_renew_handler(
    State(supervisor): State<Arc<Supervisor>>,
    axum::extract::Path(param): axum::extract::Path<String>,
    Json(payload): Json<RenewCapabilitiesRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let worker = supervisor.registry.get(&param).await.ok_or(StatusCode::NOT_FOUND)?;
    let expires_at_ms = now_ms() + payload.ttl_ms;
    let mut status = worker.status.write();
    *status = WorkerStatus::Healthy;
    drop(status);
    let mut capabilities = worker.capabilities.write();
    capabilities.push(CapabilityGrant {
        worker_id: param.clone(),
        granted: vec![],
        expires_at_ms: Some(expires_at_ms),
    });
    Ok(Json(RenewCapabilitiesResponse {
        status: "renewed".into(),
        expires_at_ms,
    }))
}

async fn metrics_handler(State(supervisor): State<Arc<Supervisor>>) -> impl IntoResponse {
    let snapshot = SupervisorObservability::snapshot(&supervisor.metrics);
    Json(snapshot)
}

async fn status_handler(State(supervisor): State<Arc<Supervisor>>) -> impl IntoResponse {
    let registry = supervisor.registry.list().await;
    let workers: Vec<WorkerStatus> = registry.into_iter().map(|w| {
        let status = w.status.read().clone();
        status
    }).collect();
    Json(SupervisorStatusResponse {
        supervisor_id: supervisor.id.clone(),
        uptime_secs: supervisor.started_at.elapsed().as_secs(),
        worker_count: workers.len(),
        workers,
    })
}

async fn health_handler(State(supervisor): State<Arc<Supervisor>>) -> impl IntoResponse {
    let registry = supervisor.registry.list().await;
    let mut healthy_count = 0;
    for worker in &registry {
        let status = worker.status.read().clone();
        if matches!(status, WorkerStatus::Healthy) {
            healthy_count += 1;
        }
    }
    if !registry.is_empty() && healthy_count == registry.len() {
        (StatusCode::OK, Json(json!(r#"{"status":"healthy"}"#))).into_response()
    } else if healthy_count > 0 {
        (StatusCode::SERVICE_UNAVAILABLE, Json(json!(r#"{"status":"degraded"}"#))).into_response()
    } else {
        (StatusCode::SERVICE_UNAVAILABLE, Json(json!(r#"{"status":"unhealthy"}"#))).into_response()
    }
}

pub async fn run_supervisor(config: SupervisorConfig, state_path: std::path::PathBuf) -> Result<SupervisorHandle, SupervisorError> {
    let supervisor = Supervisor::new(config.clone(), state_path).await?;
    let id = supervisor.id.clone();
    info!(supervisor_id=%id, "starting supervisor");
    let state = Arc::new(supervisor);
    let app = supervisor_router(state.clone());
    let addr: SocketAddr = config.bind_addr.parse().expect("invalid bind addr");
    let listener = tokio::net::TcpListener::bind(addr).await.map_err(|e| SupervisorError::Worker(e.to_string()))?;
    let actual_addr = listener.local_addr().map_err(|e| SupervisorError::Worker(e.to_string()))?;
    info!(?actual_addr, "supervisor HTTP listening");
    let monitor_state = state.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(monitor_state.config.heartbeat_interval);
        loop {
            interval.tick().await;
            maybe_restart_unhealthy_workers(&monitor_state).await;
        }
    });
    tokio::spawn(async move {
        axum::serve(listener, app.into_make_service()).await.ok();
    });
    Ok(SupervisorHandle { id, started_at: now_ms() as u64 })
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}
