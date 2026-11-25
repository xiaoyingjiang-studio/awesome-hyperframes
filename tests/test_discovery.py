"""Behavior tests with synthetic public-source fixtures; no network or credentials."""

import base64
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts import discover as d

NOW = "2026-11-25T01:23:00+00:00"
NEXT = "2026-11-26T01:23:00+00:00"
REPO = "sample/catalog"


def content(text, url="https://github.com/sample/source/blob/main/README.md"):
    return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode(), "html_url": url, "sha": "source-blob"}


def candidate(url="https://example.com/product", title="Example"):
    return d.make_candidate(url, title, "工具与集成产品", "官方使用者名单线索", d.source_record("fixture", "https://github.com/sample/source/blob/main/README.md", "blob", NOW, "Exploring HyperFrames"), summary="用途待核对。")


def repo_item(name="sample/project", repo_id=123):
    return {"id": repo_id, "full_name": name, "html_url": f"https://github.com/{name}", "owner": {"login": name.split('/')[0]}, "description": "HyperFrames demo", "license": {"spdx_id": "MIT"}, "private": False, "fork": False, "archived": False}


def config():
    result = d.read_json(d.ROOT / "discovery/config.json")
    result.update(sources=[], search_queries=["hyperframes is:public"], search_pages=1, search_page_size=2, enrich_per_run=0)
    return result


class FakeApi:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def call(self, path, method="GET", data=None):
        self.calls.append((path, method, data))
        return self.handler(path, method, data)


class IdentityTests(unittest.TestCase):
    def test_url_normalization_preserves_case_sensitive_paths_and_queries(self):
        self.assertEqual(d.canonical_url("http://GitHub.com/Owner/Repo.git/"), "https://github.com/owner/repo")
        self.assertEqual(d.canonical_url("https://github.com/Owner/Repo/tree/main/CaseStudy"), "https://github.com/owner/repo/tree/main/CaseStudy")
        self.assertEqual(d.canonical_url("https://example.com/p?id=2&utm_source=x#anchor"), "https://example.com/p?id=2")
        self.assertIn("q=hyperframes", d.canonical_url("https://github.com/search?q=hyperframes&type=repositories"))
        self.assertIsNone(d.canonical_url("javascript:alert(1)"))
        self.assertIsNone(d.canonical_url("https://user:password@example.com"))

    def test_repository_rename_keeps_review_identity(self):
        state = d.empty_state()
        original = d.repository_candidate(repo_item(), "fixture", NOW)
        d.upsert(state, original, NOW)
        key = original["id"]
        state["candidates"][key]["status"] = "rejected"
        renamed = d.repository_candidate(repo_item("sample/renamed"), "fixture", NEXT)
        d.upsert(state, renamed, NEXT)
        self.assertEqual(len(state["candidates"]), 1)
        self.assertEqual(state["candidates"][key]["id"], key)
        self.assertEqual(state["candidates"][key]["status"], "rejected")
        self.assertEqual(state["candidates"][key]["url"], "https://github.com/sample/renamed")

    def test_unrelated_source_commit_does_not_refresh_change_date(self):
        state = d.empty_state()
        original = candidate()
        d.upsert(state, original, NOW)
        refreshed = candidate()
        refreshed["evidence"][0].update(blob_sha="unrelated-edit", observed_at=NEXT)
        d.upsert(state, refreshed, NEXT)
        result = state["candidates"][original["id"]]
        self.assertEqual(result["last_changed"], NOW)
        self.assertEqual(result["last_seen"], NEXT)

    def test_project_subdirectories_remain_distinct(self):
        state = d.empty_state()
        for name in ("one", "two"):
            d.upsert(state, candidate(f"https://github.com/sample/videos/tree/main/{name}"), NOW)
        self.assertEqual(len(state["candidates"]), 2)


class ParserTests(unittest.TestCase):
    def test_adopters_preserve_exploration_claim_without_contact_data(self):
        source = {"id": "adopters", "kind": "adopters"}
        text = "| Organization | Contact | Usage |\n| --- | --- | --- |\n| [Sample](https://example.com/) | private@example.com | Exploring HyperFrames for demos. |"
        result = d.parse_source(source, text, "https://github.com/sample/source/blob/main/ADOPTERS.md", "sha", NOW)
        self.assertEqual(len(result), 1)
        self.assertIn("Exploring", result[0]["author_claim"])
        self.assertNotIn("private@example", json.dumps(result))
        self.assertEqual(result[0]["entry"], "待核对")

    def test_registry_types_and_source_tree(self):
        source = {"id": "registry", "kind": "registry", "types": ["hyperframes:example"]}
        text = json.dumps({"items": [{"name": "demo", "type": "hyperframes:example"}, {"name": "chart", "type": "hyperframes:block"}]})
        result = d.parse_source(source, text, "https://github.com/sample/source/blob/main/registry/registry.json", "sha", NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://github.com/sample/source/tree/main/registry/examples/demo")
        self.assertNotIn("preview", result[0])

    def test_launch_relative_project_and_media_links(self):
        result = d.parse_source({"id": "launches", "kind": "launches"}, "| Film | [code](./MyFilm/) | [Watch](./MyFilm/Film.mp4) |", "https://github.com/sample/launches/blob/main/README.md", "sha", NOW)
        self.assertEqual(result[0]["source_code"], "https://github.com/sample/launches/tree/main/MyFilm")
        self.assertEqual(result[0]["preview"], "https://github.com/sample/launches/blob/main/MyFilm/Film.mp4")

    def test_changed_upstream_format_is_error_not_empty_success(self):
        with self.assertRaisesRegex(ValueError, "no candidates"):
            d.parse_source({"id": "adopters", "kind": "adopters"}, "No table any more", "https://github.com/sample/source/blob/main/README.md", "sha", NOW)


class CollectionTests(unittest.TestCase):
    def test_page_budget_resumes_and_checkpoint_uses_scan_start(self):
        state = d.empty_state()
        conf = config()
        def handler(path, *args):
            page = int(parse_qs(urlsplit(path).query)["page"][0])
            return {"items": [repo_item(f"sample/project{page}", page)], "total_count": 4, "incomplete_results": False}
        api = FakeApi(handler)
        self.assertEqual(d.collect(api, conf, state, NOW), [])
        self.assertEqual(state["search_progress"]["hyperframes is:public"]["next_page"], 2)
        self.assertNotIn("search:hyperframes is:public", state["checkpoints"])
        self.assertTrue(state["last_run"]["notices"])
        self.assertEqual(d.collect(api, conf, state, NEXT), [])
        self.assertEqual(state["checkpoints"]["search:hyperframes is:public"], NOW)
        self.assertNotIn("hyperframes is:public", state["search_progress"])
        self.assertEqual(len(state["candidates"]), 2)

    def test_incomplete_search_preserves_checkpoint_and_partial_candidates(self):
        state = d.empty_state()
        key = "search:hyperframes is:public"
        state["checkpoints"][key] = NOW
        api = FakeApi(lambda *args: {"items": [repo_item()], "total_count": 10, "incomplete_results": True})
        problems = d.collect(api, config(), state, NEXT)
        self.assertTrue(problems)
        self.assertEqual(state["checkpoints"][key], NOW)
        self.assertEqual(len(state["candidates"]), 1)
        self.assertIn("pushed:>=2026-11-22", parse_qs(urlsplit(api.calls[0][0]).query)["q"][0])

    def test_search_exact_page_boundary_is_complete(self):
        state = d.empty_state()
        api = FakeApi(lambda *args: {"items": [repo_item(), repo_item("other/project", 124)], "total_count": 2, "incomplete_results": False})
        self.assertEqual(d.collect(api, config(), state, NOW), [])
        self.assertEqual(state["checkpoints"]["search:hyperframes is:public"], NOW)

    def test_failed_source_does_not_erase_other_discoveries(self):
        conf = config()
        conf["sources"] = [{"id": "broken", "kind": "adopters", "repository": "sample/source", "path": "README.md"}]
        def handler(path, *args):
            if path.startswith("/search/"):
                return {"items": [repo_item()], "total_count": 1, "incomplete_results": False}
            raise d.ApiError("rate limited", 429)
        state = d.empty_state()
        self.assertTrue(d.collect(FakeApi(handler), conf, state, NOW))
        self.assertEqual(len(state["candidates"]), 1)
        self.assertNotIn("broken", state["checkpoints"])

    def test_private_repositories_are_never_collected(self):
        private = repo_item()
        private["private"] = True
        state = d.empty_state()
        d.collect(FakeApi(lambda *args: {"items": [private], "total_count": 1, "incomplete_results": False}), config(), state, NOW)
        self.assertFalse(state["candidates"])

    def test_failed_enrichment_does_not_starve_other_candidates(self):
        state = d.empty_state()
        for n in (1, 2):
            d.upsert(state, d.repository_candidate(repo_item(f"sample/project{n}", n), "fixture", NOW), NOW)
        conf = config()
        conf.update(search_queries=[], enrich_per_run=1)
        def fail(*args):
            raise d.ApiError("README missing", 404)
        api = FakeApi(fail)
        d.collect(api, conf, state, NOW)
        d.collect(api, conf, state, NEXT)
        self.assertNotEqual(api.calls[0][0], api.calls[1][0])

    def test_replay_client_refuses_writes(self):
        with self.assertRaisesRegex(d.ApiError, "cannot publish"):
            d.GitHub(replay={}).call("/repos/sample/catalog/issues", "POST", {})


class ReviewTests(unittest.TestCase):
    def test_rejected_listed_and_watch_do_not_appear(self):
        state = d.empty_state()
        for name in ("rejected", "listed", "watch", "pending"):
            d.upsert(state, candidate(f"https://example.com/{name}", name), NOW)
        decisions = [{"url": f"https://example.com/{name}", "status": name, "reason": "维护者结论", "reviewed_at": "2026-11-25"} for name in ("rejected", "watch")]
        d.apply_reviews(state, {"decisions": decisions}, {"https://example.com/listed"})
        _, body, selected = d.render_digest(state, config(), NOW, REPO)
        self.assertEqual(selected, ["url:https://example.com/pending"])
        self.assertNotIn("## 2.", body)

    def test_backlog_rotates_after_recommendation(self):
        state = d.empty_state()
        for name in ("a", "b"):
            d.upsert(state, candidate(f"https://example.com/{name}"), NOW)
        conf = config()
        conf["digest_limit"] = 1
        _, _, first = d.render_digest(state, conf, NOW, REPO)
        state["candidates"][first[0]]["last_recommended"] = "2026-W48"
        _, _, second = d.render_digest(state, conf, "2026-12-01T00:00:00+00:00", REPO)
        self.assertNotEqual(first, second)

    def test_hostile_source_text_cannot_create_mentions_or_html(self):
        state = d.empty_state()
        item = candidate(title="@everyone\n<script>alert(1)</script>[x](javascript:bad)")
        item["author_claim"] = "@team\n## forged\n- [x] approved"
        d.upsert(state, item, NOW)
        _, body, _ = d.render_digest(state, config(), NOW, REPO)
        self.assertNotIn("@everyone", body)
        self.assertNotIn("<script>", body)
        self.assertNotIn("\n## forged", body)
        self.assertNotIn("\n- [x] approved", body)

    def test_week_uses_beijing_time_at_utc_boundary(self):
        week, _, _ = d.render_digest(d.empty_state(), config(), "2026-11-29T17:00:00+00:00", REPO)
        self.assertEqual(week, "2026-W49")

    def test_existing_closed_weekly_issue_preserves_manual_edits(self):
        body = f"{d.MARKER}2026-W48 -->\n- 记录 ID：`url:https://example.com/p`\n- [x] 已审核"
        issue = {"body": body, "user": {"type": "Bot"}, "html_url": "https://github.com/sample/catalog/issues/1", "state": "closed"}
        api = FakeApi(lambda *args: [issue])
        _, created, ids = d.publish_digest(api, REPO, "2026-W48", "new body")
        self.assertFalse(created)
        self.assertEqual(ids, ["url:https://example.com/p"])
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))


class StateTests(unittest.TestCase):
    def test_publish_and_rerun_preserve_weekly_issue_and_recommendation_state(self):
        remote = {"state": None, "issues": [], "tree_state": None}
        def handler(path, method, data):
            if path.endswith("/contents/ADOPTERS.md"):
                return content("| [Sample](https://example.com/) | Contact | Exploring HyperFrames |")
            if method == "GET" and "/contents/state.json?" in path:
                if remote["state"] is None:
                    raise d.ApiError("not installed", 404)
                return {"sha": "state-file-sha", "content": base64.b64encode(remote["state"].encode()).decode()}
            if method == "GET" and "/git/ref/heads/" in path:
                raise d.ApiError("not installed", 404)
            if method == "POST" and path.endswith("/git/trees"):
                remote["tree_state"] = data["tree"][0]["content"]
                return {"sha": "tree-sha"}
            if method == "POST" and path.endswith("/git/commits"):
                return {"sha": "commit-sha"}
            if method == "POST" and path.endswith("/git/refs"):
                remote["state"] = remote["tree_state"]
                return {}
            if method == "PUT" and path.endswith("/contents/state.json"):
                remote["state"] = base64.b64decode(data["content"]).decode()
                return {}
            if method == "GET" and "/issues?" in path:
                return remote["issues"]
            if method == "POST" and path.endswith("/issues"):
                issue = {**data, "user": {"type": "Bot"}, "html_url": "https://github.com/sample/catalog/issues/1"}
                remote["issues"].append(issue)
                return issue
            self.fail(f"Unexpected API call: {method} {path}")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conf = config()
            conf.update(search_queries=[], sources=[{"id": "adopters", "kind": "adopters", "repository": "sample/source", "path": "ADOPTERS.md"}])
            (root / "config.json").write_text(json.dumps(conf), encoding="utf-8")
            args = ["--config", str(root / "config.json"), "--repository", REPO, "--output", str(root / "out"), "--publish"]
            with patch.dict("os.environ", {"GH_TOKEN": "synthetic-test-token"}), patch.object(d, "GitHub", return_value=FakeApi(handler)):
                self.assertEqual(d.main(args), 0)
                remote["issues"][0]["body"] += "\n维护者手动审核内容"
                self.assertEqual(d.main(args), 0)
            self.assertEqual(len(remote["issues"]), 1)
            self.assertTrue(remote["issues"][0]["body"].endswith("维护者手动审核内容"))
            state = json.loads(remote["state"])
            self.assertIn("last_recommended", next(iter(state["candidates"].values())))

    def test_damaged_remote_state_cannot_be_silently_reset(self):
        def handler(path, *args):
            if "/contents/" in path:
                raise d.ApiError("missing file", 404)
            return {"ref": "refs/heads/automation/discovery-state"}
        with self.assertRaisesRegex(ValueError, "state.json is missing"):
            d.load_state(FakeApi(handler), REPO, "automation/discovery-state")

    def test_fresh_install_creates_orphan_branch_not_default_branch(self):
        api = FakeApi(lambda *args: {"sha": "new-sha"})
        d.save_state(api, REPO, "automation/discovery-state", d.empty_state(), None)
        self.assertEqual(api.calls[1][2]["parents"], [])
        self.assertEqual(api.calls[2][2]["ref"], "refs/heads/automation/discovery-state")
        self.assertEqual([entry["path"] for entry in api.calls[0][2]["tree"]], ["state.json"])

    def test_state_update_uses_optimistic_file_sha(self):
        api = FakeApi(lambda *args: {})
        d.save_state(api, REPO, "automation/discovery-state", d.empty_state(), "old-sha")
        self.assertEqual(api.calls[0][2]["sha"], "old-sha")
        self.assertEqual(api.calls[0][2]["branch"], "automation/discovery-state")

    def test_cli_replay_generates_local_preview_without_writing_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conf = config()
            conf.update(search_queries=[], sources=[{"id": "adopters", "kind": "adopters", "repository": "sample/source", "path": "ADOPTERS.md"}])
            (root / "config.json").write_text(json.dumps(conf), encoding="utf-8")
            replay = {"/repos/sample/source/contents/ADOPTERS.md": content("| [Sample](https://example.com/) | Contact | Exploring HyperFrames |")}
            (root / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
            args = ["--config", str(root / "config.json"), "--replay", str(root / "replay.json"), "--output", str(root / "out")]
            self.assertEqual(d.main(args), 0)
            self.assertTrue((root / "out/weekly-review.md").exists())
            state = d.read_json(root / "out/state.json")
            self.assertEqual(len(state["candidates"]), 1)


class RepositoryChecks(unittest.TestCase):
    def test_catalog_relative_markdown_links_exist(self):
        for path in d.ROOT.rglob("*.md"):
            if any(part in {".git", "artifacts", "node_modules"} for part in path.parts):
                continue
            text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
            for match in d.LINK.finditer(text):
                href = match[2].strip("<>").split("#")[0]
                if not href or urlsplit(href).scheme or href.startswith("/"):
                    continue
                self.assertTrue((path.parent / href).exists(), f"{path.relative_to(d.ROOT)}: {href}")

    def test_default_sources_and_reviews_are_valid(self):
        conf = d.read_json(d.ROOT / "discovery/config.json")
        self.assertEqual(len({source["id"] for source in conf["sources"]}), len(conf["sources"]))
        self.assertTrue(all("is:public" in query for query in conf["search_queries"]))
        d.apply_reviews(d.empty_state(), d.read_json(d.ROOT / "discovery/reviews.json"), set())


if __name__ == "__main__":
    unittest.main()
