"""Private Amazon S3 storage for generated workout-plan workbooks."""

from __future__ import annotations

import os
from typing import Any


XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DEFAULT_URL_EXPIRY_SECONDS = 900


class WorkoutPlanStorageError(RuntimeError):
    """Raised when an S3 workbook upload or download link cannot be created."""


class S3WorkoutPlanStorage:
    def __init__(self, client: Any, *, bucket: str, expiry_seconds: int = DEFAULT_URL_EXPIRY_SECONDS) -> None:
        self.client = client
        self.bucket = bucket
        self.expiry_seconds = expiry_seconds

    @classmethod
    def from_environment(cls) -> "S3WorkoutPlanStorage | None":
        bucket = os.getenv("AWS_S3_WORKOUT_PLAN_BUCKET", "").strip()
        if not bucket:
            return None
        try:
            import boto3
        except ImportError as error:
            raise WorkoutPlanStorageError(
                "The S3 client could not be loaded. Install boto3 and verify this Python environment can load SSL."
            ) from error
        try:
            expiry_seconds = int(
                os.getenv("AWS_S3_WORKOUT_PLAN_URL_EXPIRY_SECONDS", str(DEFAULT_URL_EXPIRY_SECONDS))
            )
            if expiry_seconds <= 0:
                raise ValueError
        except ValueError as error:
            raise WorkoutPlanStorageError(
                "AWS_S3_WORKOUT_PLAN_URL_EXPIRY_SECONDS must be a positive number of seconds."
            ) from error
        return cls(
            boto3.client("s3", region_name=os.getenv("AWS_REGION") or None),
            bucket=bucket,
            expiry_seconds=expiry_seconds,
        )

    @staticmethod
    def object_key(*, user_id: str, plan_id: str) -> str:
        return f"workout-plans/{user_id}/{plan_id}.xlsx"

    def upload_workbook(
        self,
        workbook_bytes: bytes,
        *,
        user_id: str,
        plan_id: str,
        filename: str,
    ) -> str:
        del filename  # The friendly filename is supplied when generating the download URL.
        object_key = self.object_key(user_id=user_id, plan_id=plan_id)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=workbook_bytes,
                ContentType=XLSX_CONTENT_TYPE,
                ServerSideEncryption="AES256",
            )
        except Exception as error:
            raise WorkoutPlanStorageError("I could not upload your workout workbook to secure storage.") from error
        return object_key

    def create_download_url(self, object_key: str, filename: str) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": object_key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                    "ResponseContentType": XLSX_CONTENT_TYPE,
                },
                ExpiresIn=self.expiry_seconds,
            )
        except Exception as error:
            raise WorkoutPlanStorageError("I could not create a secure download link for your workout workbook.") from error
