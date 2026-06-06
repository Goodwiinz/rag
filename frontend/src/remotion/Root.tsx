/**
 * Remotion root. Point your entry (`remotion/index.ts` →
 * `registerRoot(RemotionRoot)`) at this file. The composition id
 * "ProductDemoLayout" is what you render/preview from the Studio or CLI.
 */

import React from 'react';
import { Composition } from 'remotion';
import {
  ProductDemoLayout,
  VIDEO_DURATION_IN_FRAMES,
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
} from './ProductDemoLayout';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ProductDemoLayout"
      component={ProductDemoLayout}
      durationInFrames={VIDEO_DURATION_IN_FRAMES}
      fps={VIDEO_FPS}
      width={VIDEO_WIDTH}
      height={VIDEO_HEIGHT}
    />
  );
};
