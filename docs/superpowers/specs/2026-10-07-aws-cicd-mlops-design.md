# AWS MLOps CI/CD Design

## Goal

Complete Lab Step 2 using AWS: version datasets with DVC on S3, run a four-job GitHub Actions pipeline, and serve the trained model from an EC2-hosted FastAPI service.

## Scope

- Use S3 as the DVC remote and as the location for `artifacts/current/model.joblib`.
- Use AWS SDK for Python (`boto3`) for model upload in CI and model download by the API.
- Use an EC2 VM running Ubuntu, FastAPI, and Uvicorn; deploy by SSH from GitHub Actions.
- Complete the existing synthetic-data unit tests, serving API, and CI/CD workflow.
- Preserve the existing MLflow training flow and require positive-class F1 >= 0.65 before release.

## Design

### Data and credentials

- Track `train_batch1.csv`, `holdout.csv`, and `train_batch2.csv` with DVC; Git contains only `.dvc` pointer files, never the CSV contents or AWS credentials.
- Configure the DVC remote as `s3://<bucket>/dvc`.
- Local DVC uses the user's configured AWS profile or standard AWS credential chain. GitHub Actions receives AWS credentials through repository secrets and exports them to the job environment. The EC2 instance uses an instance profile with read access to the current model object.
- Use a separate GitHub secret for the model bucket name and the existing SSH connection secrets for EC2 deployment.

### CI/CD flow

1. **Unit Test:** Install requirements and run `pytest tests/ -v` on synthetic data, without AWS access.
2. **Train:** Configure AWS credentials, pull only the train and holdout datasets from DVC, train using `params.yaml`, publish `f1_score` as a job output, upload `model.joblib` to S3, and save `report.json` as a workflow artifact.
3. **Quality Gate:** Fail when `f1_score < 0.65`; release must depend on this job.
4. **Release:** SSH to EC2, restart `income-api`, then retry the local `/healthz` check and fail if the service does not become healthy.

### Serving API

- At startup, download `artifacts/current/model.joblib` from the configured S3 bucket into `~/models/model.joblib`, then load it.
- `GET /healthz` returns `{"status": "ok"}`.
- `POST /score` accepts exactly 10 numeric features and returns integer prediction plus the Vietnamese label. Incorrect feature counts return HTTP 400.

## Configuration still required

- AWS region and bucket name.
- AWS credentials/profile for local DVC and permission to create or use S3 and EC2 resources.
- GitHub Actions secrets and EC2 SSH access.

The code changes should remain provider-specific to AWS because the user selected AWS. No resources should be created until the account, region, and bucket choice are known.

## Acceptance criteria

- The three synthetic-data tests pass without cloud credentials.
- The serving routes return the required responses when provided a local model fixture or a model downloaded from S3.
- A push or manual workflow run follows the four-job dependency chain; release cannot run if the F1 gate fails.
- DVC pointer files and model object use the documented S3 paths.
- The local AWS setup instructions do not ask the user to commit or paste credentials into Git.
