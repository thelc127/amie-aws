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

2. It serializes the task to JSON and POSTs it to `{agent_url}/tasks`.

3. The target agent's `lambda_handler` deserializes the JSON back into an `A2ATask`, extracts the input, runs its analysis, and wraps the result in an `A2AResponse`.

4. The Ingestion Agent deserializes the HTTP response into an `A2AResponse` and checks `status`. If `ERROR`, it raises an exception. If `COMPLETE`, it extracts `output` and continues the pipeline.

Here is the dispatch helper:

```python
# backend/agents/ingestion.py, line 39
def _dispatch(agent_url: str, task: A2ATask) -> A2AResponse:
    resp = requests.post(
        f"{agent_url}/tasks",
        json=task.to_dict(),
        timeout=870,
    )
    resp.raise_for_status()
    return A2AResponse.from_dict(resp.json())
```

The 870-second timeout is just under Lambda's 900-second maximum, giving a small buffer.

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

## Why HTTP Instead of Direct Lambda Invocation

The agents could call each other using `boto3.client("lambda").invoke()` directly, skipping HTTP entirely. This system uses HTTP for two reasons:

1. **A2A compliance.** The agent-card-plus-POST-tasks pattern follows the emerging Agent-to-Agent protocol convention. If you later want to expose these agents to external systems, or replace one agent with a service running outside AWS, the HTTP interface already works.

2. **Observability.** HTTP calls through API Gateway produce access logs, latency metrics, and error rates per agent endpoint. Direct Lambda invocation produces only CloudWatch logs on the calling side.

The cost is an extra network hop per agent call (Lambda to API Gateway to Lambda instead of Lambda to Lambda). For a pipeline that takes 1-3 minutes total, the overhead of three additional API Gateway hops (milliseconds each) is not meaningful.
