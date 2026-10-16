%%{init: {'theme': 'base', 'themeVariables': {'background': '#ffffff', 'primaryColor': '#ffffff', 'primaryBorderColor': '#2563eb', 'primaryTextColor': '#0f172a', 'lineColor': '#475569', 'clusterBkg': '#ffffff', 'clusterBorder': '#94a3b8'}}}%%
flowchart LR
    Client["💻 Web Browser / Client"]

    subgraph Security["Security & Ingestion Layer"]
        CSRF["CSRF & Session Protection"]
        Limiter["Flask-Limiter (Rate Limiting)"]
        MagicValidator["Magic-Bytes & MIME Sniffer"]
    end

    subgraph Core["FinPilot AI Core Engine"]
        Storage["Storage Service (Encrypted Local / Cloud)"]
        OCR["OCR & Table Extraction (PyMuPDF / Tesseract)"]
        FinAnalytics["Financial Intelligence (Ratios & DuPont)"]
        Anomaly["Anomaly Detection Engine"]
    end

    subgraph Knowledge["Grounding & AI Assistant"]
        Evidence["Evidence Retrieval & Citation Index"]
        LLM["AI / LLM Synthesis Engine"]
    end

    subgraph Output["Reporting & Persistence"]
        DB[("MySQL Database")]
        PDFGen["ReportLab PDF Generator"]
    end

    Client -->|HTTPS POST| CSRF
    CSRF --> Limiter
    Limiter --> MagicValidator
    MagicValidator --> Storage
    Storage --> OCR
    OCR --> FinAnalytics
    FinAnalytics --> Anomaly
    Anomaly --> DB

    Client -->|Interactive Query| Evidence
    DB --> Evidence
    Evidence --> LLM
    LLM --> Client

    Client -->|Generate Report| PDFGen
    DB --> PDFGen
    FinAnalytics --> PDFGen

    classDef default fill:#ffffff,stroke:#2563eb,stroke-width:1.5px,color:#0f172a;
    classDef highlight fill:#f8fafc,stroke:#1e3a8a,stroke-width:2px,color:#0f172a;
    classDef db fill:#ffffff,stroke:#0d9488,stroke-width:2px,color:#0f172a;
    class Client,LLM highlight;
    class DB db;
