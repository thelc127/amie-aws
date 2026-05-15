"""
agents/ingestion.py
-------------------
Ingestion Agent — the A2A Orchestrator.

Responsibilities:
  1. Extract text from the uploaded PDF (via S3)
  2. Invoke IDCA Lambda directly → receive A2AResponse
  3. If SD == "Present", invoke NAA Lambda directly
  4. Invoke AA Lambda directly → get final report
  5. Update task state in S3 at each step

Agents are invoked directly as Lambda functions (bypassing API Gateway)
to avoid the 29-second API Gateway timeout on long-running agents.
"""
import json
import logging
import os
import sys

import boto3

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
for _p in [_PARENT_DIR, _THIS_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from a2a.protocol import A2ATask, A2AResponse, TaskStatus
from utils.pdf_extractor import extract_text_from_s3

logger = logging.getLogger(__name__)

_lambda_client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-west-2"))

IDCA_FUNCTION = os.environ.get("IDCA_FUNCTION_NAME", "amie-idca")
NAA_FUNCTION  = os.environ.get("NAA_FUNCTION_NAME",  "amie-naa")
AA_FUNCTION   = os.environ.get("AA_FUNCTION_NAME",   "amie-aa")


def _dispatch(function_name: str, task: A2ATask) -> A2AResponse:
    """Invoke an agent Lambda directly, bypassing API Gateway."""
    logger.info("A2A dispatch → %s  task_id=%s", function_name, task.task_id)

    event = {
        "rawPath": "/tasks",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(task.to_dict()),
    }

    response = _lambda_client.invoke(
        FunctionName   = function_name,
        InvocationType = "RequestResponse",
        Payload        = json.dumps(event).encode(),
    )

    payload = json.loads(response["Payload"].read())

    if response.get("FunctionError"):
        error_msg = payload.get("errorMessage", "Unknown Lambda error")
        logger.error("Lambda %s FunctionError: %s", function_name, error_msg)
        return A2AResponse(
            task_id=task.task_id,
            agent=function_name,
            status=TaskStatus.ERROR,
            output={},
            error=f"Lambda error: {error_msg}",
        )

    body = json.loads(payload.get("body", "{}"))
    return A2AResponse.from_dict(body)


def run_ingestion(task_id: str, s3_key: str, bucket: str, store) -> None:
    """
    Main orchestration function. Called by worker_handler in handler.py.
    Updates task state in S3 at every stage so frontend can poll progress.
    """

    task = store.load(task_id)
    if not task:
        logger.error("Ingestion: task %s not found in store", task_id)
        return

    try:
        # ── Stage 1: Extract PDF text ─────────────────────────────────────────
        task["status"] = "running"
        store.save(task_id, task)
        logger.info("Ingestion [%s]: extracting PDF from s3://%s/%s", task_id, bucket, s3_key)
        manuscript_text = extract_text_from_s3(bucket, s3_key)

        # ── Stage 2: POST A2ATask to IDCA ─────────────────────────────────────
        logger.info("Ingestion [%s]: dispatching A2A task to IDCA → %s", task_id, IDCA_FUNCTION)
        idca_response = _dispatch(IDCA_FUNCTION, A2ATask(
            agent="idca",
            input={"manuscript_text": manuscript_text},
        ))

        if idca_response.status == TaskStatus.ERROR:
            raise RuntimeError(f"IDCA failed: {idca_response.error}")

        idca_result = idca_response.output
        task["idca"]   = idca_result
        task["status"] = "idca_complete"
        store.save(task_id, task)
        logger.info("Ingestion [%s]: IDCA complete, SD=%s", task_id, idca_result.get("sd"))

        # ── Stage 3: POST A2ATask to NAA (only if SD == Present) ──────────────
        naa_result = None
        if idca_result.get("sd") == "Present":
            logger.info("Ingestion [%s]: dispatching A2A task to NAA → %s", task_id, NAA_FUNCTION)
            naa_response = _dispatch(NAA_FUNCTION, A2ATask(
                agent="naa",
                input={
                    "manuscript_text": manuscript_text,
                    "idca_result":     idca_result,
                },
            ))

            if naa_response.status == TaskStatus.ERROR:
                raise RuntimeError(f"NAA failed: {naa_response.error}")

            naa_result = naa_response.output
            task["naa"]    = naa_result
            task["status"] = "naa_complete"
            store.save(task_id, task)
            logger.info("Ingestion [%s]: NAA complete, %d references scored",
                        task_id, len(naa_result.get("references", [])))
        else:
            logger.info("Ingestion [%s]: skipping NAA (SD=%s)", task_id, idca_result.get("sd"))

        # ── Stage 4: POST A2ATask to AA ───────────────────────────────────────
        logger.info("Ingestion [%s]: dispatching A2A task to AA → %s", task_id, AA_FUNCTION)
        aa_response = _dispatch(AA_FUNCTION, A2ATask(
            agent="aa",
            input={
                "idca_result": idca_result,
                "naa_result":  naa_result,
            },
        ))

        if aa_response.status == TaskStatus.ERROR:
            raise RuntimeError(f"AA failed: {aa_response.error}")

        aa_result = aa_response.output
        task["aa"]     = aa_result
        task["status"] = "complete"
        store.save(task_id, task)
        logger.info("Ingestion [%s]: pipeline complete, novelty_risk=%s",
                    task_id, aa_result.get("novelty_risk"))

    except Exception as exc:
        logger.exception("Ingestion [%s] failed: %s", task_id, exc)
        task["status"] = "error"
        task["error"]  = str(exc)
        store.save(task_id, task)
