/**
 * Generic reverse-index helpers for nested `Record<parentId, Item[]>`
 * structures (conversations keyed by workspace, threads keyed by
 * conversation, messages keyed by thread).
 *
 * Split out of chat-store.ts (Task 5.4) with no behavior change. Kept as one
 * shared module (rather than duplicated per slice) because every slice that
 * deletes/updates a child record must keep its reverse index in lockstep —
 * see recon `chatfe.store.cross_slice_couplings`.
 */

/**
 * Generic helper to remove an item from a record of arrays by ID.
 * Used for deleting conversations, threads, and messages from their respective records.
 *
 * PERFORMANCE (GOO-86): Now uses O(1) lookup via reverse index instead of O(n*m) iteration.
 * Falls back to O(n*m) iteration if reverse index not provided (backward compatibility).
 *
 * @param record - The record containing arrays (e.g., conversations keyed by workspaceId)
 * @param itemId - The ID of the item to remove
 * @param reverseIndex - Optional reverse index mapping itemId to parentKey for O(1) lookup
 * @returns true if item was found and removed, false otherwise
 */
export function removeItemFromRecord<T extends { id: string }>(
  record: Record<string, T[]>,
  itemId: string,
  reverseIndex?: Record<string, string>
): boolean {
  // O(1) path: use reverse index if available
  if (reverseIndex) {
    const parentKey = reverseIndex[itemId];
    if (parentKey && record[parentKey]) {
      const index = record[parentKey].findIndex((item) => item.id === itemId);
      if (index !== -1) {
        record[parentKey].splice(index, 1);
        delete reverseIndex[itemId];
        return true;
      }
    }
    return false;
  }

  // O(n*m) fallback: iterate all keys (legacy behavior)
  for (const key of Object.keys(record)) {
    const index = record[key]?.findIndex((item) => item.id === itemId);
    if (index !== undefined && index !== -1) {
      record[key].splice(index, 1);
      return true;
    }
  }
  return false;
}

/**
 * O(1) helper to update an item in a nested record structure using a reverse index.
 * Used by bulk update operations (resolve, archive) for performance (GOO-86).
 *
 * @param record - The record containing arrays (e.g., threads keyed by conversationId)
 * @param itemId - The ID of the item to update
 * @param newItem - The updated item to replace the existing one
 * @param reverseIndex - Optional reverse index mapping itemId to parentKey for O(1) lookup
 * @returns true if item was found and updated, false otherwise
 */
export function updateItemInRecord<T extends { id: string }>(
  record: Record<string, T[]>,
  itemId: string,
  newItem: T,
  reverseIndex?: Record<string, string>
): boolean {
  // O(1) path: use reverse index if available
  if (reverseIndex) {
    const parentKey = reverseIndex[itemId];
    if (parentKey && record[parentKey]) {
      const index = record[parentKey].findIndex((item) => item.id === itemId);
      if (index !== -1) {
        record[parentKey][index] = newItem;
        return true;
      }
    }
    return false;
  }

  // O(n*m) fallback: iterate all keys (legacy behavior)
  for (const key of Object.keys(record)) {
    const index = record[key]?.findIndex((item) => item.id === itemId);
    if (index !== undefined && index !== -1) {
      record[key][index] = newItem;
      return true;
    }
  }
  return false;
}
