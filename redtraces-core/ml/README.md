# RedTraces CTI relevance model

This directory contains the reproducible training pipeline for the RedTraces
message-relevance classifier. It is deliberately separate from regular
expressions: regex extracts exact IOCs, while the model classifies message
meaning as `RELEVANT` or `IRRELEVANT`.

## Data used

The combined academic dataset contains:

- 12,304 human-annotated SMAH-CTI sentences with the authors' frozen
  report-level train/validation/test split.
- 2,467 manually cross-annotated CTI-ANN X summaries, added to training only.

The preparation step removes training rows that duplicate validation/test
text, contradictory training labels, blank text, and duplicate training text.
It never changes or relabels validation/test rows. The strict output currently
contains 10,576 training, 1,238 validation, and 2,431 test rows.

Do not add weak Telegram or dark-forum labels directly to the trusted training
file. They must first be reviewed under the project annotation policy. Keep
the official test set frozen even after collecting more in-domain data.

## Prepare

```powershell
python ml/prepare_relevance_dataset.py `
  ..\datasets\smah-cti\redtraces_relevance.csv `
  ..\datasets\smah-cti\redtraces_relevance_strict.csv `
  --removed-csv ..\datasets\smah-cti\removed_training_rows.csv
```

## Fine-tune

A CUDA GPU is strongly recommended. The default model is
`ehsanaghaei/SecureBERT`, which produced the strongest frozen-test accuracy in
the current RedTraces comparison. The trainer uses balanced class weights and
selects the checkpoint by validation macro-F1 so the minority `RELEVANT` class
is not ignored.

```powershell
python -m pip install -r ml/requirements.txt
python ml/train_securebert.py `
  ..\datasets\smah-cti\redtraces_relevance_strict.csv `
  models\securebert-relevance
```

The output includes the saved model, validation threshold sweep, frozen-test
predictions, and `evaluation.json`. Never report training accuracy as model
accuracy, and never tune against the test labels.

## Verified comparison

The frozen 2,431-row report-level test set currently gives:

| Run | Accuracy | Relevant recall | Macro-F1 |
|---|---:|---:|---:|
| SecureBERT accuracy mode | 80.95% | 65.31% | 78.36% |
| SecureBERT high-recall mode | 79.06% | 79.93% | — |
| DistilBERT baseline | 80.30% | 68.91% | 78.14% |
| SecureBERT2 V5 strict augmented run | 79.56% | 59.63% | 76.26% |

The verified 90% target has **not** been met. The lower-threshold high-recall
mode is recommended for discovery/triage, while analyst review remains
mandatory. Exact machine-readable metrics are in `validated_results.json`.

## Deployment contract

The classifier output should be stored as metadata alongside each collected
message:

```json
{
  "model": "ehsanaghaei/SecureBERT",
  "label": "RELEVANT",
  "probability_relevant": 0.87,
  "threshold": 0.50
}
```

Collection permissions, source provenance, deduplication, regex IOC
extraction, and analyst review remain separate controls. A model prediction is
triage evidence, not proof that a person or indicator is malicious.
# Local training and inference

The runtime includes the **English relevance pilot v1** at
`ml/outputs/relevance-cpu-2026-10-12/model.joblib`. The API and collectors load
it through `common.relevance_ai`; `GET /api/ai/status` reports availability and
the measured evaluation. `POST /api/ai/classify` accepts `{"text":"..."}` and
returns an advisory label plus the raw SVM margin (not a probability).

Automatic filtering based on the model is off by default. Set
`CTI_RELEVANCE_ENABLED=false` to disable model inference or
`CTI_RELEVANCE_FILTER_ENABLED=true` only for a controlled experiment. The pilot
is English-only and its 76.84% accuracy / 73.92% macro-F1 were measured on 2,431
held-out formal CTI report sentences. Do not report those as Telegram or
dark-forum accuracy; see the model card and evaluation for limitations.

The artifact is provided for non-commercial academic research with attribution
because the training set includes SMAH-CTI (CC BY-NC 4.0). Review dataset
licenses before using it commercially.
