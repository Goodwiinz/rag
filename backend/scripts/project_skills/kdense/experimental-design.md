---
name: experimental-design
description: Design a computational study before running it — splits, seeds, controls, comparison structure. Apply when planning an analysis, ablation, or benchmark comparison whose conclusions depend on how conditions were assigned.
---

# Experimental Design

Design the study before running it: what varies, what is held fixed, how conditions are assigned, and at what level a result counts as an independent replicate. No downstream analysis can rescue a confounded or pseudoreplicated design after the fact.

Adapted from K-Dense scientific-agent-skills (MIT license).

## When to apply

- Planning a comparison between methods, prompts, models, or parameter settings
- Structuring an ablation or ablation-style analysis
- Designing a benchmark run where results must generalize beyond the specific data used
- Any analysis where sampling, splitting, or ordering choices could bias the outcome

## The three ideas behind a sound design

- **Randomization.** Assign items to conditions (train/test folds, treatment/control prompts, evaluation order) by a seeded random process, not by convenience order. This is what licenses a causal or comparative claim rather than a correlational one.
- **Replication at the right level.** The independent unit is whatever the randomization touches. Running the same evaluation set through a model five times with different random seeds gives five replicates of the *seed*, not five replicates of the *dataset* — state explicitly what a run's n counts.
- **Blocking.** Group by a known nuisance factor (data source, time period, document length, prompt template family) and compare within each group before pooling, so that nuisance variation lands in a term you can see rather than in noise that hides the real effect.

## Workflow

1. **State the question, the unit, and the outcome.** What is being compared? What is the unit that gets assigned to a condition (a document, a query, a run, a fold)? What is measured as the outcome? This determines everything downstream.
2. **List nuisance factors.** Data source, ingestion date, prompt template, document length, model version — anything that could align with a condition by accident. Plan to block on or randomize across each one.
3. **Pick the comparison structure.** A few predefined conditions compared on independent units is the common case; a repeated-measures structure (the same items scored under every condition) trades more statistical power for the need to watch order effects; a factorial structure is warranted only when interactions between two or more varied factors are the actual question.
4. **Decide replication.** Multiple seeds test sensitivity to randomness; multiple data folds test sensitivity to the sample; multiple prompt phrasings test sensitivity to wording. These are different questions — pick the one the study needs, and do not present one as evidence for another.
5. **Build and run the design with `execute_code`.** Generate the seeded split or assignment, log the seed, and keep the assignment table alongside the run so it can be regenerated exactly. Randomize evaluation order within the sandboxed run rather than always scoring conditions in the same sequence.
6. **Document the design before results are known.** Record the question, the assignment, the seed, and what would count as support or against the comparison, in a `create_project_note`. A design written up after seeing results has already lost its evidentiary value.
7. **Match the later analysis to the design.** Blocks, folds, and repeated measures must appear in the statistical model, not be pooled away — hand this off to a statistics-focused pass once data is collected.

## The mistakes that ruin a study

1. **Pseudoreplication.** Scoring one held-out document against 200 generated passages and reporting n=200 is n=1 for anything about that document; the replicate is at the level something was actually varied.
2. **Confounding by a nuisance variable.** Evaluating condition A on documents ingested this week and condition B on documents ingested last month confounds the comparison with a time or corpus-version effect.
3. **No or broken randomization.** Assigning the first half of a dataset to one condition and the second half to another lets whatever generated that ordering leak into the result.
4. **No real control.** A comparison needs a baseline run under matched conditions, not just a single treated arm reported against expectation.
5. **Order effects in repeated measures.** Always evaluating condition A before condition B on the same items confounds the comparison with position or drift; randomize the order per item.
6. **Aliasing in multi-factor sweeps.** Varying several parameters at once without a structured design confounds their individual effects; know which factors are entangled before concluding one "does not matter."

## Pitfalls

1. Choosing the design after collecting the data, not before.
2. Treating repeated evaluation of the same item as independent samples.
3. Skipping the seed or assignment log, making the run irreproducible.
4. Reporting a comparison without a matched baseline.
5. Letting a data-source or time-period nuisance factor align with the conditions being compared.
