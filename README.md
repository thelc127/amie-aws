# AMIE – Academic Manuscript IP Evaluator

### Getting Started Guide

AMIE is a multi-agent system designed to evaluate academic manuscripts for patentability. It uses a Next.js frontend and an AWS-based serverless backend with specialized AI agents (IDCA, NAA, AA).

---

## 1. Prerequisites

Before starting, ensure you have the following installed:

- **AWS CLI**: [Installed and configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) with your credentials.
- **AWS SAM CLI**: [Installed](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) for backend deployment.
- **Node.js (v18+)**: For the frontend.
- **Python (3.10+)**: For backend development.
- **Vercel CLI**: (Optional) if you want to deploy the frontend from your terminal.

---

## 2. Backend Deployment (AWS SAM)

The backend must be deployed first to generate the API endpoints required by the frontend.

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Build the application:**
   This command compiles dependencies and packages your code.
   ```bash
   sam build
   ```

3. **Deploy to AWS:**
   If this is your first time, use the guided flag:
   ```bash
   sam deploy --guided
   ```
   **Guide through the prompts:**
   - **Stack Name**: `amie-backend`
   - **AWS Region**: `us-west-2` (recommended for Bedrock access)
   - **Confirm changes before deploy**: Yes
   - **Allow SAM CLI IAM role creation**: Yes
   - **Save arguments to configuration file**: Yes

4. **Note the Outputs:**
   After a successful deployment, SAM will print several URLs in the "Outputs" section. You specifically need the **`ApiUrl`**.

---

## 3. Frontend Configuration & Deployment

### Local Development
1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Create an environment file:**
   Create a file named `.env.local` and paste the `ApiUrl` you got from the backend deployment:
   ```bash
   NEXT_PUBLIC_API_URL=https://your-api-id.execute-api.us-west-2.amazonaws.com/prod
   ```

3. **Install dependencies:**
   ```bash
   npm install
   ```

4. **Run the development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) to see the app.

### Vercel Deployment
1. Connect your repository to Vercel.
2. Set the **Root Directory** to `frontend`.
3. Add the **Environment Variable**: 
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: (The `ApiUrl` from SAM Outputs)
4. Deploy.

---

## 4. How the Application Works (User Flow)

Once the app is running:

1. **Upload**: Select an academic manuscript (PDF) on the homepage.
2. **Analysis**: The app generates a presigned URL to upload the PDF to S3 and then triggers the **Ingestion Agent**.
3. **Pipeline (A2A Architecture)**:
   - **IDCA**: Detects if an invention is present.
   - **NAA**: (If invention found) Builds a search query and scores references via Perplexity/Patents.
   - **AA**: Compiles everything into a Final Reference Table.
4. **Polling**: The frontend polls the backend every few seconds to show real-time progress (Pending → Running → IDCA Complete → NAA Complete → Complete).
5. **Results**: Once complete, a full Novelty Assessment Report is displayed.

---

## 5. Maintenance & Updates

### Updating Backend Logic
If you modify any code in `backend/agents/` or `backend/lambda_functions/`:
```bash
cd backend
sam build
sam deploy
```

### Adding Secrets (e.g. Perplexity API Key)
If you need to update API keys used by the agents:
1. Open `backend/template.yaml`.
2. Locate the `Parameters` or `Environment Variables` section.
3. Update the value.
4. Redeploy using `sam deploy`.

---

## 6. Project Structure

- `/backend`: AWS SAM project containing the serverless backend.
  - `/agents`: The "brain" of the app (IDCA, NAA, AA logic).
  - `/a2a`: Protocol definitions for Agent-to-Agent communication.
  - `/lambda_functions`: Entry points and routing logic.
- `/frontend`: Next.js application built with Tailwind CSS.
- `template.yaml`: The Infrastructure-as-Code blueprint for your entire AWS backend.

