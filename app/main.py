"""FastAPI application entry point."""

from functools import partial

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from pydantic import BaseModel, HttpUrl

from app.config import settings
from app.line_bot import process_line_webhook
from app.rag import answer_question_from_vault
from app.save_service import save_url_to_vault


app = FastAPI(title=settings.app_name)


class SaveURLRequest(BaseModel):
    """Request body for saving a webpage to the vault."""

    url: HttpUrl


class SaveURLResponse(BaseModel):
    """Successful webpage-save response."""

    success: bool
    message: str
    path: str
    title: str


@app.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight application health check."""

    return {"status": "ok", "project": settings.app_name}


@app.post("/api/save-url", response_model=SaveURLResponse)
def save_url(request: SaveURLRequest) -> SaveURLResponse:
    """Fetch, summarize, and save a webpage as an Obsidian note."""

    result = save_url_to_vault(str(request.url), settings.vault_path)
    if not result["success"]:
        status_code = (
            500
            if result["message"] == "Could not save Markdown note"
            else 502
        )
        raise HTTPException(
            status_code=status_code,
            detail=f"{result['message']}: {result['error']}",
        )

    return SaveURLResponse(
        success=True,
        message=result["message"],
        path=result["path"],
        title=result["title"],
    )


@app.post("/line/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(alias="X-Line-Signature"),
) -> dict[str, int | str]:
    """Receive verified LINE webhook events and reply to text messages."""

    if (
        not settings.line_channel_secret
        or not settings.line_channel_access_token
    ):
        raise HTTPException(
            status_code=503,
            detail="LINE credentials are not configured.",
        )

    body = (await request.body()).decode("utf-8")
    save_handler = partial(
        save_url_to_vault,
        vault_path=settings.vault_path,
    )
    question_handler = lambda question: answer_question_from_vault(
        question,
        settings.vault_path,
    )["answer"]

    try:
        replies = process_line_webhook(
            body,
            x_line_signature,
            settings.line_channel_secret,
            settings.line_channel_access_token,
            save_handler,
            question_handler,
        )
    except InvalidSignatureError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid LINE webhook signature.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LINE webhook processing failed: {exc}",
        ) from exc

    return {"status": "ok", "replies": replies}
