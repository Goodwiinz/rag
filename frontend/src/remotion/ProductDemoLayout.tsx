/**
 * ProductDemoLayout — a 15s (450f @ 30fps, 1920x1080) premium SaaS product
 * demo built with Remotion.
 *
 * Scenes (driven by <Sequence>, so every child's `useCurrentFrame()` is
 * relative to its own scene start):
 *   1. Intro / hook            frames   0 –  90
 *   2. Product UI showcase     frames  90 – 360  (window opens, camera zoom)
 *   3. Outro / call to action  frames 360 – 450
 *
 * Styling: Tailwind for static layout/typography, inline styles only for
 * animated values (transform/opacity) — those are per-frame and cannot be
 * expressed as static utility classes. Tailwind in Remotion is enabled via
 * `@remotion/tailwind` (see ./README.md).
 */

import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from 'remotion';

// ---------------------------------------------------------------------------
// Shared constants
// ---------------------------------------------------------------------------

/** Organic, snappy spring used for every UI entrance. */
const SPRING_CONFIG = { damping: 12, mass: 0.5, stiffness: 100 } as const;

export const VIDEO_FPS = 30;
export const VIDEO_WIDTH = 1920;
export const VIDEO_HEIGHT = 1080;
export const VIDEO_DURATION_IN_FRAMES = 450;

const SCENE_1_DURATION = 90; // frames 0–90
const SCENE_2_DURATION = 270; // frames 90–360
const SCENE_3_DURATION = 90; // frames 360–450

// ---------------------------------------------------------------------------
// Background — subtle gradient + grid
// ---------------------------------------------------------------------------

const GridBackground: React.FC = () => (
  <AbsoluteFill
    className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"
    style={{
      backgroundImage:
        'linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px),' +
        'linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)',
      backgroundSize: '64px 64px',
    }}
  >
    {/* Soft radial vignette to pull focus to the center. */}
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(ellipse at center, rgba(56,189,248,0.10), transparent 60%)',
      }}
    />
  </AbsoluteFill>
);

// ---------------------------------------------------------------------------
// Scene 1 — Intro / hook
// ---------------------------------------------------------------------------

const SceneIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Title: spring-driven slide-up + fade.
  const titleSpring = spring({ frame, fps, config: SPRING_CONFIG });
  const titleY = interpolate(titleSpring, [0, 1], [48, 0]);
  const titleOpacity = interpolate(titleSpring, [0, 1], [0, 1]);

  // Subtitle tag: scales up slightly, delayed after the title.
  const tagSpring = spring({
    frame: frame - 16,
    fps,
    config: SPRING_CONFIG,
  });
  const tagScale = interpolate(tagSpring, [0, 1], [0.8, 1]);
  const tagOpacity = interpolate(tagSpring, [0, 1], [0, 1]);

  return (
    <AbsoluteFill>
      <GridBackground />
      <AbsoluteFill className="flex flex-col items-center justify-center gap-8">
        <div
          className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-400/10 px-5 py-2"
          style={{
            opacity: tagOpacity,
            transform: `scale(${tagScale})`,
          }}
        >
          <span className="h-2 w-2 rounded-full bg-sky-400" />
          <span className="text-lg font-semibold uppercase tracking-[0.3em] text-sky-300">
            Feature Spotlight
          </span>
        </div>

        <h1
          className="max-w-5xl text-center text-8xl font-bold leading-tight tracking-tight text-white"
          style={{
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
          }}
        >
          Ship faster with{' '}
          <span className="bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
            Nous Analytics
          </span>
        </h1>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Scene 2 — Product UI showcase
// ---------------------------------------------------------------------------

interface AnimatedBarProps {
  /** Stagger index — later bars rise slightly after earlier ones. */
  index: number;
  /** Target height in px once fully sprung. */
  targetHeight: number;
}

const AnimatedBar: React.FC<AnimatedBarProps> = ({ index, targetHeight }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Bars start rising shortly after the window opens (~frame 24), staggered.
  const progress = spring({
    frame: frame - 24 - index * 5,
    fps,
    config: SPRING_CONFIG,
  });
  const height = interpolate(progress, [0, 1], [0, targetHeight]);

  return (
    <div
      className="w-10 rounded-t-md bg-gradient-to-t from-sky-500 to-indigo-400"
      style={{ height }}
    />
  );
};

const WindowControls: React.FC = () => (
  <div className="flex items-center gap-2">
    <span className="h-3.5 w-3.5 rounded-full bg-red-400" />
    <span className="h-3.5 w-3.5 rounded-full bg-yellow-400" />
    <span className="h-3.5 w-3.5 rounded-full bg-green-400" />
  </div>
);

/** The mocked SaaS app inside the window: sidebar + header + content. */
const AppMock: React.FC = () => {
  const barHeights = [120, 180, 96, 220, 160, 240, 140];

  return (
    <div className="flex h-full w-full bg-slate-950 text-slate-200">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col gap-6 border-r border-white/5 bg-slate-900/60 p-6">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-sky-400 to-indigo-500" />
          <div className="h-3 w-24 rounded bg-white/20" />
        </div>
        <nav className="flex flex-col gap-3">
          {['Overview', 'Reports', 'Cohorts', 'Settings'].map((label, i) => (
            <div
              key={label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 ${
                i === 1 ? 'bg-sky-400/15 text-sky-300' : 'text-slate-400'
              }`}
            >
              <span className="h-4 w-4 rounded bg-current opacity-50" />
              <span className="text-sm font-medium">{label}</span>
            </div>
          ))}
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-white/5 px-8 py-5">
          <div className="flex flex-col gap-2">
            <div className="h-5 w-48 rounded bg-white/25" />
            <div className="h-3 w-32 rounded bg-white/10" />
          </div>
          <div className="flex items-center gap-3">
            <div className="h-9 w-24 rounded-lg bg-white/5" />
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-sky-400 to-indigo-500" />
          </div>
        </header>

        {/* Content */}
        <main className="flex flex-1 flex-col gap-6 p-8">
          {/* Stat cards */}
          <div className="grid grid-cols-3 gap-6">
            {[
              { label: 'Active users', value: '24,815' },
              { label: 'Conversion', value: '6.42%' },
              { label: 'Revenue', value: '$182k' },
            ].map((card) => (
              <div
                key={card.label}
                className="flex flex-col gap-3 rounded-xl border border-white/5 bg-slate-900/70 p-5"
              >
                <span className="text-sm text-slate-400">{card.label}</span>
                <span className="text-3xl font-semibold text-white">
                  {card.value}
                </span>
              </div>
            ))}
          </div>

          {/* Chart panel — id used as the camera focal target. */}
          <div
            id="focal-chart"
            className="flex flex-1 flex-col gap-4 rounded-xl border border-white/5 bg-slate-900/70 p-6"
          >
            <div className="flex items-center justify-between">
              <span className="text-base font-medium text-slate-200">
                Weekly engagement
              </span>
              <span className="rounded-full bg-emerald-400/15 px-3 py-1 text-sm font-semibold text-emerald-300">
                +18.2%
              </span>
            </div>
            <div className="flex flex-1 items-end gap-4">
              {barHeights.map((h, i) => (
                <AnimatedBar key={i} index={i} targetHeight={h} />
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

const SceneShowcase: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Window opens with a spring bounce from slightly under full size.
  const openSpring = spring({
    frame,
    fps,
    config: SPRING_CONFIG,
    durationInFrames: 30,
  });
  const openScale = interpolate(openSpring, [0, 1], [0.86, 1]);
  const openOpacity = interpolate(openSpring, [0, 1], [0, 1]);

  // Camera: zoom toward the chart panel around the scene midpoint, then exit
  // (slide down + scale out) over the scene's final 30 frames.
  const zoom = interpolate(frame, [80, 130], [1, 1.22], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const panY = interpolate(frame, [80, 130], [0, 90], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  const exitStart = SCENE_2_DURATION - 30; // 240
  const exitY = interpolate(frame, [exitStart, SCENE_2_DURATION], [0, 260], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  const exitScale = interpolate(
    frame,
    [exitStart, SCENE_2_DURATION],
    [1, 0.92],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.in(Easing.cubic),
    }
  );
  const exitOpacity = interpolate(
    frame,
    [exitStart, SCENE_2_DURATION],
    [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <AbsoluteFill>
      <GridBackground />
      {/* Camera rig */}
      <AbsoluteFill
        className="flex items-center justify-center"
        style={{ transform: `scale(${zoom}) translateY(${-panY}px)` }}
      >
        {/* Window */}
        <div
          className="flex h-[820px] w-[1440px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-2xl"
          style={{
            opacity: openOpacity * exitOpacity,
            transform: `scale(${openScale * exitScale}) translateY(${exitY}px)`,
            boxShadow: '0 40px 120px -20px rgba(2,6,23,0.8)',
          }}
        >
          {/* Title bar */}
          <div className="flex items-center gap-4 border-b border-white/5 bg-slate-800/80 px-6 py-4">
            <WindowControls />
            <div className="mx-auto flex items-center gap-2 rounded-md bg-slate-900/70 px-4 py-1.5">
              <span className="h-3 w-3 rounded-full bg-emerald-400" />
              <span className="text-sm text-slate-400">
                app.nousanalytics.com/dashboard
              </span>
            </div>
          </div>
          <div className="flex-1">
            <AppMock />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Scene 3 — Outro / call to action
// ---------------------------------------------------------------------------

const SceneOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoSpring = spring({ frame, fps, config: SPRING_CONFIG });
  const logoScale = interpolate(logoSpring, [0, 1], [0.7, 1]);
  const logoOpacity = interpolate(logoSpring, [0, 1], [0, 1]);

  const sloganSpring = spring({
    frame: frame - 12,
    fps,
    config: SPRING_CONFIG,
  });
  const sloganY = interpolate(sloganSpring, [0, 1], [28, 0]);
  const sloganOpacity = interpolate(sloganSpring, [0, 1], [0, 1]);

  const ctaSpring = spring({ frame: frame - 24, fps, config: SPRING_CONFIG });
  const ctaScale = interpolate(ctaSpring, [0, 1], [0.85, 1]);
  const ctaOpacity = interpolate(ctaSpring, [0, 1], [0, 1]);

  return (
    <AbsoluteFill>
      <GridBackground />
      <AbsoluteFill className="flex flex-col items-center justify-center gap-10">
        {/* Logo placeholder */}
        <div
          className="flex items-center gap-4"
          style={{ opacity: logoOpacity, transform: `scale(${logoScale})` }}
        >
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-indigo-500 text-4xl font-black text-white shadow-lg">
            N
          </div>
          <span className="text-5xl font-bold tracking-tight text-white">
            Nous Analytics
          </span>
        </div>

        <p
          className="max-w-3xl text-center text-3xl font-medium text-slate-300"
          style={{
            opacity: sloganOpacity,
            transform: `translateY(${sloganY}px)`,
          }}
        >
          Turn product data into decisions — in real time.
        </p>

        <div
          className="rounded-full bg-white px-10 py-4 text-2xl font-semibold text-slate-950 shadow-xl"
          style={{ opacity: ctaOpacity, transform: `scale(${ctaScale})` }}
        >
          Start free → nousanalytics.com
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

export const ProductDemoLayout: React.FC = () => {
  return (
    <AbsoluteFill className="bg-slate-950 font-sans">
      <Sequence durationInFrames={SCENE_1_DURATION} name="Intro">
        <SceneIntro />
      </Sequence>

      <Sequence
        from={SCENE_1_DURATION}
        durationInFrames={SCENE_2_DURATION}
        name="Showcase"
      >
        <SceneShowcase />
      </Sequence>

      <Sequence
        from={SCENE_1_DURATION + SCENE_2_DURATION}
        durationInFrames={SCENE_3_DURATION}
        name="Outro"
      >
        <SceneOutro />
      </Sequence>
    </AbsoluteFill>
  );
};
