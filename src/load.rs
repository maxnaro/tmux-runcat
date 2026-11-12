use crate::animation::SLEEP_POSE;
use crate::tmux::{Tmux, shell_quote};
use std::env;
use std::ffi::{OsStr, OsString};
use std::io;
use std::path::Path;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn context(explicit: Option<(&OsStr, &OsStr)>) -> io::Result<(OsString, OsString)> {
    if let Some((socket, pid)) = explicit {
        return Ok((socket.to_owned(), pid.to_owned()));
    }
    if let Ok(value) = env::var("TMUX") {
        let mut parts = value.rsplitn(3, ',');
        if let (Some(_), Some(pid), Some(socket)) = (parts.next(), parts.next(), parts.next()) {
            return Ok((socket.into(), pid.into()));
        }
    }
    let output = Command::new("tmux")
        .args(["display-message", "-p", "#{socket_path}\t#{pid}"])
        .output()?;
    let value = String::from_utf8_lossy(&output.stdout);
    let (socket, pid) = value
        .trim()
        .split_once('\t')
        .ok_or_else(|| io::Error::other("could not find tmux server"))?;
    Ok((socket.into(), pid.into()))
}

pub(crate) fn migrate_published_state(tmux: &Tmux, session: Option<&str>) -> io::Result<()> {
    let target = match session {
        Some(session) => vec!["-t", session],
        None => vec!["-g"],
    };
    let mut arguments = vec!["show-options"];
    arguments.extend(&target);
    let output = tmux.output(arguments)?;
    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let Some(name) = line.split_whitespace().next() else {
            continue;
        };
        let state = matches!(name, "@runcat-frame" | "@runcat-state");
        let lane = name
            .strip_prefix("@runcat-client-")
            .is_some_and(|pid| pid.parse::<u32>().is_ok());
        if !state && !lane {
            continue;
        }
        if state {
            let mut arguments = vec!["show-options", "-v"];
            arguments.extend(&target);
            arguments.push(name);
            let value = tmux.output(arguments)?;
            let value = String::from_utf8_lossy(&value.stdout);
            let mut arguments = vec!["set-environment", "-h"];
            arguments.extend(&target);
            arguments.extend([name, value.trim_end_matches('\n')]);
            tmux.execute(arguments)?;
        }
        // Attached clients receive fresh lanes; obsolete lanes need no copy.
        let mut arguments = vec!["set-option", "-qu"];
        arguments.extend(&target);
        arguments.push(name);
        tmux.execute(arguments)?;
    }
    Ok(())
}

pub fn run(plugin: &Path, explicit: Option<(&OsStr, &OsStr)>) -> io::Result<()> {
    if !plugin.is_dir() {
        return Err(io::Error::other("plugin directory does not exist"));
    }
    let (socket, pid) = context(explicit)?;
    let tmux = Tmux::new(&socket);
    let existing = tmux.output(["list-keys", "-T", "root", "Any"])?;
    let binding = String::from_utf8_lossy(&existing.stdout);
    if existing.status.success()
        && !existing.stdout.is_empty()
        && !binding.contains("@runcat-keys")
        && !binding.contains("TMUX_RUNCAT_KEYS")
    {
        return Err(io::Error::other(
            "root Any is already bound; remove that binding before loading tmux-runcat",
        ));
    }
    for (name, value) in [
        ("@runcat-idle", "2"),
        ("@runcat-min-fps", "3"),
        ("@runcat-max-fps", "0"),
        ("@runcat-size", "medium"),
        ("@runcat-skin", "classic"),
        ("@runcat-spin-chance", "0"),
        ("@runcat-roam", "off"),
        ("@runcat-color", "inherit"),
    ] {
        if !tmux.output(["show-options", "-gv", name])?.status.success() {
            tmux.execute(["set-option", "-g", name, value])?;
        }
    }
    migrate_published_state(&tmux, None)?;
    for (name, value) in [
        ("TMUX_RUNCAT_KEYS", "0"),
        ("@runcat-frame", SLEEP_POSE),
        ("@runcat-state", "sleep"),
    ] {
        if !tmux
            .output(["show-environment", "-gh", name])?
            .status
            .success()
        {
            tmux.execute(["set-environment", "-gh", name, value])?;
        }
    }
    // Unlike set-option, hidden environment updates do not redraw every pane.
    // The global default also works when loading before the first session.
    tmux.source("bind-key -T root Any if-shell -F '#{!=:#{mouse_x},}' {\n    send-keys -M\n} {\n    set-environment -hF TMUX_RUNCAT_KEYS '#{e|+:#{TMUX_RUNCAT_KEYS},1}'\n    send-keys\n}\n")?;
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(io::Error::other)?
        .as_nanos();
    let generation = format!("{}-{nanos}", std::process::id());
    tmux.execute(["set-option", "-g", "@runcat-generation", &generation])?;
    let executable = env::current_exe()?;
    let arguments = [
        executable.as_os_str(),
        OsStr::new("watch"),
        &socket,
        &pid,
        OsStr::new(&generation),
    ];
    let mut worker = OsString::new();
    for argument in arguments {
        if !worker.is_empty() {
            worker.push(" ");
        }
        worker.push(shell_quote(argument));
    }
    tmux.execute([OsStr::new("run-shell"), OsStr::new("-b"), &worker])
}
