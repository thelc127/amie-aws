# Deployment: Backend on AWS, Frontend on Vercel

This document walks through deploying AMIE end to end, including the connection between the Vercel frontend and the AWS backend.

---

## Prerequisites

Install these before you start:

| Tool | Purpose | Install |
|------|---------|---------|
| AWS CLI | Authenticate with AWS | `brew install awscli` or [AWS docs](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) |
| AWS SAM CLI | Build and deploy the backend | `brew install aws-sam-cli` or [SAM docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) |
| Python 3.9 | Backend runtime | Included on macOS; SAM builds against this version |
| Node.js v18+ | Frontend build | `brew install node` |

Configure AWS credentials:

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-west-2), Output format (json)
```

Verify Bedrock access in your account. AMIE uses `us.anthropic.claude-sonnet-4-20250514-v1:0` by default. If your account doesn't have access to this model in us-west-2, either request access in the AWS console (Bedrock > Model access) or change the `BEDROCK_MODEL_ID` in `backend/template.yaml`.

---

## Step 1: Deploy the Backend

### First-time Setup

Create a `.env` file in the project root (never committed to git) with your Perplexity API key:

```
PERPLEXITY_API_KEY=your-key-here
```

If `samconfig.toml` does not exist yet, run the guided wizard once to generate it:

```bash
cd backend
sam deploy --guided
```

SAM will prompt for these values:

| Prompt | Recommended Value | Notes |
|--------|-------------------|-------|
| Stack Name | `amie` | Saved to `samconfig.toml` |
| AWS Region | `us-west-2` | Must have Bedrock access |
| Parameter AllowedOrigin | `*` (or your Vercel domain) | CORS origin for the public API |
| Confirm changes before deploy | `y` | Review the changeset before applying |
| Allow SAM CLI IAM role creation | `y` | Required for the shared Lambda role |
| Save arguments to configuration file | `y` | Saves to `samconfig.toml` for future deploys |

Note: do not enter the Perplexity key during the guided wizard — leave it blank. The `deploy.sh` script injects it from `.env` on every deploy.

### All Deploys (first-time and subsequent)

```bash
cd backend
./deploy.sh
```

`deploy.sh` reads the Perplexity API key from the project root `.env` file and passes it securely to SAM via `--parameter-overrides`. All other parameters (stack name, region, IAM settings) are read from `samconfig.toml`. The script runs `sam build` followed by `sam deploy` automatically.

After deploy, SAM prints an Outputs section:

```
Key                 Value
-----------------   -------------------------------------------------------
ApiUrl              https://abc123.execute-api.us-west-2.amazonaws.com/prod
IdcaAgentUrl        https://def456.execute-api.us-west-2.amazonaws.com/prod
NaaAgentUrl         https://ghi789.execute-api.us-west-2.amazonaws.com/prod
AaAgentUrl          https://jkl012.execute-api.us-west-2.amazonaws.com/prod
ManuscriptBucketName  amie-manuscripts-123456789-us-west-2
TaskBucketName      amie-tasks-123456789-us-west-2
```

Copy the **ApiUrl**. The frontend needs it.

### Updating the Perplexity Key

Update the value in your local `.env` file and run `./deploy.sh`. The new key will be picked up automatically.

---

## Step 2: Deploy the Frontend

### Option A: Local Development

```bash
cd frontend
cp dotenv.local.example .env.local
```

Edit `.env.local`:

```
NEXT_PUBLIC_API_URL=https://abc123.execute-api.us-west-2.amazonaws.com/prod
```

Use the `ApiUrl` from Step 1.

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

### Option B: Deploy to Vercel

1. Push the repo to GitHub.
2. Go to [vercel.com](https://vercel.com), import the repository.
3. Set **Root Directory** to `frontend`.
4. Add one environment variable:
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: the `ApiUrl` from Step 1
5. Deploy.

Vercel will build the Next.js app and serve it at a `.vercel.app` domain.

### Connecting Vercel to GitHub (Automatic Deploys)

When you connect a GitHub repo to Vercel, Vercel automatically:

- Deploys on every push to `main`
- Creates preview deployments for pull requests
- Rebuilds when you update environment variables and trigger a redeploy

No webhook configuration is needed. Vercel's GitHub integration handles it.

If you want to restrict CORS to your Vercel domain (recommended for production), update the backend:

```bash
cd backend
sam deploy --parameter-overrides "AllowedOrigin=https://your-app.vercel.app PerplexityApiKey=sk-your-key"
```

---

## Step 3: Verify the Deployment

### Verify Backend

Check that the API responds:

```bash
# Should return the Ingestion Agent card
curl https://abc123.execute-api.us-west-2.amazonaws.com/prod/.well-known/agent-card.json
```

Check that each agent is reachable (using the agent URLs from SAM Outputs):

```bash
# IDCA agent card
curl https://def456.execute-api.us-west-2.amazonaws.com/prod/.well-known/agent-card.json

# NAA agent card
curl https://ghi789.execute-api.us-west-2.amazonaws.com/prod/.well-known/agent-card.json

# AA agent card
curl https://jkl012.execute-api.us-west-2.amazonaws.com/prod/.well-known/agent-card.json
```

Each should return a JSON object with `name`, `description`, `version`, `input_schema`, and `output_schema`.

### Verify Frontend

Open the Vercel URL (or localhost:3000). Upload a short PDF. Watch the status progress through:

`pending` > `running` > `idca_complete` > `naa_complete` > `complete`

If the pipeline stalls, check CloudWatch Logs for the relevant Lambda:

```bash
# View recent logs for the worker
aws logs tail /aws/lambda/amie-worker --follow

# View logs for a specific agent
aws logs tail /aws/lambda/amie-idca --follow
aws logs tail /aws/lambda/amie-naa --follow
aws logs tail /aws/lambda/amie-aa --follow
```

### Verify A2A Protocol

You can test the full A2A flow manually:

```bash
# 1. Get an upload URL
curl -X POST https://abc123.execute-api.us-west-2.amazonaws.com/prod/upload-url \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.pdf"}'

# 2. Upload a PDF to the presigned URL (use the upload_url from step 1)
curl -X PUT "<upload_url>" \
  -H "Content-Type: application/pdf" \
  --data-binary @your-manuscript.pdf

# 3. Create a task (use the s3_key and bucket from step 1)
curl -X POST https://abc123.execute-api.us-west-2.amazonaws.com/prod/a2a/tasks \
  -H "Content-Type: application/json" \
  -d '{"s3_key": "<s3_key>", "bucket": "<bucket>"}'

# 4. Poll for results (use the task_id from step 3)
curl https://abc123.execute-api.us-west-2.amazonaws.com/prod/a2a/tasks/<task_id>
```

---

## Troubleshooting

### "sam build" fails with dependency errors

Check `backend/requirements.txt`. The Lambda runtime is Python 3.9 — ensure your local Python version matches. SAM installs dependencies in a Docker container by default; if Docker isn't running, try `sam build --use-container` or ensure your local Python matches the Lambda runtime.

### Lambda times out

The Worker Lambda has a 900-second (15-minute) timeout, which is the Lambda maximum. The NAA agent makes multiple Bedrock calls (one per reference) plus a Perplexity call. If the manuscript is long and produces many references, it can approach this limit. Check CloudWatch Logs to see which stage is slow.

### CORS errors in the browser

Both the API Gateway and the Lambda response headers must allow the frontend's origin. If you see CORS errors:

1. Check `AllowedOrigin` in `template.yaml` (API Gateway level)
2. Check `CORS_HEADERS` in `handler.py` (Lambda level)
3. Redeploy after changes

### Bedrock returns AccessDeniedException

Your AWS account needs model access enabled for the specified model. Go to AWS Console > Bedrock > Model access > Request access for the Claude model specified in `BEDROCK_MODEL_ID`.

### Perplexity returns 401

The API key is invalid or missing. Update the key in your local `.env` file and redeploy:

```bash
cd backend
./deploy.sh
```

---

## Tearing Down

To remove all AWS resources created by AMIE:

```bash
# Empty the S3 buckets first (CloudFormation can't delete non-empty buckets)
aws s3 rm s3://amie-manuscripts-ACCOUNT-REGION --recursive
aws s3 rm s3://amie-tasks-ACCOUNT-REGION --recursive

# Delete the CloudFormation stack
aws cloudformation delete-stack --stack-name amie
```

This removes all Lambdas, API Gateways, S3 buckets, IAM roles, and log groups.
