'use client';

import type { ReactElement } from 'react';
import {
  ChatRuntimeProvider,
  type ChatRuntimeProviderProps,
} from './ChatRuntimeProvider';
import { AUI_TOOL_UI_ENABLED } from './flag';

/**
 * Mounts the assistant-ui runtime only when the stage-1 flag is on, so
 * flag-off production builds don't pay for a runtime nothing consumes.
 * The flag is a build-time constant, so the conditional hook mounting in
 * ChatRuntimeProvider can never flip within a session.
 */
export function MaybeChatRuntimeProvider(
  props: ChatRuntimeProviderProps
): ReactElement {
  if (!AUI_TOOL_UI_ENABLED) return <>{props.children}</>;
  return <ChatRuntimeProvider {...props} />;
}
