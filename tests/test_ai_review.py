"""Synthetic provider responses only: these tests never call a paid service."""

import base64
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import ai_review as a
from scripts import discover as d

NOW = "2026-11-25T01:23:00+00:00"
ENV = {"AI_ENDPOINT": "https://provider.example/v1/chat/completions", "AI_MODEL": "test-model", "AI_API_KEY": "synthetic-secret"}


def candidate(name="demo"):
    item = d.make_candidate(f"https://example.com/{name}", name, "工具与集成产品", "社区项目线索", d.source_record("repository-readme", "https://github.com/example/demo/blob/main/README.md", "blob", NOW, "Exploring HyperFrames for product videos."), summary="用途待核对。")
    item.update(status="pending", first_seen=NOW, last_seen=NOW, last_changed=NOW)
    return item


def suggestion(item):
    return {"id": item["id"], "relevance": "unclear", "category": "工具与集成产品", "entry": "待核对", "summary": "作者正在探索使用 HyperFrames 制作产品视频。", "reason": "来源自述仅说明正在探索，尚不能确定实际集成情况。", "reference_value": "可能参考产品视频工作流，具体实现需要查看原工程。", "checks": ["核对原作者和工程入口", "核对素材许可与使用条件"], "evidence_ids": [item["evidence"][0]["id"]]}


class Reply:
    def __init__(self, batch, transform=lambda x: x):
        payload = transform({"reviews": [suggestion(c) for c in batch]})
        self.raw = json.dumps({"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}], "usage": {"total_tokens": 123}}).encode()
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(self.raw)


class ContractTests(unittest.TestCase):
    def test_rejects_unknown_duplicate_missing_and_malformed_ids(self):
        item = candidate()
        for reviews in [[], [suggestion(item)] * 2, [{**suggestion(item), "id": "invented"}], [{**suggestion(item), "id": []}]]:
            with self.subTest(reviews=reviews), self.assertRaises(a.ReviewError):
                a.validate_reviews({"reviews": reviews}, [item])

    def test_rejects_invented_evidence_classification_and_verification(self):
        item = candidate()
        for update in [{"evidence_ids": ["invented"]}, {"category": []}, {"summary": "维护者已渲染并验证全部工程。"}, {"summary": "中文内容 https://evil.example"}, {"summary": "<script>中文内容</script>"}, {"summary": "English only description"}]:
            with self.subTest(update=update), self.assertRaises(a.ReviewError):
                a.validate_reviews({"reviews": [{**suggestion(item), **update}]}, [item])

    def test_search_hit_alone_cannot_support_actual_use(self):
        item = candidate()
        item["evidence"][0]["id"] = "github-search:hyperframes"
        value = {**suggestion(item), "relevance": "supported"}
        with self.assertRaises(a.ReviewError):
            a.validate_reviews({"reviews": [value]}, [item])

    def test_extra_model_fields_cannot_change_manual_status(self):
        item = candidate()
        value = {**suggestion(item), "status": "accepted", "url": "https://evil.example"}
        result = a.validate_reviews({"reviews": [value]}, [item])[item["id"]]
        self.assertNotIn("status", result)
        self.assertNotIn("url", result)

    def test_request_uses_existing_contract_without_credentials_in_prompt(self):
        item = candidate()
        item["private_data"] = "not-public"
        provider = a.Provider(ENV)
        reply = Reply([item])
        provider.opener = reply
        result = provider.request([item])
        request = reply.requests[0]
        body = json.loads(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-secret")
        self.assertEqual(body["model"], "test-model")
        self.assertNotIn("synthetic-secret", json.dumps(body))
        self.assertNotIn("not-public", json.dumps(body))
        self.assertIn(item["id"], result)
        self.assertEqual(provider.usage["total_tokens"], 123)
        self.assertEqual(provider.calls, 1)

    def test_budgets_are_checked_before_network_including_retries(self):
        item = candidate()
        provider = a.Provider({**ENV, "AI_MAX_CALLS": "1"})
        reply = Reply([item])
        provider.opener = reply
        provider.request([item])
        with self.assertRaises(a.ReviewError):
            provider.request([item])
        self.assertEqual(len(reply.requests), 1)
        provider = a.Provider({**ENV, "AI_MAX_TOTAL_TOKENS": "1000"})
        provider.opener = reply
        with self.assertRaises(a.ReviewError):
            provider.request([item])
        self.assertEqual(provider.calls, 0)

    def test_thinking_parameter_is_explicit_and_optional_for_generic_providers(self):
        item = candidate()
        for setting, expected in [(None, None), ("auto", None), ("false", False), ("true", True)]:
            env = {**ENV, **({"AI_ENABLE_THINKING": setting} if setting else {})}
            provider = a.Provider(env)
            reply = Reply([item])
            provider.opener = reply
            provider.request([item])
            body = json.loads(reply.requests[0].data)
            if expected is None:
                self.assertNotIn("enable_thinking", body)
            else:
                self.assertIs(body["enable_thinking"], expected)
        with self.assertRaises(a.ReviewError):
            a.Provider({**ENV, "AI_ENABLE_THINKING": "unrecognized"})

    def test_reasoning_only_and_truncated_responses_keep_usage_without_reasoning_text(self):
        item = candidate()
        for finish, text in [("length", ""), ("stop", ""), ("length", json.dumps({"reviews": [suggestion(item)]}))]:
            provider = a.Provider(ENV)
            raw = json.dumps({"choices": [{"finish_reason": finish, "message": {"content": text, "reasoning_content": "PRIVATE REASONING"}}], "usage": {"prompt_tokens": 100, "completion_tokens": 4000, "total_tokens": 4100, "completion_tokens_details": {"reasoning_tokens": 4000}}}).encode()
            with patch.object(provider.opener, "open", return_value=io.BytesIO(raw)), self.assertRaises(a.ReviewError):
                provider.request([item])
            self.assertEqual(provider.usage["reasoning_tokens"], 4000)
            self.assertEqual(provider.usage["total_tokens"], 4100)
            self.assertTrue(provider.responses[0]["has_reasoning"])
            self.assertNotIn("PRIVATE REASONING", json.dumps(provider.responses))

    def test_invalid_json_response_still_counts_reported_usage(self):
        provider = a.Provider(ENV)
        raw = json.dumps({"choices": [{"message": {"content": "not-json"}}], "usage": {"total_tokens": 500}}).encode()
        with patch.object(provider.opener, "open", return_value=io.BytesIO(raw)), self.assertRaises(a.ReviewError):
            provider.request([candidate()])
        self.assertEqual(provider.usage["total_tokens"], 500)

    def test_http_errors_are_redacted_and_redirects_refused(self):
        provider = a.Provider(ENV)
        with patch.object(provider.opener, "open", side_effect=HTTPError(ENV["AI_ENDPOINT"], 401, "synthetic-secret", {}, io.BytesIO(b"synthetic-secret"))):
            with self.assertRaises(a.ReviewError) as raised:
                provider.request([candidate()])
        self.assertEqual(str(raised.exception), "AI 请求失败（HTTP 401）")
        self.assertFalse(raised.exception.retryable)
        with self.assertRaises(a.ReviewError):
            a.NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.example")

    def test_invalid_response_is_a_controlled_error(self):
        for raw in [b"not-json", b"[]", b'{"choices":null}', b'{"choices":[{"message":{"content":"[]"}}]}']:
            provider = a.Provider(ENV)
            with patch.object(provider.opener, "open", return_value=io.BytesIO(raw)), self.assertRaises(a.ReviewError):
                provider.request([candidate()])


class PipelineTests(unittest.TestCase):
    def test_removed_readme_mention_invalidates_previous_ai_evidence(self):
        item = candidate()
        item["evidence"].append(d.source_record("github-search:query", "https://github.com/search?q=hyperframes", None, NOW, "搜索线索"))
        item["repository"] = "example/demo"
        state = self.state(item)
        self.run_review(state)
        response = {"encoding": "base64", "content": base64.b64encode(b"No association anymore").decode(), "html_url": "https://github.com/example/demo/blob/main/README.md", "sha": "new-blob"}
        api = unittest.mock.Mock()
        api.call.return_value = response
        d.enrich(api, item, NOW)
        self.assertFalse(any(e["id"] == "repository-readme" for e in item["evidence"]))
        self.assertIsNone(a.current_review(item))

    def state(self, *items):
        state = d.empty_state()
        state["candidates"] = {item["id"]: item for item in items}
        state["last_run"] = {"at": NOW, "problems": []}
        return state

    def run_review(self, state, env=None, **kwargs):
        def factory(settings):
            provider = a.Provider(settings)
            provider.opener = Reply(list(state["candidates"].values()))
            return provider
        return a.review_candidates(state, {}, NOW, env or ENV, provider_factory=factory, **kwargs)

    def test_cache_skips_unchanged_sources_but_not_new_text_or_model(self):
        item = candidate()
        state = self.state(item)
        self.assertEqual(self.run_review(state)["reviewed"], 1)
        item["evidence"][0].update(blob_sha="unrelated-commit", observed_at="2026-11-26")
        self.assertEqual(self.run_review(state)["cache_hits"], 1)
        item["evidence"][0]["detail"] += " Now using HyperFrames."
        self.assertIsNone(a.current_review(item))
        self.assertEqual(self.run_review(state)["reviewed"], 1)
        self.assertEqual(self.run_review(state, {**ENV, "AI_MODEL": "new-model"})["reviewed"], 1)

    def test_thinking_option_changes_invalidate_cache(self):
        state = self.state(candidate())
        self.run_review(state)
        env = {**ENV, "AI_ENABLE_THINKING": "false"}
        self.assertEqual(self.run_review(state, env)["reviewed"], 1)
        self.assertEqual(self.run_review(state, env)["cache_hits"], 1)

    def test_off_missing_and_manual_decisions_never_call_provider(self):
        state = self.state(candidate())
        with patch.object(a, "Provider", side_effect=AssertionError("must not call")):
            self.assertEqual(a.review_candidates(state, {}, NOW, ENV, "off")["status"], "disabled")
            self.assertEqual(a.review_candidates(state, {}, NOW, {})["status"], "not_configured")
            self.assertEqual(a.review_candidates(state, {}, NOW, {}, "required")["status"], "failed")
        item = next(iter(state["candidates"].values()))
        item["status"] = "accepted"
        result = self.run_review(state)
        self.assertEqual(result["calls"], 0)
        self.assertNotIn("ai_review", item)

    def test_ai_does_not_refresh_source_or_approve_and_stale_text_is_hidden(self):
        item = candidate()
        before = d.fingerprint(item)
        state = self.state(item)
        self.run_review(state)
        self.assertEqual(d.fingerprint(item), before)
        self.assertEqual(item["status"], "pending")
        config = d.read_json(d.ROOT / "discovery/config.json")
        _, body, _ = d.render_digest(state, config, NOW, "example/catalog")
        self.assertIn("AI 辅助建议（未经人工核实", body)
        item["evidence"][0]["detail"] += " changed"
        _, body, _ = d.render_digest(state, config, NOW, "example/catalog")
        self.assertNotIn("AI 简介：", body)
        self.assertIn("来源变化失效", body)

    def test_retry_is_bounded_and_failure_preserves_candidate(self):
        item = candidate()
        state = self.state(item)
        provider = a.Provider(ENV)
        with patch.object(provider.opener, "open", side_effect=TimeoutError), patch.object(a.time, "sleep") as sleeper:
            result = a.review_candidates(state, {}, NOW, ENV, provider_factory=lambda env: provider, sleep=sleeper)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["calls"], 2)
        self.assertEqual(sleeper.call_count, 1)
        self.assertNotIn("ai_review", item)
        self.assertEqual(item["status"], "pending")

    def test_truncated_http_response_retries_and_preserves_rule_preview(self):
        item = candidate()
        provider = a.Provider(ENV)
        state = self.state(item)
        with patch.object(provider.opener, "open") as opener:
            opener.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b"untrusted provider body", 10)
            report = a.review_candidates(state, {}, NOW, ENV, provider_factory=lambda env: provider, sleep=lambda seconds: None)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["calls"], 2)
        self.assertNotIn("untrusted provider body", json.dumps(report))
        self.assertNotIn("ai_review", item)
        self.assertEqual(item["status"], "pending")
        config = d.read_json(d.ROOT / "discovery/config.json")
        _, body, selected = d.render_digest(state, config, NOW, "example/catalog")
        self.assertEqual(selected, [item["id"]])
        self.assertIn("调用或配置失败", body)

    def test_cli_failure_still_saves_preview_and_replay_is_always_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state.json").write_text(json.dumps(self.state(candidate())), encoding="utf-8")
            args = ["--mode", "digest", "--state", str(root / "state.json"), "--output", str(root), "--ai", "required"]
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(d.main(args), 1)
            self.assertTrue((root / "weekly-review.md").exists())
            (root / "replay.json").write_text("{}", encoding="utf-8")
            with patch.dict("os.environ", ENV), patch.object(a.Provider, "request", side_effect=AssertionError("must stay offline")):
                self.assertEqual(d.main(args + ["--replay", str(root / "replay.json")]), 0)
            self.assertEqual(d.read_json(root / "state.json")["last_ai_run"]["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
