# How the Agents Communicate: The A2A Protocol

This document explains the Agent-to-Agent (A2A) communication protocol used in AMIE. Everything described here is implemented in `backend/a2a/protocol.py` and exercised in `backend/agents/ingestion.py`.

---

## The Problem A2A Solves

AMIE has four agents. Each runs as its own Lambda. The orchestrator (Ingestion Agent) needs to send work to IDCA, NAA, and AA and get results back. A2A is the message format they use.

Without a protocol, you'd be passing raw JSON dicts with ad-hoc keys between functions. That works until someone adds a field to one agent and forgets to update another. A2A gives every message a predictable shape.

## The Three Data Structures

All three are defined in `backend/a2a/protocol.py`.

### A2ATask (lines 30--58)

What the orchestrator sends to an agent. It says: "Here is work. Do it."

```python
@dataclass
class A2ATask:
    agent:      str       # "idca" | "naa" | "aa"
    input:      dict      # agent-specific payload
    task_id:    str       # UUID, auto-generated
    status:     str       # always "pending" when sent
    created_at: float     # timestamp
```

The `input` dict is different for each agent. IDCA gets `{"manuscript_text": "..."}`. NAA gets `{"manuscript_text": "...", "idca_result": {...}}`. AA gets `{"idca_result": {...}, "naa_result": {...}}`. The A2ATask wrapper is the same; the payload varies.

### A2AResponse (lines 62--89)

What an agent returns after processing. It says: "Here is the result" or "Here is what went wrong."

```python
@dataclass
class A2AResponse:
    task_id: str      # matches the request
    agent:   str      # who responded
    status:  str      # "complete" or "error"
    output:  dict     # agent-specific result
    error:   str      # empty unless status == "error"
```

### AgentCard (lines 93--111)

Self-description metadata. Each agent serves one at `GET /.well-known/agent-card.json`. It declares the agent's name, version, and what input/output schemas it expects. This is for discovery and documentation, not for runtime validation.

## How Messages Flow

The entire message flow happens in `backend/agents/ingestion.py`, specifically in the `_dispatch()` helper (line 39) and `run_ingestion()` (line 51).

### Step by Step

1. The Ingestion Agent constructs an `A2ATask` with the target agent name and input payload.

2. It serializes the task to JSON and invokes the target agent Lambda directly using `boto3.client("lambda").invoke()`, passing the task as the event body.

3. The target agent's `lambda_handler` deserializes the event back into an `A2ATask`, extracts the input, runs its analysis, and wraps the result in an `A2AResponse`.

4. The Ingestion Agent reads the Lambda response payload, deserializes it into an `A2AResponse`, and checks `status`. If `ERROR`, it raises an exception. If `COMPLETE`, it extracts `output` and continues the pipeline.

Here is the dispatch helper:

```python
# backend/agents/ingestion.py
def _dispatch(function_name: str, task: A2ATask) -> A2AResponse:
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
        return A2AResponse(
            task_id=task.task_id,
            agent=function_name,
            status=TaskStatus.ERROR,
            output={},
            error=f"Lambda error: {error_msg}",
        )

    body = json.loads(payload.get("body", "{}"))
    return A2AResponse.from_dict(body)
```

Direct Lambda invocation has no timeout imposed by API Gateway. The Worker Lambda (`amie-worker`) can wait up to its full 900-second timeout for any agent to finish.

### The Full Sequence

```
Ingestion                  IDCA                NAA                 AA
    |                        |                  |                   |
    |-- A2ATask ------------>|                  |                   |
    |<- A2AResponse ---------|                  |                   |
    |   (sd, synopsis, ...)  |                  |                   |
    |                        |                  |                   |
    |-- A2ATask --------------------------->|                       |
    |<- A2AResponse ------------------------|                       |
    |   (ss, references, ...)               |                       |
    |                        |              |                       |
    |-- A2ATask --------------------------------------------------->|
    |<- A2AResponse -------------------------------------------------|
    |   (FRT, summary, risk)                                        |
```

NAA is only called if IDCA returns `sd == "Present"` (see `ingestion.py`, line 86).

## What Each Agent Receives and Returns

### IDCA

- **Receives**: `{"manuscript_text": "..."}`
- **Returns**: `{"sd": "Present|Implied|Absent", "structural_synopsis": "...", "source_citation": "...", "fields_map": [...], "reasoning": "..."}`

### NAA

- **Receives**: `{"manuscript_text": "...", "idca_result": {...}}`
- **Returns**: `{"ss": [...], "ss_synopsis": "...", "ucs": "...", "ssr_criteria": {...}, "references": [...]}`

Each reference in the array includes `citation`, `rs_synopsis`, `css`, `ewss`, `url`, and per-block scoring.

### AA

- **Receives**: `{"idca_result": {...}, "naa_result": {...}}` (naa_result may be null)
- **Returns**: `{"context_header": {...}, "final_reference_table": [...], "executive_summary": "...", "novelty_risk": "High|Medium|Low|Indeterminate"}`

## Agent Cards

Each agent Lambda serves its card at `GET /.well-known/agent-card.json`. The cards are defined in `backend/a2a/protocol.py` starting at line 116 and registered in the `AGENT_CARDS` dict at line 181.

The card endpoint is handled in each agent's `lambda_handler`. For example, in `idca.py` at line 122:

```python
if raw_path.endswith("/.well-known/agent-card.json"):
    from a2a.protocol import AGENT_CARDS
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": _json.dumps(AGENT_CARDS["idca"].to_dict()),
    }
```

In the current implementation, the Ingestion Agent does not fetch agent cards before calling agents. The URLs are injected via environment variables at deploy time. The cards are available for external discovery and documentation.

## Why Direct Lambda Invocation Instead of HTTP

The Ingestion Agent invokes IDCA, NAA, and AA using `boto3.client("lambda").invoke()` directly rather than HTTP calls through each agent's API Gateway endpoint. The reason is the **API Gateway 29-second timeout**.

The NAA agent consistently takes 35–40 seconds because it makes multiple sequential calls to Amazon Bedrock (one for structural decomposition, one per patent reference) plus one call to the Perplexity API. When inter-agent calls were routed through API Gateway, the gateway cut the connection after 29 seconds and returned a 503 error to the caller before NAA could finish.

Direct Lambda invocation bypasses API Gateway entirely — there is no intermediate timeout. The Worker Lambda waits for each agent to return for up to its own 900-second limit.

Each agent Lambda still has its own API Gateway endpoint (defined in `template.yaml`). Those endpoints remain available for external discovery and manual testing via curl, but the internal pipeline does not use them.
