---
name: polars
description: Expression-based DataFrame work with Polars — lazy query optimization, fast joins/group-bys, and pandas-migration patterns — run through the sandboxed code tool.
---

# Polars

Use Polars for DataFrame work that needs to be fast or that benefits from a query-optimizer rather than sequential pandas operations: large files, multi-step pipelines, or a pandas migration where the eager, index-based model is getting in the way. All of it runs through `execute_code`; Polars is not preinstalled in the sandbox, so install it via the tool's `packages` argument at the start of the session (add the `pandas` extra only if bridging to an existing pandas frame).

Adapted from K-Dense scientific-agent-skills (MIT license).

## Core model

Polars has no row index — everything is integer position — and it does not silently coerce types the way pandas does. Two evaluation modes matter:

- **Eager** (`DataFrame`, `read_csv`/`read_parquet`/`read_json`): each call executes immediately, same mental model as pandas.
- **Lazy** (`LazyFrame`, `scan_csv`/`scan_parquet`): calls build a query plan; nothing runs until `.collect()`. The optimizer applies predicate and projection pushdown — filters and column selection get pushed as close to the file read as possible — so the same pipeline written lazily can be dramatically cheaper than the eager equivalent. Default to lazy for anything beyond a quick look at a small file, and reach for `collect(engine="streaming")` when the data doesn't comfortably fit in memory.

Every transformation is built from expressions — `col("name")` referencing a column, chained and composed method calls — that only execute inside a context: `select`, `with_columns`, `filter`, or `group_by().agg()`. Passing several expressions to `with_columns` computes them in parallel; that parallelism is the main reason `with_columns` with multiple expressions beats a chain of sequential pandas `assign` calls.

## Common operations

`select` picks and computes columns; `filter` takes one or more boolean expressions (comma-separated reads as an implicit AND, cleaner than chaining `&`); `with_columns` adds or replaces columns while keeping the rest; `group_by(...).agg(...)` aggregates, with `len()`, `sum()`, `mean()`, `min()`/`max()`, and `first()`/`last()` as the common aggregation expressions. Window functions via `.over("group_col")` compute a group-level aggregate while preserving the original row count — the Polars equivalent of a pandas `groupby().transform()`. `join` supports inner/left/outer/anti/semi with `on` or `left_on`/`right_on`; `concat` stacks frames vertically, horizontally, or diagonally (diagonal tolerates mismatched schemas). `pivot` and `unpivot` move between wide and long shapes.

Conditional values go through `when(condition).then(value).otherwise(other)`. Null handling has its own vocabulary: `fill_null`, `is_null`, `drop_nulls` — nulls are explicit, never silently dropped by an aggregation the way pandas sometimes does.

## Migrating from pandas

The conceptual shift is: no index, strict typing, and expressions instead of positional or label-based indexing. `df["col"]` becomes `select("col")`; boolean-mask filtering becomes `filter(col(...) > x)`; `.assign()` becomes `with_columns()`; `.groupby().agg()` becomes `group_by().agg()` with the underscore spelling; `.groupby().transform()` becomes `with_columns(...).over(...)`. A pandas pipeline built from several sequential `assign` calls with lambdas usually collapses into one `with_columns` call with multiple named expressions in Polars, which both reads better and runs the columns in parallel.

## Performance practice

Prefer lazy (`scan_*`) over eager (`read_*`) once a file is nontrivial, and select the needed columns as early as possible in the chain rather than filtering the whole frame first — the optimizer helps, but writing it in the efficient order also helps the reader. Stay inside the expression API rather than reaching for `.map_elements()` with a Python callable — the latter breaks the interpreter's ability to parallelize and vectorize the operation, and should be a last resort, not a first instinct. Use Parquet over CSV for anything reused across a session; use categorical types for low-cardinality string columns.

## Pitfalls

1. Reaching for eager `read_csv` on a large file when `scan_csv` plus lazy filtering would push work down before rows are even reached.
2. `.map_elements()` on a hot path — almost always replaceable by a native expression.
3. Assuming pandas index semantics carry over — there is no index; positional access and `reset_index`-style thinking don't apply.
4. Silent type mismatches — Polars raises on mismatched schema in `concat`/`join` rather than coercing; read the error instead of forcing a cast blindly.
5. Forgetting `.collect()` — a `LazyFrame` pipeline that's never collected has computed nothing yet.
