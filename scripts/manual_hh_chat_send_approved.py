#!/usr/bin/env python3
"""Send owner-approved HH chat replies from a local JSON plan.

This script is intentionally data-free in git: the approval plan lives in a local
file passed via HH_CHAT_MANUAL_APPROVED_JSON so chat ids, recruiter text, and
approved replies are not committed.

Plan schema:
{
  "items": [
    {
      "key": "human-readable-id",
      "chat_id": "541...",
      "title": "Expected title fragment",
      "url": "https://hh.ru/chat/...",
      "expected_phrases": ["phrase that must be present before send"],
      "reply": "Exact owner-approved reply"
    }
  ]
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import default_applicant_profile
from app.hh_chat import (
    HHChatPreview,
    HHChatReplyState,
    HHChatRunner,
    extract_latest_question_from_messages,
    format_chat_context,
    normalize_text,
)

STATE_FILE = Path(os.environ.get("HH_CHAT_REPLY_STATE_FILE", "./data/hh_chat_reply_state.json"))
USER_DATA_DIR = Path(os.environ.get("HH_BROWSER_USER_DATA_DIR", "./data/hh-browser-profile"))
HEADLESS = os.environ.get("HH_CHAT_REPLY_HEADLESS", "1") == "1"
APPROVAL_JSON = os.environ.get("HH_CHAT_MANUAL_APPROVED_JSON", "").strip()


def load_approved_items() -> list[dict[str, Any]]:
    if not APPROVAL_JSON:
        raise SystemExit("Set HH_CHAT_MANUAL_APPROVED_JSON to a local approval JSON file")
    path = Path(APPROVAL_JSON)
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise SystemExit("Approval JSON must be a list or an object with items[]")
    required = {"key", "chat_id", "url", "expected_phrases", "reply"}
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise SystemExit(f"Approval item #{idx} is not an object")
        missing = sorted(required - set(item))
        if missing:
            raise SystemExit(f"Approval item #{idx} missing required fields: {', '.join(missing)}")
        if not str(item.get("reply") or "").strip():
            raise SystemExit(f"Approval item #{idx} has empty reply")
    return items


def last_messages_preview(messages: list[dict[str, Any]], n: int = 6) -> list[dict[str, Any]]:
    out = []
    for item in messages[-n:]:
        text = normalize_text(str(item.get("text", "")))
        if len(text) > 260:
            text = text[:260] + "…"
        out.append({"mine": bool(item.get("isMine")), "text": text})
    return out


def main() -> int:
    profile = default_applicant_profile()
    state = HHChatReplyState(STATE_FILE)
    runner = HHChatRunner.launch(
        profile=profile,
        state=state,
        user_data_dir=USER_DATA_DIR,
        headless=HEADLESS,
    )
    results: list[dict[str, Any]] = []
    try:
        for item in load_approved_items():
            preview = HHChatPreview(
                chat_id=str(item["chat_id"]),
                url=str(item["url"]),
                title=str(item.get("title") or "HH chat"),
                preview="",
            )
            runner.page.goto(preview.url, wait_until="domcontentloaded")
            runner._safe_wait("domcontentloaded")
            runner._safe_wait("networkidle")
            runner._safe_pause(900)

            if runner._login_required():
                raise RuntimeError(f"{item['key']}: HH login is required")

            messages = runner._read_chat_messages()
            question = extract_latest_question_from_messages(messages, "") or normalize_text(runner._body_text())
            _ = format_chat_context(messages)  # keep parsing exercised for future hook points
            qnorm = normalize_text(question)
            body_norm = normalize_text(runner._body_text())

            expected = [str(phrase) for phrase in item.get("expected_phrases", [])]
            missing = [
                phrase
                for phrase in expected
                if normalize_text(phrase) not in qnorm and normalize_text(phrase) not in body_norm
            ]
            if missing:
                results.append(
                    {
                        "key": item["key"],
                        "chat_id": item["chat_id"],
                        "status": "blocked_expected_phrase_missing",
                        "missing": missing,
                        "latest_question": qnorm[:1000],
                        "last_messages": last_messages_preview(messages),
                    }
                )
                continue

            if state.was_answered(str(item["chat_id"]), question):
                results.append(
                    {
                        "key": item["key"],
                        "chat_id": item["chat_id"],
                        "status": "skipped_duplicate_state",
                        "latest_question": qnorm[:1000],
                        "last_messages": last_messages_preview(messages),
                    }
                )
                continue

            reply = str(item["reply"])
            status, detail = runner._send_plain_chat_reply(reply)
            verified = runner._message_sent_confirmed(reply)
            final_status = status if verified else (status + "_not_confirmed")
            if status in {"sent", "sent_unverified"}:
                state.mark_answered(
                    chat_id=str(item["chat_id"]),
                    question=question,
                    reply=reply,
                    status=f"manual_approved_{final_status}",
                )
            runner._safe_pause(700)
            after_messages = runner._read_chat_messages()
            results.append(
                {
                    "key": item["key"],
                    "chat_id": item["chat_id"],
                    "status": f"manual_approved_{final_status}",
                    "detail": detail,
                    "verified": verified,
                    "latest_question": qnorm[:1000],
                    "reply_len": len(reply),
                    "last_messages_after": last_messages_preview(after_messages),
                }
            )
    finally:
        runner.close()

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    bad = [r for r in results if not str(r.get("status", "")).startswith("manual_approved_sent")]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
