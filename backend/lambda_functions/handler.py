"""
AMIE – Lambda Handler
Routes HTTP requests and delegates to the Ingestion Agent orchestrator.
Agent-to-agent communication now happens over HTTP — this handler no longer
imports IDCA, NAA, or AA directly.
"""
import json
import os
import sys
import uuid
import time
import boto3
import logging
from botocore.config import Config

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
for _p in [_PARENT_DIR, _THIS_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agents.ingestion import run_ingestion
from utils.s3_store import TaskStore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

s3 = boto3.client(
    "s3",
    region_name="us-west-2",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
)
store = TaskStore(bucket=os.environ["TASK_BUCKET"], prefix="tasks/")

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json",
}


def respond(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers":    CORS_HEADERS,
        "body":       json.dumps(body),
    }


# ── Router ────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    logger.info("Event: %s", json.dumps(event, default=str))

    raw_path = event.get("rawPath") or event.get("path", "")
    method   = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod", "GET")
    )

    # Strip /prod prefix
    if raw_path.startswith("/prod/"):
        path = raw_path[5:]
    elif raw_path == "/prod":
        path = "/"
    else:
        path = raw_path

    if not path.startswith("/"):
        path = f"/{path}"

    logger.info("Routing: method=%s path=%s", method, path)

    if method == "OPTIONS":
        return respond(200, {})

    # ── Agent Card (orchestrator only — each agent Lambda serves its own card) ──
    if path == "/.well-known/agent-card.json":
        return get_agent_card("ingestion")

    # ── API Routes ────────────────────────────────────────────────────────────
    if path == "/upload-url" and method == "POST":
        return get_upload_url(event)

    if path == "/a2a/tasks" and method == "POST":
        return create_task(event)

    if path.startswith("/a2a/tasks/") and method == "GET":
        task_id = path.split("/")[-1]
        return get_task(task_id)

    logger.warning("No route matched: method=%s path=%s", method, path)
    return respond(404, {"error": "Not found", "path": path})


# ── Agent Cards ───────────────────────────────────────────────────────────────

def get_agent_card(agent_name: str) -> dict:
    from a2a.protocol import AGENT_CARDS
    card = AGENT_CARDS.get(agent_name)
    if not card:
        return respond(404, {"error": f"No agent card for '{agent_name}'"})
    return respond(200, card.to_dict())


# ── Upload URL ────────────────────────────────────────────────────────────────

def get_upload_url(event: dict) -> dict:
    body     = json.loads(event.get("body") or "{}")
    filename = body.get("filename", "manuscript.pdf")
    bucket   = os.environ["MANUSCRIPT_BUCKET"]
    key      = f"uploads/{uuid.uuid4()}/{filename}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": "application/pdf"},
        ExpiresIn=300,
    )
    logger.info("Generated presigned URL for key: %s", key)
    return respond(200, {"upload_url": url, "s3_key": key, "bucket": bucket})


# ── Create Task ───────────────────────────────────────────────────────────────

def create_task(event: dict) -> dict:
    body    = json.loads(event.get("body") or "{}")
    s3_key  = body.get("s3_key")
    bucket  = body.get("bucket", os.environ["MANUSCRIPT_BUCKET"])

    if not s3_key:
        return respond(400, {"error": "s3_key is required"})

    task_id = str(uuid.uuid4())
    task = {
        "task_id":    task_id,
        "status":     "pending",
        "created_at": int(time.time()),
        "s3_key":     s3_key,
        "bucket":     bucket,
        "idca":       None,
        "naa":        None,
        "aa":         None,
        "error":      None,
    }
    store.save(task_id, task)

    # Invoke worker Lambda asynchronously
    boto3.client("lambda", region_name="us-west-2").invoke(
        FunctionName  = os.environ["WORKER_FUNCTION_NAME"],
        InvocationType= "Event",
        Payload       = json.dumps({"task_id": task_id, "s3_key": s3_key, "bucket": bucket}),
    )

    return respond(202, {"task_id": task_id, "status": "pending"})


# ── Get Task ──────────────────────────────────────────────────────────────────

def get_task(task_id: str) -> dict:
    task = store.load(task_id)
    if not task:
        return respond(404, {"error": "Task not found"})
    return respond(200, task)


# ── Worker Entry Point ────────────────────────────────────────────────────────

def worker_handler(event: dict, context) -> None:
    """
    Entry point for the worker Lambda.
    Delegates entirely to the Ingestion Agent orchestrator.
    """
    task_id = event["task_id"]
    s3_key  = event["s3_key"]
    bucket  = event["bucket"]

    logger.info("Worker starting: task_id=%s", task_id)
    run_ingestion(task_id, s3_key, bucket, store)
    logger.info("Worker finished: task_id=%s", task_id)