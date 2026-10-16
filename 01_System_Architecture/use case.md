%%{init: {
  'theme': 'base',
  'themeVariables': {
    'background': '#ffffff',
    'primaryColor': '#ffffff',
    'primaryBorderColor': '#2563eb',
    'primaryTextColor': '#0f172a',
    'lineColor': '#475569',
    'textColor': '#0f172a',
    'clusterBkg': '#ffffff',
    'clusterBorder': '#94a3b8'
  }
}}%%
flowchart TD

    %% Primary Actor
    User["👤 Financial Analyst / User"]

    %% System Boundary
    subgraph FinPilot["FinPilot AI Platform Boundary"]

        %% 1. Authentication & Security
        subgraph GroupAuth["1. Identity & Access Management"]
            UC_Register(["Register & Verify Account"])
            UC_Login(["Sign In / Authenticate"])
            UC_Google(["Sign in with Google OAuth"])
            UC_Logout(["Sign Out & Clear Session"])
            UC_Profile(["Manage Profile & Settings"])
        end

        %% 2. Ingestion & Document Management
        subgraph GroupDoc["2. Document Ingestion & Storage"]
            UC_Upload(["Upload Financial Documents"])
            UC_Validate(["Validate Magic Bytes & MIME Type"])
            UC_OCR(["Extract Text & Tables via OCR"])
            UC_Preview(["Preview & Inspect Document"])
            UC_Delete(["Delete Document & Artifacts"])
        end

        %% 3. Financial Intelligence
        subgraph GroupFin["3. Financial Intelligence & Auditing"]
            UC_Ratios(["Compute Financial Ratios & KPIs"])
            UC_Anomaly(["Detect Anomalies & Inconsistencies"])
            UC_Diligence(["Perform Due Diligence Audit"])
        end

        %% 4. AI Assistant
        subgraph GroupAI["4. Evidence-Grounded AI Assistant"]
            UC_Chat(["Query Financial Assistant"])
            UC_Evidence(["Retrieve Grounded Citations"])
            UC_History(["Manage Chat History"])
        end

        %% 5. Reporting
        subgraph GroupRep["5. Executive Reporting & Export"]
            UC_Report(["Generate Executive Report"])
            UC_Export(["Download & Export PDF"])
        end

    end

    %% Supporting External Actors
    GoogleAuth["🌐 Google OIDC Provider"]
    LLMEngine["🧠 AI / LLM Engine"]

    %% User Associations
    User --- UC_Register
    User --- UC_Login
    User --- UC_Logout
    User --- UC_Profile
    User --- UC_Upload
    User --- UC_Preview
    User --- UC_Delete
    User --- UC_Ratios
    User --- UC_Diligence
    User --- UC_Chat
    User --- UC_History
    User --- UC_Report

    %% Use Case Relationships: <<include>>
    UC_Upload -->|"<<include>>"| UC_Validate
    UC_Upload -->|"<<include>>"| UC_OCR
    UC_Chat -->|"<<include>>"| UC_Evidence
    UC_Report -->|"<<include>>"| UC_Export

    %% Use Case Relationships: <<extend>>
    UC_Login -.->|"<<extend>>"| UC_Google
    UC_Ratios -.->|"<<extend>>"| UC_Anomaly
    UC_Report -.->|"<<extend>>"| UC_Ratios

    %% Supporting Actor Associations
    UC_Google --- GoogleAuth
    UC_Evidence --- LLMEngine

    %% Visual Styling
    classDef default fill:#ffffff,stroke:#2563eb,stroke-width:1.5px,color:#0f172a;
    classDef actor fill:#f8fafc,stroke:#1e3a8a,stroke-width:2px,color:#0f172a,font-weight:bold;
    classDef group fill:#ffffff,stroke:#64748b,stroke-width:1.5px,stroke-dasharray: 3 3,color:#0f172a;

    class User,GoogleAuth,LLMEngine actor;
    class GroupAuth,GroupDoc,GroupFin,GroupAI,GroupRep,FinPilot group;