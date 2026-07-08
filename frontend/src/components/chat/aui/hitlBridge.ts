import { create } from 'zustand';

/** Synthetic tool name for the in-band HITL approval part (AUI_FULL / P4). */
export const HITL_APPROVAL_TOOL = '__nous_approval__';

/**
 * Bridges NOUS's out-of-band HITL to an in-band assistant-ui approval part
 * (AUI_FULL / P4). NOUS resolves confirmations over a separate streamConfirm
 * endpoint, not the runtime's in-band resume — so the approval renderer, which
 * lives deep inside the runtime tree, reaches the hardened confirm flow through
 * this store instead of prop-drilling. The hook publishes a `respond` bound to
 * its existing `handleConfirmation`; the renderer calls it on approve/deny.
 *
 * The hook (pendingConfirmation) stays the source of truth for WHETHER a
 * confirmation is pending; this store only carries the resolver + the tool
 * preview so the renderer can draw the gate.
 */
export interface HitlRequest {
  /** Stable id for this confirmation gate (the owning thread id is fine — one
   * confirmation is pending per thread at a time). */
  id: string;
  toolName: string;
  args: Record<string, unknown>;
}

interface HitlBridgeState {
  request: HitlRequest | null;
  /** Resolve the gate. Bound by the hook to handleConfirmation(approved). */
  respond: ((approved: boolean) => void) | null;
  /** True while streamConfirm is in flight (drives disabled state). */
  isResponding: boolean;
  open: (
    request: HitlRequest,
    respond: (approved: boolean) => void
  ) => void;
  setResponding: (v: boolean) => void;
  close: () => void;
}

export const useHitlBridge = create<HitlBridgeState>((set) => ({
  request: null,
  respond: null,
  isResponding: false,
  open: (request, respond) => set({ request, respond, isResponding: false }),
  setResponding: (isResponding) => set({ isResponding }),
  close: () => set({ request: null, respond: null, isResponding: false }),
}));
