#[cfg(test)]
mod tests {
    #[test]
    fn protocol_schema_files_are_valid_json() {
        let schema_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../protocol/v1/schema");
        for entry in std::fs::read_dir(schema_dir).expect("schema dir") {
            let path = entry.expect("entry").path();
            if path.extension().map(|e| e == "json").unwrap_or(false) {
                let text = std::fs::read_to_string(&path).expect("schema text");
                let _: serde_json::Value = serde_json::from_str(&text).expect(path.to_string_lossy().as_ref());
            }
        }
    }
}
