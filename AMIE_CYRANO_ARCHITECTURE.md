# 🎭 AMIE — Architecture Through the Lens of Cyrano de Bergerac

> *"The best part of me is what I whisper through another's lips."*
> — Cyrano de Bergerac

---

## The Metaphor

In Edmond Rostand's play, **Cyrano de Bergerac** is the brilliant, eloquent swordsman-poet who composes beautiful words for the handsome but intellectually hollow **Christian** to speak to the beautiful **Roxane**. Roxane falls in love with what she believes is Christian's soul — never suspecting that the true author stands hidden in shadow.

**AMIE** is built on exactly this three-party choreography.

| Play Character | AMIE Component | What They Do |
|---|---|---|
| **Roxane** | The User | Receives the final report, moved by its brilliance, unaware of the backstage choreography |
| **Christian** | Next.js Frontend on Vercel | The visible, beautiful face — but intellectually hollow without Cyrano's words |
| **Cyrano** | Worker Lambda / Ingestion Orchestrator | The hidden genius composing every analysis, coordinating every agent, never taking credit |
| **The Balcony** | AWS API Gateway | The architectural boundary where the visible world meets the hidden one |
| **The Letters** | S3 Buckets | The medium carrying Cyrano's words between scenes — state persisted after every act |
| **The Three Cadets** | IDCA, NAA, AA Agents | Cyrano's three skills, each deployed as a separate Act of the analysis |
| **Cyrano's Eloquence** | AWS Bedrock / Claude Sonnet | The wit and intelligence powering every intelligent response |
| **Le Bret** | Perplexity Patents API | The loyal friend who gathers intelligence from the outside world |
| **The Stage** | AWS Cloud | The theatre in which the backstage magic happens, invisible to Roxane |

---

## Diagram 1 — The Full Stage: Complete System Architecture

> *"The entire theatre is our canvas — some of it seen, most of it hidden."*

This diagram shows every component, its metaphorical role, and every connection in the system.
Color legend: 🟡 Roxane/User · 💙 Christian/Frontend · ❤️ Cyrano/Orchestrator · 🟣 Agent Lambdas · 🟢 S3/Letters · 🟠 API Gateway/Balcony · ⚫ External APIs

```mermaid
flowchart TD
    Roxane(["👩 ROXANE — The User\nUploads manuscript · Awaits verdict\nMoved by the result — unaware of the choreography"])

    subgraph Vercel["💙 CHRISTIAN'S STAGE — Vercel"]
        Frontend["🎭 CHRISTIAN — Next.js Frontend\nThe beautiful face users see\nDrop PDF · Click Evaluate · Watch · Marvel\nAll eloquence is borrowed from Cyrano"]
    end

    subgraph AWS["THE BACKSTAGE — AWS Cloud"]

        subgraph Balcony["🏛️ THE BALCONY — AmieApi Gateway\nWhere Christian speaks Cyrano's words to Roxane"]
            R1["POST /upload-url\n'Here is your entrance, Roxane'"]
            R2["POST /a2a/tasks\n'Your manuscript is received'"]
            R3["GET /a2a/tasks/:id\n'Have patience — the letter is on its way'"]
            R4["GET /.well-known/agent-card.json\n'Here are my credentials'"]
        end

        ApiHandler["🎩 The Doorman — API Lambda\namie-api\nRoutes requests · Presigns URLs\nCreates tasks · Reads S3 state"]

        subgraph Letters["📜 THE LETTERS — S3 Buckets"]
            Manuscripts[("amie-manuscripts\n'The entrusted manuscript'\nUploaded PDFs · 30-day retention")]
            Tasks[("amie-tasks\n'Letters carrying progress'\nTask state JSON\npending → complete")]
        end

        subgraph CyranoBox["❤️ CYRANO — Worker Lambda · amie-worker"]
            Orchestrator["The Ingestion Orchestrator\n'I compose · I coordinate · I hide'\nCalls IDCA → NAA → AA over A2A\nSaves state to S3 after each Act"]
        end

        subgraph ThreeActs["🎭 THE THREE ACTS — Agent Services"]

            subgraph ActI["ACT I — IDCA Service"]
                IdcaGw["IdcaApi Gateway\nPOST /tasks"]
                IdcaFn["amie-idca Lambda\n'Is there genius here?'\nSD: Present / Implied / Absent"]
            end

            subgraph ActII["ACT II — NAA Service\nOnly if SD = Present"]
                NaaGw["NaaApi Gateway\nPOST /tasks"]
                NaaFn["amie-naa Lambda\n'What came before this genius?'\nBuilds SS · SSR · UCS · Scores refs"]
            end

            subgraph ActIII["ACT III — AA Service"]
                AaGw["AaApi Gateway\nPOST /tasks"]
                AaFn["amie-aa Lambda\n'What does it all mean?'\nFinal Reference Table · Novelty Risk"]
            end
        end

        Bedrock[["🧠 AWS Bedrock — Claude Sonnet\nCyrano's Eloquence\nPowers every intelligent response"]]
    end

    Perplexity[["🔍 Perplexity Patents — Le Bret\nThe loyal informant\nGathers prior art from the outside world"]]

    Roxane -->|"uploads PDF\nsees results"| Frontend

    Frontend -->|"1 · POST /upload-url"| R1
    Frontend -->|"3 · POST /a2a/tasks"| R2
    Frontend -->|"5 · polls every 4s"| R3

    R1 & R2 & R3 & R4 --> ApiHandler

    ApiHandler -->|"2 · presigned PUT URL"| Frontend
    Frontend -->|"direct PUT PDF\nbypasses Lambda"| Manuscripts

    ApiHandler -->|"save status: pending"| Tasks
    ApiHandler -->|"4 · async invoke\nfire and forget"| Orchestrator

    Orchestrator -->|"load task"| Tasks
    Orchestrator -->|"extract PDF text"| Manuscripts

    Orchestrator -->|"A2ATask\nmanuscript_text"| IdcaGw
    IdcaGw --> IdcaFn
    IdcaFn -->|"A2AResponse\nsd · synopsis · fields_map"| Orchestrator
    Orchestrator -->|"save idca_complete"| Tasks

    Orchestrator -->|"A2ATask\ntext + idca_result\nSD=Present only"| NaaGw
    NaaGw --> NaaFn
    NaaFn -->|"A2AResponse\nss · references · scores"| Orchestrator
    Orchestrator -->|"save naa_complete"| Tasks

    Orchestrator -->|"A2ATask\nidca + naa results"| AaGw
    AaGw --> AaFn
    AaFn -->|"A2AResponse\nFRT · executive_summary · risk"| Orchestrator
    Orchestrator -->|"save complete"| Tasks

    IdcaFn & NaaFn & AaFn -->|"invoke_model"| Bedrock
    NaaFn -->|"patent search\nUCS query"| Perplexity

    Tasks -->|"6 · final report\nvia poll"| ApiHandler

    classDef roxane fill:#fbbf24,stroke:#d97706,color:#000,font-weight:bold
    classDef christian fill:#3b82f6,stroke:#1d4ed8,color:#fff,font-weight:bold
    classDef cyrano fill:#dc2626,stroke:#991b1b,color:#fff,font-weight:bold
    classDef agent fill:#7c3aed,stroke:#5b21b6,color:#fff
    classDef letters fill:#059669,stroke:#047857,color:#fff
    classDef external fill:#4b5563,stroke:#1f2937,color:#fff
    classDef balcony fill:#f97316,stroke:#c2410c,color:#fff
    classDef doorman fill:#0891b2,stroke:#0e7490,color:#fff

    class Roxane roxane
    class Frontend christian
    class Orchestrator cyrano
    class IdcaFn,NaaFn,AaFn agent
    class Manuscripts,Tasks letters
    class Bedrock,Perplexity external
    class R1,R2,R3,R4 balcony
    class ApiHandler doorman
```

---

## Diagram 2 — The Performance: Communication Flow Sequence

> *"Every word I speak through him is a word he cannot earn himself."*

This sequence shows the exact order of events from the moment Roxane drops her PDF to the moment the final report appears — narrated as scenes of a play.

```mermaid
sequenceDiagram
    actor Roxane as 👩 Roxane (User)
    participant Christian as 💙 Christian<br/>(Next.js / Vercel)
    participant Balcony as 🏛️ The Balcony<br/>(API Gateway)
    participant Doorman as 🎩 Doorman<br/>(API Lambda)
    participant S3m as 📜 The Vault<br/>(S3 Manuscripts)
    participant S3t as 📜 The Letters<br/>(S3 Tasks)
    participant Cyrano as ❤️ Cyrano<br/>(Worker Lambda)
    participant IDCA as 🎭 Act I<br/>(IDCA Lambda)
    participant NAA as 🎭 Act II<br/>(NAA Lambda)
    participant AA as 🎭 Act III<br/>(AA Lambda)
    participant Wit as 🧠 Cyrano's Wit<br/>(Bedrock / Claude)
    participant LeBret as 🔍 Le Bret<br/>(Perplexity)

    Note over Roxane,Christian: 🎬 SCENE I — Roxane Arrives at the Theatre

    Roxane->>Christian: Drops manuscript PDF
    Note right of Roxane: "I have this paper — can you tell me if it is novel?"

    Christian->>Balcony: POST /upload-url {filename: "paper.pdf"}
    Note right of Christian: Christian speaks — but the architecture behind<br/>these words was built entirely by Cyrano
    Balcony->>Doorman: route to API Lambda
    Doorman-->>Christian: {upload_url, s3_key, bucket}
    Christian->>S3m: PUT PDF bytes (direct presigned upload)
    Note over S3m: The manuscript rests safely in the vault.<br/>No Lambda touched it.

    Note over Christian,S3t: 🎬 SCENE II — The Commission is Given

    Christian->>Balcony: POST /a2a/tasks {s3_key, bucket}
    Balcony->>Doorman: route to API Lambda
    Doorman->>S3t: save task {status: "pending", idca: null, naa: null, aa: null}
    Doorman->>Cyrano: async boto3.invoke (fire and forget — the curtain rises)
    Note right of Doorman: The Doorman walks away.<br/>Cyrano is now alone backstage.
    Doorman-->>Christian: 202 Accepted {task_id, status: "pending"}
    Christian-->>Roxane: "Your manuscript is received — please wait"
    Note right of Roxane: Roxane waits, hopeful.<br/>She does not know Cyrano is already working.

    Note over Cyrano,S3t: 🎬 SCENE III — Cyrano Takes the Stage (Unseen)

    Cyrano->>S3t: load task state
    Cyrano->>S3m: extract PDF text (PyMuPDF)
    Cyrano->>S3t: save {status: "running"}

    Note over Cyrano,IDCA: 🎭 ACT I — The Question of Genius

    Cyrano->>IDCA: A2ATask {agent:"idca", input:{manuscript_text}}
    IDCA->>Wit: invoke_model — assess concreteness + utility
    Wit-->>IDCA: {"sd":"Present", "structural_synopsis":"...", "fields_map":[...]}
    IDCA-->>Cyrano: A2AResponse {status:"complete", output:{sd, synopsis, fields_map, reasoning}}
    Cyrano->>S3t: save {status: "idca_complete", idca: {...}}
    Note right of Cyrano: "The invention is confirmed. Now — who came before?"

    Note over Cyrano,NAA: 🎭 ACT II — The Search for Prior Art (SD=Present only)

    Cyrano->>NAA: A2ATask {agent:"naa", input:{manuscript_text, idca_result}}
    NAA->>Wit: invoke_model — build Source Structure + SSR + UCS
    Wit-->>NAA: {ss:[], ss_synopsis, ucs:"search string", ssr_criteria:{}}
    NAA->>LeBret: search_patents(ucs) — up to 10 results
    LeBret-->>NAA: [{title, abstract, url, year, authors} × 10]

    loop Score each of the 10 references
        NAA->>Wit: invoke_model — score reference vs Source Structure
        Wit-->>NAA: {citation, rs_blocks[], css:28.6, ewss:66.7}
    end

    NAA-->>Cyrano: A2AResponse {status:"complete", output:{ss, references[scored], ssr_criteria}}
    Cyrano->>S3t: save {status: "naa_complete", naa: {...}}

    Note over Cyrano,AA: 🎭 ACT III — The Final Verdict

    Cyrano->>AA: A2ATask {agent:"aa", input:{idca_result, naa_result}}
    AA->>Wit: invoke_model — compile FRT + executive summary + novelty risk
    Wit-->>AA: {context_header, final_reference_table[], executive_summary, novelty_risk:"High"}
    AA-->>Cyrano: A2AResponse {status:"complete", output:{FRT, summary, risk}}
    Cyrano->>S3t: save {status: "complete", aa: {...}}
    Note right of Cyrano: Cyrano's work is done.<br/>Christian will take the credit.<br/>Roxane will never know.

    Note over Christian,Roxane: 🎬 SCENE IV — The Letter is Delivered (Polling)

    loop Every 4 seconds until status=complete or error
        Christian->>Balcony: GET /a2a/tasks/{task_id}
        Balcony->>Doorman: route to API Lambda
        Doorman->>S3t: load task state
        S3t-->>Doorman: {status, idca:{...}, naa:{...}, aa:{...}}
        Doorman-->>Christian: current task state
        Christian-->>Roxane: renders progressive results as each Act completes
    end

    Note over Roxane,Christian: 🎬 FINALE — Roxane Receives the Report

    Christian-->>Roxane: Final Report — Novelty Risk · FRT · Executive Summary
    Note over Roxane: She is moved by the brilliance of it.<br/>She believes it came from Christian.<br/>It was Cyrano all along.
```

---

## Diagram 3 — The Letters: Task State & S3 Data Flow

> *"Each letter carries more than words — it carries the progress of my soul."*

S3 is not just a database here — it is the **narrative medium** of the play. Every state change Cyrano makes is written into a letter in S3. Christian (via the API Lambda) reads those letters to report back to Roxane. The agents never talk to each other directly — they pass their findings through Cyrano, who records every step.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> pending: 🎬 Curtain rises\nAPI Lambda saves initial task\nWorker Lambda invoked async

    pending --> running: ❤️ Cyrano takes the stage\nWorker Lambda starts\nPDF text extracted from S3

    running --> idca_complete: 🎭 Act I complete\nIDCA returns SD · synopsis · fields\nCyrano writes the first letter

    idca_complete --> naa_complete: 🎭 Act II complete\nSD was Present\nNAA returns scored references\nCyrano writes the second letter

    idca_complete --> complete: 🎭 Act II skipped\nSD was Implied or Absent\nAA runs directly on IDCA output

    naa_complete --> complete: 🎭 Act III complete\nAA returns FRT · summary · risk\nCyrano writes the final letter

    complete --> [*]: 🎬 Curtain falls\nRoxane receives the verdict\nPolling stops

    running --> error: ⚔️ The duel is lost\nException caught · error saved to S3
    idca_complete --> error: ⚔️ The duel is lost
    naa_complete --> error: ⚔️ The duel is lost
```

### What the S3 Letter looks like at each stage

```
PENDING                        IDCA_COMPLETE                   COMPLETE
──────────────────────         ─────────────────────────────   ─────────────────────────────────
{                              {                               {
  task_id: "uuid",               task_id: "uuid",                task_id: "uuid",
  status:  "pending",            status:  "idca_complete",        status:  "complete",
  s3_key:  "uploads/...",        idca: {                          idca:    { sd, synopsis... },
  idca:    null,                   sd:       "Present",           naa:     { ss, references...},
  naa:     null,                   synopsis: "...",               aa: {
  aa:      null,                   fields_map: [...],               context_header: {...},
  error:   null                    reasoning:  "..."                final_reference_table: [...],
}                              },                                   executive_summary: "...",
                                 naa:  null,                        novelty_risk: "High"
                                 aa:   null                       }
                               }                               }
```

---

## Diagram 4 — The Scenes: API Endpoint Map

> *"Each door leads to a different world — some open to Roxane, some only to me."*

There are **two API Gateway stages** in AMIE: the public-facing `AmieApi` (where Christian and Roxane interact) and the backstage agent gateways (where only Cyrano is allowed to enter).

```mermaid
flowchart LR
    subgraph Public["🌐 THE PUBLIC STAGE — AmieApi\nopen to Christian and Roxane"]

        subgraph Scene1["🎬 Scene I — The Entrance"]
            E1["POST /upload-url\n──────────────────\nBody: {filename}\nReturns: {upload_url, s3_key, bucket}\nSigned URL expires: 5 minutes\nHosts: API Lambda"]
        end

        subgraph Scene2["🎬 Scene II — The Manuscript Upload"]
            E2["PUT presigned_url\n──────────────────\nBody: PDF bytes\nDirect to S3 — bypasses all Lambda\nContent-Type: application/pdf\nHost: S3 (not API Gateway)"]
        end

        subgraph Scene3["🎬 Scene III — The Commission"]
            E3["POST /a2a/tasks\n──────────────────\nBody: {s3_key, bucket}\nReturns: 202 {task_id, status:pending}\nSide effect: async Worker invoke"]
        end

        subgraph Scene4["🎬 Scene IV — Reading the Letter"]
            E4["GET /a2a/tasks/:id\n──────────────────\nReturns: full task state JSON\nstatus: pending→running→idca_complete\n        →naa_complete→complete→error\nPolled every 4s from browser"]
        end

        subgraph SceneCard["🎬 Credentials"]
            E5["GET /.well-known/agent-card.json\n──────────────────\nReturns: IngestionAgent card\nA2A discovery endpoint\nname · version · input/output schema"]
        end
    end

    subgraph Backstage["🚪 THE BACKSTAGE GATES — Agent API Gateways\nonly Cyrano may enter — no CORS needed"]

        subgraph IdcaGate["🎭 ACT I Gate — IdcaApi"]
            IG1["POST /tasks\n──────────────────\nA2ATask in: {manuscript_text}\nA2AResponse out: {sd, synopsis,\n  source_citation, fields_map, reasoning}"]
            IG2["GET /.well-known/agent-card.json\nIDCA Agent Card"]
        end

        subgraph NaaGate["🎭 ACT II Gate — NaaApi"]
            NG1["POST /tasks\n──────────────────\nA2ATask in: {manuscript_text, idca_result}\nA2AResponse out: {ss[], ss_synopsis,\n  ucs, ssr_criteria, references[]}"]
            NG2["GET /.well-known/agent-card.json\nNAA Agent Card"]
        end

        subgraph AaGate["🎭 ACT III Gate — AaApi"]
            AG1["POST /tasks\n──────────────────\nA2ATask in: {idca_result, naa_result}\nA2AResponse out: {context_header,\n  final_reference_table[], executive_summary,\n  novelty_risk: High/Medium/Low/Indeterminate}"]
            AG2["GET /.well-known/agent-card.json\nAA Agent Card"]
        end
    end

    Browser(["💙 Christian\n(Browser on Vercel)"])
    Worker(["❤️ Cyrano\n(Worker Lambda)"])

    Browser --> Scene1 & Scene3 & Scene4 & SceneCard
    Browser -->|direct — no Lambda| Scene2
    Worker --> IdcaGate & NaaGate & AaGate

    classDef public fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef backstage fill:#7c3aed,stroke:#5b21b6,color:#fff
    classDef actor fill:#dc2626,stroke:#991b1b,color:#fff

    class E1,E2,E3,E4,E5 public
    class IG1,IG2,NG1,NG2,AG1,AG2 backstage
    class Browser,Worker actor
```

---

## Diagram 5 — The Three Acts: Agent Orchestration Detail

> *"First I must know if there is something worth defending. Then I must know if it has been said before. Only then can I render judgment."*

Each agent is a separate AWS Lambda with its own API Gateway. They do not know each other exists — only Cyrano orchestrates their order and passes results between them.

```mermaid
flowchart TD
    Input(["📄 Manuscript Text\nExtracted from S3 PDF\nTruncated to 40,000 chars for IDCA\n30,000 chars for NAA"])

    subgraph Act1["🎭 ACT I — IDCA Lambda (amie-idca)\n'Is there genius here?'\nModel: Claude Sonnet via Bedrock · max_tokens: 2000"]
        I_prompt["Prompt: Assess concreteness + utility\nAssign SD · Generate synopsis\nGenerate APA citation · Map fields"]
        I_out["Output:\nsd: Present / Implied / Absent\nstructural_synopsis: actor→operation→outcome\nsource_citation: APA style\nfields_map: 3–8 domain strings\nreasoning: why this SD was assigned"]
    end

    Decision{"SD = Present?"}
    SkipNote["SD = Implied or Absent\nNAA is skipped entirely\nAA runs with naa_result = null"]

    subgraph Act2["🎭 ACT II — NAA Lambda (amie-naa)\n'What came before this genius?'\nModel: Claude Sonnet · max_tokens: 4096 · Up to 11 Bedrock calls"]

        subgraph StepA["Step A: Build Source Structure"]
            N_ss["Claude call #1\nDecompose invention into SS blocks:\narchitecture · energy/drive · transfer_elements\nrouting_guidance · compliance_safety\nsensing_measurement · external_observation\ncontrol_decision · materials_build\n+SSR weights (1-3) +UCS search string"]
        end

        subgraph StepB["Step B: Prior Art Search"]
            N_search["Perplexity Patents API\nQuery: UCS string\nReturns: up to 10 references\n{title, abstract, url, year, authors}"]
        end

        subgraph StepC["Step C: Score Each Reference"]
            N_score["Claude calls #2–#11 (one per reference)\nFor each SS block: Present/Partial/Absent/Unknown\nCSS = conservative score (Unknown=0)\nEWSS = evidence-weighted (excludes Unknown)\nBoth scores computed per reference"]
        end

        N_out["Output:\nss[]: source structure blocks + weights\nss_synopsis: actor→operation→outcome\nucs: unified composite search string\nssr_criteria: match criteria per block\nreferences[]: each with css · ewss · rs_blocks · url"]
    end

    subgraph Act3["🎭 ACT III — AA Lambda (amie-aa)\n'What does it all mean?'\nModel: Claude Sonnet · max_tokens: 4096"]
        A_prompt["Prompt: Compile context header\nBuild Final Reference Table\nsort by EWSS descending\nWrite executive summary (2–4 sentences)\nAssign overall novelty risk"]
        A_out["Output:\ncontext_header: {source_citation, ss_synopsis, sd, fields_map}\nfinal_reference_table[]: sorted by EWSS desc\n  each row: citation · rs_synopsis · css · ewss · url\nexecutive_summary: 2–4 sentences on novelty risk\nnovelty_risk: High / Medium / Low / Indeterminate"]
    end

    FinalReport(["📊 Final Report\nWritten to S3 {status: complete}\nPolled and rendered by Christian\nDelivered to Roxane"])

    Input --> I_prompt --> I_out
    I_out --> Decision
    Decision -->|"Yes — Act II begins"| StepA
    Decision -->|"No — Act II skipped"| SkipNote
    SkipNote --> A_prompt
    StepA --> StepB --> StepC --> N_out
    N_out --> A_prompt
    A_prompt --> A_out --> FinalReport

    classDef act1node fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef act2node fill:#7c3aed,stroke:#5b21b6,color:#fff
    classDef act3node fill:#059669,stroke:#047857,color:#fff
    classDef ioNode fill:#f97316,stroke:#c2410c,color:#fff,font-weight:bold
    classDef decNode fill:#dc2626,stroke:#991b1b,color:#fff,font-weight:bold
    classDef skipNode fill:#6b7280,stroke:#374151,color:#fff

    class I_prompt,I_out act1node
    class N_ss,N_search,N_score,N_out act2node
    class A_prompt,A_out act3node
    class Input,FinalReport ioNode
    class Decision decNode
    class SkipNote skipNode
```

---

## Narrative: Connecting Metaphor to Behavior

### Why this metaphor works perfectly

**Christian cannot write the letter — he delivers it.**
The frontend (`page.tsx`) contains zero AI logic. It uploads a file, creates a task, and polls. Every word of the final report was authored by agents it never calls directly.

**Cyrano composes in secret — the user never sees him.**
The Worker Lambda is invoked asynchronously. The API returns `202` before Cyrano has read a single line of the manuscript. He works entirely in shadow, writing progress into S3 letters that Christian reads to Roxane every four seconds.

**The letters travel between worlds.**
S3 is not a database — it is the narrative medium. Cyrano writes `idca_complete` into a letter. Roxane (via Christian) reads it and sees the IDCA card appear on screen. The letter travels from backstage to front of house without either party ever speaking directly.

**The balcony is the only interface between the two worlds.**
API Gateway is the architectural balcony scene. Christian stands on the Vercel side, calling down to Cyrano's world. The four routes (`/upload-url`, `/a2a/tasks`, `/a2a/tasks/:id`, `/.well-known/agent-card.json`) are the four lines Christian is allowed to speak.

**The three cadets each play their part and leave the stage.**
IDCA does not know NAA exists. NAA does not know AA exists. Each agent is invoked, responds with its A2AResponse, and exits. Only Cyrano holds the full picture — routing results from one act to the next, deciding whether Act II is even needed.

**Roxane is moved by the report — she believes in Christian.**
The user sees a beautiful Next.js UI, a progress bar advancing through stages, a final report with CSS/EWSS scores and an executive summary. She does not know there are five separate Lambda functions, three API Gateways, two S3 buckets, one Perplexity API call, and up to eleven Bedrock invocations behind that "Evaluate Novelty" button.

That is the Cyrano architecture. The performance is flawless precisely because the performer is invisible.

---

## Technical Appendix — The Facts Without Poetry

| Component | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 16 on Vercel | UI: upload, poll, display |
| API Gateway | AWS HTTP API (AmieApi) | Public-facing routes |
| API Lambda | Python 3.10 (amie-api) | Route, presign, create task, poll |
| Worker Lambda | Python 3.10 (amie-worker) | Orchestrate IDCA→NAA→AA pipeline |
| IDCA Lambda | Python 3.10 (amie-idca) | Invention detection + classification |
| NAA Lambda | Python 3.10 (amie-naa) | Prior art search + scoring |
| AA Lambda | Python 3.10 (amie-aa) | Aggregation + final report |
| Agent Gateway | AWS HTTP API × 3 | One per agent, internal only |
| S3 Manuscripts | AWS S3 | PDF storage, 30-day TTL |
| S3 Tasks | AWS S3 | Task state store, 7-day TTL |
| LLM | Claude Sonnet via AWS Bedrock | Powers all three agent calls |
| Patent Search | Perplexity Sonar API | Prior art retrieval for NAA |
| Agent Protocol | A2A (custom minimal impl.) | A2ATask / A2AResponse over HTTP POST |
| Task Polling | Browser setInterval 4s | Frontend polls GET /a2a/tasks/:id |
| IAM | Single shared LambdaRole | S3 + Bedrock + Lambda invoke |
| Infrastructure | AWS SAM (template.yaml) | All resources defined as code |
