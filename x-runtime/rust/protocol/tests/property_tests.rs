use hermes_runtime_protocol::v1::{Handshake, Ready, ReloadCompleted, ReloadRequest, Shutdown, TaskResult, TaskSubmit};
use proptest::prelude::*;

fn arbitrary_handshake() -> impl Strategy<Value = Handshake> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<String>(), any::<String>(), any::<Vec<String>>()).prop_map(|(protocol_version, message_id, timestamp, worker_id, worker_type, capabilities)| {
        Handshake {
            protocol_version,
            message_id,
            timestamp,
            worker_id,
            worker_type,
            capabilities,
            config: None,
            abi_version: None,
            language_host: None,
            features: None,
            kind: "handshake".into(),
        }
    })
}

fn arbitrary_ready() -> impl Strategy<Value = Ready> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<String>(), any::<String>(), any::<Vec<String>>()).prop_map(|(protocol_version, message_id, timestamp, worker_id, status, features)| {
        Ready {
            protocol_version,
            message_id,
            timestamp,
            worker_id,
            status,
            features,
            kind: "ready".into(),
        }
    })
}

fn arbitrary_reload_request() -> impl Strategy<Value = ReloadRequest> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<i64>(), any::<String>(), any::<String>()).prop_map(|(protocol_version, message_id, timestamp, reload_id, path, checksum)| {
        ReloadRequest {
            protocol_version,
            message_id,
            timestamp,
            reload_id,
            path,
            checksum,
            kind: "reload.request".into(),
        }
    })
}

fn arbitrary_reload_completed() -> impl Strategy<Value = ReloadCompleted> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<i64>(), any::<String>(), any::<String>()).prop_map(|(protocol_version, message_id, timestamp, reload_id, status, checksum)| {
        ReloadCompleted {
            protocol_version,
            message_id,
            timestamp,
            reload_id,
            status,
            checksum,
            kind: "reload.completed".into(),
        }
    })
}

fn arbitrary_shutdown() -> impl Strategy<Value = Shutdown> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<i64>()).prop_map(|(protocol_version, message_id, timestamp, grace_ms)| {
        Shutdown {
            protocol_version,
            message_id,
            timestamp,
            grace_ms,
            kind: "shutdown".into(),
        }
    })
}

fn arbitrary_task_result() -> impl Strategy<Value = TaskResult> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<String>(), any::<bool>(), any::<i64>()).prop_map(|(protocol_version, message_id, timestamp, task_id, ok, latency_ms)| {
        TaskResult {
            protocol_version,
            message_id,
            timestamp,
            task_id,
            ok,
            result: serde_json::json!({}),
            latency_ms,
            kind: "task.result".into(),
        }
    })
}

fn arbitrary_task_submit() -> impl Strategy<Value = TaskSubmit> {
    (any::<String>(), any::<String>(), any::<i64>(), any::<String>(), any::<String>(), any::<i64>()).prop_map(|(protocol_version, message_id, timestamp, task_id, method, timeout_ms)| {
        TaskSubmit {
            protocol_version,
            message_id,
            timestamp,
            task_id,
            method,
            params: None,
            timeout_ms: Some(timeout_ms),
            kind: "task.submit".into(),
        }
    })
}

proptest! {
    #[test]
    fn handshake_round_trip(handshake in arbitrary_handshake()) {
        let value = serde_json::to_value(&handshake).unwrap();
        let decoded: Handshake = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&handshake).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn ready_round_trip(ready in arbitrary_ready()) {
        let value = serde_json::to_value(&ready).unwrap();
        let decoded: Ready = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&ready).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn reload_request_round_trip(request in arbitrary_reload_request()) {
        let value = serde_json::to_value(&request).unwrap();
        let decoded: ReloadRequest = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&request).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn reload_completed_round_trip(completed in arbitrary_reload_completed()) {
        let value = serde_json::to_value(&completed).unwrap();
        let decoded: ReloadCompleted = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&completed).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn shutdown_round_trip(shutdown in arbitrary_shutdown()) {
        let value = serde_json::to_value(&shutdown).unwrap();
        let decoded: Shutdown = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&shutdown).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn task_result_round_trip(result in arbitrary_task_result()) {
        let value = serde_json::to_value(&result).unwrap();
        let decoded: TaskResult = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&result).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }

    #[test]
    fn task_submit_round_trip(submit in arbitrary_task_submit()) {
        let value = serde_json::to_value(&submit).unwrap();
        let decoded: TaskSubmit = serde_json::from_value(value).unwrap();
        let original_value = serde_json::to_value(&submit).unwrap();
        let decoded_value = serde_json::to_value(decoded).unwrap();
        assert_eq!(original_value, decoded_value);
    }
}

#[test]
fn malformed_json_envelope_fails_deserialization() {
    let malformed = r#"{"type":"handshake","protocol_version":"1.0","message_id":"missing-timestamp"}"#;
    let result: Result<Handshake, _> = serde_json::from_str(malformed);
    assert!(result.is_err());
}

#[test]
fn oversized_fields_round_trip_without_panic() {
    let handshake = Handshake {
        protocol_version: "1.0".into(),
        message_id: "m".into(),
        timestamp: 1,
        worker_id: "w".into(),
        worker_type: "t".into(),
        capabilities: vec!["c".repeat(8192)],
        config: None,
        abi_version: None,
        language_host: None,
        features: None,
        kind: "handshake".into(),
    };
    let value = serde_json::to_value(&handshake).unwrap();
    let decoded: Handshake = serde_json::from_value(value).unwrap();
    assert_eq!(decoded.capabilities.len(), 1);
    assert_eq!(decoded.capabilities[0].len(), 8192);
}
