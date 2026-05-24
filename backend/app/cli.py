from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.agent import JobSearchAgent
from app.config import default_applicant_profile, default_candidate_profile, get_settings
from app.db import initialize_database
from app.hh_browser import HHWebApplyRunner, row_to_apply_draft
from app.hh_client import HHClient
from app.hh_public import HHPublicSearchClient
from app.repository import CRMRepository
from app.responses import ResponseContext, generate_cover_letter
from app.review_export import render_markdown_review_queue
from app.scoring import Vacancy, score_vacancy


def _repo() -> CRMRepository:
    settings = get_settings()
    initialize_database(settings.db_path)
    return CRMRepository(settings.db_path)


def cmd_init_db(_: argparse.Namespace) -> None:
    settings = get_settings()
    initialize_database(settings.db_path)
    print(json.dumps({"ok": True, "db_path": str(settings.db_path)}, ensure_ascii=False))


def cmd_seed_demo(_: argparse.Namespace) -> None:
    repo = _repo()
    candidate = default_candidate_profile(repo.get_learning_weights())
    applicant = default_applicant_profile()
    samples = [
        Vacancy(
            external_id="demo-hh-1",
            title="Full-stack developer для AI CRM",
            company="Demo Product",
            description="Удалённо, долгосрочный контракт. React, Python, FastAPI, Telegram, CRM, dashboard.",
            url="https://hh.ru/vacancy/demo-1",
            salary_from=220000,
            salary_to=320000,
            currency="RUR",
            schedule="remote",
            employment="part",
            skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
        ),
        Vacancy(
            external_id="demo-hh-2",
            title="Backend Python integrations engineer",
            company="OpsCloud",
            description="API integrations, automation, PostgreSQL. Можно удалённо.",
            url="https://hh.ru/vacancy/demo-2",
            salary_from=180000,
            salary_to=240000,
            currency="RUR",
            schedule="remote",
            employment="full",
            skills=["Python", "API", "PostgreSQL"],
        ),
    ]
    created = 0
    for vacancy in samples:
        score = score_vacancy(vacancy, candidate)
        vacancy_id = repo.upsert_vacancy(vacancy, score)
        response = generate_cover_letter(ResponseContext(profile=applicant, vacancy=vacancy, score=score.score))
        repo.create_or_update_application(vacancy_id, cover_letter=response.message, status="draft", score_at_apply=score.score)
        created += 1
    print(json.dumps({"seeded": created, "summary": repo.dashboard_summary()}, ensure_ascii=False))


def _default_queries() -> list[str]:
    return ["React Python CRM", "Telegram bot Python", "AI automation developer"]


def cmd_run_once(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    queries = args.query or _default_queries()
    agent = JobSearchAgent(
        repo=repo,
        hh_client=HHClient(user_agent=settings.hh_user_agent, access_token=settings.hh_access_token),
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    result = agent.run_once(queries=queries, per_query=args.per_query, draft_threshold=args.draft_threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_run_public_once(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    queries = args.query or _default_queries()
    agent = JobSearchAgent(
        repo=repo,
        hh_client=HHPublicSearchClient(user_agent=settings.hh_user_agent),
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    result = agent.run_once(queries=queries, per_query=args.per_query, draft_threshold=args.draft_threshold)
    if args.export_review_queue:
        output_path = Path(args.export_review_queue)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_markdown_review_queue(
                repo.review_queue(
                    min_score=args.draft_threshold,
                    limit=args.review_limit,
                    include_demo=args.include_demo,
                )
            ),
            encoding="utf-8",
        )
        result["review_queue_path"] = str(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_export_review_queue(args: argparse.Namespace) -> None:
    repo = _repo()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = repo.review_queue(min_score=args.min_score, limit=args.limit, include_demo=args.include_demo)
    output_path.write_text(render_markdown_review_queue(rows), encoding="utf-8")
    print(json.dumps({"exported": len(rows), "output": str(output_path)}, ensure_ascii=False))


def _keep_browser_open_for_review(enabled: bool, results: list) -> None:
    if not enabled or not results:
        return
    try:
        input("HH browser is open for manual review. Press Enter here to close it…")
    except EOFError:
        return


def cmd_apply_browser_queue(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    rows = repo.review_queue(min_score=args.min_score, limit=args.limit, include_demo=args.include_demo)
    drafts = [row_to_apply_draft(row) for row in rows]
    user_data_dir = args.user_data_dir or settings.hh_browser_user_data_dir
    runner = HHWebApplyRunner.launch(user_data_dir=user_data_dir, headless=args.headless)
    try:
        results = runner.run(drafts, send=args.send)
        _keep_browser_open_for_review(args.keep_open, results)
    finally:
        runner.close()

    sent = 0
    prepared = 0
    blocked = 0
    for result in results:
        if result.status == "sent" and args.send:
            sent += 1
            repo.record_feedback(
                vacancy_id=result.vacancy_id,
                application_id=result.application_id,
                event_type="sent",
                notes="Sent via no-API HH browser runner",
            )
        elif result.status == "prepared":
            prepared += 1
        else:
            blocked += 1

    print(
        json.dumps(
            {
                "queued": len(drafts),
                "prepared": prepared,
                "sent": sent,
                "blocked": blocked,
                "send_enabled": bool(args.send),
                "statuses": [result.status for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_summary(_: argparse.Namespace) -> None:
    repo = _repo()
    print(json.dumps(repo.dashboard_summary(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HH CRM Agent CLI")
    sub = parser.add_subparsers(required=True)

    init_db = sub.add_parser("init-db", help="Initialize SQLite CRM database")
    init_db.set_defaults(func=cmd_init_db)

    seed_demo = sub.add_parser("seed-demo", help="Create demo CRM data and drafts")
    seed_demo.set_defaults(func=cmd_seed_demo)

    run_once = sub.add_parser("run-once", help="Search HH API, score vacancies, create drafts")
    run_once.add_argument("--query", action="append", help="HH search query; can be repeated")
    run_once.add_argument("--per-query", type=int, default=20)
    run_once.add_argument("--draft-threshold", type=int, default=80)
    run_once.set_defaults(func=cmd_run_once)

    run_public_once = sub.add_parser(
        "run-public-once",
        help="No-API mode: parse public HH search pages, score vacancies, create drafts",
    )
    run_public_once.add_argument("--query", action="append", help="HH search query; can be repeated")
    run_public_once.add_argument("--per-query", type=int, default=20)
    run_public_once.add_argument("--draft-threshold", type=int, default=80)
    run_public_once.add_argument(
        "--export-review-queue",
        default="./data/review_queue.md",
        help="Write a markdown queue with vacancy links, response links, and drafts; empty string disables",
    )
    run_public_once.add_argument("--review-limit", type=int, default=20)
    run_public_once.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts in the exported review queue",
    )
    run_public_once.set_defaults(func=cmd_run_public_once)

    export_review = sub.add_parser(
        "export-review-queue",
        help="Export current draft queue to markdown with no-API HH response links",
    )
    export_review.add_argument("--output", default="./data/review_queue.md")
    export_review.add_argument("--min-score", type=int, default=80)
    export_review.add_argument("--limit", type=int, default=20)
    export_review.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts; disabled by default for real HH review queues",
    )
    export_review.set_defaults(func=cmd_export_review_queue)

    apply_browser = sub.add_parser(
        "apply-browser-queue",
        help="No-API browser mode: open HH apply links and fill cover letters from CRM drafts",
    )
    apply_browser.add_argument("--min-score", type=int, default=80)
    apply_browser.add_argument("--limit", type=int, default=5)
    apply_browser.add_argument("--user-data-dir", default=None)
    apply_browser.add_argument("--headless", action="store_true")
    apply_browser.add_argument(
        "--keep-open",
        action="store_true",
        help="After inserting drafts, keep the browser open until Enter is pressed for manual review",
    )
    apply_browser.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts; disabled by default for real HH browser applications",
    )
    apply_browser.add_argument(
        "--send",
        action="store_true",
        help="Actually click HH submit buttons. Without this flag drafts are only inserted.",
    )
    apply_browser.set_defaults(func=cmd_apply_browser_queue)

    summary = sub.add_parser("summary", help="Print dashboard summary")
    summary.set_defaults(func=cmd_summary)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
