# AMIE: Academic Manuscript IP Evaluator

AMIE is a multi-agent system that evaluates academic manuscripts for patentability. You upload a PDF. AMIE reads it, decides whether it describes a concrete invention, searches for prior art, scores each reference against the invention's structure, and produces a novelty risk report.

<img width="919" height="416" alt="AMIE pipeline diagram" src="https://github.com/user-attachments/assets/ab439df7-0ecc-4de1-97ab-2ea38abd6382" />

---

## What AMIE Does

The system answers one question: **does this manuscript describe something novel enough to patent?**

It answers that question through a four-agent pipeline:

```
User uploads PDF
       |
       v
  [API Lambda] -- generates presigned S3 URL, creates task,
       |           invokes Worker Lambda async
       v
  [Worker Lambda / Ingestion Agent]
       |
       |-- Extract PDF text from S3
       |
       |-- POST to IDCA --> SD, synopsis, fields, citation
       |
       |-- if SD == "Present":
       |      POST to NAA --> structural decomposition,
       |                       patent search, scored references
       |
       +-- POST to AA --> final report, novelty risk rating

  (state saved to S3 after each step; frontend polls GET /a2a/tasks/{id})
```

### The Four Agents

| Agent | File | Role |
|-------|------|------|
| **Ingestion** | `backend/agents/ingestion.py` | Orchestrator. Extracts PDF text, calls the other three agents in sequence over HTTP, saves pipeline state to S3 after each step. |
| **IDCA** | `backend/agents/idca.py` | Invention Detection and Classification. Reads the manuscript and assigns a Status Determination: Present (concrete invention disclosed), Implied (something there but incomplete), or Absent (no invention). Also produces a structural synopsis, fields map, and citation. |
| **NAA** | `backend/agents/naa.py` | Novelty Assessment. Only runs if SD == "Present". Decomposes the invention into structural blocks, builds a scoring rubric with weights, constructs a search query, calls Perplexity Sonar for prior art, then scores each reference with two metrics: CSS (conservative, penalizes unknowns) and EWSS (evidence-weighted, counts only what's evidenced). |
| **AA** | `backend/agents/aa.py` | Aggregation. Compiles IDCA and NAA outputs into a Final Reference Table sorted by EWSS, an executive summary, and a novelty risk rating (High/Medium/Low/Indeterminate). |

### How the Agents Communicate

Each agent is an independent AWS Lambda with its own API Gateway endpoint. They communicate using a lightweight Agent-to-Agent (A2A) protocol defined in `backend/a2a/protocol.py`. The Ingestion Agent POSTs an `A2ATask` to each agent's `/tasks` endpoint and receives an `A2AResponse`. Each agent also serves a self-description at `/.well-known/agent-card.json`.

### External Services

- **Claude Sonnet via Amazon Bedrock**: all three analytical agents (IDCA, NAA, AA) use this for reasoning
- **Perplexity Sonar**: NAA uses this for patent and literature search (`backend/tools/perplexity_patents.py`)

---

## Project Structure

```
backend/
  template.yaml          # SAM template: defines all AWS resources
  samconfig.toml         # SAM deployment parameters
  lambda_functions/
    handler.py           # API Lambda (routing) + Worker Lambda (orchestration entry point)
  agents/
    ingestion.py         # Orchestrator: calls IDCA, NAA, AA over HTTP
    idca.py              # Invention Detection and Classification Agent
    naa.py               # Novelty Assessment Agent
    aa.py                # Aggregation Agent
  a2a/
    protocol.py          # A2ATask, A2AResponse, AgentCard, TaskStatus
  tools/
    perplexity_patents.py  # Perplexity Sonar wrapper for patent search
  utils/
    pdf_extractor.py     # PDF text extraction (PyMuPDF or pdfminer)
    s3_store.py          # S3-backed task state persistence

frontend/               # Next.js application (Vercel)

Architecture/           # Teaching documents about how this system works
  01-SAM-and-Lambda.md       # How SAM and Lambda work in this project
  02-Configuration-vs-Code.md  # Where configuration lives vs. where logic lives
  03-A2A-Protocol.md         # How the agents communicate
  04-Deployment.md           # How to deploy backend and frontend
```

---

## Quick Start

### Prerequisites

- **AWS CLI** configured with credentials
- **AWS SAM CLI**
- **Python 3.10+**
- **Node.js v18+**
- **Vercel CLI** (optional, for frontend deploy from terminal)

### Deploy Backend

```bash
cd backend
sam build
sam deploy --guided
```

SAM will prompt for stack name (`amie`), region (`us-west-2` recommended for Bedrock), IAM role creation, and Perplexity API key. After deployment, note the `ApiUrl` from the Outputs section.

### Deploy Frontend

**Local development:**

```bash
cd frontend
cp dotenv.local.example .env.local
# Edit .env.local: set NEXT_PUBLIC_API_URL to the ApiUrl from SAM Outputs
npm install
npm run dev
```

**Vercel:**

1. Connect the repository to Vercel
2. Set Root Directory to `frontend`
3. Add environment variable `NEXT_PUBLIC_API_URL` with the ApiUrl from SAM Outputs
4. Deploy

### Updating

After modifying any backend code:

```bash
cd backend
sam build
sam deploy
```

SAM reuses the parameters from `samconfig.toml` on subsequent deploys.

---

## Further Reading

- **[Architecture/01-SAM-and-Lambda.md](Architecture/01-SAM-and-Lambda.md)**: How SAM and Lambda work in this project
- **[Architecture/02-Configuration-vs-Code.md](Architecture/02-Configuration-vs-Code.md)**: Where configuration lives vs. where logic lives
- **[Architecture/03-A2A-Protocol.md](Architecture/03-A2A-Protocol.md)**: How the agents communicate
- **[Architecture/04-Deployment.md](Architecture/04-Deployment.md)**: Full deployment walkthrough with Vercel webhook and A2A verification
- **[Architecture/architecture-diagrams.md](Architecture/architecture-diagrams.md)**: Mermaid diagrams of the system architecture
- **[Architecture/DOCUMENTATION.md](Architecture/DOCUMENTATION.md)**: Detailed A2A protocol reference

