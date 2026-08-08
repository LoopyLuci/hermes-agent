use std::io::{Cursor, Read, Write};
use hermes_runtime_protocol::v1::{Handshake, Ready};

#[test]
fn template_handshake_parses_and_ready_serializes() {
    let input = r#"{"protocol_version":"1.0","message_id":"hs-1","timestamp":0,"type":"handshake","worker_id":"rust-worker","worker_type":"rust","capabilities":[],"config":{},"kind":"handshake"}
"#;
    let handshake: Handshake = serde_json::from_str(input.trim()).unwrap();
    assert_eq!(handshake.worker_id, "rust-worker");

    let ready = Ready {
        protocol_version: "1.0".into(),
        message_id: "ready-1".into(),
        timestamp: 0,
        worker_id: "rust-worker".into(),
        status: "healthy".into(),
        features: vec![],
        kind: "ready".into(),
    };
    let mut buf = Vec::new();
    writeln!(buf, "{}", serde_json::to_string(&ready).unwrap()).unwrap();
    let text = String::from_utf8(buf).unwrap();
    assert!(text.contains("\"type\":\"ready\""));
}
