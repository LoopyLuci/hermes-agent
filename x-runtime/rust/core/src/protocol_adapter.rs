use std::io::{Error, ErrorKind};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProtocolEnvelope {
    pub correlation_id: String,
    pub kind: String,
    pub payload: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProtocolCapabilityGrant {
    pub worker_id: String,
    pub granted: Vec<String>,
    pub expires_at_ms: u64,
}

#[derive(Debug, Clone, Copy)]
pub enum FrameKind {
    Submit,
    Result,
    Event,
}

#[derive(Debug)]
pub struct VersionedFrame {
    pub kind: FrameKind,
    pub correlation_id: String,
    pub payload: Vec<u8>,
}

impl ProtocolEnvelope {
    pub fn new(kind: impl Into<String>, payload: Vec<u8>) -> Self {
        Self { correlation_id: format!("env-{}", Uuid::new_v4()), kind: kind.into(), payload }
    }
}

impl ProtocolCapabilityGrant {
    pub fn new(worker_id: impl Into<String>, granted: Vec<String>, expires_at_ms: u64) -> Self {
        Self { worker_id: worker_id.into(), granted, expires_at_ms }
    }
}

impl FrameKind {
    pub fn wire_value(self) -> u8 {
        match self { FrameKind::Submit => 0x01, FrameKind::Result => 0x02, FrameKind::Event => 0x03 }
    }
}

impl VersionedFrame {
    pub fn parse(input: &[u8]) -> Result<Self, Error> {
        if input.len() < 7 { return Err(Error::new(ErrorKind::InvalidData, "frame too short")); }
        let kind = match input[0] { 0x01 => FrameKind::Submit, 0x02 => FrameKind::Result, 0x03 => FrameKind::Event, other => return Err(Error::new(ErrorKind::InvalidData, format!("unknown frame kind: {other}"))), };
        let correlation_id_len = u16::from_le_bytes([input[1], input[2]]) as usize;
        let payload_len = u32::from_le_bytes([input[3], input[4], input[5], input[6]]) as usize;
        if input.len() < 7 + correlation_id_len + payload_len { return Err(Error::new(ErrorKind::InvalidData, "frame truncated")); }
        let correlation_id = std::str::from_utf8(&input[7..7 + correlation_id_len]).map_err(|e| Error::new(ErrorKind::InvalidData, e.to_string()))?.to_string();
        let payload = input[7 + correlation_id_len..7 + correlation_id_len + payload_len].to_vec();
        Ok(Self { kind, correlation_id, payload })
    }
}

pub fn write_versioned_frame<W: std::io::Write>(mut writer: W, kind: FrameKind, correlation_id: &str, payload: &[u8]) -> std::io::Result<()> {
    let mut header = [0u8; 7];
    header[0] = kind.wire_value();
    header[1..3].copy_from_slice(&(correlation_id.len() as u16).to_le_bytes());
    header[3..7].copy_from_slice(&(payload.len() as u32).to_le_bytes());
    writer.write_all(&header)?;
    writer.write_all(correlation_id.as_bytes())?;
    writer.write_all(payload)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn round_trip_frame_parse() {
        let mut buf = Vec::new();
        write_versioned_frame(&mut buf, FrameKind::Submit, "corr-1", b"hello").unwrap();
        let frame = VersionedFrame::parse(&buf).unwrap();
        assert!(matches!(frame.kind, FrameKind::Submit));
        assert_eq!(frame.correlation_id, "corr-1");
        assert_eq!(frame.payload, b"hello");
    }
}
