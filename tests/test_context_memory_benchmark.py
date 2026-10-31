from tools.benchmark_context_memory import measure


def test_offline_benchmark_measures_requests_without_claiming_billed_tokens(tmp_path):
    report = measure(tmp_path / "benchmark")
    assert report["paid_calls"] == 0
    assert report["adapter"] == "FakeModelAdapter"
    assert report["tokenizer"] is None and not report["billed_token_savings_measured"]
    for case in report["cases"][:3]:
        baseline = case["arms"]["bounded_baseline"]
        lexical = case["arms"]["lexical_only"]
        associative = case["arms"]["associative"]
        assert associative["required_file_recall"] == 1
        assert associative["required_file_recall"] > lexical["required_file_recall"]
        assert associative["message_utf8_bytes"] < baseline["message_utf8_bytes"]
        assert (
            associative["conservative_reservation_units"]
            == associative["request_utf8_bytes"] + 1024
        )
    unmatched = report["cases"][-1]
    assert unmatched["arms"]["associative"]["message_byte_reduction"] == 0
