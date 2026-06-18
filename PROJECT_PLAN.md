# PROJECT_PLAN.md — Chat-to-Obsidian AI Second Brain

## 0. Role and Operating Rules for Codex

You are acting as a coding agent inside VS Code.

Your job is to build this project step by step.

Important rules:

1. Work in small phases.
2. At the start of each phase, briefly restate:

   * what you will build,
   * which files you will edit,
   * how you will verify it.
3. After completing each phase:

   * run the verification steps,
   * report what passed and what failed,
   * fix obvious errors if needed,
   * then stop.
4. Do **not** continue to the next phase until the user explicitly says:

   * "continue",
   * "下一步",
   * "go on",
   * or another clear approval.
5. Do not skip tests or verification.
6. Do not introduce unnecessary frameworks.
7. Keep the first version simple and demo-friendly.
8. Prefer readable, maintainable code over clever abstractions.
9. Do not implement advanced RAG until the basic `/record URL` workflow works.
10. If environment variables, API keys, or external service settings are missing, create placeholders and document them clearly.

---

## 1. Project Overview

Project name:

```text
Chat-to-Obsidian AI Second Brain
```

Goal:

Build a FastAPI backend that connects to a chat app, preferably LINE, and allows the user to save web articles into an Obsidian-compatible Markdown vault.

The user can send a message like:

```text
/record https://example.com/article
```

or:

```text
/紀錄 https://example.com/article
```

The backend should:

1. Receive the message through a webhook.
2. Detect whether the message is a save command.
3. Extract the URL.
4. Fetch the webpage content.
5. Ask an LLM to summarize and structure the content.
6. Generate a Markdown file.
7. Save the Markdown file into a local `vault/Inbox/` folder.
8. Reply with a success message.

Later, the project may support normal Q&A using the saved Obsidian notes.

---

## 2. MVP Scope

The MVP only needs to support this flow:

```text
User sends:
/紀錄 https://example.com/article

System does:
LINE webhook or local test input
→ parse command
→ fetch webpage
→ summarize with LLM
→ generate Markdown
→ save .md file into vault/Inbox/
→ return success response
```

The MVP does **not** need:

* Full vector database RAG.
* WhatsApp integration.
* Messenger integration.
* Google Drive sync.
* Obsidian plugin development.
* User authentication.
* Database.
* Multi-user support.

Those are future improvements.

---

## 3. Recommended Tech Stack

Use:

```text
Python 3.11+
FastAPI
Uvicorn
python-dotenv
requests
beautifulsoup4
trafilatura
openai
pydantic
pytest
```

Optional later:

```text
line-bot-sdk
chromadb
sentence-transformers
google-api-python-client
```

---

## 4. Initial Project Structure

Create this structure:

```text
chat-to-obsidian/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── command_parser.py
│   ├── scraper.py
│   ├── summarizer.py
│   ├── markdown_writer.py
│   ├── line_bot.py
│   └── rag.py
│
├── tests/
│   ├── __init__.py
│   ├── test_command_parser.py
│   ├── test_markdown_writer.py
│   └── test_scraper.py
│
├── vault/
│   └── Inbox/
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── PROJECT_PLAN.md
```

---

## 5. Development Order

Build in this order:

```text
Phase 1: Bootstrap FastAPI
Phase 2: Command Parser
Phase 3: Markdown Writer
Phase 4: Web Scraper
Phase 5: LLM Summarizer
Phase 6: Local Save URL API
Phase 7: LINE Bot Webhook
Phase 8: Simple Q&A
Phase 9: README and Demo
Phase 10: Optional Deployment
```

Do not change this order unless there is a strong reason.

---

# Phase 1 — Project Bootstrap

## Goal

Create the basic project structure, install dependencies, and confirm FastAPI runs locally.

## Files to create or edit

```text
requirements.txt
.env.example
.gitignore
README.md
app/__init__.py
app/main.py
app/config.py
```

## Verification

Run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then test:

```bash
curl http://127.0.0.1:8000/health
```

Expected result:

```json
{"status":"ok","project":"chat-to-obsidian"}
```

## Stop Condition

After Phase 1 is complete:

1. Report created files.
2. Report verification result.
3. Stop and ask the user whether to continue to Phase 2.

Do not start Phase 2 automatically.

---

# Phase 2 — Command Parser

## Goal

Implement command parsing for:

```text
/record https://example.com
/紀錄 https://example.com
```

Also handle normal questions.

## Files to create or edit

```text
app/command_parser.py
tests/test_command_parser.py
```

## Expected Behavior

Input:

```text
/紀錄 https://example.com/article
```

Output:

```python
{
    "type": "save_url",
    "url": "https://example.com/article",
    "raw_text": "/紀錄 https://example.com/article"
}
```

Input:

```text
What did I save about AI agents?
```

Output:

```python
{
    "type": "question",
    "question": "What did I save about AI agents?",
    "raw_text": "What did I save about AI agents?"
}
```

## Verification

Run:

```bash
pytest tests/test_command_parser.py
```

## Stop Condition

After Phase 2 is complete:

1. Report parser behavior.
2. Report test results.
3. Stop and ask the user whether to continue to Phase 3.

Do not start Phase 3 automatically.

---

# Phase 3 — Markdown Writer

## Goal

Generate safe Markdown filenames and save Markdown content into the Obsidian-compatible vault folder.

## Files to create or edit

```text
app/markdown_writer.py
tests/test_markdown_writer.py
vault/Inbox/.gitkeep
```

## Filename Format

Use:

```text
YYYY-MM-DD-title-slug.md
```

Example:

```text
2026-06-18-ai-agents-and-automation.md
```

## Requirements

1. Create the target folder if it does not exist.
2. Avoid unsafe filename characters.
3. If a file already exists, append a counter.
4. Return the saved file path.

## Verification

Run:

```bash
pytest tests/test_markdown_writer.py
```

Also manually confirm:

```bash
ls vault/Inbox
```

## Stop Condition

After Phase 3 is complete:

1. Report file saving behavior.
2. Report test results.
3. Stop and ask the user whether to continue to Phase 4.

Do not start Phase 4 automatically.

---

# Phase 4 — Webpage Scraper

## Goal

Fetch a URL and extract readable article text.

## Files to create or edit

```text
app/scraper.py
tests/test_scraper.py
```

## Required Function

```python
def fetch_webpage_content(url: str) -> dict:
    ...
```

Expected return:

```python
{
    "url": "https://example.com/article",
    "title": "Example Article Title",
    "text": "Clean article text...",
    "success": True,
    "error": None
}
```

## Implementation Guidance

Use `trafilatura` first.

Fallback to:

```text
requests + BeautifulSoup
```

## Verification

Run:

```bash
pytest tests/test_scraper.py
```

Manual test:

```bash
python - <<'PY'
from app.scraper import fetch_webpage_content
result = fetch_webpage_content("https://example.com")
print(result)
PY
```

## Stop Condition

After Phase 4 is complete:

1. Report scraper behavior.
2. Report test results.
3. Stop and ask the user whether to continue to Phase 5.

Do not start Phase 5 automatically.

---

# Phase 5 — LLM Summarizer

## Goal

Send webpage content to an LLM and return a structured Markdown note.

## Files to create or edit

```text
app/summarizer.py
```

## Required Function

```python
def summarize_to_markdown(title: str, url: str, text: str) -> dict:
    ...
```

## Markdown Output Format

```md
---
title: "Article Title"
source: "https://example.com/article"
created: "2026-06-18"
tags:
  - ai
  - automation
  - second-brain
type: web-clip
---

# Article Title

## Summary

Short summary of the article.

## Key Points

- Key point 1
- Key point 2
- Key point 3

## Why It Matters

Explain why this source may be useful.

## My Notes

- Personal interpretation or possible use cases.

## Related Concepts

- [[AI Agent]]
- [[Automation]]
- [[Second Brain]]
```

## LLM Prompt Requirements

The prompt should tell the model:

1. Convert the article into an Obsidian-friendly Markdown note.
2. Preserve the source URL.
3. Use Traditional Chinese by default.
4. Generate 3 to 7 useful tags.
5. Keep the note structured and concise.
6. Do not invent facts not supported by the article.
7. If the article is too short or unclear, say so in the note.

## Stop Condition

After Phase 5 is complete:

1. Report LLM behavior.
2. Report whether the API key is configured.
3. Report manual test result.
4. Stop and ask the user whether to continue to Phase 6.

Do not start Phase 6 automatically.

---

# Phase 6 — Local API Endpoint for Saving URL

## Goal

Create a local API endpoint that can test the full save flow without LINE first.

## Endpoint

```text
POST /api/save-url
```

Request body:

```json
{
  "url": "https://example.com/article"
}
```

Response body:

```json
{
  "success": true,
  "message": "Saved to Obsidian vault",
  "path": "vault/Inbox/2026-06-18-example-article.md",
  "title": "Example Article"
}
```

## Verification

Start server:

```bash
uvicorn app.main:app --reload
```

Test:

```bash
curl -X POST http://127.0.0.1:8000/api/save-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Then verify:

```bash
ls vault/Inbox
```

## Stop Condition

After Phase 6 is complete:

1. Report endpoint behavior.
2. Report generated Markdown path.
3. Report limitations.
4. Stop and ask the user whether to continue to Phase 7.

Do not start Phase 7 automatically.

---

# Phase 7 — LINE Bot Webhook Integration

## Goal

Connect the FastAPI backend to LINE Messaging API.

## Required Behavior

When the user sends:

```text
/紀錄 https://example.com/article
```

The system should:

1. Receive LINE webhook event.
2. Parse the text message.
3. Run the save URL workflow.
4. Reply to LINE with success or failure message.

When the user sends a normal message:

```text
你可以做什麼？
```

The system should reply:

```text
目前我支援：
/紀錄 [網址]：把網頁整理成 Markdown 並存進 Obsidian Vault。
```

## Suggested Route

```text
POST /line/webhook
```

## Verification

Use one of these:

```text
ngrok
Cloudflare Tunnel
Render deployment
```

Webhook URL format:

```text
https://your-public-url/line/webhook
```

## Stop Condition

After Phase 7 is complete:

1. Report webhook route status.
2. Report whether credentials are configured.
3. Report local test result.
4. If possible, report real LINE test result.
5. Stop and ask the user whether to continue to Phase 8.

Do not start Phase 8 automatically.

---

# Phase 8 — Simple Obsidian Q&A Without Vector DB

## Goal

Support normal user questions by searching saved Markdown notes using simple keyword search.

This is not full RAG yet. It is a simple demo-friendly retrieval system.

## Required Functions

```python
def search_notes(query: str, vault_path: str, max_results: int = 5) -> list[dict]:
    ...
```

```python
def answer_from_notes(question: str, notes: list[dict]) -> dict:
    ...
```

## Behavior

When user sends normal question:

```text
我之前存過的 AI Agent 重點是什麼？
```

System should:

1. Search Markdown notes.
2. Extract relevant snippets.
3. Ask LLM to answer using only those snippets.
4. Reply to LINE.

## Stop Condition

After Phase 8 is complete:

1. Report search behavior.
2. Report Q&A behavior.
3. Report limitations.
4. Stop and ask the user whether to continue to Phase 9.

Do not start Phase 9 automatically.

---

# Phase 9 — README and Demo Preparation

## Goal

Prepare the project for presentation and Task 4 submission.

## README Must Include

1. Project title.
2. Problem statement.
3. Automation idea.
4. Tech stack.
5. Architecture diagram.
6. Setup instructions.
7. Environment variables.
8. How to run locally.
9. How to test `/api/save-url`.
10. How to connect LINE webhook.
11. Demo flow.
12. Limitations.
13. Future work.

## Demo Flow

```text
LINE Message
   ↓
FastAPI Webhook
   ↓
Command Parser
   ↓
Web Scraper
   ↓
LLM Summarizer
   ↓
Markdown Writer
   ↓
Obsidian Vault
```

## Stop Condition

After Phase 9 is complete:

1. Report documentation files.
2. Report whether the project is ready for demo.
3. Stop and ask the user if they want help preparing slides.

Do not continue automatically.

---

# Phase 10 — Optional Deployment

Only do this phase if the user asks.

## Goal

Deploy the FastAPI backend so LINE can call it through a public HTTPS URL.

Recommended options:

```text
Render
Railway
Fly.io
```

## Render Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Important Limitation

If deployed on Render, writing Markdown files to local disk may not be persistent long-term.

For demo, this may be acceptable.

For a more durable solution, use:

```text
GitHub repo storage
Google Drive
Supabase Storage
S3-compatible storage
```

## Stop Condition

After Phase 10 is complete:

1. Report deployment status.
2. Report public URL.
3. Report LINE webhook verification status.
4. Stop.

