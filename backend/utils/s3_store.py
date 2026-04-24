"""
S3-backed task store.
Location: backend/utils/s3_store.py

Saves and loads task state as JSON files in S3.
Simple alternative to DynamoDB for MVP.
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class TaskStore:
    def __init__(self, bucket: str, prefix: str = "tasks/"):
        self.bucket = bucket
        self.prefix = prefix
        self.s3 = boto3.client("s3")

    def _key(self, task_id: str) -> str:
        return f"{self.prefix}{task_id}.json"

    def save(self, task_id: str, data: dict) -> None:
        key = self._key(task_id)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        logger.debug("Saved task %s to s3://%s/%s", task_id, self.bucket, key)

    def load(self, task_id: str) -> dict | None:
        key = self._key(task_id)
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise