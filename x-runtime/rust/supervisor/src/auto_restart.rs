use std::collections::HashMap;
use std::time::{Duration, Instant};
use crate::SupervisorObservability;
use tracing::{info, warn};
use uuid::Uuid;

const RESTART_BACKOFF_THRESHOLD: usize = 3;
const RESTART_BACKOFF_WINDOW: Duration = Duration::from_secs(60);

pub async fn maybe_restart_unhealthy_workers(supervisor: &crate::Supervisor) {
    let workers = supervisor.registry.list().await;
    let now = std::time::Instant::now();
    let stale_threshold = supervisor.config.heartbeat_interval * 3;
    let mut restart_counts = HashMap::<String, (usize, Instant)>::new();
    for worker in &workers {
        let status = worker.status.read().clone();
        let last_hb = *worker.last_heartbeat.read();
        let stale = now.duration_since(last_hb) > stale_threshold;
        let should_restart = matches!(status, crate::WorkerStatus::Error { .. })
            || matches!(status, crate::WorkerStatus::Stopped)
            || stale;
        if !should_restart {
            continue;
        }
        if let Some((count, last)) = restart_counts.get(&worker.id) {
            if *count >= RESTART_BACKOFF_THRESHOLD && now.duration_since(*last) < RESTART_BACKOFF_WINDOW {
                SupervisorObservability::record_backoff(&supervisor.metrics);
                warn!(worker_id=%worker.id, ?status, stale, backoff=?last, "backoff preventing worker restart");
                continue;
            }
        }
        restart_counts.entry(worker.id.clone()).and_modify(|(count, last)| {
            *count += 1;
            *last = now;
        }).or_insert((1, now));
        warn!(worker_id=%worker.id, ?status, stale, "restarting unhealthy worker");
        let _ = worker.shutdown(Duration::from_secs(2)).await;
        let mut spec = worker.spec.clone();
        spec.id = format!("{}-retry-{}", worker.id, Uuid::new_v4());
        match supervisor.spawn_worker(spec.clone()).await {
            Ok(_) => {
                SupervisorObservability::record_restart(&supervisor.metrics, true);
                info!(worker_id=%worker.id, "worker restarted");
            }
            Err(err) => {
                SupervisorObservability::record_restart(&supervisor.metrics, false);
                warn!(?err, "worker restart failed");
            }
        }
    }
}
