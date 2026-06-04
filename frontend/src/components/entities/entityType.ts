/**
 * Shared helpers for presenting entity types in the knowledge-graph UI.
 *
 * Entity type *values* are stored as machine constants (e.g. `JOB_TITLE`).
 * These helpers keep the display human and on-brand without changing the
 * underlying value used for filtering, sorting, or persistence.
 */

/**
 * Humanize a stored entity-type value for display.
 * `JOB_TITLE` -> `Job title`, `PERSON` -> `Person`, `__null__` -> `Unknown type`.
 */
export const formatEntityType = (type?: string | null): string => {
  if (!type) return 'Unknown type';
  if (type === '__null__') return 'Unknown type';
  const spaced = type.replace(/_/g, ' ').trim().toLowerCase();
  if (!spaced) return 'Unknown type';
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

/**
 * One neutral, tokenized badge style for every entity type.
 * Meaning is carried by the type label itself, not by color, so the dense
 * table stays calm and scannable (no rainbow hue map).
 */
export const entityTypeBadgeClass =
  'border-border bg-muted text-muted-foreground font-normal';
