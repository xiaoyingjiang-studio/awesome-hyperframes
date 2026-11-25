"""Publish evidence-backed, multilingual discoveries in one non-forced main commit."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import quote, urlencode

if __package__:
    from . import ai_review
else:
    import ai_review

START = "<!-- AUTO-CATALOG:START -->"
END = "<!-- AUTO-CATALOG:END -->"
DATA_PATH = "catalog/resources.json"
LANGUAGES = ai_review.LANGUAGES
NAMES = ("English", "简体中文", "日本語", "Español", "Français", "Deutsch", "Português (Brasil)", "한국어")
HOME_PATHS = {lang: "README.md" if lang == "en" else f"i18n/README.{lang}.md" for lang in LANGUAGES}
CATALOG_PATHS = {lang: "catalog/README.md" if lang == "en" else f"catalog/README.{lang}.md" for lang in LANGUAGES}
ALLOWED_PATHS = {DATA_PATH, *HOME_PATHS.values(), *CATALOG_PATHS.values()}
UI = {
    "en": ("Automatic catalog", "Automatically compiled from cited sources, with AI-written summaries. Projects have not been independently run and reuse rights still need checking.", "Browse the full catalog", "No qualifying entries yet; source-backed candidates are processed within the per-run AI budget.", "Resource", "Description", "Sources", "Repository owner / author", "License metadata (unverified)", "Not established", "AI summary", "Back to the homepage"),
    "zh-CN": ("自动资源目录", "按引用来源自动整理，简介由 AI 生成；尚未独立运行工程，复用授权仍须核对。", "浏览完整目录", "暂无符合规则的条目；有来源依据的候选按单次 AI 额度继续处理。", "资源", "简介", "来源", "仓库所有者 / 作者", "许可元数据（未核实）", "尚未确认", "AI 简介", "返回首页"),
    "ja": ("自動カタログ", "引用元に基づいて自動整理し、AI が紹介文を作成します。プロジェクトの実行や再利用権は独立に確認していません。", "全件を見る", "掲載条件を満たす項目はまだありません。出典のある候補を実行ごとの AI 予算内で処理します。", "リソース", "紹介", "出典", "リポジトリ所有者 / 作者", "ライセンス情報（未確認）", "未確認", "AI 紹介文", "ホームに戻る"),
    "es": ("Catálogo automático", "Recopilado automáticamente a partir de las fuentes citadas, con descripciones de IA. Los proyectos no se han ejecutado de forma independiente y los permisos de reutilización requieren revisión.", "Ver el catálogo completo", "Aún no hay entradas aptas; los candidatos con fuentes se procesan dentro del presupuesto de IA por ejecución.", "Recurso", "Descripción", "Fuentes", "Propietario del repositorio / autor", "Datos de licencia (sin verificar)", "Sin confirmar", "Descripción de IA", "Volver al inicio"),
    "fr": ("Catalogue automatique", "Compilation automatique des sources citées, avec des descriptions rédigées par l’IA. Les projets n’ont pas été exécutés indépendamment et les droits de réutilisation restent à vérifier.", "Voir le catalogue complet", "Aucune entrée admissible pour le moment ; les candidats sourcés sont traités dans le budget de l’IA par exécution.", "Ressource", "Description", "Sources", "Propriétaire du dépôt / auteur", "Métadonnées de licence (non vérifiées)", "Non établi", "Description par l’IA", "Retour à l’accueil"),
    "de": ("Automatischer Katalog", "Automatisch aus den genannten Quellen zusammengestellt, mit KI-Beschreibungen. Die Projekte wurden nicht unabhängig ausgeführt; Nutzungsrechte müssen noch geprüft werden.", "Vollständigen Katalog öffnen", "Noch keine geeigneten Einträge; belegte Kandidaten werden innerhalb des KI-Budgets pro Lauf verarbeitet.", "Ressource", "Beschreibung", "Quellen", "Repository-Inhaber / Autor", "Lizenzmetadaten (ungeprüft)", "Nicht festgestellt", "KI-Beschreibung", "Zur Startseite"),
    "pt-BR": ("Catálogo automático", "Compilado automaticamente a partir das fontes citadas, com descrições de IA. Os projetos não foram executados de forma independente e os direitos de reutilização precisam ser verificados.", "Ver o catálogo completo", "Ainda não há entradas aptas; candidatos com fontes são processados dentro do orçamento de IA por execução.", "Recurso", "Descrição", "Fontes", "Proprietário do repositório / autor", "Metadados de licença (não verificados)", "Não confirmado", "Descrição de IA", "Voltar ao início"),
    "ko": ("자동 카탈로그", "인용된 출처를 바탕으로 자동 정리하며 소개는 AI가 작성합니다. 프로젝트를 독립적으로 실행하지 않았으며 재사용 권한은 별도 확인이 필요합니다.", "전체 카탈로그 보기", "아직 조건에 맞는 항목이 없습니다. 출처가 있는 후보를 실행별 AI 예산 내에서 처리합니다.", "자료", "소개", "출처", "저장소 소유자 / 작성자", "라이선스 메타데이터 (미확인)", "확인되지 않음", "AI 소개", "홈으로 돌아가기"),
}
CATEGORY_ORDER = ("作品与案例", "案例与模板", "模板与组件", "工具与集成产品", "教程与学习资源", "项目（待分类）")
CATEGORY_LABELS = {
    "en": ("Videos & examples", "Examples & templates", "Templates & components", "Tools & integrations", "Tutorials & learning", "Projects"),
    "zh-CN": CATEGORY_ORDER,
    "ja": ("動画と制作例", "制作例とテンプレート", "テンプレートとコンポーネント", "ツールと連携", "チュートリアルと学習", "プロジェクト"),
    "es": ("Vídeos y ejemplos", "Ejemplos y plantillas", "Plantillas y componentes", "Herramientas e integraciones", "Tutoriales y aprendizaje", "Proyectos"),
    "fr": ("Vidéos et exemples", "Exemples et modèles", "Modèles et composants", "Outils et intégrations", "Tutoriels et apprentissage", "Projets"),
    "de": ("Videos und Beispiele", "Beispiele und Vorlagen", "Vorlagen und Komponenten", "Werkzeuge und Integrationen", "Anleitungen und Lernen", "Projekte"),
    "pt-BR": ("Vídeos e exemplos", "Exemplos e modelos", "Modelos e componentes", "Ferramentas e integrações", "Tutoriais e aprendizado", "Projetos"),
    "ko": ("영상과 예제", "예제와 템플릿", "템플릿과 구성 요소", "도구와 연동", "튜토리얼과 학습", "프로젝트"),
}


def strip_managed(text):
    return re.sub(re.escape(START) + r".*?" + re.escape(END), "", text, flags=re.S)


def replace_managed(text, body):
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise ValueError("Homepage must contain one intact AUTO-CATALOG marker pair")
    before, rest = text.split(START)
    _, after = rest.split(END)
    return before + START + "\n\n" + body.rstrip() + "\n\n" + END + after


def validate_entry(entry, core):
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"].startswith("url:") or not core.canonical_url(entry["id"][4:]) or not core.canonical_url(entry.get("url", "")):
        raise ValueError("Invalid automatic catalog resource identity")
    if entry.get("category") not in ai_review.CATEGORIES or entry.get("verification") != "source-text-only":
        raise ValueError("Invalid automatic catalog category or verification boundary")
    try:
        ai_review.validate_summaries(entry.get("summaries"))
    except ai_review.ReviewError as error:
        raise ValueError("Invalid catalog translations: " + str(error)) from None
    if not isinstance(entry.get("title"), str) or not 1 <= len(entry["title"]) <= 160:
        raise ValueError("Invalid automatic catalog title")
    evidence = entry.get("evidence")
    if not isinstance(evidence, list) or not evidence or not any(not e.get("id", "").startswith("github-search:") for e in evidence):
        raise ValueError("Automatic catalog requires original-source evidence")
    for source in evidence:
        if not isinstance(source.get("id"), str) or not core.canonical_url(source.get("url", "")):
            raise ValueError("Invalid automatic catalog evidence")
    datetime.fromisoformat(entry["ai"]["generated_at"])


def update_resources(previous, state, manual_urls, core):
    if not isinstance(previous, dict) or previous.get("schema_version") != 1 or not isinstance(previous.get("resources"), dict):
        raise ValueError("Invalid automatic catalog; refusing to reset it")
    resources = dict(previous["resources"])
    for key, entry in resources.items():
        validate_entry(entry, core)
        if key != entry["id"]:
            raise ValueError("Automatic catalog key/identity mismatch")
    for candidate in state["candidates"].values():
        key = candidate["id"]
        review = ai_review.current_review(candidate)
        blocked = candidate["status"] in {"rejected", "watch", "listed"} or candidate["url"] in manual_urls
        if blocked or (review and review["relevance"] != "supported"):
            resources.pop(key, None)
            continue
        if not review or review["relevance"] != "supported":
            continue
        sources = [e for e in candidate["evidence"] if e["id"] in review["evidence_ids"]]
        if not any(not e["id"].startswith("github-search:") for e in sources):
            continue
        # Read dates change on every scan. Avoid commits when the substantive input
        # and its validated AI output have not changed.
        old = resources.get(key)
        ai = {field: review[field] for field in ("model", "generated_at", "input_hash", "prompt_version")}
        if old and old["ai"] == ai and old["url"] == candidate["url"]:
            continue
        entry = {"id": key, "url": candidate["url"], "title": candidate["title"], "category": review["category"], "entry": review["entry"], "origin": candidate["origin"], "summaries": review["summaries"], "author": candidate.get("author"), "license_spdx": candidate.get("license_spdx"), "evidence": [{field: e[field] for field in ("id", "url", "detail", "observed_at", "blob_sha")} for e in sources], "verification": "source-text-only", "ai": ai}
        validate_entry(entry, core)
        resources[key] = entry
    # A URL can appear in more than one discovery source; publish it only once.
    unique = {}
    for key, entry in sorted(resources.items()):
        normalized = core.canonical_url(entry["url"])
        if normalized not in unique or entry["ai"]["generated_at"] > unique[normalized][1]["ai"]["generated_at"]:
            unique[normalized] = (key, entry)
    return {key: entry for key, entry in sorted(unique.values())}


def render(resources, language, core, homepage=False):
    ui = UI[language]
    entries = sorted(resources.values(), key=lambda e: (e["ai"]["generated_at"], e["id"]), reverse=True)
    if homepage:
        prefix = "" if language == "en" else "../"
        lines = ['<a id="automated-catalog"></a>', "", "## " + ui[0], "", ui[1], "", f"[{ui[2]} ({len(entries)})]({prefix}{CATALOG_PATHS[language]})", ""]
        if entries:
            lines += [f"| {ui[4]} | {ui[5]} |", "| --- | --- |"]
            lines += [f"| {core.md_link(e['title'], e['url'])}<br><sub>{CATEGORY_LABELS[language][CATEGORY_ORDER.index(e['category'])]}</sub> | {core.plain(e['summaries'][language], 240)} |" for e in entries[:10]]
        else:
            lines.append(ui[3])
    else:
        lines = ["# " + ui[0], "", ui[1], ""]
        lines += [" · ".join(f"**{name}**" if lang == language else f"[{name}]({PurePosixPath(CATALOG_PATHS[lang]).name})" for lang, name in zip(LANGUAGES, NAMES)), "", f"[{ui[11]}](../{HOME_PATHS[language]}#automated-catalog)", ""]
        if not entries:
            lines += [ui[3], ""]
        for category, label in zip(CATEGORY_ORDER, CATEGORY_LABELS[language]):
            group = [entry for entry in entries if entry["category"] == category]
            if group:
                lines += ["## " + label, ""]
            for entry in group:
                lines += ["### " + core.md_link(entry["title"], entry["url"]), "", core.plain(entry["summaries"][language], 240), "", f"- {ui[7]}: {core.plain(entry.get('author') or ui[9])}", f"- {ui[8]}: {core.plain(entry.get('license_spdx') or ui[9])}", f"- {ui[6]}: " + " · ".join(core.md_link(e["id"], e["url"]) for e in entry["evidence"]), f"- {ui[10]}: {core.plain(entry['ai']['model'])} · {entry['ai']['generated_at'][:10]}", ""]
    return "\n".join(lines).rstrip() + "\n"


def publish(api, repository, state, config, now, core):
    """Read one main snapshot, preserve manual edits, publish all locales atomically."""
    repo = api.call(f"/repos/{repository}")
    branch = repo["default_branch"]
    if branch == config["state_branch"]:
        raise ValueError("Catalog branch must differ from discovery-state branch")
    ref_path = f"/repos/{repository}/git/refs/heads/{quote(branch, safe='/')}"
    head = api.call(ref_path)["object"]["sha"]
    commit = api.call(f"/repos/{repository}/git/commits/{head}")
    base_tree = commit["tree"]["sha"]
    cache = {}

    def read(path, optional=False):
        if path not in cache:
            try:
                result = api.call(f"/repos/{repository}/contents/{quote(path, safe='/')}?" + urlencode({"ref": head}))
                cache[path] = core.decode_file(api, repository, result)
            except core.ApiError as error:
                if not optional or error.status != 404:
                    raise
                cache[path] = None
        return cache[path]

    homes = {lang: read(path) for lang, path in HOME_PATHS.items()}
    # Validate all boundaries before even creating a Git tree or commit object.
    for text in homes.values():
        replace_managed(text, "")
    tree = api.call(f"/repos/{repository}/git/trees/{base_tree}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Repository tree truncated; refusing incomplete catalog deduplication")
    manual_urls = set()
    for item in tree["tree"]:
        # Match repository-root patterns, not pathlib's basename-only suffix match:
        # catalog/README.md must never count as a manually selected root README.
        if item["type"] == "blob" and any(len(PurePosixPath(item["path"]).parts) == len(PurePosixPath(pattern).parts) and PurePosixPath(item["path"]).match(pattern) for pattern in config["catalog_files"]):
            text = strip_managed(read(item["path"]))
            manual_urls.update(url for match in core.LINK.finditer(text) if (url := core.canonical_url(match[2])))
    raw = read(DATA_PATH, optional=True)
    previous = json.loads(raw) if raw is not None else {"schema_version": 1, "resources": {}}
    resources = update_resources(previous, state, manual_urls, core)
    document = {"schema_version": 1, "resources": resources}
    if resources == previous["resources"] and "updated_at" in previous:
        document["updated_at"] = previous["updated_at"]
    else:
        document["updated_at"] = now
    files = {DATA_PATH: json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"}
    for language in LANGUAGES:
        files[HOME_PATHS[language]] = replace_managed(homes[language], render(resources, language, core, homepage=True))
        files[CATALOG_PATHS[language]] = render(resources, language, core)
    if set(files) != ALLOWED_PATHS:
        raise ValueError("Automatic publication attempted an unexpected file path")
    changed = {path: text for path, text in files.items() if read(path, optional=path not in HOME_PATHS.values()) != text}
    old_keys, new_keys = set(previous["resources"]), set(resources)
    report = {"status": "unchanged", "count": len(resources), "added": len(new_keys-old_keys), "removed": len(old_keys-new_keys), "updated": sum(previous["resources"][key] != resources[key] for key in old_keys & new_keys), "branch": branch, "files": len(changed), "commit": None}
    if not changed:
        return report
    tree = api.call(f"/repos/{repository}/git/trees", "POST", {"base_tree": base_tree, "tree": [{"path": path, "mode": "100644", "type": "blob", "content": text} for path, text in sorted(changed.items())]})
    created = api.call(f"/repos/{repository}/git/commits", "POST", {"message": "chore: refresh multilingual catalog", "tree": tree["sha"], "parents": [head]})
    # A non-fast-forward update fails if a maintainer changed main meanwhile.
    # No force, no reset, no automatic retry of an uncertain write.
    api.call(ref_path, "PATCH", {"sha": created["sha"], "force": False})
    report.update(status="published", commit=created["sha"])
    return report
