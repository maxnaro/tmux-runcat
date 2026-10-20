use std::collections::VecDeque;

pub const SLEEP_POSE: &str = "\u{effa}\u{effb}";
const SLEEP_POSES: [&str; 3] = [SLEEP_POSE, "\u{effc}\u{effd}", "\u{effe}\u{efff}"];
const SLEEP_STEP_SECONDS: f64 = 0.75;

#[derive(Clone, Copy, Debug)]
pub struct Settings {
    pub idle: f64,
    pub minimum: f64,
    pub maximum: f64,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            idle: 2.0,
            minimum: 3.0,
            maximum: 12.0,
        }
    }
}

impl Settings {
    pub fn parse(idle: &str, minimum: &str, maximum: &str) -> Self {
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
            maximum: number(maximum, 12.0, minimum, 20.0),
        }
    }
}

pub struct Animation {
    count: u64,
    last_input: f64,
    samples: VecDeque<(f64, u64)>,
    fps: f64,
    frame: u32,
    next_frame: f64,
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
            frame: 0,
            next_frame: now,
            updated: now,
            pose: SLEEP_POSE.to_owned(),
            sleep_since: None,
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
            self.next_frame = now;
            let started = *self.sleep_since.get_or_insert(now);
            self.sleep_step = ((now - started) / SLEEP_STEP_SECONDS) as usize % 4;
            self.pose = SLEEP_POSES[[0, 1, 2, 1][self.sleep_step]].to_owned();
            return &self.pose;
        }

        let was_sleeping = self.sleep_since.take().is_some();

        let rate: f64 = self.samples.iter().map(|(_, count)| *count as f64).sum();
        let target = (settings.minimum + rate * 0.75).min(settings.maximum);
        let smoothing = 1.0 - 0.15_f64.powf(elapsed / 0.3);
        self.fps =
            (self.fps + (target - self.fps) * smoothing).clamp(settings.minimum, settings.maximum);
        if was_sleeping {
            self.next_frame = now;
        }
        if now >= self.next_frame {
            self.pose = [
                char::from_u32(0xeff0 + self.frame).unwrap(),
                char::from_u32(0xeff5 + self.frame).unwrap(),
            ]
            .iter()
            .collect();
            self.frame = (self.frame + 1) % 5;
            self.next_frame = now + 1.0 / self.fps;
        }
        &self.pose
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
    fn typing_accelerates_with_a_speed_limit() {
        let (mut slow, mut fast) = (Animation::new(0, 0.0), Animation::new(0, 0.0));
        let settings = Settings::default();
        for step in 1..=20 {
            slow.update(1 + step / 6, step as f64 * 0.05, settings);
            fast.update(step, step as f64 * 0.05, settings);
        }
        assert!(fast.fps > slow.fps * 1.5);
        assert!(fast.fps <= settings.maximum);
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
        let settings = Settings::parse("NaN", "bad", "-1");
        assert_eq!(
            (settings.idle, settings.minimum, settings.maximum),
            (2.0, 3.0, 3.0)
        );
        let settings = Settings::parse("0.5", "8", "20");
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
}
