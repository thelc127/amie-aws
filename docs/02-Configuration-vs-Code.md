# Configuration vs. Code: Where Things Live

This document maps every piece of configuration and logic in the AMIE backend to its file. The goal is to answer: "I need to change X; which file do I edit?"

---

## The Split

Configuration tells AWS what resources to create and how to wire them together. Code tells those resources what to do when invoked. In this project, the boundary is clean.

### Configuration Files

| File | What It Controls |
|------|-----------------|
| `backend/template.yaml` | All AWS resources: Lambdas, API Gateways, S3 buckets, IAM role, log groups. Also defines environment variables that Lambdas read at runtime. |
| `backend/samconfig.toml` | Deployment parameters: stack name, region, S3 prefix for artifacts, IAM capability acknowledgment. |
| `backend/requirements.txt` | Python dependencies installed at build time. |
| `frontend/.env.local` | Frontend environment: the API URL the frontend calls. |
| `frontend/next.config.js` | Next.js build configuration. |

### Code Files

| File | What It Does |
|------|-------------|
| `backend/lambda_functions/handler.py` | HTTP routing (API Lambda) and pipeline entry point (Worker Lambda). No business logic; it delegates to `agents/ingestion.py`. |
| `backend/agents/ingestion.py` | Orchestrator logic: extract PDF, call IDCA/NAA/AA in sequence, persist state. |
| `backend/agents/idca.py` | Invention detection: LLM prompt, Bedrock call, JSON parsing, HTTP handler. |
| `backend/agents/naa.py` | Novelty assessment: structural decomposition, patent search, reference scoring, HTTP handler. |
| `backend/agents/aa.py` | Aggregation: compile results into final report, HTTP handler. |
| `backend/a2a/protocol.py` | Data structures (A2ATask, A2AResponse, AgentCard) and agent card definitions. |
| `backend/tools/perplexity_patents.py` | Perplexity Sonar API wrapper for prior art search. |
| `backend/utils/pdf_extractor.py` | PDF text extraction from S3 using PyMuPDF or pdfminer. |
| `backend/utils/s3_store.py` | S3-backed JSON persistence for task state. |

---

## Common "I Need to Change X" Scenarios

### "I want to change which LLM model the agents use"

Edit `backend/template.yaml`, under `Globals > Function > Environment > Variables`:

```yaml
BEDROCK_MODEL_ID: "us.anthropic.claude-sonnet-4-20250514-v1:0"
```

All three agent Lambdas read this environment variable at import time. Redeploy with `sam build && sam deploy`.

### "I want to change the Perplexity API key"

The key is a SAM parameter, not hardcoded. It is passed at deploy time:

```yaml
# template.yaml
Parameters:
  PerplexityApiKey:
    Type: String
    NoEcho: true
```

To update it, run `sam deploy --parameter-overrides PerplexityApiKey=sk-new-key-here`. Or use `sam deploy --guided` and enter the new value when prompted.

The key flows from the SAM parameter into the Lambda environment variable `PERPLEXITY_API_KEY`, which `backend/tools/perplexity_patents.py` reads at line 21.

### "I want to change what the IDCA agent does"

Edit the prompts and logic in `backend/agents/idca.py`. The system prompt starts at line 24 (`IDCA_SYSTEM_PROMPT`). The user prompt template starts at line 29 (`IDCA_USER_TEMPLATE`). The Bedrock call is in `run_idca()` at line 62. Same pattern for NAA (`naa.py`) and AA (`aa.py`).

No configuration changes needed. Redeploy with `sam build && sam deploy`.

### "I want to add a new agent"

This requires changes in both configuration and code:

1. **Code**: Create `backend/agents/new_agent.py` with a `run_new_agent()` function and a `lambda_handler()` for HTTP. Follow the pattern in `idca.py`.
2. **Code**: Add an AgentCard to `backend/a2a/protocol.py` and register it in `AGENT_CARDS`.
3. **Code**: Update `backend/agents/ingestion.py` to call the new agent at the appropriate pipeline stage.
4. **Configuration**: Add a new Lambda function, HttpApi, and LogGroup to `backend/template.yaml`. Follow the IDCA block as a template.
5. **Configuration**: Add the new agent's URL as an environment variable on the Worker Lambda.
6. **Configuration**: Add the new Lambda's ARN to the IAM policy's `LambdaInvoke` statement.

### "I want to change the frontend API URL"

Edit `frontend/.env.local`. If deployed on Vercel, update the environment variable in the Vercel dashboard. No backend changes needed.

### "I want to change Lambda timeout or memory"

Edit `backend/template.yaml`. Global defaults are under `Globals > Function`. Per-function overrides are on individual function resources (e.g., `WorkerFunction` has `Timeout: 900` and `MemorySize: 2048`).

### "I want to change CORS settings"

CORS is configured in two places:

1. **API Gateway level**: in `template.yaml`, each `AWS::Serverless::HttpApi` resource has a `CorsConfiguration` block.
2. **Lambda response level**: in `handler.py` (line 35) and in each agent's `lambda_handler`, the `CORS_HEADERS` dict is attached to every response.

Both must agree. If you restrict the origin at the API Gateway level but leave `*` in the Lambda headers, it will still work but is inconsistent. Change both.

---

## Environment Variables: The Seam Between Configuration and Code

Environment variables are how configuration reaches code at runtime. They are defined in `template.yaml` and read by Python's `os.environ` in the code files.

| Variable | Defined In (template.yaml) | Read By | Purpose |
|----------|---------------------------|---------|---------|
| `MANUSCRIPT_BUCKET` | Globals | `handler.py` | S3 bucket name for uploaded PDFs |
| `TASK_BUCKET` | Globals | `handler.py` | S3 bucket name for task state JSON |
| `BEDROCK_MODEL_ID` | Globals | `idca.py`, `naa.py`, `aa.py` | Which Claude model to invoke |
| `PERPLEXITY_API_KEY` | Globals | `perplexity_patents.py` | API authentication for patent search |
| `PERPLEXITY_PATENTS_ENDPOINT` | Globals | `perplexity_patents.py` | Perplexity API URL |
| `PERPLEXITY_MAX_RESULTS` | Globals | `perplexity_patents.py` | Max references to return |
| `PATENT_BACKEND` | Globals | `perplexity_patents.py` | Which search backend to use |
| `WORKER_FUNCTION_NAME` | ApiFunction | `handler.py` | Lambda name for async invocation |
| `IDCA_AGENT_URL` | WorkerFunction | `ingestion.py` | IDCA agent HTTP endpoint |
| `NAA_AGENT_URL` | WorkerFunction | `ingestion.py` | NAA agent HTTP endpoint |
| `AA_AGENT_URL` | WorkerFunction | `ingestion.py` | AA agent HTTP endpoint |

The `Globals` section sets variables on all Lambdas. Individual function definitions can add or override variables. The Worker Lambda adds the three agent URLs because only it needs them.
