use std::collections::VecDeque;

pub const SLEEP_POSE: &str = "\u{effa}\u{effb}";
#[cfg(test)]
const SLEEP_POSES: [&str; 3] = [SLEEP_POSE, "\u{effc}\u{effd}", "\u{effe}\u{efff}"];
const SLEEP_STEP_SECONDS: f64 = 0.75;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum CatSize {
    Small,
    #[default]
    Medium,
    Large,
}

impl CatSize {
    pub fn parse(value: &str) -> Self {
        match value.trim().to_ascii_lowercase().as_str() {
            "small" | "1" => Self::Small,
            "large" | "3" => Self::Large,
            _ => Self::Medium,
        }
    }

    fn pose(self, frame: u32, sleeping: bool) -> String {
        let index = if sleeping { 5 + frame } else { frame };
        let points: Vec<u32> = match self {
            Self::Small => vec![0xf600 + index],
            Self::Medium if sleeping => vec![0xeffa + 2 * frame, 0xeffb + 2 * frame],
            Self::Medium => vec![0xeff0 + frame, 0xeff5 + frame],
            Self::Large => (0..3).map(|half| 0xf620 + 3 * index + half).collect(),
        };
        points
            .into_iter()
            .map(|point| char::from_u32(point).unwrap())
            .collect()
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Settings {
    pub idle: f64,
    pub minimum: f64,
    pub maximum: Option<f64>,
    pub size: CatSize,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            idle: 2.0,
            minimum: 3.0,
            maximum: None,
            size: CatSize::Medium,
        }
    }
}

impl Settings {
    pub fn parse(idle: &str, minimum: &str, maximum: &str, size: &str) -> Self {
        fn number(value: &str, fallback: f64, low: f64, high: f64) -> f64 {
            value
                .parse::<f64>()
                .ok()
                .filter(|v| v.is_finite())
                .unwrap_or(fallback)
                .clamp(low, high)
        }
        let minimum = number(minimum, 3.0, 1.0, 20.0);
        Self {
            idle: number(idle, 2.0, 0.1, 3600.0),
            minimum,
            maximum: maximum
                .parse::<f64>()
                .ok()
                .filter(|value| value.is_finite() && *value > 0.0)
                .map(|value| value.max(minimum)),
            size: CatSize::parse(size),
        }
    }
}

pub struct Animation {
    count: u64,
    last_input: f64,
    samples: VecDeque<(f64, u64)>,
    fps: f64,
    frame: u32,
    phase: f64,
    updated: f64,
    pose: String,
    sleep_since: Option<f64>,
    sleep_step: usize,
}

impl Animation {
    pub fn new(count: u64, now: f64) -> Self {
        Self {
            count,
            last_input: f64::NEG_INFINITY,
            samples: VecDeque::new(),
            fps: 3.0,
            frame: 4,
            phase: 0.0,
            updated: now,
            pose: SLEEP_POSE.to_owned(),
            sleep_since: Some(now),
            sleep_step: 0,
        }
    }

    pub fn update(&mut self, count: u64, now: f64, settings: Settings) -> &str {
        let elapsed = (now - self.updated).max(0.0);
        self.updated = now;
        let delta = count.saturating_sub(self.count);
        self.count = count;
        if delta > 0 {
            self.last_input = now;
            self.samples.push_back((now, delta));
        }
        while self.samples.front().is_some_and(|(at, _)| now - at >= 1.0) {
            self.samples.pop_front();
        }
        if now - self.last_input >= settings.idle {
            self.samples.clear();
            self.fps = settings.minimum;
            self.phase = 0.0;
            let started = *self.sleep_since.get_or_insert(now);
            self.sleep_step = ((now - started) / SLEEP_STEP_SECONDS) as usize % 4;
            self.pose = settings.size.pose([0, 1, 2, 1][self.sleep_step], true);
            return &self.pose;
        }

        let was_sleeping = self.sleep_since.take().is_some();

        let rate: f64 = self.samples.iter().map(|(_, count)| *count as f64).sum();
        let target = settings.minimum + rate * 0.75;
        let smoothing = 1.0 - 0.15_f64.powf(elapsed / 0.3);
        let previous_fps = self.fps;
        self.fps = (self.fps + (target - self.fps) * smoothing).max(settings.minimum);
        if let Some(maximum) = settings.maximum {
            self.fps = self.fps.min(maximum);
        }
        if was_sleeping {
            self.frame = (self.frame + 1) % 5;
            self.phase = 0.0;
        } else {
            // Keep fractional progress between polls, and advance by elapsed
            // animation time if a slow redraw skipped one or more frames.
            let frames = self.phase + elapsed * (previous_fps + self.fps) * 0.5;
            self.frame = (self.frame + (frames % 5.0) as u32) % 5;
            self.phase = frames.fract();
        }
        self.pose = settings.size.pose(self.frame, false);
        &self.pose
    }

    pub fn next_update(&self) -> f64 {
        if let Some(started) = self.sleep_since {
            let step = ((self.updated - started) / SLEEP_STEP_SECONDS).floor();
            started + (step + 1.0) * SLEEP_STEP_SECONDS
        } else {
            self.updated + (1.0 - self.phase) / self.fps
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sleep_wake_and_two_second_timeout() {
        let mut cat = Animation::new(0, 0.0);
        let settings = Settings::default();
        assert_eq!(cat.update(0, 0.0, settings), SLEEP_POSE);
        assert_ne!(cat.update(1, 0.1, settings), SLEEP_POSE);
        assert_ne!(cat.update(1, 2.09, settings), SLEEP_POSE);
        assert_eq!(cat.update(1, 2.11, settings), SLEEP_POSE);
    }

    #[test]
    fn typing_accelerates_without_a_speed_limit() {
        let (mut slow, mut fast) = (Animation::new(0, 0.0), Animation::new(0, 0.0));
        let settings = Settings::default();
        for step in 1..=20 {
            slow.update(1 + step / 6, step as f64 * 0.05, settings);
            fast.update(step * 4, step as f64 * 0.05, settings);
        }
        assert!(fast.fps > slow.fps * 2.0);
        assert!(fast.fps > 50.0);
        assert!(fast.next_update() - 1.0 < 0.02);
    }

    #[test]
    fn fast_typing_produces_more_than_twenty_frames_per_second() {
        let mut cat = Animation::new(0, 0.0);
        let mut changes = 0;
        let mut previous = String::new();
        for step in 1..=3000 {
            let pose = cat.update(step / 10, step as f64 * 0.001, Settings::default());
            if step > 2000 && pose != previous {
                changes += 1;
            }
            previous = pose.to_owned();
        }
        assert!(
            changes > 60,
            "only {changes} frame changes during fast typing"
        );
    }

    #[test]
    fn explicit_limits_still_apply_and_can_be_removed_live() {
        let mut cat = Animation::new(0, 0.0);
        let capped = Settings::parse("2", "3", "12", "medium");
        for step in 1..=20 {
            cat.update(step * 4, step as f64 * 0.05, capped);
        }
        assert!(cat.fps <= 12.0);
        cat.update(84, 1.05, Settings::default());
        assert!(cat.fps > 12.0);
        assert_eq!(
            Settings::parse("2", "3", "120", "medium").maximum,
            Some(120.0)
        );
        for maximum in ["0", "unlimited", "NaN", "inf", "bad", "-1"] {
            assert_eq!(Settings::parse("2", "3", maximum, "medium").maximum, None);
        }
    }

    #[test]
    fn delayed_updates_preserve_frame_progress() {
        let mut cat = Animation::new(0, 0.0);
        let settings = Settings::parse("2", "10", "10", "medium");
        cat.update(1, 0.0, settings);
        assert_eq!(
            cat.update(1, 0.35, settings),
            CatSize::Medium.pose(3, false)
        );
        assert!((cat.next_update() - 0.4).abs() < 0.000_001);
    }

    #[test]
    fn slows_smoothly_before_sleeping() {
        let mut cat = Animation::new(0, 0.0);
        let settings = Settings::default();
        for step in 1..=20 {
            cat.update(step, step as f64 * 0.05, settings);
        }
        let peak = cat.fps;
        for step in 21..=50 {
            cat.update(20, step as f64 * 0.05, settings);
        }
        assert!(cat.fps < peak);
        assert_ne!(cat.pose, SLEEP_POSE);
    }

    #[test]
    fn counter_reset_does_not_create_activity() {
        let mut cat = Animation::new(100, 0.0);
        assert_eq!(cat.update(0, 0.1, Settings::default()), SLEEP_POSE);
        assert_ne!(cat.update(1, 0.2, Settings::default()), SLEEP_POSE);
    }

    #[test]
    fn sessions_have_independent_activity() {
        let (mut first, mut second) = (Animation::new(0, 0.0), Animation::new(0, 0.0));
        assert_ne!(first.update(1, 0.1, Settings::default()), SLEEP_POSE);
        assert_eq!(second.update(0, 0.1, Settings::default()), SLEEP_POSE);
    }

    #[test]
    fn settings_validate_and_apply_live() {
        let settings = Settings::parse("NaN", "bad", "-1", "invalid");
        assert_eq!(
            (settings.idle, settings.minimum, settings.maximum),
            (2.0, 3.0, None)
        );
        let settings = Settings::parse("0.5", "8", "20", "medium");
        let mut cat = Animation::new(0, 0.0);
        cat.update(1, 0.1, settings);
        assert!(cat.fps >= 8.0);
        assert_eq!(cat.update(1, 0.61, settings), SLEEP_POSE);
    }

    #[test]
    fn sleeping_breathes_with_a_fixed_width_and_wakes_immediately() {
        let mut cat = Animation::new(0, 0.0);
        let settings = Settings::default();
        let expected = [0, 1, 2, 1, 0];
        for (step, frame) in expected.into_iter().enumerate() {
            let pose = cat.update(0, step as f64 * 0.75, settings);
            assert_eq!(pose, SLEEP_POSES[frame]);
            assert_eq!(pose.chars().count(), 2);
        }
        let pose = cat.update(1, 3.1, settings);
        assert_ne!(pose, SLEEP_POSE);
        assert_eq!(pose.chars().count(), 2);
    }

    #[test]
    fn all_sizes_keep_their_width_while_running_and_breathing() {
        for (size, width) in [
            (CatSize::Small, 1),
            (CatSize::Medium, 2),
            (CatSize::Large, 3),
        ] {
            let mut cat = Animation::new(0, 0.0);
            let settings = Settings {
                size,
                ..Settings::default()
            };
            for step in 0..4 {
                assert_eq!(
                    cat.update(0, step as f64 * 0.75, settings).chars().count(),
                    width
                );
            }
            assert_eq!(cat.update(1, 3.1, settings).chars().count(), width);
        }
    }

    #[test]
    fn size_updates_immediately_without_resetting_activity() {
        let mut cat = Animation::new(0, 0.0);
        cat.update(1, 0.1, Settings::default());
        let large = Settings {
            size: CatSize::Large,
            ..Settings::default()
        };
        assert_eq!(cat.update(1, 0.11, large).chars().count(), 3);
        let small = Settings {
            size: CatSize::Small,
            ..Settings::default()
        };
        assert_eq!(cat.update(1, 0.12, small).chars().count(), 1);
        assert_eq!(CatSize::parse(" LARGE "), CatSize::Large);
        assert_eq!(CatSize::parse("1"), CatSize::Small);
        assert_eq!(CatSize::parse("2"), CatSize::Medium);
    }
}
