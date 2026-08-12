---
name: scikit-learn
description: Predictive modeling and validation with scikit-learn in the sandboxed code tool. Apply for classifiers, regressors, clustering, dimensionality reduction, or cross-validated model comparison and hyperparameter search.
---

# Scikit-learn

Build and validate predictive models with scikit-learn: correct train/test discipline, a leakage-free pipeline, cross-validated model comparison, and honest metrics. All computation runs through `execute_code` (sandboxed Python; scikit-learn, numpy, pandas, scipy, and matplotlib are preinstalled).

Adapted from K-Dense scientific-agent-skills (MIT license).

This skill is for prediction: does the model generalize, and how well. For inference — coefficients, standard errors, hypothesis tests about a covariate's effect — use the statsmodels skill instead; the two are complementary, not overlapping. For plain hypothesis testing and effect sizes without a predictive model, use the statistical-analysis skill.

## When to apply

- Classification or regression where the deliverable is a model that predicts well on new data
- Clustering or dimensionality reduction to explore structure in a dataset
- Comparing several algorithms or hyperparameter settings under cross-validation
- Building a preprocessing-plus-model pipeline that must not leak test information into training

## Workflow

1. Split before touching anything else: hold out a test set (stratified for classification) and never let it influence preprocessing, feature selection, or model choice.
2. Build preprocessing as a pipeline, not free-standing transforms: imputation, scaling, and encoding belong inside a `Pipeline`/`ColumnTransformer` so `fit` only ever sees training folds. Fitting a scaler or imputer on the full dataset before splitting is the single most common source of inflated validation scores.
3. Choose a baseline first — `DummyClassifier`/`DummyRegressor` or a simple linear model — so later complexity has to earn its keep against a known floor.
4. Select candidate model families appropriate to the data (linear models, tree ensembles, support vector machines, nearest neighbors) and compare them with cross-validation on the training set only.
5. Tune hyperparameters with `GridSearchCV` or `RandomizedSearchCV` wrapping the full pipeline, using nested cross-validation when the reported score itself needs to be unbiased.
6. Fit the selected pipeline once on the full training set and evaluate exactly once on the untouched test set.
7. Report metrics with cross-validation spread (mean and standard deviation across folds), not a single point estimate.

## Preprocessing and leakage

- Numeric features: impute (median for skewed data), then scale — `StandardScaler` for models sensitive to feature scale (linear models, SVMs, k-nearest neighbors), no scaling required for tree ensembles.
- Categorical features: `OneHotEncoder` for nominal categories, ordinal encoding only when a true order exists; set `handle_unknown="ignore"` so unseen test-time categories do not crash inference.
- Class imbalance: prefer `class_weight="balanced"` or stratified sampling over naive oversampling before the split; if resampling is used, it must sit inside the cross-validation fold, never applied once to the whole dataset before splitting.
- Feature selection and dimensionality reduction (PCA, `SelectKBest`) are model-fitting steps — they go inside the pipeline, fit only on training folds, exactly like the scaler.

## Model selection and validation

- Use stratified k-fold cross-validation for classification, plain k-fold for regression, and a time-respecting split (no shuffling) for any sequential or time-ordered data — a random split on time series leaks the future into training.
- Classification metrics: accuracy is misleading under imbalance — report precision, recall, F1, and ROC-AUC or PR-AUC (PR-AUC when the positive class is rare), and inspect the confusion matrix, not just the aggregate score.
- Regression metrics: report RMSE or MAE in the outcome's native units alongside R², since R² alone hides whether errors are practically acceptable.
- Learning curves and validation curves diagnose underfitting (both train and validation scores low) versus overfitting (train high, validation low) before reaching for a more complex model.
- Compare model families under the same cross-validation folds so the comparison is apples-to-apples, and report the spread across folds, not just the mean.

## Clustering and dimensionality reduction

- K-means requires scaled features and a chosen k — support the choice with silhouette score and an elbow plot rather than picking k by eye alone; DBSCAN or hierarchical clustering when cluster shapes are non-convex or the count of clusters is unknown.
- PCA for linear dimensionality reduction: report explained-variance ratio per component and the cumulative curve so the retained dimensionality is a stated decision, not a default.
- t-SNE and UMAP are for visualization, not for feeding downstream models — their distances are not meaningful outside the 2D/3D embedding they were fit for.

## Reporting

Record with `create_project_note`: the pipeline definition (preprocessing steps and model), the cross-validation scheme and fold count, metrics with their cross-validation spread, the held-out test score, and any hyperparameters selected by search. Plots produced with `execute_code` should include the confusion matrix or ROC curve for classification, and predicted-versus-actual with a residual plot for regression.

## Pitfalls

1. Fitting a scaler, imputer, or feature selector on the full dataset before splitting — the classic leakage that inflates every downstream number.
2. Reporting a single train/test score with no cross-validation spread — one split is one sample of the model's true variance.
3. Accuracy on an imbalanced dataset as the headline metric — a model that always predicts the majority class scores high and predicts nothing useful.
4. Random k-fold splits on time-ordered data — the model trains on the future and tests on the past.
5. Tuning hyperparameters against the test set, even implicitly by re-running until the test score looks good — that set is then no longer held out.
6. Treating resampling (SMOTE-style oversampling) as a one-time preprocessing step outside the cross-validation loop.
7. No baseline — added model complexity that never beats a dummy classifier is complexity with no payoff.
