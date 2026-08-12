---
name: statistical-analysis
description: Rigorous statistical analysis with the sandboxed code tool. Apply when choosing tests, checking assumptions, computing effect sizes, running frequentist or Bayesian analyses, or reporting statistical results.
---

# Statistical Analysis

Run statistical analyses that hold up to review: choose the right test, check its assumptions, report effect sizes with uncertainty, and write results in reportable form. All computation runs through `execute_code` (sandboxed Python with numpy, pandas, scipy, matplotlib, seaborn, scikit-learn preinstalled; statsmodels and pingouin installable via the packages parameter).

Adapted from K-Dense scientific-agent-skills (MIT license).

## Workflow

1. Understand the data: types, structure, missingness, sample size per group.
2. Explore first: descriptive statistics and plots before any test.
3. Check assumptions for the intended test.
4. Select the test based on question, data type, and assumption status.
5. Run the analysis and compute effect sizes with confidence intervals.
6. Report completely: test statistic, degrees of freedom, p-value, effect size, interval, and the assumption checks performed.

## Test selection

Match the question and data to the test family:

- Two independent group means: t-test; Welch correction when variances differ; Mann-Whitney U when normality fails badly at small n.
- Paired measurements: paired t-test; Wilcoxon signed-rank as the nonparametric fallback.
- Three or more group means: one-way ANOVA with Tukey HSD post-hoc; Kruskal-Wallis nonparametric.
- Two categorical variables: chi-square test of independence; Fisher exact when expected cell counts fall below five.
- Association of two continuous variables: Pearson correlation; Spearman for monotonic non-linear or ordinal data.
- Outcome predicted from covariates: linear regression for continuous outcomes, logistic for binary; check residual diagnostics before trusting coefficients.
- Repeated measures over conditions or time: repeated-measures ANOVA or a mixed model when the design is unbalanced.

## Assumption checking

Check before testing, and report what was checked:

- Normality: Shapiro-Wilk per group plus a Q-Q plot; at large n rely on the plot, since the test rejects trivially.
- Homogeneity of variance: Levene test; on failure use Welch variants rather than abandoning the comparison.
- Independence: a design question, not a computed one — state why observations are independent, and reach for mixed models when they are not.
- Outliers: inspect with box plots; investigate rather than silently exclude. An excluded point is documented with its reason, and the analysis is reported with and without it when influential.
- Regression additionally: linearity of the mean, homoscedastic residuals, low multicollinearity (variance inflation factors), and residual normality via diagnostic plots.

When assumptions fail: prefer the robust variant (Welch, rank-based, robust standard errors) over dropping to a weaker question. State which variant was used and why.

## Effect sizes and uncertainty

A p-value alone is not a result. Always pair it with a magnitude and its uncertainty:

- Mean differences: Cohen's d (or Hedges' g at small n) with its confidence interval.
- ANOVA: partial eta-squared per factor.
- Categorical associations: Cramér's V or an odds ratio with interval.
- Correlations and regressions: the coefficient itself with its interval is the effect size.

Interpret magnitudes in domain terms, not just conventional small-medium-large labels.

## Bayesian analysis

When the question is "how probable is an effect of at least this size" rather than "reject the null": fit with PyMC (installable in the sandbox), report posterior means with credible intervals, check convergence via R-hat and effective sample size, and state priors explicitly. Direct probability statements about the effect are the payoff of the Bayesian route; use it when the researcher needs them.

## Multiple comparisons

Family-wise corrections (Tukey, Bonferroni-family) for confirmatory sets of comparisons; false-discovery-rate control for exploratory screens. Always state how many comparisons were run and which correction applied — uncorrected multiplicity is one of the most common review failures.

## Reporting

Write results with `create_draft` or record them via `create_project_note` in reportable form: test name and variant, statistic with degrees of freedom, exact p-value, effect size with interval, assumption checks performed and their outcomes, sample sizes per group, and software noted as the sandboxed Python stack. Plots produced with `execute_code` should show the data (not just bar means): box or violin plots with points for group comparisons, scatter with fit and interval for associations.

## Pitfalls

1. Testing before looking — exploration first catches coding errors and absurd values.
2. Assumption checks skipped or unreported — reviewers assume unchecked means violated.
3. P-value without effect size — statistically detectable is not practically meaningful.
4. Silent outlier exclusion — document, justify, and show sensitivity.
5. Uncorrected multiple comparisons — count the family, correct, and say so.
6. Nonparametric as automatic fallback — Welch variants often preserve the actual question better.
7. Overfitting small samples with many covariates — the model must be simpler than the data.
