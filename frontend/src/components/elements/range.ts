/** Constrains a value to min…max; NaN maps to min. */
export function clamp(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

/** The first count items, with count constrained to the collection. */
export function take<T>(items: readonly T[], count: number): T[] {
  return items.slice(0, Math.floor(clamp(count, 0, items.length)));
}

/** A value as a percentage of total, constrained to 0…100. */
export function pct(value: number, total: number): number {
  if (!(total > 0)) return 0;
  return clamp((value / total) * 100, 0, 100);
}
