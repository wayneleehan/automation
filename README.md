# Chat-to-Obsidian AI Second Brain

A FastAPI backend that turns links sent through LINE or a local API into
Obsidian-compatible Markdown notes. It includes non-LLM commands for checking
webpages, saving raw content, listing recent notes, and keyword search, so the
core demo still works when AI quota is unavailable.

## Problem statement

Useful articles often arrive in chat and disappear into message history,
bookmarks, or open browser tabs. Saving them manually into Obsidian requires
copying the content, summarizing it, adding metadata, choosing a filename, and
moving the note into the correct vault folder.

This project automates that workflow so a user can save an article with one
LINE message:

```text
/紀錄 https://example.com/article
```

## Automation idea

For a save command, the backend:

1. verifies and receives the LINE webhook, or accepts a local API request;
2. validates and fetches the URL;
3. extracts readable article content;
4. asks OpenAI, then Gemini, to produce concise Traditional Chinese Markdown;
5. generates a safe, date-prefixed filename;
6. saves the note locally, or saves raw notes to GitHub when configured; and
7. replies with the result.

For a normal LINE message, it searches existing Markdown notes by keyword and
asks OpenAI to answer using only the matched snippets.

## Architecture

```text
                            ┌─────────────────────┐
LINE message ──────────────▶│ POST /line/webhook │
                            └──────────┬──────────┘
                                       │ signature verification
                                       ▼
                                Command parser
                      ┌──────────┼─────────────┐
                      ▼          ▼             ▼
                /紀錄 URL   Non-LLM tools   Normal question
                      │      /raw /check      │
Local API ──────▶ Save service  /最近 /搜尋    ▼
POST /api/save-url     │          │       Grounded Q&A
                      ▼          │
                 Web scraper ◀────┘
               Trafilatura → BS4
                      │
                      ▼
              OpenAI → Gemini
                      │ failures
                      ▼
               Raw-note fallback
                      │
                ┌─────┴─────┐
                ▼           ▼
          Local vault     GitHub
```

## Tech stack

- Python 3.11+
- FastAPI and Uvicorn
- LINE Bot SDK v3
- OpenAI Responses API
- Gemini `generateContent` API fallback
- GitHub Contents API
- Trafilatura, Requests, and Beautiful Soup
- Pydantic
- pytest
- Obsidian-compatible Markdown files

## Project structure

```text
app/
├── main.py             # FastAPI routes
├── config.py           # Environment configuration
├── command_parser.py   # /record and /紀錄 parsing
├── save_service.py     # Shared save workflow
├── scraper.py          # Web fetching and text extraction
├── summarizer.py       # OpenAI Markdown generation
├── markdown_writer.py  # Safe vault file creation
├── raw_service.py      # Non-LLM raw-note workflow
├── github_writer.py    # GitHub Contents API writes
├── note_storage.py     # GitHub/local listing and search
├── line_bot.py         # LINE webhook processing and replies
└── rag.py              # Keyword search and grounded note Q&A

tests/                  # Unit and API tests
vault/Inbox/            # Generated Markdown notes
```

## Local setup

Create the environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add the credentials needed for the features you want to test.
Never put real credentials in `.env.example` or commit `.env`.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_NAME` | No | FastAPI project name; defaults to `chat-to-obsidian` |
| `APP_ENV` | No | Environment label |
| `HOST` | No | Local bind host |
| `PORT` | No | Local server port |
| `OPENAI_API_KEY` | Save/Q&A | OpenAI API authentication |
| `OPENAI_MODEL` | No | Model used for summaries and answers |
| `GEMINI_API_KEY` | No | Gemini fallback authentication for summaries |
| `GEMINI_MODEL` | No | Gemini fallback model |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE | Sends LINE reply messages |
| `LINE_CHANNEL_SECRET` | LINE | Verifies LINE webhook signatures |
| `GITHUB_TOKEN` | GitHub | GitHub token with repository content access |
| `GITHUB_OWNER` | GitHub | Repository owner or organization |
| `GITHUB_REPO` | GitHub | Repository name |
| `GITHUB_BRANCH` | GitHub | Target branch, usually `main` |
| `GITHUB_NOTES_DIR` | GitHub | Note directory, usually `Inbox` |
| `VAULT_PATH` | No | Vault root; defaults to `vault` |

If any credential was previously placed in a shared file, terminal output, or
chat transcript, revoke it and generate a replacement before deployment.

## Run locally

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Verify the server:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","project":"chat-to-obsidian"}
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Test the local save API

With `OPENAI_API_KEY` configured and the server running:

```bash
curl -X POST http://127.0.0.1:8000/api/save-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Successful response:

```json
{
  "success": true,
  "message": "Saved to Obsidian vault",
  "path": "vault/Inbox/YYYY-MM-DD-example-domain.md",
  "title": "Example Domain"
}
```

Confirm that the Markdown file exists:

```bash
ls -la vault/Inbox
```

If OpenAI fails, Gemini is attempted. If all configured AI providers fail
because OpenAI quota is unavailable, the save workflow creates a fallback note
containing the extracted webpage text.

## LINE commands

| Command | Description | Requires OpenAI |
| --- | --- | --- |
| `/指令` | Show all commands | No |
| `/help` | Show all commands | No |
| `/status` | Show configuration presence without revealing secrets | No |
| `/紀錄 URL` | Save with AI summary when available; raw fallback otherwise | Optional |
| `/raw URL` | Save extracted webpage content without AI | No |
| `/check URL` | Check whether the server can fetch a webpage | No |
| `/最近` | List up to five recent notes | No |
| `/搜尋 keyword` | Search notes with short matching snippets | No |

`/status` checks configuration only. It does not call OpenAI and does not prove
that billing or quota is currently available.

## Connect the LINE webhook

1. Create or open a Messaging API channel in the LINE Developers Console.
2. Put its channel access token and channel secret in the local `.env`.
3. Run this application.
4. Expose it through a public HTTPS URL using a tunnel or deployment service.
5. Set the LINE webhook URL to:

   ```text
   https://your-public-url/line/webhook
   ```

6. Enable webhooks and use the console's webhook verification.
7. Add the LINE Official Account as a friend and send:

   ```text
   /紀錄 https://example.com
   ```

Empty LINE verification requests return HTTP 200 with `{"ok":true}`. Valid
deliveries are acknowledged with HTTP 200 even if a scraper, AI, storage, or
reply operation fails, which prevents repeated webhook retries. Non-empty
requests still require a valid LINE signature; malformed payloads and invalid
signatures return HTTP 400.

## Storage behavior

`/紀錄`, `/raw`, `/最近`, and `/搜尋` select storage as follows:

1. If all five `GITHUB_*` variables are configured, use the GitHub repository.
2. Otherwise, use `VAULT_PATH/Inbox` on the local filesystem.

GitHub is recommended for Render because Render's default filesystem is
ephemeral. If you intentionally use local files on Render, attach a persistent
disk and point `VAULT_PATH` at its mount path. Render storage does not directly
write into a Vault folder on your Mac.

For this repository, the suggested Render values are:

```env
GITHUB_OWNER=wayneleehan
GITHUB_REPO=automation
GITHUB_BRANCH=main
GITHUB_NOTES_DIR=Inbox
GITHUB_TOKEN=your-fine-grained-token
```

Create the fine-grained token with access only to `wayneleehan/automation` and
grant repository **Contents: Read and write** permission. Store it only in
Render's environment variables, never in `.env.example` or Git.

## Q&A behavior

After notes exist in the vault, send a normal LINE question such as:

```text
我之前存過的 AI Agent 重點是什麼？
```

The backend:

1. recursively searches Markdown files under `VAULT_PATH`;
2. ranks matches using English keywords and Chinese character bigrams;
3. extracts short relevant snippets; and
4. asks OpenAI to answer only from those snippets.

If no note matches, it says so instead of inventing an answer.

## Tests

Run the full suite:

```bash
source .venv/bin/activate
pytest -q
```

The tests mock external OpenAI and LINE operations. The scraper also has a
separate live smoke test documented in `PROJECT_PLAN.md`.

## Demo flow without LLM quota

Recommended presentation sequence:

1. Send `/指令` to show the supported commands.
2. Send `/status` to show configuration without exposing secrets.
3. Send `/check https://example.com` to prove the scraper works.
4. Send `/raw https://example.com` to save without AI.
5. Send `/最近` to list the new note.
6. Send `/搜尋 Example` to retrieve it with a snippet.

If a public LINE webhook is unavailable during the presentation, demonstrate
the same save workflow with `POST /api/save-url`.

Optional AI portion:

1. Send `/紀錄 URL`.
2. Show OpenAI summary, Gemini fallback, or raw-note fallback.

## Limitations

- Web extraction quality varies across JavaScript-heavy, paywalled, or
  access-restricted sites.
- AI summary prefers OpenAI and falls back to Gemini; both still require
  configured keys, quota, and network access.
- Non-LLM commands continue to work without any AI key.
- Q&A uses keyword scoring, not embeddings or semantic vector search.
- There is no authentication, database, multi-user isolation, or rate limit.
- LINE webhook processing is synchronous; long article processing may approach
  webhook timeout limits.
- Local vault files are not automatically synchronized to another device.
- Render's default local disk is ephemeral; use GitHub or a persistent disk.
- Filename transliteration is intentionally conservative; titles containing no
  ASCII filename characters use `untitled`.

## Future work

- Process LINE save requests asynchronously with a job queue.
- Add semantic search with embeddings and a vector store.
- Add source-level citations and better Markdown section retrieval.
- Add authentication, multi-user vault isolation, and rate limiting.
- Support more chat platforms.
- Store notes in Git, Google Drive, S3-compatible storage, or another durable
  backend.
- Add duplicate-URL detection and update existing notes.
- Add observability, retries, and deployment health monitoring.

## Security notes

- Keep `.env` private; it is ignored by Git.
- Rotate any credential that has appeared in a shared location.
- Verify every LINE webhook signature before processing its body.
- Treat fetched webpages and note text as untrusted input.
