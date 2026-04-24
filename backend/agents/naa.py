"""
NAA – Novelty Assessment Agent.
Location: backend/agents/naa.py

Given IDCA output (SD=Present), this agent:
  1. Builds Source Structure (SS) + SS Synopsis
  2. Designs a Structural Scoring Rubric (SSR)
  3. Builds a Unified Composite String (UCS) for patent search
  4. Calls the Perplexity Patents tool to get a List of References (LoR)
  5. For each reference, extracts Reference Structure (RS) and computes CSS/EWSS
  6. Returns scored reference list
"""
import json
import logging
import os
import sys

import boto3

# Ensure backend root is on the path so tools/ is importable
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from tools.perplexity_patents import search_patents

logger = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

NAA_SYSTEM = """You are AMIE's Novelty Assessment Agent – a senior patent analyst.
You MUST respond with valid JSON only. No prose, no markdown fences, no explanations outside JSON."""

# ── Step A: Build SS, SSR, UCS ───────────────────────────────────────────────

SS_TEMPLATE = """You are analyzing an invention from an academic manuscript.

IDCA Summary:
- Status Determination: {sd}
- Structural Synopsis: {structural_synopsis}
- Fields Map: {fields_map}

MANUSCRIPT TEXT (first 30,000 chars):
{manuscript_text}

Perform the following:

1. SOURCE STRUCTURE (SS): Decompose the invention into elemental blocks using these neutral
   categories where applicable: architecture, energy/drive, transfer_elements,
   routing_guidance, compliance_safety, sensing_measurement, external_observation,
   control_decision, materials_build. List each element with a one-line description.

2. SSR TABLE: For each SS block, assign a Weight (1-3, reflecting how critical it is to novelty).
   Define match criteria (Present=2, Partial=1, Absent=0).

3. SS SYNOPSIS: One sentence following actor → operation → object/outcome. Only SSR-listed
   elements. Present tense, plain English. No hedges, performance claims, or citations.

4. UCS (Unified Composite String): A patent/literature search string using proximity operators
   and synonyms targeting the structural elements. Aim for specificity.

Return ONLY this JSON:
{{
  "ss": [
    {{"block": "architecture", "description": "...", "weight": 3}},
    ...
  ],
  "ss_synopsis": "...",
  "ucs": "...",
  "ssr_criteria": {{
    "block_name": {{"present": "...", "partial": "...", "absent": "..."}}
  }}
}}"""

# ── Step B: Score each reference ─────────────────────────────────────────────

SCORE_TEMPLATE = """You are AMIE's Novelty Assessment Agent scoring a reference against a source invention.

SOURCE STRUCTURE (SS):
{ss_json}

SSR CRITERIA:
{ssr_json}

REFERENCE (title, snippet, or abstract):
{reference_text}

For each SS block, assess how well this reference discloses the same structural element.
Assign EXACTLY one of these four statuses per block:
- Present (score=2): The reference clearly discloses this element with comparable specificity
- Partial (score=1): The reference partially discloses or implies this element
- Absent (score=0): The reference explicitly does NOT disclose this element
- Unknown (score=0): The reference text is insufficient to determine disclosure — use this
  when the reference is a title/abstract only and simply does not mention this element at all

IMPORTANT: Use "Unknown" liberally for any block the reference text does not address.
Do NOT assume "Absent" just because an element is not mentioned — if the reference is a
short abstract, many blocks will naturally be "Unknown".

Calculate BOTH scores carefully — they will differ whenever any block is "Unknown":

CSS (Conservative Similarity Score):
  Treats Unknown as 0 — penalizes sparse references
  CSS = sum(score * weight for ALL blocks, Unknown=0) / sum(2 * weight for ALL blocks) * 100

EWSS (Evidence-Weighted Similarity Score):
  Excludes Unknown blocks from denominator entirely — rewards what IS evidenced
  EWSS = sum(score * weight for KNOWN blocks only) / sum(2 * weight for KNOWN blocks only) * 100
  A "known" block is any block with status Present, Partial, or Absent (not Unknown)

Example: 7 blocks, 3 are Unknown → CSS denominator uses all 7, EWSS denominator uses only 4.
This means EWSS will always be >= CSS when Unknown blocks exist.

Return ONLY this JSON:
{{
  "citation": "APA-style citation for the reference",
  "rs_synopsis": "One sentence: actor → operation → object/outcome for the reference technology",
  "rs_blocks": [
    {{"block": "architecture", "score": 2, "status": "Present", "evidence": "quote or section reference", "weight": 3}},
    {{"block": "sensing_measurement", "score": 0, "status": "Unknown", "evidence": "not addressed in abstract", "weight": 2}},
    ...
  ],
  "css": 28.6,
  "ewss": 66.7,
  "notes": "Any contradictions, ambiguities, or access limitations"
}}"""


def run_naa(manuscript_text: str, idca_result: dict) -> dict:
    """Run the NAA agent pipeline."""

    # ── 1. Build SS, SSR, UCS ────────────────────────────────────────────────
    ss_prompt = SS_TEMPLATE.format(
        sd=idca_result.get("sd"),
        structural_synopsis=idca_result.get("structural_synopsis", ""),
        fields_map=", ".join(idca_result.get("fields_map", [])),
        manuscript_text=manuscript_text[:30000],
    )

    ss_raw = _invoke(ss_prompt)
    ss_data = _parse_json(ss_raw)
    logger.info("SS built with %d blocks, UCS: %s", len(ss_data.get("ss", [])), ss_data.get("ucs", "")[:80])

    # ── 2. Search for prior art ───────────────────────────────────────────────
    ucs = ss_data.get("ucs", idca_result.get("structural_synopsis", ""))
    references = search_patents(ucs)
    logger.info("Patent search returned %d references", len(references))

    # ── 3. Score each reference ───────────────────────────────────────────────
    scored_refs = []
    for ref in references:
        ref_text = f"Title: {ref.get('title', '')}\n{ref.get('abstract', ref.get('snippet', ''))}"
        score_prompt = SCORE_TEMPLATE.format(
            ss_json=json.dumps(ss_data.get("ss", []), indent=2),
            ssr_json=json.dumps(ss_data.get("ssr_criteria", {}), indent=2),
            reference_text=ref_text[:4000],
        )
        try:
            score_raw = _invoke(score_prompt)
            score_data = _parse_json(score_raw)
            score_data["url"] = ref.get("url", "")
            scored_refs.append(score_data)
        except Exception as exc:
            logger.warning("Failed to score reference '%s': %s", ref.get("title", ""), exc)
            scored_refs.append({
                "citation": ref.get("title", "Unknown"),
                "rs_synopsis": "Could not score this reference.",
                "css": 0.0,
                "ewss": 0.0,
                "url": ref.get("url", ""),
                "error": str(exc),
            })

    return {
        "ss": ss_data.get("ss", []),
        "ss_synopsis": ss_data.get("ss_synopsis", ""),
        "ucs": ucs,
        "ssr_criteria": ss_data.get("ssr_criteria", {}),
        "references": scored_refs,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _invoke(user_prompt: str) -> str:
    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": NAA_SYSTEM,
            "messages": [{"role": "user", "content": user_prompt}],
        }),
        contentType="application/json",
        accept="application/json",
    )
    raw = json.loads(response["body"].read())
    return raw["content"][0]["text"].strip()


def _parse_json(text: str) -> dict:
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


# ── A2A HTTP Lambda Handler ───────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    """
    HTTP entry point: POST /tasks
    Accepts A2ATask JSON body, returns A2AResponse JSON.
    """
    import json as _json
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
            "body": _json.dumps(AGENT_CARDS["naa"].to_dict()),
        }

    try:
        body = _json.loads(event.get("body") or "{}")
        task = A2ATask.from_dict(body)
        result = run_naa(task.input["manuscript_text"], task.input["idca_result"])
        response = A2AResponse(
            task_id=task.task_id,
            agent="naa",
            status=TaskStatus.COMPLETE,
            output=result,
        )
    except Exception as exc:
        logger.exception("NAA lambda_handler failed: %s", exc)
        response = A2AResponse(
            task_id=_json.loads(event.get("body", "{}")).get("task_id", "unknown"),
            agent="naa",
            status=TaskStatus.ERROR,
            output={},
            error=str(exc),
        )
        return {"statusCode": 500, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}

    return {"statusCode": 200, "headers": CORS_HEADERS, "body": _json.dumps(response.to_dict())}