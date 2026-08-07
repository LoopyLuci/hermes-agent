use std::env;
use std::net::SocketAddr;
use hermes_runtime_supervisor::{run_supervisor, SupervisorConfig};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let bind: SocketAddr = env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or_else(|| "127.0.0.1:18181".parse().unwrap());
    let state_path = env::temp_dir().join("hermes-runtime-supervisor-state.json");
    let config = SupervisorConfig {
        bind_addr: bind.to_string(),
        health_port: 0,
        task_timeout: std::time::Duration::from_secs(60),
        reload_timeout: std::time::Duration::from_secs(5),
        heartbeat_interval: std::time::Duration::from_secs(10),
        shutdown_grace: std::time::Duration::from_secs(5),
    };
    let rt = tokio::runtime::Runtime::new()?;
    let handle = rt.block_on(run_supervisor(config, state_path))?;
    println!("supervisor started id={} started_at={} bind={}", handle.id, handle.started_at, bind);
    std::thread::park();
    Ok(())
}
