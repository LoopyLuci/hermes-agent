use std::io::{BufRead, Write};
use uuid::Uuid;

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let stdin = std::io::stdin();
    let mut stdout = std::io::stdout();
    let mut lock = stdout.lock();
    let mut lines = stdin.lines();

    let handshake_line = lines.next().ok_or_else(|| String::from("missing handshake"))??;
    let _handshake: hermes_runtime_protocol::v1::Handshake = serde_json::from_str(&handshake_line)?;

    let ready = hermes_runtime_protocol::v1::Ready {
        protocol_version: "1.0".into(),
        message_id: Uuid::new_v4().to_string(),
        timestamp: now_ms(),
        worker_id: "rust-worker".into(),
        status: "healthy".into(),
        features: vec!["task.echo".into()],
        kind: "ready".into(),
    };
    writeln!(lock, "{}", serde_json::to_string(&ready)?)?;

    for line in lines {
        let line = line?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let envelope: serde_json::Value = serde_json::from_str(trimmed)?;
        let kind = envelope.get("type").and_then(|v| v.as_str()).unwrap_or_default();
        match kind {
            "task.submit" => {
                let task: hermes_runtime_protocol::v1::TaskSubmit = serde_json::from_value(envelope)?;
                let result = hermes_runtime_protocol::v1::TaskResult {
                    protocol_version: "1.0".into(),
                    message_id: Uuid::new_v4().to_string(),
                    timestamp: now_ms(),
                    task_id: task.task_id,
                    ok: true,
                    result: serde_json::json!({"echo": task.params}),
                    latency_ms: 1,
                    kind: "task.result".into(),
                };
                writeln!(lock, "{}", serde_json::to_string(&result)?)?;
            }
            "reload.request" => {
                let request: hermes_runtime_protocol::v1::ReloadRequest = serde_json::from_value(envelope)?;
                let completed = hermes_runtime_protocol::v1::ReloadCompleted {
                    protocol_version: "1.0".into(),
                    message_id: Uuid::new_v4().to_string(),
                    timestamp: now_ms(),
                    reload_id: request.reload_id,
                    status: "active".into(),
                    checksum: request.checksum,
                    kind: "reload.completed".into(),
                };
                writeln!(lock, "{}", serde_json::to_string(&completed)?)?;
            }
            "shutdown" => break,
            _ => {}
        }
    }

    Ok(())
}
