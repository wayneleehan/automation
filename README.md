# Chat-to-Obsidian AI Second Brain

A FastAPI backend that turns links sent through LINE or a local API into
structured, Obsidian-compatible Markdown notes. It can also answer simple
questions by searching the saved notes.

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
4. asks OpenAI to produce concise Traditional Chinese Markdown;
5. generates a safe, date-prefixed filename;
6. saves the note in `vault/Inbox/`; and
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
                                 │           │
                    /紀錄 [URL]  │           │ normal question
                                 ▼           ▼
Local API ───────────────▶ Save service   Keyword note search
POST /api/save-url              │           │
                                ▼           ▼
                         Web scraper     Grounded LLM answer
                    Trafilatura → BS4        │
                                │             └──▶ LINE reply
                                ▼
                         OpenAI summarizer
                                │
                                ▼
                         Markdown writer
                                │
                                ▼
                         vault/Inbox/*.md
```

## Tech stack

- Python 3.11+
- FastAPI and Uvicorn
- LINE Bot SDK v3
- OpenAI Responses API
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
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE | Sends LINE reply messages |
| `LINE_CHANNEL_SECRET` | LINE | Verifies LINE webhook signatures |
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

If the API key is missing, the endpoint returns a controlled HTTP 502 error
and does not create a partial note.

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

The webhook rejects missing credentials with HTTP 503 and invalid LINE
signatures with HTTP 400. Do not disable signature verification.

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

## Demo flow

Recommended presentation sequence:

1. Show an empty or known `vault/Inbox/` folder.
2. Start FastAPI and show the successful `/health` response.
3. Send `/紀錄 https://example.com` through LINE.
4. Show the LINE success reply.
5. Open the generated Markdown note in Obsidian and point out:
   - YAML frontmatter;
   - Traditional Chinese summary;
   - key points and related concepts; and
   - source URL.
6. Ask a normal LINE question about the saved note.
7. Show the answer grounded in the vault content.

If a public LINE webhook is unavailable during the presentation, demonstrate
the same save workflow with `POST /api/save-url`.

## Limitations

- Web extraction quality varies across JavaScript-heavy, paywalled, or
  access-restricted sites.
- Summary and Q&A require an available OpenAI API key and network access.
- Q&A uses keyword scoring, not embeddings or semantic vector search.
- There is no authentication, database, multi-user isolation, or rate limit.
- LINE webhook processing is synchronous; long article processing may approach
  webhook timeout limits.
- Local vault files are not automatically synchronized to another device.
- Local disk may be ephemeral on some hosting platforms.
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
