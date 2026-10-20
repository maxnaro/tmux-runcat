use crate::animation::CatSize;
use std::sync::OnceLock;

const BASE: u32 = 0xf700;
const XLARGE_BASE: u32 = 0xe400;
const REST_ACTIONS: [&str; 6] = ["lick-paw", "idle", "itch", "lick-body", "meow", "sit"];

#[derive(Clone, Copy)]
struct Clip {
    name: &'static str,
    first: u32,
    frames: u32,
}

fn clip(name: &str) -> Clip {
    static CLIPS: OnceLock<Vec<Clip>> = OnceLock::new();
    let clips = CLIPS.get_or_init(|| {
        let mut first = 0;
        include_str!("../fonts/pet-cats/animations.tsv")
            .lines()
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .map(|line| {
                let fields: Vec<_> = line.split('\t').collect();
                let frames = fields[2].parse().expect("valid bundled Pet Cats manifest");
                let clip = Clip {
                    name: fields[0],
                    first,
                    frames,
                };
                first += frames;
                clip
            })
            .collect()
    });
    *clips
        .iter()
        .find(|clip| clip.name == name)
        .expect("known Pet Cats animation")
}

pub fn pose(size: CatSize, action: &str, frame: u32) -> String {
    let clip = clip(action);
    let frame = clip.first + frame % clip.frames;
    if size == CatSize::XLarge {
        return (0..4)
            .map(|half| char::from_u32(XLARGE_BASE + 4 * frame + half).unwrap())
            .collect();
    }
    let (cells, offset) = match size {
        CatSize::Small => (1, 0),
        CatSize::Medium => (2, 1),
        CatSize::Large => (3, 3),
        CatSize::XLarge => unreachable!(),
    };
    let first = BASE + 6 * frame + offset;
    (0..cells)
        .map(|half| char::from_u32(first + half).unwrap())
        .collect()
}

pub struct Activity {
    pub now: f64,
    pub elapsed: f64,
    pub last_input: f64,
    pub pressed: bool,
    pub rate: f64,
    pub idle: f64,
    pub fps: f64,
    pub previous_fps: f64,
    pub size: CatSize,
}

pub struct Pet {
    pub action: &'static str,
    pub deadline: f64,
    started: f64,
    wake_since: Option<f64>,
    rest_cycle: usize,
    frame: u32,
    phase: f64,
}

impl Pet {
    pub fn new(now: f64) -> Self {
        Self {
            action: "sleep",
            deadline: now,
            started: now,
            wake_since: None,
            rest_cycle: 0,
            frame: 0,
            phase: 0.0,
        }
    }

    pub fn update(&mut self, activity: Activity) -> String {
        let Activity {
            now,
            elapsed,
            last_input,
            pressed,
            rate,
            idle,
            fps,
            previous_fps,
            size,
        } = activity;
        let age = now - last_input;
        let pause = 0.35_f64.min(idle * 0.2);
        let lying = 0.8_f64.min(idle * 0.4);
        let waking = 0.65_f64.min(idle * 0.4);
        if pressed && matches!(self.action, "sleep" | "deep-sleep") {
            self.wake_since = Some(now);
        }

        let (action, started) = if age >= idle {
            if last_input.is_finite() && age >= idle + 30.0 {
                ("deep-sleep", last_input + idle + 30.0)
            } else {
                (
                    "sleep",
                    if last_input.is_finite() {
                        last_input + idle
                    } else {
                        now
                    },
                )
            }
        } else if let Some(wake) = self.wake_since.filter(|wake| now - wake < waking) {
            ("stretch", wake)
        } else if age >= idle - lying {
            ("lie-down", last_input + idle - lying)
        } else if age >= pause {
            if !REST_ACTIONS.contains(&self.action) {
                self.rest_cycle = self.rest_cycle.wrapping_add(1);
            }
            (
                REST_ACTIONS[self.rest_cycle.wrapping_sub(1) % REST_ACTIONS.len()],
                last_input + pause,
            )
        } else if rate >= 8.0 || (self.action == "run" && rate >= 6.0) {
            ("run", now)
        } else {
            ("walk", now)
        };

        let changed = action != self.action;
        if changed {
            self.action = action;
            self.started = started;
            self.frame = 0;
            self.phase = 0.0;
        }
        let clip = clip(action);
        let time = (now - self.started).max(0.0);
        if matches!(action, "walk" | "run") {
            if !changed {
                let frames = self.phase + elapsed * (previous_fps + fps) * 0.5;
                self.frame = (self.frame + (frames % clip.frames as f64) as u32) % clip.frames;
                self.phase = frames.fract();
            }
            self.deadline = now + (1.0 - self.phase) / fps;
        } else if matches!(action, "sleep" | "deep-sleep") {
            let step = (time / 0.75).floor();
            self.frame = [0, 1, 2, 1][step as usize % 4];
            self.deadline = self.started + (step + 1.0) * 0.75;
        } else {
            let (speed, once) = match action {
                "stretch" => (clip.frames as f64 / waking, true),
                "lie-down" => (clip.frames as f64 / lying, true),
                "meow" => (8.0, true),
                "itch" => (6.0, false),
                "sit" => (1.0, false),
                _ => (10.0, false),
            };
            let step = (time * speed).floor();
            self.frame = if once {
                (step as u32).min(clip.frames - 1)
            } else {
                (step % clip.frames as f64) as u32
            };
            self.deadline = self.started + (step + 1.0) / speed;
        }
        pose(size, action, self.frame)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_clips_share_the_font_manifest_and_keep_the_selected_width() {
        for name in [
            "idle",
            "walk",
            "run",
            "meow",
            "lie-down",
            "itch",
            "sleep",
            "deep-sleep",
            "sit",
            "lick-paw",
            "lick-body",
            "stretch",
        ] {
            let clip = clip(name);
            for frame in 0..clip.frames {
                for (size, width) in [
                    (CatSize::Small, 1),
                    (CatSize::Medium, 2),
                    (CatSize::Large, 3),
                    (CatSize::XLarge, 4),
                ] {
                    let text = pose(size, name, frame);
                    assert_eq!(text.chars().count(), width);
                    let range = if size == CatSize::XLarge {
                        0xe400..0xe518
                    } else {
                        0xf700..0xf8a4
                    };
                    assert!(text.chars().all(|value| range.contains(&(value as u32))));
                }
            }
        }
        assert_eq!(clip("stretch").first + clip("stretch").frames, 70);
    }
}
