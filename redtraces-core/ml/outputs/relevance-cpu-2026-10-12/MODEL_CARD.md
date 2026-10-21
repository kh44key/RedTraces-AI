# RedTraces English relevance pilot v1

## Intended use

Research and analyst triage of English cyber-threat-intelligence text. The
pilot returns a binary relevance label and raw LinearSVC decision margin. It
does not establish that an IOC is malicious, identify an actor, or support
automated attribution. Automatic rejection is disabled by default.

## Model and evaluation

- Model: word and character TF-IDF features with a LinearSVC classifier.
- Training/evaluation: the strict RedTraces relevance dataset with document-
  disjoint train/validation/test partitions; the decision threshold was chosen
  using validation only.
- Frozen test: 2,431 formal CTI report sentences; accuracy 76.84%, relevant
  precision 69.80%, relevant recall 61.14%, macro-F1 73.92%.
- Evaluation details: `evaluation.json`.

These numbers are not Telegram, Reddit, or dark-forum performance. Expect domain
shift. The model is English-only and should be treated as a review hint until a
source-disjoint, independently human-reviewed conversation test is available.

## Data provenance and attribution

Training data is based on the RedTraces strict relevance set, which includes
SMAH-CTI (CC BY-NC 4.0) and CTI-ANN (CC BY 4.0) data. This model artifact is
provided for non-commercial academic research with attribution. The source
datasets and their license texts are in `datasets/smah-cti/` at repository
root. See the source README and papers for required academic citations.

## Runtime

The artifact is loaded by `common.relevance_ai` from this directory. Set
`CTI_RELEVANCE_ENABLED=false` to disable inference. Set
`CTI_RELEVANCE_FILTER_ENABLED=true` only for controlled experiments; it is
`false` by default so model false negatives do not discard collected signals.
