---
name: scientific-brainstorming
description: Facilitate evidence-aware research ideation — independent generation, structured evaluation, adversarial review, a decision log. Apply for early-stage direction-finding, before committing to hypothesis testing.
---

# Scientific Brainstorming

Generate, organize, challenge, and transparently prioritize candidate research directions. Every output here is a proposal, not a finding — brainstorming widens the option set, it does not validate any of the options it produces.

Adapted from K-Dense scientific-agent-skills (MIT license).

## Boundaries

- Ideation produces candidate questions and directions; it does not check whether any of them hold. A promising idea still needs hypothesis-generation to become a testable claim and experimental-design to become a checkable study.
- Do not treat consensus, vote counts, or a high score as proof. They are traceable aids to a decision the accountable researcher still makes.
- Record where every idea came from (which source, which prior document, which round of the session), and keep dissenting or lower-scoring ideas visible rather than discarding them once a favorite emerges.

## Workflow

### 1. Scope the session

Write one focal question in a `create_project_note`: what decision this session feeds, what is explicitly in and out of scope, what is already known, and what constraints are fixed versus negotiable.

### 2. Generate independently first

Produce an initial list of candidate directions before consulting the literature or letting one strong idea dominate the set — early exposure to examples anchors everything generated afterward. For each candidate, capture a one-sentence statement, its assumptions, and what evidence would make it more or less promising.

### 3. Ground candidates in what already exists

After the independent round, check what is already known. Use `search_arxiv` and `search_external_database` (via `list_external_databases` for what is configured) for outside literature, and `search_knowledge_graph` or `find_entity_paths` for connections already surfaced in the project's own corpus — a direction that duplicates settled work is a weaker candidate than one that does not. Record what was searched and when; absence from a bounded search is not proof the direction is novel, only that it was not found within that search.

### 4. Cluster and re-open

Group candidates by shared question, mechanism, or population rather than by surface wording — similar phrasing does not mean the same idea. After clustering, reopen generation briefly: the literature check and clustering pass often surface a direction nobody proposed independently.

### 5. Define evaluation criteria before scoring

State the criteria explicitly before rating anything: potential to inform the focal question, feasibility with the tools and data actually available, originality relative to what the literature check found, and what would be learned even if the result comes back null. Score with visible reasoning, not a bare number.

### 6. Run adversarial review

For each shortlisted direction, ask: what observation would show this direction is unproductive or already answered? What alternative explanation would produce the same expected result? What data or corpus gap would undermine it before it even starts? Record the answer and whether the direction was revised, not just a pass or fail.

### 7. Decide and log

Record the final call in `create_project_note`: candidates considered, criteria and their weights, dissenting views, what was searched and when, the decision, the rejected alternatives, and the next concrete step — further search, formal hypothesis-generation, or an experimental-design pass. Label the outcome as a decision to pursue, not as a validated conclusion.

## Bias controls

- **Anchoring.** No leader answer and no literature search until after the independent round.
- **Premature convergence.** Fix a generation window before moving to evaluation; do not let the first well-argued idea end the round early.
- **Research-gap inflation.** Report "not located within the documented search," never "never studied" — a bounded search proves what was checked, not what exists.
- **False precision.** Keep scores paired with their reasoning and disagreement; a single averaged number hides where reviewers actually differed.
- **Groupthink.** Assign someone to argue the alternative explicitly and keep rejected directions in the log rather than silently dropping them.

## Pitfalls

1. Treating a brainstorm output as a validated hypothesis rather than a candidate.
2. Searching the literature before the independent generation round, biasing what gets proposed.
3. Collapsing distinct ideas into one because their wording looks similar.
4. Letting a numeric score substitute for the qualitative judgment behind it.
5. Discarding minority or lower-scoring ideas from the record instead of logging them.
6. Skipping the adversarial-review step for the favored direction because it "obviously" works.
