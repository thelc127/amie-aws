"""
IDCA – Invention Detection and Classification Agent.
Location: backend/agents/idca.py

Detects whether a Source Manuscript discloses a concrete, useful technology
and returns:
  sd                  : Present | Implied | Absent
  structural_synopsis : One-sentence description
  fields_map          : List of academic/engineering fields
  source_citation     : APA-style citation
"""
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")


IDCA_SYSTEM_PROMPT = """You are AMIE – the Academic Manuscript IP Evaluator.
Your role: ingest a manuscript, detect and classify inventions for patent analysis.
You MUST respond with valid JSON only. No prose, no markdown fences."""


IDCA_USER_TEMPLATE = """Analyze the following academic manuscript and perform these steps:

1. Assess Concreteness: Does the manuscript describe structural elements, mechanisms,
   or processes specific enough for a skilled person to understand how to build and operate it?

2. Assess Utility: Is the technology directed toward a practical application or function
   (not just background or abstract theory)?

3. Assign Status Determination (SD):
   - "Present" = clearly discloses a concrete, useful technology
   - "Implied" = suggests a technology but only indirectly or incompletely
   - "Absent" = does not disclose a concrete, useful technology

4. Generate a structural synopsis (one sentence: actor → operation → object/outcome).

5. Generate an APA-style citation for this manuscript.

6. Generate a Fields Map: a short list of academic/engineering domains required to understand
   the technology (plain strings, 3–8 items).

Return ONLY this JSON structure, no markdown:
{{
  "sd": "Present|Implied|Absent",
  "structural_synopsis": "...",
  "source_citation": "...",
  "fields_map": ["field1", "field2", "..."],
  "reasoning": "Brief explanation of why this SD was assigned"
}}

MANUSCRIPT TEXT:
{manuscript_text}"""


def run_idca(manuscript_text: str) -> dict:
    """Run the IDCA agent and return structured JSON result."""
    truncated = manuscript_text[:40000]  # Bedrock token budget

    prompt = IDCA_USER_TEMPLATE.format(manuscript_text=truncated)

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "system": IDCA_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }),
        contentType="application/json",
        accept="application/json",
    )

    raw = json.loads(response["body"].read())
    text = raw["content"][0]["text"].strip()

    # Strip accidental markdown fences if model adds them
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)
    logger.info("IDCA result: sd=%s", result.get("sd"))
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
            "body": _json.dumps(AGENT_CARDS["idca"].to_dict()),
        }

    try:
        body = _json.loads(event.get("body") or "{}")
        task = A2ATask.from_dict(body)
        result = run_idca(task.input["manuscript_text"])
        response = A2AResponse(
            task_id=task.task_id,
            agent="idca",
            status=TaskStatus.COMPLETE,
            output=result,
        )
    except Exception as exc:
        logger.exception("IDCA lambda_handler failed: %s", exc)
        response = A2AResponse(
            task_id=event.get("body", "{}") and _json.loads(event.get("body", "{}")).get("task_id", "unknown"),
            agent="idca",
            status=TaskStatus.ERROR,
            output={},
            error=str(exc),
        )
        return {"statusCode": 500, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}

    return {"statusCode": 200, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}