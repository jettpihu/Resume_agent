# AI Resume Agent

Content-only resume generator agent using Fetch.ai chat protocol.

## Features

- Takes raw resume content from user chat (no LinkedIn/GitHub profile fetch dependency)
- Converts content to structured JSON using ASI:One
- Generates LaTeX, compiles PDF, uploads to tmpfiles, returns only PDF link
- Supports paid resume editing via `EDIT RESUME:` command
- Editing is gated behind `0.01 FET` payment request
- Maintains user state in storage (consent, last resume JSON, pending edit)

## Commands (chat)

- **Create resume:** send full resume content in plain text
- **Edit resume:** `EDIT RESUME: <your changes>`
  - Example: `EDIT RESUME: Replace summary with backend-focused version and add Kubernetes in skills`
  - If payment is required, complete `0.01 FET` and send any follow-up message; pending edit is auto-applied.

## State flow

- `consent_<sender>`: privacy consent flag
- `resume_profile_<sender>`: latest structured resume JSON memory
- `pending_edit_<sender>`: queued edit instructions before payment
- `edit_unlocked_<sender>`: edit payment unlock flag

## Workflow (Mermaid)

```mermaid
flowchart TD
    A[User sends chat message] --> B{Consent already given?}
    B -- No --> C[Ask user to reply AGREE]
    C --> A
    B -- Yes --> D{Message starts with EDIT RESUME:?}

    D -- No --> E[Parse content to structured JSON via ASI:One]
    E --> F[Generate LaTeX from template]
    F --> G[Compile PDF]
    G --> H[Upload PDF to tmpfiles]
    H --> I[Send PDF link to user]
    I --> J[Store resume_profile_sender]

    D -- Yes --> K{edit_unlocked_sender?}
    K -- No --> L[Store pending_edit_sender]
    L --> M[Send RequestPayment 0.01 FET]
    M --> N[On CommitPayment set edit_unlocked_sender true]
    N --> O[User sends any next message]
    O --> P[Auto-apply pending edit]
    P --> F

    K -- Yes --> Q[Apply edit instructions on stored resume JSON]
    Q --> F
```

## Environment variables

Create `.env` with:

```env
AGENT_SEED_PHRASE=your_seed_phrase
ASI_ONE_API_KEY=your_asi_one_api_key
ADMIN_ADDR=optional_admin_address
```

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python agent.py
```

## Docker run

```bash
docker compose up --build
```

Agent runs on `http://0.0.0.0:8001`.

## File structure

- `agent.py` - chat flow, content parsing, resume generate/edit pipeline
- `resume_generator.py` - LaTeX render + PDF compile
- `templates/resume_template.tex.j2` - printable resume template
- `payment_module.py` - payment protocol handlers (`0.1 FET` premium + `0.01 FET` edit unlock support)

## Notes

- For PDF compile, LaTeX tools must be installed in runtime container/host.
- If upload fails, agent reports upload error instead of sending LaTeX code.
