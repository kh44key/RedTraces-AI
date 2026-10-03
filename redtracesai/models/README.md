# Local Layer 2 models

Place the official FastText language model at `models/lid.176.ftz`.
It is mounted read-only in collector containers as `/app/models/lid.176.ftz`.

To train the optional spam classifier, prepare a UTF-8 CSV with `text,label`
columns and labels `cti` or `spam`, then run:

```powershell
docker compose run --rm api python -m scripts.train_spam_classifier data/spam_training.csv
```

The resulting `models/spam_classifier.joblib` stays local and is not copied
into the Docker image or committed to Git.

`models/test_spam_classifier.joblib` is a separate temporary model generated
from public MITRE ATT&CK and UCI SMS Spam examples. It is for pipeline testing
only and is not loaded by any collector.
