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
const FORMAT: &str = "#{client_name}\t#{session_id}\t#{@runcat-keys}\t#{@runcat-idle}\t#{@runcat-min-fps}\t#{@runcat-max-fps}\t#{@runcat-size}\t#{@runcat-skin}";

struct Session {
    count: u64,
    clients: Vec<String>,
    settings: Settings,
}

fn parse_clients(lines: impl Iterator<Item = String>) -> HashMap<String, Session> {
    let mut sessions: HashMap<String, Session> = HashMap::new();
    for line in lines {
        let fields: Vec<_> = line.split('\t').collect();
        if fields.len() != 8 {
            continue;
        }
        sessions
            .entry(fields[1].to_owned())
            .or_insert_with(|| Session {
                count: fields[2].parse().unwrap_or(0),
                clients: Vec::new(),
                settings: Settings::parse(fields[3], fields[4], fields[5], fields[6], fields[7]),
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
    let list_clients = format!("list-clients -F '{FORMAT}'");
    loop {
        let output = tmux.output([
            // A fresh server may still be processing its startup config and
            // have no session yet. Query the global option without a target.
            "show-options",
            "-gv",
            "@runcat-generation",
            ";",
            // list-clients also requires a session, even without -t. The
            // format-only conditional can safely run before the first one.
            "if-shell",
            "-F",
            "#{session_id}",
            &list_clients,
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
        let mut next_update = now + POLL.as_secs_f64();
        let mut update = Vec::new();
        for (session, activity) in sessions {
            let animation = animations
                .entry(session.clone())
                .or_insert_with(|| Animation::new(activity.count, now));
            let pose = animation
                .update(activity.count, now, activity.settings)
                .to_owned();
            next_update = next_update.min(animation.next_update());
            if published.get(&session).is_some_and(|value| value == &pose) {
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
                pose.clone(),
                ";".to_owned(),
                "set-option".to_owned(),
                "-t".to_owned(),
                session.clone(),
                "@runcat-state".to_owned(),
                animation.state().to_owned(),
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
            published.insert(session, pose);
        }
        if !update.is_empty() && !tmux.output(update)?.status.success() {
            published.clear();
        }
        // Poll input at least every 50 ms, waking earlier for fast frames.
        // Time spent querying/redrawing tmux counts toward the deadline.
        let delay = next_update - start.elapsed().as_secs_f64();
        if delay > 0.0 {
            thread::sleep(Duration::from_secs_f64(delay));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn clients_are_grouped_by_session_with_independent_counts() {
        let sessions = parse_clients(
            [
                "/dev/pts/1\t$1\t4\t2\t3\t12\tmedium\tclassic",
                "/dev/pts/2\t$1\t4\t2\t3\t12\tmedium\tclassic",
                "/dev/pts/3\t$2\t9\t1\t4\t8\tlarge\tpet-cats",
                "invalid",
            ]
            .into_iter()
            .map(str::to_owned),
        );
        assert_eq!(sessions.len(), 2);
        assert_eq!(sessions["$1"].clients.len(), 2);
        assert_eq!(sessions["$2"].count, 9);
        assert_eq!(sessions["$2"].settings.idle, 1.0);
        assert_eq!(
            sessions["$2"].settings.skin,
            crate::animation::Skin::PetCats
        );
        assert_eq!(
            sessions["$2"].settings.size,
            crate::animation::CatSize::Large
        );
    }
}
