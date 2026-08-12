---
name: hypothesis-generation
description: Turn a literature or knowledge-graph observation into candidate explanations, rival accounts, and discriminating predictions. Apply when moving from a preliminary finding to a testable question, before treating any candidate as established.
---

# Hypothesis Generation

Turn an observation into a transparent set of candidate explanations and the predictions that would discriminate between them. A hypothesis is a proposal to be challenged, never a finding, and never restated as a fact once written down.

Adapted from K-Dense scientific-agent-skills (MIT license).

## Keep the objects distinct

- **Observation** — what was found, with its source and how confident that source is.
- **Research question** — the specific, answerable question the observation raises.
- **Hypothesis** — one candidate explanation among several, not the explanation.
- **Rival explanation** — a genuinely different account of the same observation, including a mundane one (measurement artifact, selection effect, coincidence).
- **Prediction** — an observable consequence derived from a hypothesis before checking whether it holds.
- **Evidence** — a source or observation that bears on a claim; never the claim itself.

Do not collapse these. A prediction is not evidence until checked; support for one candidate does not eliminate rivals that were never tested.

## Workflow

### 1. Freeze the observation

Write down what was actually found before interpreting it: the source document or dataset, its scope, and any known limitation or gap in coverage. Use "reported" or "observed," not causal language, until a design justifies stronger wording.

### 2. Frame the research question

State the question the observation raises in answerable form: what population or corpus, what comparison, what outcome. A vague question ("is X related to Y") cannot be discriminated between rival explanations; a framed one ("does X predict Y after controlling for Z") can.

### 3. Establish a dated evidence boundary

Before generating candidates, search what is already known. Use `search_arxiv` for recent preprints, `search_external_database` (after `list_external_databases` to see what is configured) for domain literature, and `search_knowledge_graph` or `explore_entity_neighborhood` for what the project's own corpus already connects. Record the search date, the queries used, and what was and was not covered — a bounded search establishes what was found, not that nothing else exists. State "not located within the documented search" rather than "no prior work."

### 4. Generate rival explanations before choosing a test

For the observation, generate multiple candidates from genuinely different classes: the proposed mechanism, a measurement or data-processing artifact, a confounding variable, a selection effect in how the corpus or sample was assembled, reverse causation, and plain stochastic variation. Write an initial set independently before refining it, so early candidates are not anchored on the first idea. Label every candidate as a candidate, not a conclusion.

### 5. Derive discriminating predictions

For each candidate, state: the observable that would follow, the pattern expected, and a result that would be incompatible with that candidate. Prefer predictions where rivals genuinely diverge — a prediction every candidate satisfies equally cannot discriminate between them. Where verifying a prediction requires pulling and quoting actual source content, use `do_kb_retrieve` (relevance-scored passages, verbatim quotes) rather than `search_documents`, which only matches titles and cannot confirm what a source says.

### 6. Match the claim type to what the evidence can support

Classify the target claim as descriptive, associational, predictive, or causal. A causal claim needs a design that can support it — correlation observed in existing documents or knowledge-graph relationships is not sufficient on its own. State explicitly which claim type is being made and why the available evidence licenses it.

### 7. Plan the check

Describe what data or analysis would test the surviving candidates, and route it: computational checks or simulations to `execute_code`, literature-based checks back through search, and document synthesis to `create_project_note`. If a check would require new data collection or a formal experiment, hand off to the experimental-design method rather than improvising here.

### 8. Keep a decision trail

Before checking predictions, note them down (in a `create_project_note`) so that later results cannot be quietly relabeled as having been predicted in advance. Afterward, mark any analysis run without a prior prediction as exploratory. This distinction protects the difference between confirmatory and exploratory findings.

## Pitfalls

1. Treating the first plausible explanation as sufficient — generate rivals before testing.
2. Presenting a hypothesis or a search result as established evidence.
3. Claiming novelty because a bounded search found nothing.
4. Inferring causation from association, order, or predictive accuracy alone.
5. Relabeling a pattern noticed after the fact as a prior prediction (hindsight bias).
6. Letting a single supportive source stand in for a checked claim — verify with quoted content, not a title match.
