# Contributing

[English](CONTRIBUTING.en.md) · [简体中文](CONTRIBUTING.md)

Recommend a resource through the [submission form](https://github.com/xiaoyingjiang-studio/awesome-hyperframes/issues/new/choose), or open a pull request. Search the catalog and existing issues first to avoid duplicates.

## What belongs here

- Videos with an original source and a useful explanation of how they were made.
- Accessible projects, reusable templates, components and production workflows.
- Tutorials with a clear audience, practical value and honest verification boundaries.
- Tools and products with evidence of an actual HyperFrames relationship. State account requirements, payment conditions and any affiliation.

Paid resources are welcome when their conditions are clear. Link to the author's pricing and licensing pages rather than copying prices that may change. Promotional claims alone, unrelated projects, unauthorized copies and invented test results do not qualify.

## Submit an entry

1. Add a concise entry to the appropriate category. Preserve the resource's original name and link to its original author.
2. Explain what it does and what someone can learn or reuse. Identify the entry point: Studio, HyperFrames framework or another integration.
3. Link to the video, source project and original licenses where available. Distinguish inspiration from a reproducible template.
4. State what was checked: links, the author's published records or work actually performed by the maintainer. Include dates and versions for practical checks. Do not claim a video was watched or a project rendered unless that happened.
5. Check Markdown, relative links and external destinations. Maintainers review the source, attribution and scope before merging.

Suggested format:

```markdown
- [Original resource name](original-url) — Purpose and practical reference value. Author: …; entry point: Studio / framework / other; source: available / unavailable; license: original license link; verification: links checked / author record / maintainer execution (date, version).
```

Detailed examples follow the [example record format](examples/README.md) (Chinese). Link to the original project instead of copying its code, media, fonts or installation files.

## Languages

The English [README](README.md) is the primary catalog. The [translated editions](i18n/README.md) cover the same resources and keep the same verification and licensing boundaries. When an entry changes, update its translations and keep resource names, source links and language labels consistent. Please keep substantive translation changes reviewable.

## Discovery and review

Automation collects leads, deduplicates them and directly updates the default branch each day. Entries need original-source evidence, a supported relationship and validated summaries in all eight catalog languages. They appear in the automatic catalog and the managed homepage sections without a weekly issue or a manual merge. Automatic publication does not establish that a project works or that reuse is permitted.

Maintain exclusion decisions through [reviews.json](discovery/reviews.json), following the [discovery guide](discovery/README.md) (Chinese). Rejected and deferred leads retain their reasons and are removed from the automatic catalog on its next successful update. Handpicked highlights and external submissions still follow maintainer review; the workflow does not automatically merge external pull requests.

The `AUTO-CATALOG` sections and `catalog/` files are generated. Put handpicked entries outside those sections and let the publisher deduplicate them. A publication updates all languages in one non-forced commit, preserves handwritten content and does not create a commit when nothing changed.

Record access problems with their dates and symptoms. A 403, 429 or login requirement does not establish that a resource is unavailable. Preserve attribution and the original licenses. Never submit credentials, account information or private materials.
