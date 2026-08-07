use serde_json::json;

#[test]
fn generated_types_round_trip_schema_examples() {
    let handshake = hermes_runtime_protocol::v1::Handshake {
        protocol_version: "1.0".into(),
        message_id: "hs-1".into(),
        timestamp: 0,
        kind: "handshake".into(),
        worker_id: "python-1".into(),
        worker_type: "python".into(),
        capabilities: vec![],
        config: Some(json!({})),
        abi_version: None,
        language_host: None,
        features: None,
    };
    let encoded = serde_json::to_string(&handshake).expect("serialize handshake");
    let decoded: hermes_runtime_protocol::v1::Handshake = serde_json::from_str(&encoded).expect("deserialize handshake");
    assert_eq!(decoded.kind, "handshake");
    assert_eq!(decoded.worker_id, "python-1");

    let task = hermes_runtime_protocol::v1::TaskSubmit {
        protocol_version: "1.0".into(),
        message_id: "t1".into(),
        timestamp: 0,
        kind: "task.submit".into(),
        task_id: "task-1".into(),
        method: "task.echo".into(),
        params: Some(json!({"hello":"world"})),
        timeout_ms: Some(5000),
    };
    let encoded = serde_json::to_string(&task).expect("serialize task");
    let decoded: hermes_runtime_protocol::v1::TaskSubmit = serde_json::from_str(&encoded).expect("deserialize task");
    assert_eq!(decoded.method, "task.echo");
    assert_eq!(decoded.kind, "task.submit");
}
