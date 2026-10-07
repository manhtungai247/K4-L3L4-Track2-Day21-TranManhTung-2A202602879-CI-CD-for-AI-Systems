import importlib
import sys

import boto3
import joblib
import pytest
from fastapi.testclient import TestClient


class StubModel:
    def predict(self, rows):
        return [1]


def _import_serve(monkeypatch):
    monkeypatch.delenv("ARTIFACT_BUCKET", raising=False)
    sys.modules.pop("src.serve", None)
    importlib.invalidate_caches()
    return importlib.import_module("src.serve")


def _model_file(tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump(StubModel(), path)
    return path


def _client_with_local_model(serve, monkeypatch, model_path):
    monkeypatch.setattr(serve, "download_model", lambda: str(model_path))
    return TestClient(serve.app)


def test_import_does_not_access_aws_or_require_bucket(monkeypatch):
    def fail_if_called(*args, **kwargs):
        pytest.fail("importing the serving module must not call AWS")

    monkeypatch.setattr(boto3, "client", fail_if_called)
    serve = _import_serve(monkeypatch)
    assert serve.app is not None


def test_healthz_returns_ok(tmp_path, monkeypatch):
    serve = _import_serve(monkeypatch)
    with _client_with_local_model(serve, monkeypatch, _model_file(tmp_path)) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_score_returns_prediction_and_label(tmp_path, monkeypatch):
    serve = _import_serve(monkeypatch)
    with _client_with_local_model(serve, monkeypatch, _model_file(tmp_path)) as client:
        response = client.post("/score", json={"features": [28, 2, 14, 2, 11, 0, 1, 0, 0, 45]})
    assert response.status_code == 200
    assert response.json() == {"prediction": 1, "label": "thu_nhap_cao"}


def test_score_rejects_wrong_feature_count(tmp_path, monkeypatch):
    serve = _import_serve(monkeypatch)
    with _client_with_local_model(serve, monkeypatch, _model_file(tmp_path)) as client:
        response = client.post("/score", json={"features": [28, 2, 14]})
    assert response.status_code == 400
