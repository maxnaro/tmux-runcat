use crate::animation::{Animation, Settings};
use crate::tmux::Tmux;
use std::collections::HashMap;
use std::ffi::OsStr;
use std::fs::{OpenOptions, TryLockError};
use std::io;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

const POLL: Duration = Duration::from_millis(50);
const FORMAT: &str = "#{client_name}\t#{session_id}\t#{@runcat-keys}\t#{@runcat-idle}\t#{@runcat-min-fps}\t#{@runcat-max-fps}";

struct Session {
    count: u64,
    clients: Vec<String>,
    settings: Settings,
}

fn parse_clients(lines: impl Iterator<Item = String>) -> HashMap<String, Session> {
    let mut sessions: HashMap<String, Session> = HashMap::new();
    for line in lines {
        let fields: Vec<_> = line.split('\t').collect();
        if fields.len() != 6 {
            continue;
        }
        sessions
            .entry(fields[1].to_owned())
            .or_insert_with(|| Session {
                count: fields[2].parse().unwrap_or(0),
                clients: Vec::new(),
                settings: Settings::parse(fields[3], fields[4], fields[5]),
            })
            .clients
            .push(fields[0].to_owned());
    }
    sessions
}

pub fn run(socket: &OsStr, pid: &OsStr, generation: &str) -> io::Result<()> {
    let pid = pid
        .to_str()
        .and_then(|value| value.parse::<u32>().ok())
        .filter(|value| *value != 0)
        .ok_or_else(|| io::Error::other("invalid server PID"))?;
    let directory = Path::new(socket)
        .parent()
        .ok_or_else(|| io::Error::other("socket has no directory"))?;
    let lock = OpenOptions::new()
        .create(true)
        .truncate(false)
        .append(true)
        .open(directory.join(format!("runcat-{pid}.lock")))?;
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        match lock.try_lock() {
            Ok(()) => break,
            Err(TryLockError::WouldBlock) if Instant::now() < deadline => thread::sleep(POLL),
            Err(TryLockError::WouldBlock) => return Ok(()),
            Err(TryLockError::Error(error)) => return Err(error),
        }
    }
    let tmux = Tmux::new(socket);
    let start = Instant::now();
    let mut animations: HashMap<String, Animation> = HashMap::new();
    let mut published: HashMap<String, String> = HashMap::new();
    loop {
        let output = tmux.output([
            "display-message",
            "-p",
            "#{@runcat-generation}",
            ";",
            "list-clients",
            "-F",
            FORMAT,
        ])?;
        let text = String::from_utf8_lossy(&output.stdout);
        let mut lines = text.lines();
        if !output.status.success() || lines.next() != Some(generation) {
            return Ok(());
        }
        let sessions = parse_clients(lines.map(str::to_owned));
        animations.retain(|session, _| sessions.contains_key(session));
        published.retain(|session, _| sessions.contains_key(session));
        if sessions.is_empty() {
            thread::sleep(Duration::from_millis(250));
            continue;
        }
        let now = start.elapsed().as_secs_f64();
        let mut update = Vec::new();
        for (session, activity) in sessions {
            let animation = animations
                .entry(session.clone())
                .or_insert_with(|| Animation::new(activity.count, now));
            let pose = animation.update(activity.count, now, activity.settings);
            if published.get(&session).is_some_and(|value| value == pose) {
                continue;
            }
            if !update.is_empty() {
                update.push(";".to_owned());
            }
            update.extend([
                "set-option".to_owned(),
                "-t".to_owned(),
                session.clone(),
                "@runcat-frame".to_owned(),
                pose.to_owned(),
            ]);
            for client in activity.clients {
                update.extend([
                    ";".to_owned(),
                    "refresh-client".to_owned(),
                    "-S".to_owned(),
                    "-t".to_owned(),
                    client,
                ]);
            }
            published.insert(session, pose.to_owned());
        }
        if !update.is_empty() && !tmux.output(update)?.status.success() {
            published.clear();
        }
        thread::sleep(POLL);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn clients_are_grouped_by_session_with_independent_counts() {
        let sessions = parse_clients(
            [
                "/dev/pts/1\t$1\t4\t2\t3\t12",
                "/dev/pts/2\t$1\t4\t2\t3\t12",
                "/dev/pts/3\t$2\t9\t1\t4\t8",
                "invalid",
            ]
            .into_iter()
            .map(str::to_owned),
        );
        assert_eq!(sessions.len(), 2);
        assert_eq!(sessions["$1"].clients.len(), 2);
        assert_eq!(sessions["$2"].count, 9);
        assert_eq!(sessions["$2"].settings.idle, 1.0);
    }
}
