# AWS MLOps CI/CD Design

## Goal

Complete Lab Steps 2 and 3 using AWS: version datasets with DVC on S3, run a four-job GitHub Actions pipeline, and serve the trained model from an EC2-hosted FastAPI service. A DVC pointer update on `main` must trigger the same test, train, quality-gate, and release flow.

## Scope

- Use S3 as the DVC remote, store commit-specific candidates under `artifacts/candidates/<sha>/model.joblib`, and promote only approved models to `artifacts/current/model.joblib`.
- Use AWS SDK for Python (`boto3`) for model upload in CI and model download by the API; use AWS CLI to promote a passing candidate.
- Use an EC2 VM running Ubuntu, FastAPI, and Uvicorn; deploy through AWS Systems Manager (SSM) from GitHub Actions using GitHub OIDC.
- Complete the existing synthetic-data unit tests, serving API, and CI/CD workflow.
- Preserve the existing MLflow training flow and require positive-class F1 >= 0.65 before release.

## Design

### Data and credentials

- Track `train_batch1.csv`, `holdout.csv`, and `train_batch2.csv` with DVC; Git contains only `.dvc` pointer files, never the CSV contents or AWS credentials.
- Configure the DVC remote as `s3://<bucket>/dvc`.
- Local DVC uses the user's configured AWS profile or standard AWS credential chain. GitHub Actions exchanges its OIDC token for short-lived credentials through a role restricted to this repository and `main` branch. The Release job promotes a passing candidate to the current model key; the EC2 instance uses an instance profile with read access to that object and SSM managed-instance permissions.
- GitHub repository variables hold the role ARN, region, bucket name, and EC2 instance ID. No long-lived AWS access keys or SSH private key are stored in GitHub.

### CI/CD flow

1. **Unit Test:** Install requirements and run `pytest tests/ -v` on synthetic data, without AWS access.
2. **Train:** Configure AWS credentials, pull only the train and holdout datasets from DVC, train using `params.yaml`, publish `f1_score` as a job output, upload `model.joblib` to a commit-specific candidate key, and save `report.json` as a workflow artifact.
3. **Quality Gate:** Fail when `f1_score < 0.65`; release must depend on this job.
4. **Release:** Promote the approved candidate to `artifacts/current/model.joblib`, invoke SSM to restart `income-api`, then retry the instance-local `/healthz` check and fail if the service does not become healthy.

### Serving API

- At startup, download `artifacts/current/model.joblib` from the configured S3 bucket into `~/models/model.joblib`, then load it.
- `GET /healthz` returns `{"status": "ok"}`.
- `POST /score` accepts exactly 10 numeric features and returns integer prediction plus the Vietnamese label. Incorrect feature counts return HTTP 400.

## Configuration established

- AWS region `us-east-1` and the lab S3 bucket are configured.
- Local DVC uses the `lab` AWS profile; the GitHub workflow uses short-lived credentials through an OIDC role restricted to the repository's `main` branch.
- The four GitHub Actions variables are configured; EC2 has an instance profile for current-model reads and SSM management.
- The EC2 service is installed under `/srv/income-api` and listens on port 8080. Security Group access to SSH and port 8080 is limited to the approved client `/32`.

The code remains provider-specific to AWS because AWS was selected for this lab.

## Acceptance criteria

- The three synthetic-data tests pass without cloud credentials.
- The serving routes return the required responses when provided a local model fixture or a model downloaded from S3.
- A push or manual workflow run follows the four-job dependency chain; release cannot run if the F1 gate fails.
- A training-data DVC pointer commit triggers the workflow without manual dispatch.
- DVC pointer files and model object use the documented S3 paths.
- The local AWS setup instructions do not ask the user to commit or paste credentials into Git.
