/** Synthetic tool name for the in-band HITL approval part (P4).
 * Neutral module so both convertMessage (pure mapper) and the renderer can
 * import it without a component ↔ mapper cycle. */
export const HITL_APPROVAL_TOOL = '__nous_approval__';
