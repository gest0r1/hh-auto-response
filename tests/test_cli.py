from app.cli import build_parser


def test_cli_has_no_api_public_search_command():
    args = build_parser().parse_args(["run-public-once", "--query", "React Python", "--per-query", "7"])

    assert args.query == ["React Python"]
    assert args.per_query == 7
    assert callable(args.func)


def test_cli_has_review_queue_export_command(tmp_path):
    output = tmp_path / "queue.md"
    args = build_parser().parse_args(
        ["export-review-queue", "--output", str(output), "--min-score", "75", "--include-demo"]
    )

    assert args.output == str(output)
    assert args.min_score == 75
    assert args.include_demo is True
    assert callable(args.func)


def test_cli_has_browser_apply_queue_command():
    args = build_parser().parse_args(
        [
            "apply-browser-queue",
            "--min-score",
            "80",
            "--limit",
            "3",
            "--user-data-dir",
            "./data/hh-browser-profile",
            "--include-demo",
            "--keep-open",
            "--send",
        ]
    )

    assert args.min_score == 80
    assert args.limit == 3
    assert args.user_data_dir == "./data/hh-browser-profile"
    assert args.include_demo is True
    assert args.keep_open is True
    assert args.send is True
    assert callable(args.func)
