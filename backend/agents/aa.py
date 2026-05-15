"""
AA – Aggregation Agent.
Location: backend/agents/aa.py

Compiles IDCA + NAA outputs into the Final Reference Table (FRT) and report.
Also handles the case where SD is Implied/Absent (no NAA output).
"""
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

AA_SYSTEM = """You are AMIE's Aggregation Agent – compile patent analysis results into a clear final report.
Respond with valid JSON only. No markdown fences."""

AA_TEMPLATE = """Generate the AMIE Final Report based on the following analysis results.

IDCA RESULT:
{idca_json}

NAA RESULT (may be null if SD is not Present):
{naa_json}

Produce:
1. A Context Header summarizing Source Manuscript, Source Structure, and Status Determination.
2. A Final Reference Table (FRT) sorted by EWSS descending. Each row:
   {{ "citation": "...", "rs_synopsis": "...", "css": 72.5, "ewss": 81.0 }}
3. An Executive Summary (2-4 sentences) about novelty risk.

Return ONLY this JSON:
{{
  "context_header": {{
    "source_citation": "...",
    "ss_synopsis": "...",
    "sd": "Present|Implied|Absent",
    "fields_map": ["..."]
  }},
  "final_reference_table": [
    {{"citation": "...", "rs_synopsis": "...", "css": 0.0, "ewss": 0.0, "url": "..."}}
  ],
  "executive_summary": "...",
  "novelty_risk": "High|Medium|Low|Indeterminate"
}}"""


def run_aa(idca_result: dict, naa_result: "dict | None") -> dict:
    """Run the Aggregation Agent."""

    prompt = AA_TEMPLATE.format(
        idca_json=json.dumps(idca_result, indent=2),
        naa_json=json.dumps(naa_result, indent=2) if naa_result else "null",
    )

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": AA_SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        }),
        contentType="application/json",
        accept="application/json",
    )

    raw = json.loads(response["body"].read())
    text = raw["content"][0]["text"].strip()

    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)

    # Sort FRT by EWSS descending
    frt = result.get("final_reference_table", [])
    frt.sort(key=lambda x: float(x.get("ewss", 0)), reverse=True)
    result["final_reference_table"] = frt

    logger.info(
        "AA complete: %d references, novelty_risk=%s",
        len(frt),
        result.get("novelty_risk", "?"),
    )
    return result


# ── A2A HTTP Lambda Handler ───────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    HTTP entry point: POST /tasks
    Accepts A2ATask JSON body, returns A2AResponse JSON.
    """
    import json as _json
    import sys, os
    _p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from a2a.protocol import A2ATask, A2AResponse, TaskStatus

    CORS_HEADERS = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }

    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod", "POST")
    )
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": "{}"}

    raw_path = event.get("rawPath") or event.get("path", "")
    if raw_path.endswith("/.well-known/agent-card.json"):
        from a2a.protocol import AGENT_CARDS
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": _json.dumps(AGENT_CARDS["aa"].to_dict()),
        }

    try:
        body = _json.loads(event.get("body") or "{}")
        task = A2ATask.from_dict(body)
        result = run_aa(task.input["idca_result"], task.input.get("naa_result"))
        response = A2AResponse(
            task_id=task.task_id,
            agent="aa",
            status=TaskStatus.COMPLETE,
            output=result,
        )
    except Exception as exc:
        logger.exception("AA lambda_handler failed: %s", exc)
        response = A2AResponse(
            task_id=_json.loads(event.get("body", "{}")).get("task_id", "unknown"),
            agent="aa",
            status=TaskStatus.ERROR,
            output={},
            error=str(exc),
        )
        return {"statusCode": 500, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}

    return {"statusCode": 200, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}