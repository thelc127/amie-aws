# How SAM and Lambda Work in This Project

This document explains how AWS SAM (Serverless Application Model) and Lambda functions operate in AMIE. It is anchored to specific files in this repo, not to AWS concepts in the abstract.

---

## What SAM Is

SAM is a framework for defining serverless applications as code. You describe your Lambda functions, API Gateways, S3 buckets, and IAM roles in a YAML template. SAM translates that template into AWS CloudFormation, which creates or updates the actual resources in your AWS account.

The template for this project is `backend/template.yaml`.

The deployment configuration is `backend/samconfig.toml`.

That is the entire SAM footprint. Everything else is application code.

## What the Template Defines

`backend/template.yaml` declares five Lambda functions, four API Gateways, two S3 buckets, one IAM role, and associated log groups.

### The Five Lambdas

| Function Name | Handler | Purpose |
|---------------|---------|---------|
| `amie-api` | `lambda_functions/handler.lambda_handler` | HTTP router. Handles upload URLs, task creation, task polling, and agent card requests. |
| `amie-worker` | `lambda_functions/handler.worker_handler` | Pipeline executor. Invoked asynchronously by amie-api. Runs the Ingestion Agent orchestrator. |
| `amie-idca` | `agents/idca.lambda_handler` | IDCA agent. Receives A2ATask over HTTP, runs invention detection via Bedrock, returns A2AResponse. |
| `amie-naa` | `agents/naa.lambda_handler` | NAA agent. Receives A2ATask over HTTP, decomposes invention, searches patents, scores references. |
| `amie-aa` | `agents/aa.lambda_handler` | AA agent. Receives A2ATask over HTTP, compiles final report and novelty risk rating. |

All five Lambdas use `CodeUri: ./`, which means SAM packages the entire `backend/` directory into a single deployment artifact. Each Lambda points to a different handler function within that shared package.

### How Lambda Functions Are Invoked

There are two invocation patterns in this system:

**1. HTTP invocation (synchronous).** API Gateway receives an HTTP request and invokes the Lambda synchronously. The Lambda's return value becomes the HTTP response. This is how `amie-api`, `amie-idca`, `amie-naa`, and `amie-aa` are invoked. The SAM template wires this up through `Events` blocks:

```yaml
# From template.yaml -- amie-api
Events:
  CreateTask:
    Type: HttpApi
    Properties:
      ApiId: !Ref AmieApi
      Path: /a2a/tasks
      Method: POST
```

Each `Events` entry creates an API Gateway route that triggers the Lambda.

**2. Async invocation (fire-and-forget).** `amie-api` invokes `amie-worker` using the Lambda SDK with `InvocationType: "Event"`. This means the API Lambda fires the worker and immediately returns HTTP 202 to the client. The worker runs independently in the background.

```python
# From lambda_functions/handler.py, line 148
boto3.client("lambda").invoke(
    FunctionName  = os.environ["WORKER_FUNCTION_NAME"],
    InvocationType= "Event",
    Payload       = json.dumps({...}),
)
```

The worker then calls the three agent Lambdas synchronously over HTTP (pattern 1 above).

### The Four API Gateways

| Gateway | Serves | Routes |
|---------|--------|--------|
| `AmieApi` | Public frontend traffic | `/upload-url`, `/a2a/tasks`, `/a2a/tasks/{id}`, `/.well-known/agent-card.json` |
| `IdcaApi` | IDCA agent | `/tasks` (POST), `/.well-known/agent-card.json` (GET) |
| `NaaApi` | NAA agent | `/tasks` (POST), `/.well-known/agent-card.json` (GET) |
| `AaApi` | AA agent | `/tasks` (POST), `/.well-known/agent-card.json` (GET) |

The agent APIs are internal. The worker Lambda calls them using URLs injected as environment variables (`IDCA_AGENT_URL`, `NAA_AGENT_URL`, `AA_AGENT_URL`). The frontend only talks to `AmieApi`.

### The Two S3 Buckets

| Bucket | Purpose | TTL |
|--------|---------|-----|
| `amie-manuscripts-{account}-{region}` | Stores uploaded PDFs | 30 days |
| `amie-tasks-{account}-{region}` | Stores pipeline state as JSON files | 7 days |

### The IAM Role

All five Lambdas share a single IAM role (`LambdaRole`) with permissions for:

- S3 read/write on both buckets
- Bedrock model invocation
- Lambda invocation (so amie-api can call amie-worker, and technically so any Lambda can call any other)
- CloudWatch Logs (via the managed `AWSLambdaBasicExecutionRole` policy)

## What Happens at Deploy Time

When you run `sam build && sam deploy`:

1. **`sam build`** reads `template.yaml`, identifies the `CodeUri` for each function, installs Python dependencies from `requirements.txt`, and packages everything into `.aws-sam/build/`.

2. **`sam deploy`** uploads the build artifacts to S3, generates a CloudFormation changeset, and applies it. CloudFormation creates or updates each resource. On first deploy, this creates the API Gateways, Lambdas, buckets, and IAM role. On subsequent deploys, it updates only what changed.

3. **Outputs** are printed after deploy. The critical one is `ApiUrl`, which the frontend needs.

## What Happens at Runtime

1. User hits the frontend, which calls `POST /upload-url` on `AmieApi`.
2. `amie-api` generates a presigned S3 URL. Frontend uploads PDF directly to S3.
3. Frontend calls `POST /a2a/tasks` on `AmieApi`.
4. `amie-api` creates a task record in the task bucket, async-invokes `amie-worker`, returns 202.
5. `amie-worker` (the Ingestion Agent) calls IDCA, NAA, AA in sequence over HTTP. After each call, it writes updated state to S3.
6. Frontend polls `GET /a2a/tasks/{id}` and renders progress as state advances through `pending`, `running`, `idca_complete`, `naa_complete`, `complete`.

## Key Design Decisions

**Why separate Lambdas per agent instead of one Lambda with branching logic?** Network isolation. Each agent can be deployed, monitored, and scaled independently. If NAA times out, it doesn't kill the IDCA or AA containers. The A2A protocol means you could replace any agent with a different implementation (different language, different cloud, different model) without touching the others.

**Why a shared CodeUri?** Simplicity. All agents import from `a2a/protocol.py` and share the same data structures. Packaging the full backend directory into each Lambda avoids maintaining separate dependency trees. The cost is slightly larger deployment artifacts. At this scale, that cost is negligible.

**Why async invocation for the worker?** The pipeline takes 1-3 minutes depending on manuscript length and reference count. API Gateway has a 30-second timeout. Async invocation lets the API return immediately while the worker runs for up to 15 minutes (the Lambda maximum).
