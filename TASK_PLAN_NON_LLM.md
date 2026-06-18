# CODEX_TASK_PLAN.md — Add Non-LLM Commands and Robust LINE Webhook Handling

## 0. Role and Operating Rules for Codex

You are acting as a coding agent inside VS Code.

Your job is to improve the existing **Chat-to-Obsidian AI Second Brain** project.

The current project already has or is expected to have:

- FastAPI backend
- LINE webhook endpoint
- `/紀錄 URL` command
- webpage scraper
- OpenAI summarization
- Markdown note generation
- GitHub or local vault storage
- fallback behavior when OpenAI quota is unavailable

Current observed behavior:

- LINE webhook is connected.
- LINE can send requests to `/line/webhook`.
- OpenAI API may return `429 insufficient_quota`.
- Some websites may fail to fetch.
- The bot can save fallback raw notes when AI summarization fails.
- There have been repeated `502 Bad Gateway` responses from `/line/webhook`.

Your goal is to add robust, demo-friendly commands that work even when OpenAI billing/quota is unavailable.

Important operating rules:

1. Work phase by phase.
2. At the start of each phase, state:
   - what you will change,
   - which files you will edit,
   - how you will test it.
3. After each phase:
   - run verification steps,
   - report what passed and what failed,
   - fix obvious errors,
   - then stop.
4. Do **not** continue to the next phase until the user explicitly approves.
5. Never print full API keys, tokens, or secrets.
6. Do not remove existing working features.
7. Keep the code simple and readable.
8. Do not add vector database RAG in this task.
9. Prioritize demo stability over advanced features.
10. `/line/webhook` must not return 502 for ordinary processing errors.

---

## 1. Project Context

The project is a LINE bot that helps users save web URLs into an Obsidian-compatible Markdown knowledge base.

Example input:

```text
/紀錄 https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html
```

Expected system behavior:

```text
LINE message
→ FastAPI `/line/webhook`
→ parse command
→ fetch webpage
→ optionally summarize using OpenAI
→ create Markdown note
→ save to GitHub repo or local vault
→ reply to LINE
```

Because OpenAI API quota may be unavailable, the system must still work without AI summarization.

---

## 2. New Feature Scope

Add these commands:

| Command | Purpose | Requires OpenAI |
|---|---|---|
| `/指令` | Show help menu | No |
| `/help` | Show help menu | No |
| `/status` | Check service configuration | No |
| `/check URL` | Check whether a webpage can be fetched | No |
| `/raw URL` | Save raw webpage content as Markdown without OpenAI | No |
| `/最近` | List recent saved notes | No |
| `/搜尋 keyword` | Search saved notes by keyword | No |
| `/問 question` | Optional future command for LLM-based Q&A | Yes, not required now |

This task should implement all non-LLM commands.

---

## 3. Required Final Behavior

### 3.1 `/指令` or `/help`

User sends:

```text
/指令
```

or:

```text
/help
```

Bot replies:

```text
目前支援的指令：

/紀錄 [網址]
儲存網址為 Obsidian Markdown。若 AI 摘要失敗，會儲存原始筆記。

/raw [網址]
不使用 AI，直接儲存網頁原始內容為 Markdown。

/check [網址]
檢查網頁是否可以被伺服器抓取。

/最近
列出最近儲存的筆記。

/搜尋 [關鍵字]
搜尋已儲存的 Markdown 筆記。

/status
檢查 LINE、GitHub、OpenAI 等服務設定狀態。
```

---

### 3.2 `/status`

User sends:

```text
/status
```

Bot should check whether these environment variables are configured:

```text
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO
GITHUB_BRANCH
GITHUB_NOTES_DIR
OPENAI_API_KEY
OPENAI_MODEL
```

Expected reply example:

```text
系統狀態：

LINE webhook：OK
LINE access token：OK
GitHub storage：OK
OpenAI API key：OK
OpenAI quota：未檢查或可能不可用

注意：OpenAI API key 存在不代表 billing/quota 可用。
```

Important:

- Do not print full secret values.
- It is acceptable to show only `OK` or `Missing`.
- Do not call OpenAI in `/status` unless a safe minimal check already exists.
- If checking OpenAI would cost tokens, skip it.

---

### 3.3 `/check URL`

User sends:

```text
/check https://example.com
```

System should:

1. Extract URL.
2. Use existing scraper.
3. Do not call OpenAI.
4. Do not save a file.
5. Reply with:
   - success/failure,
   - title if available,
   - extracted text length,
   - short error if failed.

Success reply example:

```text
網頁抓取成功：

Title: Variables and Mutability
Text length: 8421 characters
URL: https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html
```

Failure reply example:

```text
網頁抓取失敗：

URL: https://example.com
原因：Could not extract readable article text.
```

---

### 3.4 `/raw URL`

User sends:

```text
/raw https://example.com/article
```

System should:

1. Extract URL.
2. Fetch webpage content.
3. Generate Markdown without OpenAI.
4. Save to GitHub or local vault using the existing storage layer.
5. Reply with saved path or GitHub URL.

Markdown format:

```md
---
title: "Article Title"
source: "https://example.com/article"
created: "YYYY-MM-DD"
tags:
  - raw
  - web-clip
type: raw-web-clip
---

# Article Title

## Source

https://example.com/article

## Raw Extracted Content

Extracted webpage text here.
```

If content is very long, limit raw extracted text to a reasonable size, such as 5000 to 8000 characters.

Expected reply:

```text
已儲存原始筆記：

Title: Article Title
Path: Inbox/YYYY-MM-DD-article-title.md
```

If using GitHub storage and an `html_url` is available:

```text
已儲存原始筆記：

Title: Article Title
GitHub: https://github.com/...
```

---

### 3.5 `/最近`

User sends:

```text
/最近
```

System should list recent Markdown notes from the current storage backend.

If GitHub storage is configured:

- Use GitHub API to list files under `GITHUB_NOTES_DIR`.
- Sort by available metadata if possible.
- If GitHub API cannot provide reliable modified time from listing, sort by filename descending because filenames usually start with dates.

If local vault is used:

- Read `.md` files from `vault/Inbox`.
- Sort by modified time descending.

Expected reply:

```text
最近 5 篇筆記：

1. 2026-06-18-variables-and-mutability.md
2. 2026-06-18-openai-api-error-codes.md
3. 2026-06-17-line-webhook-setup.md
```

If no notes found:

```text
目前還沒有找到任何 Markdown 筆記。
```

---

### 3.6 `/搜尋 keyword`

User sends:

```text
/搜尋 Rust
```

System should:

1. Search saved Markdown files.
2. Match keyword case-insensitively.
3. Return up to 5 matching notes.
4. Include short snippets.
5. Do not call OpenAI.

Expected reply:

```text
找到 2 篇相關筆記：

1. Variables and Mutability
檔案：2026-06-18-variables-and-mutability.md
片段：...variables are immutable by default...

2. Rust Ownership
檔案：2026-06-18-rust-ownership.md
片段：...ownership is Rust's most unique feature...
```

If no result:

```text
找不到包含「Rust」的筆記。
```

---

## 4. Required Technical Improvements

### 4.1 Webhook Must Not Return 502 for Normal Processing Errors

Current issue:

```text
POST /line/webhook HTTP/1.1 502 Bad Gateway
```

Required behavior:

- `/line/webhook` should return HTTP 200 for normal LINE webhook requests.
- If one event fails, log the error and continue.
- If LINE sends an empty events array, return `{"ok": true}`.
- Do not let OpenAI, GitHub, scraper, or reply failures bubble up into 502.

Suggested structure:

```python
@router.post("/line/webhook")
async def line_webhook(request: Request):
    try:
        body = await request.json()
        events = body.get("events", [])

        if not events:
            return {"ok": True}

        for event in events:
            try:
                await handle_line_event(event)
            except Exception:
                logger.exception("Failed to handle LINE event")

        return {"ok": True}

    except Exception:
        logger.exception("Unexpected LINE webhook error")
        return {"ok": False}
```

Do not copy this blindly if the project structure differs. Adapt it to the existing code.

---

### 4.2 Error Messages to LINE Must Be Short and Safe

Do not send full stack traces or full API responses to LINE.

Bad:

```text
OpenAI summarization failed: Error code: 429 - {'error': {'message': ...}}
```

Good:

```text
已儲存原始筆記，但 AI 摘要失敗：OpenAI API quota/billing 尚未可用。
```

or:

```text
儲存失敗：GitHub 寫入失敗，請查看伺服器記錄。
```

Full error details should only appear in server logs.

---

### 4.3 Add Storage Reader Layer

If not already present, add a storage reader abstraction for listing and reading notes.

Suggested new file:

```text
app/note_storage.py
```

Possible functions:

```python
def list_recent_notes(limit: int = 5) -> list[dict]:
    ...
```

```python
def search_notes(keyword: str, limit: int = 5) -> list[dict]:
    ...
```

```python
def read_note(path: str) -> dict:
    ...
```

Each note item should use a consistent shape:

```python
{
    "title": "Variables and Mutability",
    "path": "Inbox/2026-06-18-variables-and-mutability.md",
    "html_url": "https://github.com/...",
    "snippet": "..."
}
```

This layer should support:

1. GitHub repo storage if GitHub variables exist.
2. Local vault fallback if GitHub variables are missing.

---

## 5. Suggested File Changes

Likely files to edit:

```text
app/main.py
app/line_bot.py
app/command_parser.py
app/scraper.py
app/markdown_writer.py
app/github_writer.py
app/note_storage.py
app/config.py
README.md
tests/
```

Do not edit all files unnecessarily. Inspect the existing project and adapt.

---

# Phase 1 — Stabilize `/line/webhook`

## Goal

Ensure LINE webhook does not return 502 for ordinary errors.

## Tasks

1. Inspect existing `/line/webhook` route.
2. Add robust `try/except`.
3. Ensure empty `events` returns HTTP 200.
4. Ensure per-event failure is logged but does not crash entire route.
5. Replace unsafe user-facing error messages with short safe messages.

## Verification

Run locally:

```bash
uvicorn app.main:app --reload
```

Test empty events:

```bash
curl -i -X POST http://127.0.0.1:8000/line/webhook   -H "Content-Type: application/json"   -d '{"events":[]}'
```

Expected:

```text
HTTP/1.1 200 OK
```

Expected body:

```json
{"ok":true}
```

If deployed on Render, test:

```bash
curl -i -X POST https://YOUR-RENDER-APP.onrender.com/line/webhook   -H "Content-Type: application/json"   -d '{"events":[]}'
```

## Stop Condition

After Phase 1:

1. Report what changed.
2. Report test results.
3. Stop and ask whether to continue to Phase 2.

---

# Phase 2 — Add Help and Status Commands

## Goal

Add `/指令`, `/help`, and `/status`.

## Tasks

1. Update command parser to recognize:
   - `/指令`
   - `/help`
   - `/status`
2. Add handler functions.
3. Ensure these commands do not call OpenAI.
4. Ensure secrets are not printed.

## Expected Parser Results

Input:

```text
/help
```

Output type:

```text
help
```

Input:

```text
/status
```

Output type:

```text
status
```

## Verification

Add or update tests:

```bash
pytest tests/test_command_parser.py
```

Manual LINE test:

```text
/help
/status
```

Expected:

- Bot replies with command list.
- Bot replies with status summary.

## Stop Condition

After Phase 2:

1. Report what changed.
2. Report parser tests.
3. Report manual test suggestions.
4. Stop and ask whether to continue to Phase 3.

---

# Phase 3 — Add `/check URL`

## Goal

Add webpage fetch checking without saving and without OpenAI.

## Tasks

1. Update parser to recognize `/check URL`.
2. Reuse existing URL extraction.
3. Call existing scraper.
4. Reply with title, success/failure, text length, and short error.
5. Do not save anything.

## Verification

Test parser:

```bash
pytest tests/test_command_parser.py
```

Manual local test if a route exists, or LINE test:

```text
/check https://example.com
```

Expected:

```text
網頁抓取成功
```

Also test a likely blocked or invalid URL:

```text
/check https://invalid.invalid
```

Expected:

```text
網頁抓取失敗
```

## Stop Condition

After Phase 3:

1. Report behavior.
2. Report tests.
3. Stop and ask whether to continue to Phase 4.

---

# Phase 4 — Add `/raw URL`

## Goal

Save webpage content as Markdown without using OpenAI.

## Tasks

1. Update parser to recognize `/raw URL`.
2. Fetch webpage content with existing scraper.
3. Generate raw Markdown.
4. Save using GitHub storage if configured; otherwise local vault.
5. Reply with title and saved path or GitHub URL.

## Raw Markdown Requirements

Use this template:

```md
---
title: "{{ title }}"
source: "{{ url }}"
created: "{{ created_date }}"
tags:
  - raw
  - web-clip
type: raw-web-clip
---

# {{ title }}

## Source

{{ url }}

## Raw Extracted Content

{{ extracted_text }}
```

Limit extracted text to a safe length if needed.

## Verification

Manual LINE test:

```text
/raw https://example.com
```

Expected:

```text
已儲存原始筆記
```

Then verify:

- GitHub repo has a new `.md` file, or
- local `vault/Inbox` has a new `.md` file.

## Stop Condition

After Phase 4:

1. Report saved file path.
2. Report GitHub/local storage behavior.
3. Stop and ask whether to continue to Phase 5.

---

# Phase 5 — Add Note Listing with `/最近`

## Goal

List recent Markdown notes.

## Tasks

1. Add `app/note_storage.py` if needed.
2. Implement listing from GitHub or local vault.
3. Update parser for `/最近`.
4. Reply with up to 5 recent notes.

## GitHub Listing Guidance

Use GitHub Contents API:

```text
GET /repos/{owner}/{repo}/contents/{GITHUB_NOTES_DIR}
```

Use environment variables:

```text
GITHUB_TOKEN
GITHUB_OWNER
GITHUB_REPO
GITHUB_BRANCH
GITHUB_NOTES_DIR
```

If file metadata does not include modified time, sort filenames descending.

## Verification

Manual LINE test:

```text
/最近
```

Expected:

```text
最近 5 篇筆記：
1. ...
```

## Stop Condition

After Phase 5:

1. Report listing behavior.
2. Report whether GitHub or local storage was used.
3. Stop and ask whether to continue to Phase 6.

---

# Phase 6 — Add Keyword Search with `/搜尋 keyword`

## Goal

Search saved Markdown notes by keyword without OpenAI.

## Tasks

1. Update parser for `/搜尋 keyword`.
2. Implement note reading and keyword matching.
3. Search case-insensitively.
4. Return up to 5 matches with snippets.
5. Do not call OpenAI.

## Snippet Requirements

Each snippet should:

- Be short.
- Include surrounding text around the match.
- Avoid returning the entire note.

## Verification

Manual LINE test:

```text
/搜尋 Rust
```

Expected:

```text
找到 X 篇相關筆記：
```

Also test no-match case:

```text
/搜尋 unlikelykeyword123
```

Expected:

```text
找不到包含「unlikelykeyword123」的筆記。
```

## Stop Condition

After Phase 6:

1. Report search behavior.
2. Report tests.
3. Stop and ask whether to continue to Phase 7.

---

# Phase 7 — README Update

## Goal

Document the new commands for demo and future maintenance.

## Tasks

Update `README.md` with:

1. Command list.
2. Setup requirements.
3. Environment variables.
4. Render deployment note.
5. GitHub storage note.
6. OpenAI quota fallback explanation.
7. Demo flow.

## README Command Table

Add:

| Command | Description | Requires OpenAI |
|---|---|---|
| `/指令` | Show all commands | No |
| `/help` | Show all commands | No |
| `/status` | Show service status | No |
| `/紀錄 URL` | Save URL with AI summary if available | Optional |
| `/raw URL` | Save raw webpage note | No |
| `/check URL` | Check whether webpage can be fetched | No |
| `/最近` | List recent notes | No |
| `/搜尋 keyword` | Search notes | No |

## Stop Condition

After Phase 7:

1. Report documentation changes.
2. Confirm project is demo-ready.
3. Stop.

---

## 6. Demo Script After These Features

The demo can show:

```text
1. Send /指令
   → Bot shows supported commands.

2. Send /status
   → Bot shows LINE/GitHub/OpenAI status.

3. Send /check https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html
   → Bot confirms the page can be fetched.

4. Send /raw https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html
   → Bot saves a raw Markdown note.

5. Send /最近
   → Bot lists the note just saved.

6. Send /搜尋 Rust
   → Bot finds the saved Rust note.
```

This proves the automation works even without OpenAI quota.

---

## 7. Important Constraints

Do not implement these in this task:

- Vector database
- ChromaDB
- Full RAG
- Login system
- Multi-user account management
- Obsidian plugin
- WhatsApp
- Messenger
- Google Drive API

Keep the scope focused on stable LINE bot commands.

---

## 8. Final Instruction to Codex

Start with **Phase 1 only**.

Do not implement later phases yet.

After Phase 1 verification is complete, stop and ask:

```text
Phase 1 is complete. Do you want me to continue to Phase 2?
```
