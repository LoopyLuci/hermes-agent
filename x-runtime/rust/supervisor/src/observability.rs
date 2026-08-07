use parking_lot::RwLock;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityToken {
    pub worker_id: String,
    pub granted: Vec<String>,
    pub expires_at_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SupervisorMetrics {
    pub workers_total: usize,
    pub workers_healthy: usize,
    pub workers_degraded: usize,
    pub workers_unhealthy: usize,
    pub reloads_total: u64,
    pub reloads_failed: u64,
    pub restarts_total: u64,
    pub restarts_failed: u64,
    pub backoff_triggered: u64,
    pub capability_grants_total: u64,
    pub capability_denials_total: u64,
    pub transport_send_total: u64,
    pub transport_receive_total: u64,
    pub transport_dropped_total: u64,
    pub avg_latency_ms: f64,
    pub max_latency_ms: f64,
    pub uptime_secs: u64,
}

impl Default for SupervisorMetrics {
    fn default() -> Self {
        Self {
            workers_total: 0,
            workers_healthy: 0,
            workers_degraded: 0,
            workers_unhealthy: 0,
            reloads_total: 0,
            reloads_failed: 0,
            restarts_total: 0,
            restarts_failed: 0,
            backoff_triggered: 0,
            capability_grants_total: 0,
            capability_denials_total: 0,
            transport_send_total: 0,
            transport_receive_total: 0,
            transport_dropped_total: 0,
            avg_latency_ms: 0.0,
            max_latency_ms: 0.0,
            uptime_secs: 0,
        }
    }
}

#[derive(Debug, Default)]
pub struct SupervisorObservability;

impl SupervisorObservability {
    pub fn record_reload(metrics: &RwLock<SupervisorMetrics>, success: bool) {
        let mut guard = metrics.write();
        guard.reloads_total += 1;
        if !success {
            guard.reloads_failed += 1;
        }
    }

    pub fn record_restart(metrics: &RwLock<SupervisorMetrics>, success: bool) {
        let mut guard = metrics.write();
        guard.restarts_total += 1;
        if !success {
            guard.restarts_failed += 1;
        }
    }

    pub fn record_backoff(metrics: &RwLock<SupervisorMetrics>) {
        let mut guard = metrics.write();
        guard.backoff_triggered += 1;
    }

    pub fn record_capability_grant(metrics: &RwLock<SupervisorMetrics>, count: usize) {
        let mut guard = metrics.write();
        guard.capability_grants_total += count as u64;
    }

    pub fn record_capability_deny(metrics: &RwLock<SupervisorMetrics>) {
        let mut guard = metrics.write();
        guard.capability_denials_total += 1;
    }

    pub fn record_transport_send(metrics: &RwLock<SupervisorMetrics>) {
        let mut guard = metrics.write();
        guard.transport_send_total += 1;
    }

    pub fn record_transport_receive(metrics: &RwLock<SupervisorMetrics>) {
        let mut guard = metrics.write();
        guard.transport_receive_total += 1;
    }

    pub fn record_transport_drop(metrics: &RwLock<SupervisorMetrics>) {
        let mut guard = metrics.write();
        guard.transport_dropped_total += 1;
    }

    pub fn record_latency(metrics: &RwLock<SupervisorMetrics>, latency_ms: f64) {
        let mut guard = metrics.write();
        let n = if guard.transport_receive_total > 0 {
            (guard.avg_latency_ms * (guard.transport_receive_total - 1) as f64 + latency_ms)
                / guard.transport_receive_total as f64
        } else {
            latency_ms
        };
        guard.avg_latency_ms = n;
        if latency_ms > guard.max_latency_ms {
            guard.max_latency_ms = latency_ms;
        }
    }

    pub fn snapshot(metrics: &RwLock<SupervisorMetrics>) -> SupervisorMetrics {
        metrics.read().clone()
    }
}
