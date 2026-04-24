"""
agents/ingestion.py
-------------------
Ingestion Agent — the A2A Orchestrator.

Responsibilities:
  1. Extract text from the uploaded PDF (via S3)
  2. POST an A2ATask to the IDCA agent endpoint → receive A2AResponse
  3. If SD == "Present", POST an A2ATask to the NAA agent endpoint
  4. POST an A2ATask to the AA agent endpoint → get final report
  5. Update task state in S3 at each step

Each agent is an independent Lambda with its own HTTP endpoint.
The orchestrator communicates with them over HTTP using the A2A protocol.
"""
import json
import logging
import os
import sys

import requests

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
for _p in [_PARENT_DIR, _THIS_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from a2a.protocol import A2ATask, A2AResponse, TaskStatus
from utils.pdf_extractor import extract_text_from_s3

logger = logging.getLogger(__name__)

IDCA_URL = os.environ["IDCA_AGENT_URL"].rstrip("/")
NAA_URL  = os.environ["NAA_AGENT_URL"].rstrip("/")
AA_URL   = os.environ["AA_AGENT_URL"].rstrip("/")


def _dispatch(agent_url: str, task: A2ATask) -> A2AResponse:
    """POST an A2ATask to an agent endpoint and return the A2AResponse."""
    logger.info("A2A dispatch → %s/tasks  task_id=%s", agent_url, task.task_id)
    resp = requests.post(
        f"{agent_url}/tasks",
        json=task.to_dict(),
        timeout=870,
    )
    resp.raise_for_status()
    return A2AResponse.from_dict(resp.json())


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
        logger.info("Ingestion [%s]: dispatching A2A task to IDCA at %s", task_id, IDCA_URL)
        idca_response = _dispatch(IDCA_URL, A2ATask(
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
            logger.info("Ingestion [%s]: dispatching A2A task to NAA at %s", task_id, NAA_URL)
            naa_response = _dispatch(NAA_URL, A2ATask(
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
        logger.info("Ingestion [%s]: dispatching A2A task to AA at %s", task_id, AA_URL)
        aa_response = _dispatch(AA_URL, A2ATask(
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