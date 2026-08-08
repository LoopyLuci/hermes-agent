use std::path::PathBuf;

#[test]
fn generated_protocol_files_match_schema() {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let generated = manifest_dir.join("src/v1/generated.rs");
    let text = std::fs::read_to_string(&generated).expect("read generated rust types");
    assert!(text.contains("pub struct Handshake"));
    assert!(text.contains("pub struct TaskSubmit"));
    assert!(text.contains("pub struct ReloadRequest"));
    assert!(text.contains("pub kind: String,"));
}
