---
name: shap
description: Explain fitted model predictions with SHAP in the sandboxed code tool — explainer selection, feature attributions, additivity checks, local and global plots. Installs via execute_code packages.
---

# SHAP

Explain how a fitted predictive model maps inputs to outputs, using SHAP feature attributions. Work from the modern `shap.Explanation` API, make the explained output and background data explicit, and validate every explanation before interpreting it. All computation runs through `execute_code` (sandboxed Python; SHAP is not preinstalled, so pass it via the `packages` argument alongside the model library — typically scikit-learn, which is already available).

Adapted from K-Dense scientific-agent-skills (MIT license).

SHAP explains a model that has already been fit and validated — it is not a substitute for the model-validation discipline in the scikit-learn skill, and it does not replace the coefficient-based inference of the statsmodels skill. Fit and validate the model first; reach for SHAP only once its predictions are already trustworthy and the question shifts to "why did it predict this."

## Operating rules

1. Explain a fixed, already-evaluated model. If the model has not been validated, that is a scikit-learn or statsmodels task first.
2. Use held-out or clearly labeled rows for the explanation, and choose background rows from an appropriate reference population — never the same rows being explained.
3. State the explained output up front: regression value, raw margin, probability, or log-odds. Never infer units from a plot's color or sign.
4. Keep explanations as `shap.Explanation` objects returned by calling the explainer (`explainer(X)`); avoid the older `.shap_values(X)` array-only interface except when maintaining legacy code.
5. For multi-output or multi-class models, select one output before making a tabular plot — index the explanation object to a single class or target first.
6. Check additivity before interpreting: base value plus the sum of a row's SHAP values should reconstruct that row's model output. A mismatch signals a preprocessing, output-space, or version problem, not a SHAP quirk to explain away.
7. Treat SHAP as a description of model behavior under a chosen masking and background distribution — it is not evidence of causality, fairness, or scientific mechanism, and should not be reported as such.
8. Do not load model or explainer files from untrusted sources; pickle-based formats can execute arbitrary code on load.

## Explainer selection

Match the explainer to the model family rather than defaulting to the slowest general-purpose option:

- Tree ensembles (random forest, gradient boosting): `TreeExplainer` — fast, exact for supported models; set the model-output mode explicitly (margin versus probability) and use interventional masking with real background data when explaining probabilities.
- Linear models: `LinearExplainer` — the masker choice determines whether correlated features are treated independently or jointly.
- Small, fixed feature sets: `ExactExplainer` — exact but cost grows quickly as features increase, so it does not scale past a handful of features.
- General tabular models with no faster path available: `PermutationExplainer` — budget for at least one full permutation pass; slower than the model-specific explainers above.
- Hierarchical, grouped, text, or image features: `PartitionExplainer` — the partition tree structures which features are perturbed together, changing what "attribution" means.
- Differentiable neural networks: `DeepExplainer` or `GradientExplainer`, with background choice and output shape checked before trusting results.
- Legacy workflows only: `KernelExplainer` — model-agnostic but usually far slower than a model-specific explainer; prefer one of the above when the model family supports it.

## Workflow

1. Record the explanation target: model version, the exact callable or method being explained, the output name and units, which rows are being explained, and which rows form the background/reference set.
2. Choose the explainer and masker from the table above, matched to the model family and feature structure.
3. Compute the explanation by calling the explainer on the evaluation rows, producing a `shap.Explanation` object rather than a bare array.
4. Validate: confirm additivity (base value plus SHAP values equals the model output for each row) before reading anything into the attributions.
5. For local explanations (why this one prediction), use a waterfall or force-style plot for a single row. For global explanations (what matters across many predictions), use a summary/beeswarm plot or mean absolute SHAP value per feature.
6. Interpret attributions relative to the stated background — a feature's SHAP value is its contribution relative to the reference distribution, not an absolute measure of importance in isolation.

## Reporting

Record with `create_project_note`: the model and preprocessing version explained, the explainer and masker chosen and why, the background population, the explained output (units), the additivity check's result, and both a local example plot and a global summary plot from `execute_code`. State plainly that the attributions describe model behavior under the chosen background, not a causal claim about the real-world process the model was trained to approximate.

## Pitfalls

1. Explaining an unvalidated model — SHAP will faithfully attribute a bad model's bad predictions; validate first.
2. Using the same rows for background and for explanation, which collapses the comparison the attributions are relative to.
3. Skipping the additivity check and interpreting attributions from a broken pipeline (mismatched preprocessing, wrong output index, stale model version).
4. Plotting a multi-class explanation without selecting an output index first, producing attributions that mix classes.
5. Reporting SHAP values as causal or fair-treatment evidence rather than a description of the fitted model's behavior.
6. Choosing `KernelExplainer` by default when a faster, exact model-specific explainer (`TreeExplainer`, `LinearExplainer`) already fits the model family.
7. Reading feature importance off SHAP values without stating the explained output's units, leaving probability, margin, and log-odds indistinguishable in the report.
