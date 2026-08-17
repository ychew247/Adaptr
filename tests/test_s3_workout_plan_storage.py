import builtins

import pytest

from src.s3_workout_plan_storage import S3WorkoutPlanStorage
from src.s3_workout_plan_storage import WorkoutPlanStorageError


class FakeS3Client:
    def __init__(self):
        self.put_calls = []
        self.presign_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def generate_presigned_url(self, client_method, *, Params, ExpiresIn):
        self.presign_calls.append((client_method, Params, ExpiresIn))
        return "https://private-bucket.example.test/signed-download"


def test_storage_uploads_a_private_plan_workbook_and_returns_a_presigned_download_url():
    client = FakeS3Client()
    storage = S3WorkoutPlanStorage(client, bucket="fitness-plan-exports", expiry_seconds=600)

    object_key = storage.upload_workbook(
        b"workbook-bytes",
        user_id="user-1",
        plan_id="plan-7",
        filename="alex_workout_plan.xlsx",
    )
    download_url = storage.create_download_url(object_key, "alex_workout_plan.xlsx")

    assert object_key == "workout-plans/user-1/plan-7.xlsx"
    assert client.put_calls == [
        {
            "Bucket": "fitness-plan-exports",
            "Key": "workout-plans/user-1/plan-7.xlsx",
            "Body": b"workbook-bytes",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ServerSideEncryption": "AES256",
        }
    ]
    assert client.presign_calls == [
        (
            "get_object",
            {
                "Bucket": "fitness-plan-exports",
                "Key": "workout-plans/user-1/plan-7.xlsx",
                "ResponseContentDisposition": 'attachment; filename="alex_workout_plan.xlsx"',
                "ResponseContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
            600,
        )
    ]
    assert download_url == "https://private-bucket.example.test/signed-download"


def test_configured_storage_reports_a_clear_error_when_boto3_cannot_load(monkeypatch):
    monkeypatch.setenv("AWS_S3_WORKOUT_PLAN_BUCKET", "fitness-plan-exports")
    original_import = builtins.__import__

    def fail_boto3_import(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("SSL library unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_boto3_import)

    with pytest.raises(WorkoutPlanStorageError, match="could not be loaded"):
        S3WorkoutPlanStorage.from_environment()
