use std::fs::{self, File};
use std::io::{self, Write};
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct AtomicFileWrite {
    pub path: PathBuf,
    pub temp_path: PathBuf,
}

impl AtomicFileWrite {
    pub fn new(path: impl Into<PathBuf>) -> io::Result<Self> {
        let path = path.into();
        let temp_path = Self::temp_path(&path)?;
        Ok(Self { path, temp_path })
    }

    fn temp_path(path: &Path) -> io::Result<PathBuf> {
        let mut name = path.file_name().ok_or_else(|| io::Error::new(io::ErrorKind::Other, "missing file name"))?.to_os_string();
        name.push(".tmp");
        Ok(path.with_file_name(name))
    }

    pub fn write(&self, payload: &[u8]) -> io::Result<()> {
        let mut file = File::create(&self.temp_path)?;
        file.write_all(payload)?;
        file.sync_all()?;
        fs::rename(&self.temp_path, &self.path)?;
        if let Some(parent) = self.path.parent() {
            Self::fsync_dir(parent)?;
        }
        Ok(())
    }

    pub fn commit(&self) -> io::Result<()> {
        if !self.temp_path.exists() {
            return Ok(());
        }
        fs::rename(&self.temp_path, &self.path)?;
        if let Some(parent) = self.path.parent() {
            Self::fsync_dir(parent)?;
        }
        Ok(())
    }

    pub fn rollback(&self) -> io::Result<()> {
        if self.temp_path.exists() {
            fs::remove_file(&self.temp_path)?;
        }
        Ok(())
    }

    #[cfg(unix)]
    fn fsync_dir(path: &Path) -> io::Result<()> {
        let dir = File::open(path)?;
        let fd = dir.raw_fd();
        unsafe { libc::fsync(fd) };
        Ok(())
    }

    #[cfg(not(unix))]
    fn fsync_dir(path: &Path) -> io::Result<()> {
        let _ = path;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicBool, Ordering};

    #[test]
    fn atomic_write_preserves_complete_content() {
        let dir = std::env::temp_dir().join("hermes-atomic-tests");
        let _ = fs::create_dir_all(&dir);
        let target = dir.join("atomic.txt");
        let _ = fs::remove_file(&target);
        let writer = AtomicFileWrite::new(&target).expect("create writer");
        let payload = b"durable payload";
        writer.write(payload).expect("write");
        let content = fs::read(&target).expect("read target");
        assert_eq!(content, payload);
    }

    #[test]
    fn atomic_write_never_leaves_partial_content() {
        let dir = std::env::temp_dir().join("hermes-atomic-tests");
        let _ = fs::create_dir_all(&dir);
        let target = dir.join("atomic_partial.txt");
        let _ = fs::remove_file(&target);
        let _ = fs::write(&target, b"original");
        let writer = AtomicFileWrite::new(&target).expect("create writer");
        let mut partial = b"new content".to_vec();
        partial.truncate(5);
        let result = writer.write(&partial);
        assert!(result.is_ok() || result.unwrap_err().raw_os_error().is_some());
        let content = fs::read(&target).expect("read target");
        let valid = content == b"new content" || content == b"original";
        assert!(valid, "found partial bytes: {:?}", content);
    }
}
