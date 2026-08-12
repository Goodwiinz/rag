---
name: scientific-critical-thinking
description: Evaluate the rigor of a claim, paper, or dataset — methodology, bias, statistics, and evidence quality. Apply when assessing whether a source's conclusions are supported, before citing it or relying on it in synthesis or drafting.
---

# Scientific Critical Thinking

Evaluate scientific rigor systematically: methodology, evidence quality, statistical validity, and the biases most likely to distort a conclusion. The goal is a proportionate, specific judgment of what a source actually supports, not a verdict of good or bad.

Adapted from K-Dense scientific-agent-skills (MIT license).

## When to apply

- Deciding whether a source's claim is strong enough to cite as support
- Assessing a paper's methodology before relying on it in synthesis
- Comparing the evidentiary strength of conflicting sources
- Checking a draft's own claims for overreach before it goes out

## Core capability areas

Work through these systematically rather than reacting to whichever issue is most visible:

1. **Methodology.** Does the design used actually answer the question asked? Look for missing controls, confounds not addressed, and a sample too small or too narrow for the claim made.
2. **Bias.** Selection bias (who or what ended up in the sample), measurement bias (how the outcome was captured), and publication bias (null results are underrepresented in what gets published) each distort differently — name which one applies rather than saying "biased."
3. **Statistical validity.** Underpowered samples, uncorrected multiple comparisons, p-values reported without effect sizes, and correlational findings described in causal language are the recurring failures. State the specific one found, not a general statistics complaint.
4. **Evidence quality.** Weight sources by their position in the evidence hierarchy — a single small study, a large well-controlled study, and a systematic review of several studies do not carry equal weight even when they agree.
5. **Logical structure.** Watch for the fallacies common in scientific argument: appeal to authority (a claim is true because a prominent source said it), hasty generalization (a small or unusual sample generalized broadly), and post-hoc reasoning (temporal sequence treated as causal proof).
6. **Claim-evidence fit.** Separate what the data show from what is asserted. "Suggests" should not be read as "demonstrates"; a trend in one dataset should not be read as an established effect.

## Workflow

1. **Establish scope.** Confirm what is under evaluation — a specific claim, a paper's methods section, an entire draft — and what evidence is available to check it against. Use `list_project_documents` to see what is in the active project.
2. **Extract before judging.** Read for what was actually done and claimed, using `summarize_document` for structure, before forming an assessment. Premature judgment anchors everything that follows.
3. **Trace claims to evidence.** For each central claim, pull the actual supporting passage with `do_kb_retrieve` — it returns relevance-scored content with verbatim quotes, which is what a fidelity check needs. `search_documents` matches only titles and cannot confirm what a source says, so it cannot do this step.
4. **Check statistics where numbers matter.** When a stated statistic, effect size, or interval needs recomputation or a sanity check, use `execute_code` rather than trusting an assertion.
5. **Compare against related sources.** Use `compare_documents` to see whether a source's methodological choices or reported effects are consistent with, or diverge from, other work already in the project.
6. **Write the assessment as structured feedback**, in a `create_project_note`: what was evaluated, strengths, concerns ranked by severity (critical, important, minor), and what remains unassessed. Note explicitly when something could not be checked — figures and rendered images are outside what these tools can inspect, since document tools extract text only.

## Application guidelines

Be constructive: name what was done well, not only what is wrong. Be specific: point at the exact section, table, or sentence rather than a general impression. Be proportionate: a critical issue threatens the paper's main conclusion, a minor one does not — say which is which. Apply the same standard to every source regardless of whether its conclusion is convenient. When uncertain, say so and state what additional information would resolve it, rather than forcing a verdict.

## Pitfalls

1. Verdict-first evaluation — trace claims to evidence before judging them.
2. Flat criticism that does not distinguish fatal flaws from minor ones.
3. Statistics theater — noting that a p-value exists is not checking the statistics.
4. Treating correlation, prediction, or temporal order as causal proof.
5. Applying stricter scrutiny to conclusions one disagrees with.
6. Declaring something unverifiable checked when it was not (figures, raw data, code).
