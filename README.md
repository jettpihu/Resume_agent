# 📄 AI Career Resume Agent

A production-ready Fetch.ai uAgent designed to generate ATS-friendly, personalized resumes and career profiles. It features automated AI data extraction (GitHub, LinkedIn, LeetCode), premium monetization (Fetch.ai Payments), and military-grade security (PII stripping, GDPR consent).

## 🏗️ Architecture

```mermaid
graph TD
    User([User Chat]) -->|Agentverse Protocol| Agent[agent.py (Core Router)]
    Agent -->|Validation| SecRouter[Security Layer (Consent, PII Skip)]
    
    SecRouter --> Router(Routing & LLM)
    Router -->|GitHub/LinkedIn Query| Fetcher[profile_fetcher.py]
    Fetcher --> ASI[ASI:One Model]
    
    Router -->|Assess Resume| ATS[ats_checker.py]
    ATS --> ASI
    
    Router -->|Latex PDF Request| Generator[resume_generator.py]
    Generator -.->|If available| pdflatex([pdflatex Compile])
    
    Router -->|Premium Request| Payment[payment_module.py]
    Payment -->|CosmPy Verify Ledger| FetchNet[(Fetch.ai Testnet)]
```

## 🚀 Key Modules
- **`agent.py`**: The secure uAgent combining Chat handlers, Consent loops, and Kill switches.
- **`resume_generator.py`**: Manages Jinja2 formatting of LaTeX templates for beautiful ATS-friendly outputs.
- **`ats_checker.py`**: Algorithm simulating corporate ATS screeners (Keyword density, Action Verbs, Measurability).
- **`profile_fetcher.py`**: Connects via API to GitHub/LeetCode to extract stats for Auto mode.
- **`payment_module.py`**: Handles subscription gating (Basic vs Unlimited Premium usage).

## ☁️ Agentverse Deployment Instructions
1. Upload all `.py` files into a managed Agentverse instance.
2. Ensure you add `ASI_ONE_API_KEY` and `AGENT_SEED_PHRASE` to the **Secrets** tab.
3. Because `pdflatex` is a raw system binary, the Agentverse instance will output **LaTeX code** directly to the user to compile locally (or you can hook it to an external API like overleaf/pdf generator via `httpx`).
4. Click **Run** and chat with your AI Resume builder!
