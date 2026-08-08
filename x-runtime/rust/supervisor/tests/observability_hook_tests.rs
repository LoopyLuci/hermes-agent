use std::sync::Arc;
use parking_lot::RwLock;
use hermes_runtime_supervisor::SupervisorObservability;

#[test]
fn observability_hooks_emit_events_after_reload_and_capability_grant() {
    let metrics = Arc::new(RwLock::new(hermes_runtime_supervisor::SupervisorMetrics::default()));

    SupervisorObservability::record_reload(&metrics, true);
    SupervisorObservability::record_reload(&metrics, false);
    SupervisorObservability::record_backoff(&metrics);
    SupervisorObservability::record_capability_grant(&metrics, 2);
    SupervisorObservability::record_capability_deny(&metrics);
    SupervisorObservability::record_transport_send(&metrics);
    SupervisorObservability::record_transport_receive(&metrics);
    SupervisorObservability::record_transport_drop(&metrics);
    SupervisorObservability::record_latency(&metrics, 12.5);

    let snapshot = SupervisorObservability::snapshot(&metrics);
    assert_eq!(snapshot.reloads_total, 2);
    assert_eq!(snapshot.reloads_failed, 1);
    assert_eq!(snapshot.backoff_triggered, 1);
    assert_eq!(snapshot.capability_grants_total, 2);
    assert_eq!(snapshot.capability_denials_total, 1);
    assert_eq!(snapshot.transport_send_total, 1);
    assert_eq!(snapshot.transport_receive_total, 1);
    assert_eq!(snapshot.transport_dropped_total, 1);
    assert_eq!(snapshot.avg_latency_ms, 12.5);
    assert_eq!(snapshot.max_latency_ms, 12.5);
}
