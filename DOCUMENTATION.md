# AMIE – Academic Manuscript IP Evaluator Documentation

## 1. Introduction
AMIE (Academic Manuscript IP Evaluator) is a sophisticated multi-agent system designed to assess the novelty of academic manuscripts. It automates the process of invention detection, prior art searching, and novelty risk assessment through a coordinated pipeline of specialized AI agents.

## 2. System Architecture
The system follows a serverless architecture on AWS, utilizing Lambda functions for compute, API Gateway for routing, and S3 for storage.

- **Frontend**: Next.js application hosted on Vercel.
- **API Gateway (AmieApi)**: Public entry point for user requests.
- **Worker (amie-worker / Ingestion Agent)**: Orchestrates the multi-agent pipeline.
- **Agent Services (IDCA, NAA, AA)**: Independent services specializing in specific parts of the analysis.
- **Persistence**: S3 buckets for manuscript storage and task state management.

## 3. A2A Protocol Implementation
The **Agent-to-Agent (A2A) protocol** is the communication layer that enables independent agent services to work together in a decoupled manner.

### 3.1. Core Concepts
The protocol is built on four primary entities defined in `a2a/protocol.py`:

1.  **A2ATask**: A wrapper for a work request. It contains:
    - `task_id`: A unique UUID.
    - `agent`: The target agent name.
    - `input`: A dictionary containing the actual payload for the agent.
    - `status`: Current task status (pending, running, etc.).
    - `created_at`: Timestamp of creation.

2.  **A2AResponse**: A wrapper for the agent's output. It contains:
    - `task_id`: Matches the request ID.
    - `agent`: The responding agent name.
    - `status`: Result status (complete or error).
    - `output`: The actual computed result payload.
    - `error`: Error message in case of failure.

3.  **AgentCard**: A self-describing metadata object for discovery. It contains:
    - `name`, `description`, `version`.
    - `input_schema` and `output_schema`: JSON Schema fragments describing expected payloads.

4.  **TaskStatus**: A set of standardized strings representing the lifecycle of an A2A operation.

### 3.2. Messaging Mechanics
Communication occurs over **HTTP POST** requests to standardized `/tasks` endpoints.

- **Request**: The orchestrator POSTs an `A2ATask` (serialized to JSON) to the agent's endpoint.
- **Response**: The agent returns an `A2AResponse` (serialized to JSON) within the same HTTP session.

### 3.3. Endpoint Discovery
Each agent service implements a standard discovery endpoint:
`GET /.well-known/agent-card.json`

This returns the `AgentCard` for that specific agent, allowing for dynamic registration and documentation of agent capabilities.

### 3.4. Orchestration Flow
The `IngestionAgent` (in `backend/agents/ingestion.py`) acts as the conductor. It manages the following sequence using the A2A protocol:

1.  **Extract Text**: Orchestrator extracts text from the PDF in S3.
2.  **IDCA Call**: Dispatches an `A2ATask` to the IDCA agent to detect if an invention is present.
3.  **NAA Call (Conditional)**: If the IDCA result confirms an invention (`SD == "Present"`), an `A2ATask` is dispatched to the NAA agent for patent searching and scoring.
4.  **AA Call**: Dispatches an `A2ATask` containing both IDCA and NAA results to the Aggregation Agent to compile the final report.

Each step in the orchestrator is wrapped in a `_dispatch` helper:
```python
def _dispatch(agent_url: str, task: A2ATask) -> A2AResponse:
    resp = requests.post(f"{agent_url}/tasks", json=task.to_dict(), timeout=870)
    resp.raise_for_status()
    return A2AResponse.from_dict(resp.json())
```

## 4. Agent Definitions

### 4.1. IDCA (Invention Detection and Classification Agent)
- **Role**: Determines if the manuscript describes a concrete invention.
- **Input**: `manuscript_text`
- **Output**: Status Determination (`sd`), synopsis, and field mapping.

### 4.2. NAA (Novelty Assessment Agent)
- **Role**: Searches for prior art and scores references against the source invention.
- **Input**: `manuscript_text`, `idca_result`
- **Output**: Scored reference list (`references`), source structure (`ss`), and search string (`ucs`).
- **Optimization**: Uses `ThreadPoolExecutor` for parallel reference scoring to maintain performance.

### 4.3. AA (Aggregation Agent)
- **Role**: Summarizes findings into an executive report with a final novelty risk rating.
- **Input**: `idca_result`, `naa_result`
- **Output**: Executive summary, final reference table, and novelty risk.

## 5. Deployment and State Management
- **Infrastructure as Code**: Managed via AWS SAM (`template.yaml`).
- **State Store**: The orchestrator saves the evolving task JSON to `amie-tasks` bucket after every successful A2A exchange. This allows the frontend to poll for progress using `GET /a2a/tasks/:id`.
- **Async Execution**: The initial API request triggers the worker Lambda asynchronously using a "fire-and-forget" pattern, allowing the API to respond immediately with a `202 Accepted`.
