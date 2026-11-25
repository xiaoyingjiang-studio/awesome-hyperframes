"""Publication contracts: no live GitHub, AI calls, credentials or external writes."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

from scripts import ai_review as a, catalog as c, discover as d

NOW = "2026-11-25T09:00:00+00:00"
NEXT = "2026-11-26T09:00:00+00:00"
REPO = "sample/catalog"
SUMMARIES = {"en": "A project using HyperFrames to compose product videos.", "zh-CN": "使用 HyperFrames 编排产品视频的项目。", "ja": "HyperFrames で製品動画を構成するプロジェクトです。", "es": "Un proyecto que utiliza HyperFrames para vídeos de producto.", "fr": "Un projet qui utilise HyperFrames pour des vidéos produit.", "de": "Ein Projekt, das HyperFrames für Produktvideos verwendet.", "pt-BR": "Um projeto que usa HyperFrames para vídeos de produto.", "ko": "HyperFrames를 사용해 제품 영상을 구성하는 프로젝트입니다."}


def candidate(name="demo", relevance="supported"):
    item = d.make_candidate(f"https://github.com/sample/{name}", name, "工具与集成产品", "社区项目线索", d.source_record("repository-readme", f"https://github.com/sample/{name}/blob/main/README.md", "a"*40, NOW, "Uses HyperFrames to compose videos."), summary="来源说明用于编排视频的项目。")
    item.update(status="pending", first_seen=NOW, last_seen=NOW, last_changed=NOW)
    payload = {"id": item["id"], "relevance": relevance, "category": "工具与集成产品", "entry": "HyperFrames 框架", "summary": "使用 HyperFrames 编排产品视频的项目。", "reason": "原始来源说明了具体的视频编排用途。", "reference_value": "可能参考视频编排方式，实际实现仍需核对。", "checks": ["核对工程与素材许可"], "evidence_ids": ["repository-readme"], "summaries": SUMMARIES}
    result = a.validate_reviews({"reviews": [payload]}, [item])[item["id"]]
    item["ai_review"] = {**result, "model": "synthetic-model", "generated_at": NOW, "input_hash": a.input_hash(item), "prompt_version": a.PROMPT_VERSION, "request_options": {}}
    return item


def state(*items):
    result = d.empty_state()
    result["last_run"] = {"at": NOW, "problems": [], "warnings": []}
    result["candidates"] = {item["id"]: item for item in items}
    return result


def config():
    return {"state_branch": "automation/discovery-state", "catalog_files": ["README.md", "examples/*/README.md"]}


class GitFixture:
    def __init__(self):
        self.head = "head-0"
        self.files = {path: "# Handwritten content\n\n" + c.START + "\nold generated content\n" + c.END + "\n\nManual footer\n" for path in c.HOME_PATHS.values()}
        self.calls = []
        self.commits = 0
        self.conflict = False

    def call(self, path, method="GET", data=None):
        self.calls.append((path, method, data))
        route = urlsplit(path).path
        if method == "GET" and route == f"/repos/{REPO}":
            return {"default_branch": "main"}
        if method == "GET" and route.endswith("/git/refs/heads/main"):
            return {"object": {"sha": self.head}}
        if method == "GET" and "/git/commits/" in route:
            assert route.endswith(self.head)
            return {"tree": {"sha": "base-tree"}}
        if method == "GET" and route.endswith("/git/trees/base-tree"):
            return {"tree": [{"type": "blob", "path": path} for path in self.files]}
        if method == "GET" and "/contents/" in route:
            assert parse_qs(urlsplit(path).query)["ref"] == [self.head]
            key = unquote(route.split("/contents/")[1])
            if key not in self.files:
                raise d.ApiError("missing", 404)
            return {"sha": "a"*40, "encoding": "base64", "content": base64.b64encode(self.files[key].encode()).decode()}
        if method == "POST" and route.endswith("/git/trees"):
            assert data["base_tree"] == "base-tree"
            self.pending = {entry["path"]: entry["content"] for entry in data["tree"]}
            return {"sha": "new-tree"}
        if method == "POST" and route.endswith("/git/commits"):
            assert data["parents"] == [self.head]
            self.parent = self.head
            self.commits += 1
            return {"sha": f"published-{self.commits}"}
        if method == "PATCH" and route.endswith("/git/refs/heads/main"):
            assert data["force"] is False
            if self.conflict:
                self.head = "maintainer-new-head"
                self.files["README.md"] += "\nConcurrent maintainer edit\n"
                raise d.ApiError("non-fast-forward", 409)
            self.files.update(self.pending)
            self.head = data["sha"]
            return {}
        raise AssertionError(f"Unexpected API operation: {method} {path}")


class PublicationTests(unittest.TestCase):
    def test_atomic_publication_updates_all_locales_and_never_creates_issue_or_pr(self):
        api, item = GitFixture(), candidate()
        report = c.publish(api, REPO, state(item), config(), NOW, d)
        self.assertEqual(report["status"], "published")
        self.assertEqual(report["added"], 1)
        self.assertEqual(report["files"], 17)
        self.assertEqual(set(api.pending), c.ALLOWED_PATHS)
        self.assertEqual([method for _, method, _ in api.calls if method != "GET"], ["POST", "POST", "PATCH"])
        self.assertTrue(all("/issues" not in path and "/pulls" not in path for path, _, _ in api.calls))
        for language in a.LANGUAGES:
            home = api.files[c.HOME_PATHS[language]]
            self.assertTrue(home.startswith("# Handwritten content\n\n"))
            self.assertTrue(home.endswith("Manual footer\n"))
            self.assertIn(SUMMARIES[language], home)
            self.assertIn(SUMMARIES[language], api.files[c.CATALOG_PATHS[language]])
        stored = json.loads(api.files[c.DATA_PATH])["resources"][item["id"]]
        self.assertEqual(stored["verification"], "source-text-only")
        self.assertEqual(stored["evidence"][0]["id"], "repository-readme")
        self.assertEqual(item["status"], "pending")

    def test_rerun_and_read_date_changes_do_not_create_duplicate_commits_or_entries(self):
        api, item = GitFixture(), candidate()
        c.publish(api, REPO, state(item), config(), NOW, d)
        item["evidence"][0]["observed_at"] = NEXT
        api.files["README.md"] += "\nA later handwritten note\n"
        report = c.publish(api, REPO, state(item), config(), NEXT, d)
        self.assertEqual(report["status"], "unchanged")
        self.assertEqual(report["files"], 0)
        self.assertEqual(api.commits, 1)
        self.assertTrue(api.files["README.md"].endswith("A later handwritten note\n"))

    def test_manual_listing_or_exclusion_removes_automatic_duplicate(self):
        for action in ("manual", "rejected", "watch"):
            with self.subTest(action=action):
                api, item = GitFixture(), candidate()
                c.publish(api, REPO, state(item), config(), NOW, d)
                if action == "manual":
                    api.files["README.md"] += f"\n[Manually selected]({item['url']})\n"
                else:
                    item["status"] = action
                report = c.publish(api, REPO, state(item), config(), NEXT, d)
                self.assertEqual(report["removed"], 1)
                self.assertEqual(report["count"], 0)
                if action == "manual":
                    self.assertIn("[Manually selected]", api.files["README.md"])

    def test_search_only_unclear_and_stale_reviews_cannot_add_resources(self):
        for case in ("search-only", "unclear", "stale"):
            with self.subTest(case=case):
                item = candidate(relevance="unclear" if case == "unclear" else "supported")
                if case == "search-only":
                    item["evidence"][0]["id"] = "github-search:query"
                    item["ai_review"]["evidence_ids"] = ["github-search:query"]
                    item["ai_review"]["input_hash"] = a.input_hash(item)
                elif case == "stale":
                    item["evidence"][0]["detail"] += " Substantive source change."
                result = c.update_resources({"schema_version": 1, "resources": {}}, state(item), set(), d)
                self.assertEqual(result, {})

    def test_failed_sources_do_not_erase_previously_published_resources(self):
        api, item = GitFixture(), candidate()
        c.publish(api, REPO, state(item), config(), NOW, d)
        previous = json.loads(api.files[c.DATA_PATH])
        item["evidence"][0]["detail"] += " Changed, awaiting a new AI review."
        self.assertEqual(c.update_resources(previous, state(item), set(), d), previous["resources"])

    def test_missing_markers_and_corrupt_data_fail_before_any_write(self):
        for corruption in ("marker", "json"):
            with self.subTest(corruption=corruption):
                api = GitFixture()
                if corruption == "marker":
                    api.files[c.HOME_PATHS["ja"]] = "# Maintainer removed the marker\n"
                else:
                    api.files[c.DATA_PATH] = '{"schema_version":99,"resources":{}}'
                with self.assertRaises(ValueError):
                    c.publish(api, REPO, state(candidate()), config(), NOW, d)
                self.assertTrue(all(method == "GET" for _, method, _ in api.calls))

    def test_concurrent_main_edit_is_never_overwritten_or_force_pushed(self):
        api = GitFixture()
        api.conflict = True
        with self.assertRaises(d.ApiError):
            c.publish(api, REPO, state(candidate()), config(), NOW, d)
        self.assertEqual(api.head, "maintainer-new-head")
        self.assertIn("Concurrent maintainer edit", api.files["README.md"])
        self.assertNotIn(c.DATA_PATH, api.files)
        self.assertEqual(sum(method == "PATCH" for _, method, _ in api.calls), 1)

    def test_hostile_resource_text_is_escaped_in_both_views(self):
        item = candidate()
        item["title"] = "[bad] | @all <script>"
        item["ai_review"]["input_hash"] = a.input_hash(item)
        resources = c.update_resources({"schema_version": 1, "resources": {}}, state(item), set(), d)
        for homepage in (False, True):
            text = c.render(resources, "en", d, homepage=homepage)
            self.assertNotIn("@all", text)
            self.assertNotIn("<script>", text)
            self.assertIn("［bad］", text)

    def test_multilingual_contract_rejects_missing_language_links_and_fake_tests(self):
        for update in ({"ja": ""}, {"en": "See https://example.com for the details"}, {"en": "We have tested this project successfully."}):
            with self.subTest(update=update), self.assertRaises(a.ReviewError):
                a.validate_summaries({**SUMMARIES, **update})
        with self.assertRaises(a.ReviewError):
            a.validate_summaries({key: value for key, value in SUMMARIES.items() if key != "ko"})

    def test_daily_cli_persists_failed_ai_without_touching_main_or_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["--mode", "publish", "--publish", "--repository", REPO, "--output", directory, "--ai", "required"]
            failed = {"status": "failed", "calls": 1, "reviewed": 0, "cache_hits": 0, "errors": ["synthetic failure"], "notices": []}
            with patch.dict("os.environ", {"GH_TOKEN": "synthetic-test-token"}), patch.object(d, "load_state", return_value=(state(candidate()), "state-sha")), patch.object(d, "save_state") as save, patch.object(a, "review_candidates", return_value=failed), patch.object(c, "publish", side_effect=AssertionError("must preserve main")), patch("builtins.print"):
                self.assertEqual(d.main(args), 1)
                self.assertEqual(save.call_count, 1)
            summary = (Path(directory) / "run-summary.md").read_text(encoding="utf-8")
            self.assertIn("skipped", summary)
            self.assertIn("synthetic failure", summary)

    def test_managed_rows_are_not_interpreted_as_manual_acceptance(self):
        item = candidate()
        text = "[Manual](https://example.com/manual)\n" + c.START + f"\n[Automatic]({item['url']})\n" + c.END
        self.assertNotIn(item["url"], c.strip_managed(text))
        self.assertIn("https://example.com/manual", c.strip_managed(text))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(text, encoding="utf-8")
            with patch.object(d, "ROOT", root):
                urls = d.catalog_urls({"catalog_files": ["README.md"]})
            self.assertEqual(urls, {"https://example.com/manual"})

    def test_successful_daily_cli_calls_atomic_publisher_and_reports_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["--mode", "publish", "--publish", "--repository", REPO, "--output", directory, "--ai", "required"]
            complete = {"status": "completed", "calls": 1, "reviewed": 1, "cache_hits": 0, "errors": [], "notices": []}
            publication = {"status": "published", "count": 1, "commit": "new-main-commit"}
            events = []
            with patch.dict("os.environ", {"GH_TOKEN": "synthetic-test-token"}), patch.object(d, "load_state", return_value=(state(candidate()), "state-sha")), patch.object(d, "save_state", side_effect=lambda *args: events.append("state")), patch.object(a, "review_candidates", return_value=complete), patch.object(c, "publish", side_effect=lambda *args: (events.append("catalog") or publication)), patch("builtins.print"):
                self.assertEqual(d.main(args), 0)
            self.assertEqual(events, ["state", "catalog"])
            summary = (Path(directory) / "run-summary.md").read_text(encoding="utf-8")
            self.assertIn("new-main-commit", summary)
            self.assertIn("published", summary)


if __name__ == "__main__":
    unittest.main()
