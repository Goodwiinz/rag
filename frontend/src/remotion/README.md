# ProductDemoLayout — Remotion product demo

A 15s (450 frames @ 30fps, 1920×1080) premium SaaS demo video.

| Scene | Frames | Content |
|-------|--------|---------|
| Intro | 0–90 | Grid/gradient backdrop, spring slide-up title, "Feature Spotlight" tag |
| Showcase | 90–360 | Browser window opens with a spring bounce; mock SaaS UI (sidebar/header/stat cards/animated bar chart); camera zooms toward the chart (~frame 180 absolute), then the window slides out |
| Outro | 360–450 | Logo placeholder, slogan, CTA URL — staggered spring entrance |

## Files
- `ProductDemoLayout.tsx` — the composition component + scenes (single file).
- `Root.tsx` — `<Composition id="ProductDemoLayout">` registration.
- `index.ts` — `registerRoot(RemotionRoot)` entry.
- `remotion.config.ts` — enables Tailwind in the Remotion bundler.

> Remotion is **not yet a dependency** of this app. The steps below add it.

## Install
```bash
cd frontend
pnpm add remotion @remotion/cli @remotion/tailwind
```

## Tailwind
Ensure your `tailwind.config.{js,ts}` `content` includes the Remotion sources:
```js
content: ['./src/remotion/**/*.{ts,tsx}', /* …existing globs… */]
```
The bundler hookup lives in `remotion.config.ts` (move it to the project root if
you run the CLI from there — the CLI loads `remotion.config.ts` from the cwd).

## Preview / render
Add scripts to `package.json`:
```json
{
  "scripts": {
    "video:studio": "remotion studio src/remotion/index.ts",
    "video:render": "remotion render src/remotion/index.ts ProductDemoLayout out/product-demo.mp4"
  }
}
```
```bash
pnpm video:studio    # interactive preview
pnpm video:render    # → out/product-demo.mp4
```

## Plugging into an existing Remotion root
If you already have a root, drop the composition in instead of using `Root.tsx`:
```tsx
import { ProductDemoLayout, VIDEO_DURATION_IN_FRAMES, VIDEO_FPS, VIDEO_WIDTH, VIDEO_HEIGHT } from './remotion/ProductDemoLayout';

<Composition
  id="ProductDemoLayout"
  component={ProductDemoLayout}
  durationInFrames={VIDEO_DURATION_IN_FRAMES}
  fps={VIDEO_FPS}
  width={VIDEO_WIDTH}
  height={VIDEO_HEIGHT}
/>
```

## Notes
- All entrance motion uses Remotion `spring` (`{ damping: 12, mass: 0.5, stiffness: 100 }`); camera/exit moves use `interpolate` with clamped, eased ranges.
- Static layout/typography is Tailwind; per-frame values (transform/opacity) are inline styles by necessity.
- Strict TypeScript, no `any`.
