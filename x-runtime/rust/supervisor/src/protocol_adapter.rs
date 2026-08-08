use std::fmt;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FrameKind {
    TaskSubmit = 0x01,
    CapabilityGrant = 0x02,
    ReloadRequest = 0x03,
    Heartbeat = 0x04,
    Message = 0xFF,
}

impl FrameKind {
    pub fn wire_value(self) -> u8 {
        self as u8
    }
}

impl fmt::Display for FrameKind {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            FrameKind::TaskSubmit => "task.submit",
            FrameKind::CapabilityGrant => "capability.grant",
            FrameKind::ReloadRequest => "reload.request",
            FrameKind::Heartbeat => "heartbeat",
            FrameKind::Message => "message",
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionedFrame {
    pub version: u16,
    pub kind: FrameKind,
    pub correlation_id: u8,
    pub payload_len: u32,
    pub payload: Vec<u8>,
}

impl VersionedFrame {
    pub fn parse(input: &[u8]) -> Result<Self, String> {
        if input.len() < 8 {
            return Err("frame too short for header".into());
        }
        let version = u16::from_be_bytes([input[0], input[1]]);
        let kind = match input[2] {
            0x01 => FrameKind::TaskSubmit,
            0x02 => FrameKind::CapabilityGrant,
            0x03 => FrameKind::ReloadRequest,
            0x04 => FrameKind::Heartbeat,
            0xFF => FrameKind::Message,
            other => return Err(format!("unknown frame kind: {other}")),
        };
        let correlation_id = input[3];
        let payload_len = u32::from_be_bytes([input[4], input[5], input[6], input[7]]);
        if input.len() < 8 + payload_len as usize {
            return Err("frame truncated".into());
        }
        let payload = input[8..8 + payload_len as usize].to_vec();
        Ok(Self {
            version,
            kind,
            correlation_id,
            payload_len,
            payload,
        })
    }
}

pub fn write_versioned_frame<W: std::io::Write>(mut writer: W, kind: FrameKind, correlation_id: u8, payload: &[u8]) -> std::io::Result<()> {
    if payload.len() > u32::MAX as usize {
        return Err(std::io::Error::new(std::io::ErrorKind::InvalidData, "payload too large"));
    }
    let mut header = [0u8; 8];
    header[0..2].copy_from_slice(&1u16.to_be_bytes());
    header[2] = kind.wire_value();
    header[3] = correlation_id;
    header[4..8].copy_from_slice(&(payload.len() as u32).to_be_bytes());
    writer.write_all(&header)?;
    writer.write_all(payload)?;
    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)] // Kept as part of the stable protocol surface even if unused in lib
pub struct ProtocolEnvelope {
    pub protocol_version: String,
    pub message_id: String,
    pub timestamp: i64,
    pub kind: String,
    pub worker_id: Option<String>,
    pub payload: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)] // Kept as part of the stable protocol surface even if unused in lib
pub struct ProtocolCapabilityGrant {
    pub worker_id: String,
    pub granted: Vec<String>,
    pub expires_at_ms: u64,
}

impl ProtocolCapabilityGrant {
    #[allow(dead_code)] // Kept as part of the stable protocol surface even if unused in lib
    pub fn new(worker_id: impl Into<String>, granted: Vec<String>, expires_at_ms: u64) -> Self {
        Self { worker_id: worker_id.into(), granted, expires_at_ms }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_frame_parse() {
        let payload = b"{ \"ok\": true }";
        let mut buffer = Vec::new();
        write_versioned_frame(&mut buffer, FrameKind::TaskSubmit, 7, payload).unwrap();
        let frame = VersionedFrame::parse(&buffer).unwrap();
        assert_eq!(frame.version, 1);
        assert_eq!(frame.kind, FrameKind::TaskSubmit);
        assert_eq!(frame.correlation_id, 7);
        assert_eq!(frame.payload, payload);
    }

    #[test]
    fn rejects_truncated_header() {
        let err = VersionedFrame::parse(&[1, 2, 3]).unwrap_err();
        assert!(err.contains("too short"));
    }

    #[test]
    fn rejects_truncated_payload() {
        let mut buffer = Vec::new();
        write_versioned_frame(&mut buffer, FrameKind::TaskSubmit, 1, b"payload").unwrap();
        buffer.truncate(buffer.len() - 2);
        let err = VersionedFrame::parse(&buffer).unwrap_err();
        assert!(err.contains("truncated"));
    }

    #[test]
    fn rejects_unknown_frame_kind() {
        let mut buffer = Vec::new();
        buffer.extend_from_slice(&[0u8; 8]);
        buffer[2] = 0xAB;
        let err = VersionedFrame::parse(&buffer).unwrap_err();
        assert!(err.contains("unknown frame kind"));
    }

    #[test]
    fn reload_request_round_trip() {
        let payload = b"{ \"reload_id\": 5, \"path\": \"/x\", \"checksum\": \"abc\" }";
        let mut buffer = Vec::new();
        write_versioned_frame(&mut buffer, FrameKind::ReloadRequest, 3, payload).unwrap();
        let frame = VersionedFrame::parse(&buffer).unwrap();
        assert_eq!(frame.kind, FrameKind::ReloadRequest);
        assert_eq!(frame.payload, payload);
    }
}
