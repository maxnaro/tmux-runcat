use std::ffi::{OsStr, OsString};
use std::io::{self, Write};
use std::os::unix::ffi::{OsStrExt, OsStringExt};
use std::process::{Command, Output, Stdio};

pub struct Tmux {
    socket: OsString,
}

impl Tmux {
    pub fn new(socket: &OsStr) -> Self {
        Self {
            socket: socket.to_owned(),
        }
    }

    pub fn command(&self) -> Command {
        let mut command = Command::new("tmux");
        command.args([OsStr::new("-S"), &self.socket]);
        command
    }

    pub fn output<I, S>(&self, args: I) -> io::Result<Output>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<OsStr>,
    {
        self.command().args(args).output()
    }

    pub fn execute<I, S>(&self, args: I) -> io::Result<()>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<OsStr>,
    {
        let output = self.output(args)?;
        check(&output)
    }

    pub fn source(&self, source: &str) -> io::Result<()> {
        let mut child = self
            .command()
            .args(["source-file", "-"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        child
            .stdin
            .take()
            .ok_or_else(|| io::Error::other("no tmux stdin"))?
            .write_all(source.as_bytes())?;
        check(&child.wait_with_output()?)
    }
}

fn check(output: &Output) -> io::Result<()> {
    if output.status.success() {
        Ok(())
    } else {
        Err(io::Error::other(
            String::from_utf8_lossy(&output.stderr).trim().to_owned(),
        ))
    }
}

pub fn shell_quote(value: &OsStr) -> OsString {
    let mut output = vec![b'\''];
    for byte in value.as_bytes() {
        if *byte == b'\'' {
            output.extend_from_slice(b"'\\''");
        } else {
            output.push(*byte);
        }
    }
    output.push(b'\'');
    OsString::from_vec(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shell_arguments_preserve_spaces_and_metacharacters() {
        let value = OsStr::new("a b'$(false);`false`");
        let mut command = OsString::from("printf '%s' ");
        command.push(shell_quote(value));
        let output = Command::new("sh")
            .args([OsStr::new("-c"), &command])
            .output()
            .unwrap();
        assert!(output.status.success());
        assert_eq!(output.stdout, value.as_bytes());
    }
}
