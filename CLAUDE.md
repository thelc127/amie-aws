# CLAUDE.md -- AMIE Reference Implementation

## What this project is

AMIE (Academic Manuscript IP Evaluator) is a multi-agent system that evaluates academic manuscripts for patentability. A user uploads a PDF; four agents (Ingestion, IDCA, NAA, AA) run a sequential pipeline that detects inventions, searches for prior art, scores references, and produces a novelty risk report.

## Architecture at a glance

- **Backend**: AWS SAM (Python 3.10, Lambda, API Gateway, S3). Five Lambdas, four API Gateways, two S3 buckets.
- **Frontend**: Next.js 16 on Vercel (React 19, Tailwind CSS, TypeScript).
- **LLM**: Claude Sonnet via Amazon Bedrock (all three analytical agents).
- **External tool**: Perplexity Sonar for patent/literature search (NAA only).
- **Inter-agent communication**: Lightweight A2A protocol over HTTP. Each agent is an independent Lambda with its own API Gateway. The Ingestion Agent orchestrates by POSTing A2ATasks and receiving A2AResponses.

## Key files

| File | Purpose |
|------|---------|
| `backend/template.yaml` | SAM template: all AWS resources, environment variables |
| `backend/samconfig.toml` | SAM deployment parameters |
| `backend/lambda_functions/handler.py` | API Lambda (routing) + Worker Lambda (entry point) |
| `backend/agents/ingestion.py` | Orchestrator: PDF extraction, calls IDCA/NAA/AA |
| `backend/agents/idca.py` | Invention Detection and Classification Agent |
| `backend/agents/naa.py` | Novelty Assessment Agent (most complex) |
| `backend/agents/aa.py` | Aggregation Agent |
| `backend/a2a/protocol.py` | A2ATask, A2AResponse, AgentCard, AGENT_CARDS registry |
| `backend/tools/perplexity_patents.py` | Perplexity Sonar API wrapper |
| `backend/utils/pdf_extractor.py` | PDF text extraction (PyMuPDF, pdfminer fallback) |
| `backend/utils/s3_store.py` | S3-backed JSON persistence for task state |

## Build and deploy

### Backend

```bash
cd backend
sam build
sam deploy          # uses saved params from samconfig.toml
sam deploy --guided # first time or to change parameters
```

Region: `us-west-2`. Stack name: `amie`. Requires Bedrock model access.

### Frontend

```bash
cd frontend
npm install
npm run dev         # local dev at localhost:3000
```

Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to the ApiUrl from SAM Outputs.

Production: deploy to Vercel with Root Directory set to `frontend`.

## Conventions

- **Agent pattern**: each agent has a `run_<name>()` function (the logic) and a `lambda_handler()` (HTTP wrapper). Both live in the same file. The handler deserializes A2ATask, calls the run function, wraps the result in A2AResponse.
- **Prompts**: LLM prompts are module-level string constants (e.g., `IDCA_SYSTEM_PROMPT`, `IDCA_USER_TEMPLATE`). Agents instruct the LLM to return JSON only; parsing strips accidental markdown fences.
- **Environment variables**: configuration reaches code through env vars defined in `template.yaml`. See `docs/02-Configuration-vs-Code.md` for the full mapping.
- **Shared CodeUri**: all Lambdas package the entire `backend/` directory. Agents import from `a2a/` and `utils/` as top-level packages via sys.path manipulation at the top of each file.
- **State persistence**: task state is saved to S3 as JSON after each pipeline stage. The frontend polls `GET /a2a/tasks/{id}`.
- **No tests currently exist.** There is no test suite.

## Things to know before editing

- Changing LLM prompts does not require configuration changes. Edit the prompt constants in the agent file and redeploy with `sam build && sam deploy`.
- Changing the Bedrock model: edit `BEDROCK_MODEL_ID` in `template.yaml` under `Globals > Function > Environment > Variables`.
- Changing the Perplexity API key: `sam deploy --parameter-overrides "PerplexityApiKey=sk-new-key AllowedOrigin=*"`.
- Adding a new agent requires changes in both `template.yaml` (Lambda, API Gateway, IAM, env vars) and code (agent file, protocol.py, ingestion.py). See `docs/02-Configuration-vs-Code.md`.
- CORS is set in two places: API Gateway config in `template.yaml` and `CORS_HEADERS` dicts in handler.py and each agent's lambda_handler. Both must agree.
- The Worker Lambda has a 900-second timeout (Lambda max). The A2A dispatch timeout is 870 seconds. NAA is the bottleneck: it makes N+1 Bedrock calls (one for structural decomposition + one per reference) plus one Perplexity call.

## Documentation

- `docs/01-SAM-and-Lambda.md` -- how SAM and Lambda work in this project
- `docs/02-Configuration-vs-Code.md` -- where configuration lives vs. where logic lives
- `docs/03-A2A-Protocol.md` -- how the agents communicate
- `docs/04-Deployment.md` -- full deployment walkthrough
- `docs/architecture-diagrams.md` -- Mermaid diagrams
- `docs/DOCUMENTATION.md` -- A2A protocol reference
- `docs/example_calls.sh` -- executable API walkthrough

## Session memory

Session memory: CLAUDE_MEMORY.md (project root) -- read at session start.
