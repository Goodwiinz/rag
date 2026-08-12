---
name: sympy
description: Exact symbolic math in Python via the sandboxed code tool — algebra, calculus, equation solving, symbolic linear algebra, and conversion to numeric code with lambdify.
---

# SymPy

Use SymPy when a result needs to be exact rather than a floating-point approximation: symbolic algebra, calculus, equation solving, symbolic linear algebra, and converting a derived expression into a fast numeric function. Everything runs through `execute_code`; SymPy is not preinstalled in the sandbox, so install it via the tool's `packages` argument (add numpy/scipy/matplotlib alongside it when a symbolic result needs to feed a numeric pipeline or a plot).

Adapted from K-Dense scientific-agent-skills (MIT license).

## When this beats NumPy or SciPy

Reach for SymPy when the question is "what is the exact form" rather than "what is the number": a closed-form derivative or integral, a simplified algebraic expression, an eigenvalue expressed as a radical, a differential equation's general solution. Once the exact form is in hand and needs to be evaluated many times or plotted, convert it to a numeric function rather than repeatedly substituting and evaluating symbolically — that conversion (`lambdify`) is the bridge back to NumPy/SciPy for anything performance-sensitive.

## Working practice

Define symbols explicitly before using them, and attach assumptions (`real`, `positive`, `integer`, and similar) whenever they're known — a `sqrt(x**2)` only simplifies to `x` rather than `Abs(x)` when SymPy knows `x` is positive, and assumptions like this cascade through later simplification instead of leaving irreducible absolute values and branch cuts in the output. Keep arithmetic exact throughout the symbolic phase — `Rational(1, 2)` or `S(1)/2`, never a bare `0.5`, which silently introduces a floating-point value into an otherwise exact expression. Call `.evalf()` (with an explicit precision when it matters) only at the point a numeric answer is actually needed.

For calculus, `diff` and `integrate` cover derivatives and both definite and indefinite integrals; `limit` and `series` handle limiting behavior and expansions. For equation solving, prefer `solveset` for a single algebraic equation, `linsolve`/`nonlinsolve` for systems, and `dsolve` for differential equations; fall back to the older, more permissive `solve` when the newer solvers reject a form they can't fully classify. After solving, substitute each solution back into the original equation and simplify to confirm it reduces to zero — a returned solution set is only worth trusting once checked. For matrices, build with `Matrix` and use `.eigenvals()`, `.eigenvects()`, `.inv()`, `.rref()`, and friends for the standard linear-algebra operations, all computed exactly.

When an expression is going to be evaluated repeatedly or over an array, convert it once with `lambdify(symbols, expr, 'numpy')` rather than looping `subs`/`evalf` — the loop is slow enough to matter and the numeric function evaluates directly across a NumPy array or a SciPy solver such as `fsolve`. For write-ups, `latex(expr)` renders publication-ready notation and `pprint` gives a readable console form; put exact and evaluated numeric forms side by side in the report rather than one or the other.

## Reporting

When symbolic results feed a project note or draft (via `create_project_note`), state the exact closed form, the assumptions under which it holds, and a numeric evaluation for the reader who wants a number — don't present only one of the two.

## Pitfalls

1. Using a bare float instead of `Rational`/`S` — introduces an approximation into what should be an exact derivation.
2. Skipping assumptions on symbols — leaves unnecessary `Abs()`, unresolved branch cuts, or an unsimplified `sqrt` in results that should have collapsed.
3. Repeated `subs`/`evalf` in a loop instead of `lambdify` — correct but needlessly slow once the array is nontrivial.
4. Trusting a solver's output without back-substitution — confirm each solution actually zeroes the original equation before reporting it.
5. Reaching for the legacy `solve` first out of habit — try `solveset`/`linsolve`/`nonlinsolve` for the matching problem shape, and fall back only when they can't handle the form.
6. Treating a `dsolve` general solution as fully determined — initial or boundary conditions still need to be applied to fix the constants.
