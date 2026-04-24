# AMIE – System Architecture

## Illustration 1 — The Two Worlds: Visible vs Hidden

```mermaid
flowchart TD
    Roxane(["👩 ROXANE\nThe User\nSees only the beautiful result"])

    subgraph Visible["✨ THE VISIBLE WORLD  —  What Roxane sees"]
        Christian["💙 CHRISTIAN\nNext.js on Vercel\nBeautiful face · Zero intelligence\nUploads · Polls · Renders"]
    end

    subgraph Balcony["🏛️   THE BALCONY  —  AmieApi Gateway  —  Where visible meets hidden"]
        B1["POST /upload-url"]
        B2["POST /a2a/tasks  ①"]
        B3["GET  /a2a/tasks/:id"]
        B4["GET  /.well-known/agent-card.json  ②"]
    end

    subgraph Hidden["🎭 THE HIDDEN WORLD  —  What Roxane never sees"]

        subgraph Cyrano["❤️   CYRANO  —  Worker Lambda  —  The brilliant mind"]
            Step1["① Read PDF from S3"]
            Step2["② Call IDCA via A2A"]
            Step3["③ Call NAA via A2A\n    only if SD = Present"]
            Step4["④ Call AA via A2A"]
            Step5["⑤ Write progress to S3\n    after every act"]
            Step1 --> Step2 --> Step3 --> Step4 --> Step5
        end

        S3t[("📜 S3 Task Letters\npending → running\n→ idca_complete\n→ naa_complete\n→ complete")]
        S3m[("📄 S3 Manuscripts\nUploaded PDFs")]

        subgraph Agents["🎭 THE THREE ACTS  —  Agent Lambdas"]
            IDCA["Act I · IDCA\nIs there genius here?"]
            NAA["Act II · NAA\nWhat came before?"]
            AA["Act III · AA\nWhat does it mean?"]
        end

        Bedrock[["🧠 AWS Bedrock\nClaude Sonnet\nCyrano's eloquence"]]
        Perplexity[["🔍 Perplexity\nPrior art search"]]
    end

    Roxane --> Christian
    Christian --> B1 & B2 & B3 & B4

    B2 -->|"creates task\nasync invokes"| Cyrano
    B3 -->|"reads"| S3t
    B1 -->|"presigns"| S3m
    Christian -->|"direct PUT PDF"| S3m

    Step2 -->|"A2ATask"| IDCA
    Step3 -->|"A2ATask"| NAA
    Step4 -->|"A2ATask"| AA
    Step5 --> S3t

    IDCA & NAA & AA --> Bedrock
    NAA --> Perplexity

    classDef user fill:#fbbf24,stroke:#d97706,color:#000,font-weight:bold
    classDef christian fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef cyrano fill:#dc2626,stroke:#991b1b,color:#fff,font-weight:bold
    classDef agent fill:#7c3aed,stroke:#5b21b6,color:#fff
    classDef storage fill:#059669,stroke:#047857,color:#fff
    classDef external fill:#4b5563,stroke:#1f2937,color:#fff
    classDef balcony fill:#f97316,stroke:#ea580c,color:#fff

    class Roxane user
    class Christian christian
    class Step1,Step2,Step3,Step4,Step5 cyrano
    class IDCA,NAA,AA agent
    class S3t,S3m storage
    class Bedrock,Perplexity external
    class B1,B2,B3,B4 balcony
```

---

## Illustration 2 — The Two Endpoints on Every Agent

Every agent in the system exposes exactly two endpoints. One receives work (A2A), one advertises capability (Agent Card).

```mermaid
flowchart LR
    Cyrano(["❤️  CYRANO\nWorker Lambda\nThe only caller\nof these endpoints"])

    subgraph IDCA["🎭 ACT I — IDCA Agent  (amie-idca + IdcaApi)"]
        direction TB
        I1["① A2A Endpoint\nPOST /tasks\n─────────────────────\nReceives:  manuscript_text\nRuns:      Claude via Bedrock\nReturns:   sd · synopsis\n           fields_map · reasoning"]
        I2["② Agent Card\nGET /.well-known/agent-card.json\n─────────────────────\nReturns static JSON:\nname · version · description\ninput_schema · output_schema"]
    end

    subgraph NAA["🎭 ACT II — NAA Agent  (amie-naa + NaaApi)"]
        direction TB
        N1["① A2A Endpoint\nPOST /tasks\n─────────────────────\nReceives:  manuscript_text\n            idca_result\nRuns:      Claude × 11 + Perplexity\nReturns:   ss · references[]\n           css · ewss scores"]
        N2["② Agent Card\nGET /.well-known/agent-card.json\n─────────────────────\nReturns static JSON:\nname · version · description\ninput_schema · output_schema"]
    end

    subgraph AA["🎭 ACT III — AA Agent  (amie-aa + AaApi)"]
        direction TB
        A1["① A2A Endpoint\nPOST /tasks\n─────────────────────\nReceives:  idca_result\n                naa_result (or null)\nRuns:      Claude via Bedrock\nReturns:   FRT · executive_summary\n               novelty_risk"]
        A2["② Agent Card\nGET /.well-known/agent-card.json\n─────────────────────\nReturns static JSON:\nname · version · description\ninput_schema · output_schema"]
    end

    Cyrano -->|"sends A2ATask\ngets A2AResponse"| I1
    Cyrano -->|"sends A2ATask\ngets A2AResponse"| N1
    Cyrano -->|"sends A2ATask\ngets A2AResponse"| A1

    Cyrano -.->|"discovery\nbefore calling"| I2
    Cyrano -.->|"discovery\nbefore calling"| N2
    Cyrano -.->|"discovery\nbefore calling"| A2

    classDef endpoint1 fill:#dc2626,stroke:#991b1b,color:#fff
    classDef endpoint2 fill:#059669,stroke:#047857,color:#fff
    classDef cyrano fill:#f97316,stroke:#c2410c,color:#fff,font-weight:bold

    class I1,N1,A1 endpoint1
    class I2,N2,A2 endpoint2
    class Cyrano cyrano
```

---

## Illustration 3 — Cyrano's Role: The Full Pipeline Walk-through

```mermaid
sequenceDiagram
    actor Roxane as 👩 Roxane (User)
    participant Christian as 💙 Christian (Frontend)
    participant Balcony as 🏛️  API Gateway
    participant Cyrano as ❤️  Cyrano (Worker Lambda)
    participant Letters as 📜 S3 Letters
    participant IDCA as 🎭 Act I · IDCA
    participant NAA as 🎭 Act II · NAA
    participant AA as 🎭 Act III · AA

    Note over Roxane,Christian: Roxane sees only this side of the curtain

    Roxane->>Christian: uploads manuscript PDF
    Christian->>Balcony: POST /a2a/tasks
    Balcony->>Letters: save {status: "pending"}
    Balcony->>Cyrano: async invoke — fire and forget
    Balcony-->>Christian: 202 {task_id, status:"pending"}
    Christian-->>Roxane: "Your manuscript is received — please wait"

    Note over Cyrano,AA: The curtain rises — Roxane cannot see this

    Cyrano->>Letters: load task · extract PDF text
    Cyrano->>Letters: save {status: "running"}

    rect rgb(59, 130, 246)
        Note over Cyrano,IDCA: ACT I — Is there an invention?
        Cyrano->>IDCA: POST /tasks  A2ATask {manuscript_text}
        IDCA-->>Cyrano: A2AResponse {sd:"Present", synopsis, fields_map}
        Cyrano->>Letters: save {status:"idca_complete", idca:{...}}
    end

    rect rgb(124, 58, 237)
        Note over Cyrano,NAA: ACT II — What prior art exists? (SD=Present only)
        Cyrano->>NAA: POST /tasks  A2ATask {text, idca_result}
        NAA-->>Cyrano: A2AResponse {ss, references[scored], ssr_criteria}
        Cyrano->>Letters: save {status:"naa_complete", naa:{...}}
    end

    rect rgb(5, 150, 105)
        Note over Cyrano,AA: ACT III — What is the verdict?
        Cyrano->>AA: POST /tasks  A2ATask {idca_result, naa_result}
        AA-->>Cyrano: A2AResponse {FRT, executive_summary, novelty_risk}
        Cyrano->>Letters: save {status:"complete", aa:{...}}
    end

    Note over Roxane,Christian: Christian reads Cyrano's letters and delivers them to Roxane

    loop every 4 seconds until complete
        Christian->>Balcony: GET /a2a/tasks/{task_id}
        Balcony->>Letters: load task state
        Letters-->>Christian: current status + results so far
        Christian-->>Roxane: renders each act as it completes
    end

    Note over Roxane: Roxane sees the final report and is amazed.<br/>She believes Christian is brilliant.<br/>It was Cyrano all along.
```

---

## The Core Insight in One Picture

```mermaid
graph TD
    subgraph Sees["WHAT ROXANE SEES"]
        UI["Beautiful Next.js UI"]
        PB["Progress bar advances"]
        FR["Final report appears"]
        UI --> PB --> FR
    end

    subgraph Logic["WHAT ACTUALLY HAPPENS"]
        CR["Cyrano reads PDF"]
        CI["Cyrano calls IDCA"]
        CN["Cyrano calls NAA"]
        CA["Cyrano calls AA"]
        CS["Cyrano saves complete"]
        CR --> CI --> CN --> CA --> CS
    end

    PB -.->|"triggered by"| CI
    PB -.->|"triggered by"| CN
    FR -.->|"renders"| CS

    classDef roxane fill:#fbbf24,stroke:#d97706,color:#000
    classDef logic fill:#dc2626,stroke:#991b1b,color:#fff

    class UI,PB,FR roxane
    class CR,CI,CN,CA,CS logic
```
