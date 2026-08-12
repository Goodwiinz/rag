---
name: statsmodels
description: Inference and model diagnostics with statsmodels in the sandboxed code tool. Apply for OLS/GLM/mixed models, time series (ARIMA), coefficient tables with standard errors, and residual diagnostics. Installs via execute_code packages.
---

# Statsmodels

Fit statistical models for inference — coefficients, standard errors, confidence intervals, and diagnostics — rather than raw predictive accuracy. All computation runs through `execute_code` (sandboxed Python; statsmodels is not preinstalled, so pass it via the `packages` argument alongside numpy, pandas, and scipy, which are already available).

Adapted from K-Dense scientific-agent-skills (MIT license).

This skill is for inference: does a covariate have an effect, how large, how uncertain, and does the model's fit hold up to diagnostics. When the deliverable is a model that predicts well on new data rather than an interpretable coefficient, use the scikit-learn skill instead. For test selection and effect sizes outside a regression framework, use the statistical-analysis skill; statsmodels is the right tool once the question calls for a specific model class with a coefficient table.

## When to apply

- Regression where the coefficients themselves are the answer (linear, generalized linear, quantile)
- Discrete or count outcomes needing a matched link function (logistic, Poisson, negative binomial)
- Time series modeling and forecasting (ARIMA, SARIMAX)
- Repeated-measures or clustered data needing a mixed-effects model
- Any result that must report a coefficient table with standard errors, not just a prediction

## Workflow

1. State the outcome type and pick the matching model family before touching data: continuous → OLS/WLS/GLS, binary → logistic GLM, counts → Poisson or negative binomial GLM, ordered/multinomial categories → discrete-choice models.
2. Prepare data: add a constant with `sm.add_constant()` unless deliberately excluding the intercept, encode categoricals (the formula API handles this automatically via `statsmodels.formula.api`), and handle missing values explicitly rather than letting the fit silently exclude rows.
3. Fit the model and read the full `.summary()` output, not just the headline coefficient.
4. Run diagnostics matched to the model family before trusting any coefficient.
5. Compare candidate specifications with AIC/BIC for non-nested models, or a likelihood-ratio test for nested ones.
6. Report coefficients with confidence intervals, and translate link-function coefficients back to interpretable units (for example, exponentiate a logistic coefficient to an odds ratio).

## Model families

- Continuous outcome, roughly linear relationship: OLS via `statsmodels.formula.api.ols`; move to WLS when variance is known to differ by group, or use heteroskedasticity-robust standard errors (`cov_type="HC3"`) when it is only suspected.
- Binary outcome: logistic GLM (`sm.Logit` or the formula API's `logit`); report odds ratios alongside raw coefficients.
- Count outcome: Poisson GLM as the default, switch to negative binomial when a dispersion test shows overdispersion (variance exceeding the mean beyond what Poisson allows).
- Ordinal or multinomial categorical outcome: the discrete-choice models in `statsmodels.discrete` (ordered logit/probit, multinomial logit).
- Time series: `ARIMA`/`SARIMAX` for univariate series with trend, seasonality, and exogenous regressors; check stationarity first (Augmented Dickey-Fuller test) and difference if needed; validate residuals are white noise via the Ljung-Box test.
- Clustered or repeated-measures data: mixed linear models (`MixedLM`) when observations are nested within subjects or groups and a fixed-effects model would understate standard errors.

## Diagnostics

Check before trusting any coefficient, and report what was checked:

- Residual plots: residuals versus fitted values for non-linearity, Q-Q plot for residual normality.
- Heteroskedasticity: Breusch-Pagan or White's test; on failure, refit with robust standard errors rather than trusting the naive ones.
- Multicollinearity: variance inflation factors on the design matrix; a VIF well above 10 on a covariate means its coefficient is unstable and hard to interpret in isolation.
- Autocorrelation (time series and any ordered data): Durbin-Watson or Ljung-Box on residuals.
- Influence: Cook's distance to flag observations that dominate the fit; investigate flagged points rather than silently excluding them.
- GLM-specific: a dispersion check for Poisson (mean-variance ratio) before trusting standard errors as-is.

## Reporting

Record with `create_project_note`: the model specification (formula or design matrix), the fitted coefficient table with standard errors and confidence intervals, the diagnostics run and their outcomes, model comparison statistics (AIC/BIC or likelihood-ratio result) when multiple specifications were tried, and sample size. Plots produced with `execute_code` should include the residual-vs-fitted and Q-Q plots at minimum, plus an ACF/PACF pair for any time series model.

## Pitfalls

1. Skipping `sm.add_constant()` and getting a coefficient table with no meaningful intercept.
2. Reading only the headline p-value from `.summary()` and ignoring the diagnostics below it.
3. Trusting standard errors under known heteroskedasticity instead of switching to robust ones.
4. Fitting a fixed-effects model on clustered or repeated-measures data, understating uncertainty.
5. Using AIC/BIC to compare models fit on different subsets of data (for example, after silently dropping rows with missing values) — the comparison is only valid on the same sample.
6. Forecasting from an ARIMA model without checking stationarity or residual whiteness first.
7. Reporting a raw GLM coefficient as if it were on the outcome's original scale, when the link function means it is log-odds, log-count, or another transformed unit.
