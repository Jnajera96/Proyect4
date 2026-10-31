from tools.benchmark_context_memory import measure


def test_fts_history_reaches_multilanguage_requests_without_contamination(tmp_path):
    from tools.benchmark_context_memory import measure_history

    cases = measure_history(tmp_path / "history")
    assert {case["language"] for case in cases} == {"python", "javascript", "typescript", "sql"}
    for case in cases:
        assert case["unmatched_history_hits"] == 0
        cold, warm = (case["arms"][key] for key in ("without_history", "with_history"))
        assert not cold["lesson_received"] and cold["history_chars"] == 0
        assert warm["lesson_received"] and 0 < warm["history_chars"] <= 800
        assert warm["message_utf8_bytes"] > cold["message_utf8_bytes"]
        for arm in (cold, warm):
            assert arm["code_received"] and arm["secret_absent"]
            assert arm["isolation_preserved"] and arm["history_block_intact"]


def test_offline_benchmark_measures_requests_without_claiming_billed_tokens(tmp_path):
    report = measure(tmp_path / "benchmark")
    assert report["paid_calls"] == 0
    assert report["adapter"] == "FakeModelAdapter"
    assert report["tokenizer"] is None and not report["billed_token_savings_measured"]
    for case in report["cases"]:
        baseline = case["arms"]["bounded_baseline"]
        lexical = case["arms"]["content_only"]
        associative = case["arms"]["associative"]
        assert associative["required_file_recall"] == 1
        assert associative["required_file_recall"] >= lexical["required_file_recall"]
        assert associative["message_utf8_bytes"] < baseline["message_utf8_bytes"]
        assert (
            associative["conservative_reservation_units"]
            == associative["request_utf8_bytes"] + 1024
        )
    for case in report["cases"][3:]:
        assert (
            0
            < case["arms"]["content_only"]["required_file_recall"]
            < case["arms"]["associative"]["required_file_recall"]
        )
        assert case["arms"]["content_only"]["code_body_received"]
        assert case["arms"]["associative"]["code_body_received"]
