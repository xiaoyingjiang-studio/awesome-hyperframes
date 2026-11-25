"""Discover resource leads; never execute third-party code or edit the curated catalog.

Python 3.11+, standard library only. See discovery/README.md for operation.
"""

from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    from . import ai_review, catalog
else:
    import ai_review
    import catalog

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = timezone(timedelta(hours=8))
STATE_PATH = "state.json"
STATE_VERSION = 1
MARKER = "<!-- awesome-hyperframes:weekly:"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
LINK = re.compile(r"\[([^\]]+)\]\(([^\s)]+)(?:\s+[^)]*)?\)")
VALID_STATUS = {"accepted", "rejected", "watch"}


class ApiError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ApiRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https" or urlsplit(newurl).netloc != "api.github.com":
            raise ApiError("Refusing GitHub API redirect to another host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GitHub:
    """Only talk to api.github.com. Never forward the token to resource URLs."""

    def __init__(self, token="", replay=None):
        self.token = token
        self.replay = replay
        self.opener = build_opener(ApiRedirects())

    def call(self, path, method="GET", data=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("GitHub API path required")
        if self.replay is not None:
            if method != "GET":
                raise ApiError("Replay mode cannot publish")
            if path not in self.replay:
                raise ApiError(f"Replay response missing: {path}", 404)
            return copy.deepcopy(self.replay[path])
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "awesome-hyperframes-discovery"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        if payload is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(3):
            try:
                req = Request("https://api.github.com" + path, data=payload, headers=headers, method=method)
                with self.opener.open(req, timeout=30) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ApiError("GitHub response exceeded size limit")
                return json.loads(raw)
            except HTTPError as error:
                # Do not retry writes: a lost response may already have created an issue.
                wait = error.headers.get("Retry-After", "")
                rate_limited = error.code == 429 or (error.code == 403 and (wait or error.headers.get("X-RateLimit-Remaining") == "0"))
                if method == "GET" and attempt < 2 and (rate_limited or error.code >= 500):
                    delay = min(int(wait), 30) if wait.isdigit() else 2 ** (attempt + 1)
                    time.sleep(delay)
                    continue
                raise ApiError(f"GitHub API HTTP {error.code}: {path.split('?')[0]}", error.code) from None
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                if method == "GET" and attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ApiError(f"GitHub request failed ({type(error).__name__}): {path.split('?')[0]}") from None
        raise ApiError("GitHub request failed")


def canonical_url(value):
    """Conservative identity: drop tracking, retain meaningful query and project path."""
    try:
        parts = urlsplit(value.strip().strip("<>"))
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        host = parts.hostname.lower()
        port = parts.port
    except ValueError:
        return None
    if host == "www.github.com":
        host = "github.com"
    path = parts.path.rstrip("/")
    query = "&".join(p for p in parts.query.split("&") if p and not p.split("=")[0].lower().startswith(("utm_", "fbclid", "gclid")))
    scheme = parts.scheme
    if host == "github.com":
        scheme = "https"
        segments = path.split("/")
        segments[:3] = [segment.lower() for segment in segments[:3]]
        path = "/".join(segments)
        if len(segments) == 3:
            path = re.sub(r"\.git$", "", path)
    default_port = 443 if scheme == "https" else 80
    authority = host if port in (None, default_port) else f"{host}:{port}"
    return urlunsplit((scheme, authority, path, query, ""))


def identity(url):
    normalized = canonical_url(url)
    if not normalized:
        raise ValueError("Invalid resource URL")
    return "url:" + normalized


def plain(value, limit=300):
    # Prevent author text from creating mentions, HTML, headings or checkboxes in issues.
    value = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip()[:limit]
    for original, replacement in [("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("@", "＠"), ("[", "［"), ("]", "］"), ("*", "＊"), ("`", "｀"), ("|", "｜"), ("\\", "＼")]:
        value = value.replace(original, replacement)
    return value


def md_link(label, url):
    normalized = canonical_url(url or "")
    if not normalized:
        return plain(label) + "（地址待核对）"
    return f"[{plain(label)}](<{normalized.replace('>', '%3E').replace('<', '%3C')}>)"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def empty_state():
    return {"schema_version": STATE_VERSION, "checkpoints": {}, "candidates": {}, "last_run": None}


def validate_state(state):
    if state.get("schema_version") != STATE_VERSION or not isinstance(state.get("candidates"), dict) or not isinstance(state.get("checkpoints"), dict):
        raise ValueError("Unsupported or invalid discovery state; refusing to overwrite it")
    return state


def decode_file(api, repository, result):
    # Contents API omits inline content above 1 MiB. Fetch the immutable blob,
    # retaining the original file SHA for optimistic updates and never resetting data.
    if result.get("encoding") == "none":
        sha = result.get("sha", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Missing or invalid file blob SHA")
        blob = api.call(f"/repos/{repository}/git/blobs/{sha}")
        if blob.get("sha") != sha:
            raise ValueError("File blob SHA mismatch")
    else:
        blob = result
    if blob.get("encoding") != "base64" or not blob.get("content"):
        raise ValueError("Unsupported or empty GitHub file content")
    return base64.b64decode(blob["content"]).decode("utf-8-sig")


def load_state(api, repository, branch):
    try:
        result = api.call(f"/repos/{repository}/contents/{STATE_PATH}?" + urlencode({"ref": branch}))
    except ApiError as error:
        if error.status != 404:
            raise
        # A missing file in an existing branch is damage, not a fresh installation.
        try:
            api.call(f"/repos/{repository}/git/ref/heads/{quote(branch, safe='/')}")
        except ApiError as ref_error:
            if ref_error.status == 404:
                return empty_state(), None
            raise
        raise ValueError("State branch exists but state.json is missing") from None
    return validate_state(json.loads(decode_file(api, repository, result))), result["sha"]


def save_state(api, repository, branch, state, sha):
    content = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if sha:
        api.call(f"/repos/{repository}/contents/{STATE_PATH}", "PUT", {
            "message": "chore: update discovery records", "branch": branch, "sha": sha,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii")})
    else:
        # Create a dedicated orphan branch: no catalog files or third-party source copies.
        tree = api.call(f"/repos/{repository}/git/trees", "POST", {"tree": [{"path": STATE_PATH, "mode": "100644", "type": "blob", "content": content}]})
        commit = api.call(f"/repos/{repository}/git/commits", "POST", {"message": "chore: initialize discovery records", "tree": tree["sha"], "parents": []})
        api.call(f"/repos/{repository}/git/refs", "POST", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})


def get_file(api, repository, path):
    result = api.call(f"/repos/{repository}/contents/{quote(path, safe='/')}")
    text = decode_file(api, repository, result)
    return text, result["html_url"], result["sha"]


def source_record(source, url, blob_sha, now, detail):
    return {"id": source, "url": url, "blob_sha": blob_sha, "observed_at": now, "detail": detail[:300]}


def make_candidate(url, title, kind, origin, evidence, **extra):
    return {"id": identity(url), "url": canonical_url(url), "title": title[:160], "kind": kind,
            "origin": origin, "entry": "待核对", "evidence": [evidence], **extra}


def resolve_relative(source_url, href):
    # GitHub's /blob/ URLs need directory semantics for ./subdir links.
    return canonical_url(urljoin(source_url, href))


def parse_source(source, text, source_url, sha, now):
    kind = source["kind"]
    candidates = []
    if kind == "registry":
        data = json.loads(text)
        if not isinstance(data.get("items"), list):
            raise ValueError("Registry items missing")
        for item in data["items"]:
            if item.get("type") not in source["types"]:
                continue
            name = item["name"]
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
                raise ValueError("Invalid registry item name")
            section = {"hyperframes:example": "examples", "hyperframes:block": "blocks", "hyperframes:component": "components"}.get(item["type"])
            if section is None:
                continue
            # Source tree is a project entry, not a claimed video preview.
            url = source_url.rsplit("/registry.json", 1)[0].replace("/blob/", "/tree/", 1) + f"/{section}/{name}"
            candidates.append(make_candidate(url, name, "案例与模板" if section == "examples" else "模板与组件", "官方框架资源",
                source_record(source["id"], source_url, sha, now, f"索引条目：{name}；类型：{item['type']}"),
                source_code=url, summary="官方索引中的资源候选；用途、演示与复用条件待审核。"))
    else:
        for line in text.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            if kind == "adopters":
                match = LINK.search(cells[0])
                if not match or not canonical_url(match[2]):
                    continue
                title, url = match[1], match[2]
                detail = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cells[2])
                candidates.append(make_candidate(url, title, "工具与集成产品", "官方使用者名单线索",
                    source_record(source["id"], source_url, sha, now, detail),
                    summary="官方名单中的使用或探索线索；不代表维护者实测或成熟生产应用。", author_claim=detail[:300]))
            elif kind == "launches":
                project = LINK.search(cells[1])
                if not project:
                    continue
                url = resolve_relative(source_url, project[2])
                if not url:
                    continue
                url = url.replace("/blob/", "/tree/", 1)
                video = LINK.search(cells[2])
                preview = resolve_relative(source_url, video[2]) if video else None
                candidates.append(make_candidate(url, cells[0], "作品与案例", "官方作品工程",
                    source_record(source["id"], source_url, sha, now, f"作品表记录：{cells[0]}"),
                    source_code=url, preview=preview,
                    summary="官方发布的作品工程；成片观看、工程运行及素材许可待核对。"))
            else:
                raise ValueError(f"Unknown source kind: {kind}")
    if not candidates:
        raise ValueError(f"Source parsed no candidates: {source['id']}; inspect upstream format")
    return candidates


def fingerprint(candidate):
    value = {k: v for k, v in candidate.items() if k not in {"first_seen", "last_seen", "last_changed", "status", "review", "evidence", "enriched_at", "last_enrichment_attempt", "enrichment_error", "last_recommended", "ai_review", "last_ai_attempt"}}
    # Unrelated edits to the source file must not make every resource look updated.
    value["evidence"] = [{k: v for k, v in e.items() if k not in {"observed_at", "blob_sha"}} for e in candidate["evidence"]]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def upsert(state, incoming, now):
    candidates = state["candidates"]
    key = incoming["id"]
    if incoming.get("github_id"):
        key = next((k for k, v in candidates.items() if v.get("github_id") == incoming["github_id"]), key)
    existing = candidates.get(key)
    if not existing:
        incoming.update(first_seen=now, last_seen=now, last_changed=now, status="pending")
        candidates[key] = incoming
        return incoming
    before = fingerprint(existing)
    evidence = {e["id"]: e for e in existing["evidence"]}
    evidence.update({e["id"]: e for e in incoming["evidence"]})
    existing.update({k: v for k, v in incoming.items() if k != "id"})
    existing["evidence"] = sorted(evidence.values(), key=lambda e: e["id"])
    existing["last_seen"] = now
    if before != fingerprint(existing):
        existing["last_changed"] = now
    return existing


def catalog_urls(config):
    urls = set()
    for pattern in config["catalog_files"]:
        for path in ROOT.glob(pattern):
            for match in LINK.finditer(catalog.strip_managed(path.read_text(encoding="utf-8"))):
                url = canonical_url(match[2])
                if url:
                    urls.add(url)
    return urls


def apply_reviews(state, reviews, known):
    decisions = {}
    for decision in reviews["decisions"]:
        if decision.get("status") not in VALID_STATUS or not decision.get("reason") or not decision.get("reviewed_at"):
            raise ValueError("Review requires status, reason and reviewed_at")
        key = decision.get("id") or identity(decision["url"])
        if key in decisions:
            raise ValueError(f"Duplicate review: {key}")
        decisions[key] = decision
    for candidate in state["candidates"].values():
        review = decisions.get(candidate["id"]) or decisions.get(identity(candidate["url"]))
        if review:
            candidate["status"] = review["status"]
            candidate["review"] = review
        elif candidate["url"] in known:
            candidate["status"] = "listed"
            candidate.pop("review", None)
        else:
            candidate["status"] = "pending"
            candidate.pop("review", None)


def repository_candidate(item, query, now, official_owners=()):
    url = item["html_url"]
    official = item["owner"]["login"].lower() in {owner.lower() for owner in official_owners}
    return make_candidate(url, item["full_name"], "项目（待分类）", "官方仓库搜索线索" if official else "社区仓库搜索线索",
        source_record("github-search:" + query, "https://github.com/search?" + urlencode({"q": query, "type": "repositories"}), None, now, "搜索命中仅代表候选相关性，尚未核对实际使用。"),
        github_id=item["id"], repository=item["full_name"], author=item["owner"]["login"],
        source_code=url, homepage=canonical_url(item.get("homepage") or ""),
        author_claim=(item.get("description") or "")[:300],
        license_spdx=(item.get("license") or {}).get("spdx_id"),
        summary="GitHub 搜索发现的项目候选；需核对与 HyperFrames 的实际关系和参考价值。")


def enrich(api, candidate, now):
    repository = candidate["repository"]
    result = api.call(f"/repos/{repository}/readme")
    readme = decode_file(api, repository, result)[:60000]
    matches = [line.strip() for line in readme.splitlines() if re.search(r"hyperframes", line, re.I)]
    candidate["association"] = "README 提及，实际使用待核对" if matches else "仅搜索命中，关系待核对"
    # Do not retain an obsolete excerpt when the current README removes the mention.
    candidate["evidence"] = [e for e in candidate["evidence"] if e["id"] != "repository-readme"]
    if matches:
        candidate["evidence"].append(source_record("repository-readme", result["html_url"], result["sha"], now, " ".join(matches)[:240]))
    candidate["enriched_at"] = now
    candidate.pop("enrichment_error", None)


def collect(api, config, state, now, full=False):
    problems = []
    warnings = []
    notices = []
    for source in config["sources"]:
        try:
            text, url, sha = get_file(api, source["repository"], source["path"])
            parsed = parse_source(source, text, url, sha, now)
            for candidate in parsed:
                upsert(state, candidate, now)
            state["checkpoints"][source["id"]] = now
        except (ApiError, ValueError, KeyError, TypeError) as error:
            problems.append(f"{source['id']}: {error}")
    excluded = {r.lower() for r in config["excluded_repositories"]}
    for query in config["search_queries"]:
        checkpoint_key = "search:" + query
        checkpoint = state["checkpoints"].get(checkpoint_key)
        progress = state.setdefault("search_progress", {})
        session = progress.get(query) if not full else None
        effective = query
        if checkpoint and not full:
            since = datetime.fromisoformat(checkpoint) - timedelta(days=config["overlap_days"])
            effective += " pushed:>=" + since.date().isoformat()
        if session:
            effective = session["query"]
        else:
            session = {"query": effective, "next_page": 1, "started_at": now}
        try:
            for _ in range(config["search_pages"]):
                page = session["next_page"]
                params = {"q": effective, "sort": "updated", "order": "desc", "per_page": config["search_page_size"], "page": page}
                response = api.call("/search/repositories?" + urlencode(params))
                for item in response["items"]:
                    if item.get("private") or item.get("fork") or item.get("archived") or item["full_name"].lower() in excluded:
                        continue
                    upsert(state, repository_candidate(item, query, now, config.get("official_owners", [])), now)
                if response.get("incomplete_results"):
                    progress[query] = session
                    problems.append(f"搜索返回不完整结果，保留检查点并重试第 {page} 页：{query}")
                    break
                if page * config["search_page_size"] >= response["total_count"]:
                    # Keep the start time: edits during a multi-day scan must be revisited.
                    state["checkpoints"][checkpoint_key] = session["started_at"]
                    progress.pop(query, None)
                    break
                if page * config["search_page_size"] >= 1000:
                    progress[query] = session
                    problems.append(f"搜索超过 GitHub 的 1000 项限制，需按创建日期等拆分查询：{query}")
                    break
                session["next_page"] = page + 1
                progress[query] = session
            else:
                notices.append(f"已保存分页进度，下次从第 {session['next_page']} 页续查；尚未推进完整查询检查点：{query}")
        except (ApiError, ValueError, KeyError, TypeError) as error:
            progress[query] = session
            problems.append(f"搜索失败，保留原检查点：{query}: {error}")
    # Old, unprocessed candidates get a turn even when the per-run budget is exhausted.
    queue = sorted((c for c in state["candidates"].values() if c.get("repository") and c["status"] == "pending"), key=lambda c: (c.get("last_enrichment_attempt", ""), c["first_seen"], c["id"]))
    for candidate in queue[:config["enrich_per_run"]]:
        before = fingerprint(candidate)
        candidate["last_enrichment_attempt"] = now
        try:
            enrich(api, candidate, now)
            if before != fingerprint(candidate):
                candidate["last_changed"] = now
        except (ApiError, ValueError, KeyError, TypeError) as error:
            candidate["enrichment_error"] = str(error)
            # Optional enrichment must not invalidate discoveries from primary sources.
            # Keep the gap visible and the candidate in the fair retry queue.
            warnings.append(f"README 信息未补齐（保留候选，后续轮换重试）：{candidate['repository']}: {error}")
    state["last_run"] = {"at": now, "full_search": full, "problems": problems, "warnings": warnings, "notices": notices}
    return problems


def render_digest(state, config, now, repository):
    local = datetime.fromisoformat(now).astimezone(SHANGHAI)
    iso = local.isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    pending = [c for c in state["candidates"].values() if c["status"] == "pending"]
    # Include backlog, so a busy first scan doesn't permanently hide later candidates.
    ranked = sorted(pending, key=lambda c: (c.get("last_recommended", ""), 0 if c["origin"].startswith("官方") else 1, c["first_seen"], c["id"]))
    selected = ranked[:config["digest_limit"]]
    marker = f"{MARKER}{week} -->"
    lines = [marker, "# HyperFrames 每周候选审核", "", f"审核周：{week}（北京时间）；生成：{local:%Y-%m-%d %H:%M}。", "", "这些是自动发现的线索，不是正式收录、质量排名或维护者实测。自动任务仅读取来源文字；未观看成片、运行工程、登录 Studio 或核实素材授权。", "", f"待审核 {len(pending)} 项；本期展示 {len(selected)} 项；已收录、已接受、已拒绝与暂缓项不进入推荐队列。", "", "审核结论请通过 discovery/reviews.json 提交 PR；此清单及其勾选状态不用于自动批准。旧周报保留，新一周创建新 Issue。", ""]
    for index, c in enumerate(selected, 1):
        changed = datetime.fromisoformat(c["last_changed"]).astimezone(SHANGHAI) >= start
        lines += [f"## {index}. {md_link(c['title'], c['url'])}", "", f"- 类型建议：{plain(c['kind'])}；归属：{plain(c['origin'])}；入口：{plain(c['entry'])}。", f"- 整理说明：{plain(c['summary'])}", f"- 状态：{'本周新增或信息变化' if changed else '待审核积压'}；首次发现：{c['first_seen'][:10]}。", f"- 记录 ID：`{c['id'].replace('`', '%60')}`"]
        if c.get("author_claim"):
            lines.append("- 来源自述（未独立验证）：" + plain(c["author_claim"]))
        if c.get("author"):
            lines.append("- 仓库所有者：" + plain(c["author"]) + "（不等同于全部素材作者）。")
        if c.get("preview"):
            lines.append("- " + md_link("成片入口（未观看）", c["preview"]))
        if c.get("source_code"):
            lines.append("- " + md_link("工程入口（未执行）", c["source_code"]))
        if c.get("homepage"):
            lines.append("- " + md_link("仓库声明的产品官网（未核对）", c["homepage"]))
        lines.append("- 许可：" + (f"GitHub 元数据报告 {plain(c['license_spdx'])}；原始声明与素材许可待核对。" if c.get("license_spdx") else "未确认；代码、文字与素材需分别核对。"))
        for e in c["evidence"]:
            lines.append(f"- 来源证据：{md_link(e['id'], e['url'])}；读取于 {e['observed_at'][:10]}；{plain(e['detail'])}")
        suggestion = ai_review.current_review(c)
        if suggestion:
            relevance = {"supported": "来源片段支持使用关系", "mention_only": "仅提及名称", "unclear": "证据不足", "unrelated": "来源片段表明无关"}[suggestion["relevance"]]
            lines += [f"- AI 辅助建议（未经人工核实；{plain(suggestion['model'])}；{suggestion['generated_at'][:10]}）：{relevance}；建议分类：{plain(suggestion['category'])}；建议入口：{plain(suggestion['entry'])}。",
                      "- AI 简介：" + plain(suggestion["summary"]),
                      "- AI 判断依据：" + plain(suggestion["reason"]),
                      "- AI 参考价值：" + plain(suggestion["reference_value"]),
                      "- AI 引用来源 ID：" + "、".join(plain(key) for key in suggestion["evidence_ids"])]
            lines += ["- AI 待核实：" + plain(check) for check in suggestion["checks"]]
        elif c.get("ai_review"):
            lines.append("- AI 建议已因来源变化失效，等待重新分析。")
        if c.get("enrichment_error"):
            lines.append("- 信息缺口：README 补充读取失败，需人工核对。")
        lines += ["- [ ] 核对作者与 HyperFrames 关系、用途与参考价值、成片与工程入口、许可与使用条件、实际验证边界。", ""]
    if not selected:
        lines += ["本期没有待审核候选。", ""]
    lines += ["## 采集范围与异常", ""]
    last = state.get("last_run")
    lines.append("最近采集：" + (last["at"] if last else "尚无成功记录") + "。")
    problems = last.get("problems", []) if last else []
    lines += ["- " + plain(p, 500) for p in problems] if problems else ["最近一次任务未记录主要来源采集错误；不代表全网覆盖或资源内容已验证。"]
    if last:
        lines += ["- 补充信息警告：" + plain(warning, 500) for warning in last.get("warnings", [])]
        lines += ["- " + plain(notice, 500) for notice in last.get("notices", [])]
    ai = state.get("last_ai_run", {})
    lines += ["", "## AI 辅助记录", ""]
    labels = {"completed": "已完成本次额度内的分析", "partial": "部分完成后出错", "failed": "调用或配置失败", "not_configured": "未配置，使用规则采集", "disabled": "本次关闭"}
    lines.append(f"状态：{labels.get(ai.get('status'), '尚无调用记录')}；本次请求 {ai.get('calls', 0)} 次、分析 {ai.get('reviewed', 0)} 项、命中缓存 {ai.get('cache_hits', 0)} 项、待分析 {ai.get('remaining', 0)} 项。")
    if ai.get("reserved_tokens"):
        lines.append(f"保守预算用量（输入 UTF-8 字节数加输出 Token 上限）：{ai['reserved_tokens']}；服务报告实际用量：{plain(json.dumps(ai.get('usage', {}), ensure_ascii=False))}。")
    if "request_options" in ai:
        lines.append("请求选项：" + plain(json.dumps(ai["request_options"], ensure_ascii=False)) + "。")
    for response in ai.get("responses", []):
        lines.append(f"- AI 响应诊断：finish_reason={plain(response['finish_reason'])}；有正文={response['has_content']}；有思考内容={response['has_reasoning']}（不保存思考正文）。")
    lines += ["- " + plain(error) for error in ai.get("errors", [])]
    lines += ["- " + plain(notice) for notice in ai.get("notices", [])]
    lines.append("AI 只处理已提取的公开来源片段；没有浏览或执行能力，不决定收录，也不证明工程、成片或授权已验证。有效缓存可能来自早先运行，生成日期见各条建议。")
    state_url = f"https://github.com/{repository}/blob/{config['state_branch']}/{STATE_PATH}"
    lines += ["", md_link("完整候选记录与处理状态", state_url), "", "请勿在此 Issue 粘贴密钥、私人素材或账号信息。"]
    body = "\n".join(lines) + "\n"
    # GitHub issues have a 65,536-character body limit. Fail, never silently drop evidence.
    if len(body) > 60000:
        raise ValueError("Weekly digest too large; lower digest_limit")
    return week, body, [c["id"] for c in selected]


def publish_digest(api, repository, week, body):
    marker = f"{MARKER}{week} -->"
    found = None
    # Read all pages; old or closed digests still suppress accidental duplicates.
    for page in range(1, 101):
        batch = api.call(f"/repos/{repository}/issues?" + urlencode({"state": "all", "per_page": 100, "page": page, "sort": "created", "direction": "desc"}))
        for issue in batch:
            if "pull_request" not in issue and (issue.get("body") or "").startswith(marker) and issue.get("user", {}).get("type") == "Bot":
                found = issue
                break
        if found or len(batch) < 100:
            break
    else:
        raise ValueError("Issue scan exceeded limit; refusing to risk a duplicate digest")
    if found:
        # Never overwrite checkboxes, comments or manual edits to an existing report.
        return found["html_url"], False, re.findall(r"^- 记录 ID：`([^`]+)`$", found["body"], re.M)
    issue = api.call(f"/repos/{repository}/issues", "POST", {"title": f"[自动发现] HyperFrames 候选审核 {week}", "body": body})
    return issue["html_url"], True, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["daily", "discover", "publish"], default="daily", help="daily collects and publishes; discover only saves candidates; publish uses saved candidates")
    parser.add_argument("--ai", choices=["auto", "off", "required"], default="auto", help="Optional AI editing; required fails visibly when configuration is absent")
    parser.add_argument("--config", type=Path, default=ROOT / "discovery/config.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "discovery/reviews.json")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "xiaoyingjiang-studio/awesome-hyperframes"))
    parser.add_argument("--state", type=Path, help="Local state file; default: artifacts/discovery/state.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/discovery")
    parser.add_argument("--replay", type=Path, help="Replay captured public API responses without network or writes")
    parser.add_argument("--full", action="store_true", help="Ignore incremental search checkpoints")
    parser.add_argument("--publish", action="store_true", help="Write remote state and, in daily/publish mode, update the default-branch catalog")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Invalid repository")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if args.publish and (not token or args.replay or args.state):
        parser.error("Publishing requires GH_TOKEN/GITHUB_TOKEN and remote state; replay/local state cannot publish")
    config, reviews = read_json(args.config), read_json(args.reviews)
    if config.get("schema_version") != 1 or reviews.get("schema_version") != 1:
        parser.error("Unsupported configuration version")
    if not re.fullmatch(r"automation/[a-zA-Z0-9_-]+", config["state_branch"]):
        parser.error("State branch must be automation/<name>, separate from the default branch")
    for key, minimum, maximum in [("search_pages", 1, 10), ("search_page_size", 1, 100), ("enrich_per_run", 0, 100), ("digest_limit", 1, 30), ("overlap_days", 1, 30)]:
        if not isinstance(config.get(key), int) or not minimum <= config[key] <= maximum:
            parser.error(f"Invalid {key}: expected {minimum}..{maximum}")
    api = GitHub(token, read_json(args.replay) if args.replay else None)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    args.output.mkdir(parents=True, exist_ok=True)
    local_state = args.state or args.output / STATE_PATH
    sha = None
    if args.publish:
        state, sha = load_state(api, args.repository, config["state_branch"])
    else:
        state = validate_state(read_json(local_state)) if local_state.exists() else empty_state()
    known = catalog_urls(config)
    apply_reviews(state, reviews, known)
    if args.mode == "publish" and not state.get("last_run"):
        raise ValueError("No collection record found; run discover first")
    problems = []
    if args.mode != "publish":
        # A monthly unfiltered scan also finds old projects with newly indexed mentions.
        full = args.full or datetime.fromisoformat(now).astimezone(SHANGHAI).day == 1
        problems = collect(api, config, state, now, full)
    apply_reviews(state, reviews, known)
    # Replay must remain offline even when the host has provider credentials.
    ai = ai_review.review_candidates(state, config, now, os.environ, "off" if args.replay else args.ai)
    week, body, selected = render_digest(state, config, now, args.repository)
    (args.output / "weekly-review.md").write_text(body, encoding="utf-8")
    publication = {"status": "preview"}
    catalog_failed = False
    if args.publish:
        # Preserve discoveries even if main publication subsequently fails.
        save_state(api, args.repository, config["state_branch"], state, sha)
        if args.mode in {"daily", "publish"}:
            if problems or ai["status"] in {"failed", "partial"}:
                publication = {"status": "skipped", "reason": "采集或 AI 未完整通过，本次保留已有目录"}
            else:
                try:
                    publication = catalog.publish(api, args.repository, state, config, now, sys.modules[__name__])
                except (ApiError, ValueError, KeyError, OSError) as error:
                    publication = {"status": "failed", "reason": str(error)}
                    catalog_failed = True
    state["last_catalog_run"] = publication
    summary = ["# 定时采集与自动入库", "", f"采集记录：{now}；候选：{len(state['candidates'])}。", "", f"AI：{ai['status']}；请求 {ai['calls']} 次，分析 {ai['reviewed']} 项，缓存 {ai['cache_hits']} 项。", "", "自动目录：" + plain(json.dumps(publication, ensure_ascii=False), 1500), "", md_link("查看默认分支完整目录", f"https://github.com/{args.repository}/blob/HEAD/catalog/README.md"), ""]
    summary += ["- " + plain(note, 500) for note in [*problems, *(state.get("last_run") or {}).get("warnings", []), *ai["errors"], *ai.get("notices", [])]]
    if publication.get("commit"):
        summary += ["", md_link("本次自动提交", f"https://github.com/{args.repository}/commit/{publication['commit']}")]
    (args.output / "run-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    local_state.parent.mkdir(parents=True, exist_ok=True)
    local_state.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    warnings = (state.get("last_run") or {}).get("warnings", [])
    print(f"Candidates: {len(state['candidates'])}; source problems: {len(problems)}; enrichment warnings: {len(warnings)}; preview: {args.output / 'weekly-review.md'}")
    for problem in problems:
        print("Source problem: " + problem, file=sys.stderr)
    for warning in warnings:
        print("Enrichment warning: " + warning, file=sys.stderr)
    print(f"AI: {ai['status']}; calls: {ai['calls']}; reviewed: {ai['reviewed']}; cache hits: {ai['cache_hits']}")
    for error in ai["errors"]:
        print("AI problem: " + error, file=sys.stderr)
    print("Catalog: " + json.dumps(publication, ensure_ascii=False))
    # A partial run preserves usable evidence but visibly fails CI instead of claiming success.
    return 1 if problems or ai["status"] in {"failed", "partial"} or catalog_failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ApiError, ValueError, KeyError, OSError) as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        sys.exit(1)
