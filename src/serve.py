from contextlib import asynccontextmanager

import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os

MODEL_KEY = "artifacts/current/model.joblib"
MODEL_PATH = os.path.expanduser("~/models/model.joblib")


def download_model():
    """
    Download model.joblib from S3 when the API starts.

    boto3 uses the standard AWS credential chain; on EC2 this should be the
    instance profile attached to the VM.
    """
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    client = boto3.client("s3")
    client.download_file(os.environ["ARTIFACT_BUCKET"], MODEL_KEY, MODEL_PATH)
    print("Model da duoc tai xuong tu S3.")
    return MODEL_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = joblib.load(download_model())
    yield


app = FastAPI(lifespan=lifespan)


class ScoreRequest(BaseModel):
    features: list[float]


@app.get("/healthz")
def healthz():
    """
    Endpoint kiem tra suc khoe server.
    GitHub Actions goi endpoint nay sau khi deploy de xac nhan server dang chay.

    Tra ve: {"status": "ok"}
    """
    return {"status": "ok"}


@app.post("/score")
def score(req: ScoreRequest):
    """
    Endpoint suy luan chinh.

    Dau vao : JSON {"features": [f1, f2, ..., f10]}
    Dau ra  : JSON {"prediction": <0|1>, "label": <"thu_nhap_thap"|"thu_nhap_cao">}

    Thu tu 10 dac trung (khop voi thu tu trong FEATURE_NAMES cua test):
        age, workclass, education_num, marital_status, occupation,
        relationship, sex, capital_gain, capital_loss, hours_per_week
    """
    if len(req.features) != 10:
        raise HTTPException(
            status_code=400,
            detail="Expected 10 features (adult income)",
        )

    prediction = int(app.state.model.predict([req.features])[0])
    label = "thu_nhap_cao" if prediction == 1 else "thu_nhap_thap"
    return {"prediction": prediction, "label": label}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
