# 自动发现与候选审核

本流程为精选目录发现线索：每天采集，每周生成一个审核 Issue，由维护者决定是否收录。自动任务不修改正式目录、不合并投稿、不执行第三方工程，也不将链接或文字读取写成成片、Studio 或渲染实测。

## 数据来源与范围

[config.json](config.json) 配置以下来源：

- GitHub 公开仓库搜索：名称、描述或 README 提及 HyperFrames / hyperframes-studio 的非 fork、未归档项目。命中只能说明可能相关。
- 官方 [ADOPTERS.md](https://github.com/heygen-com/hyperframes/blob/main/ADOPTERS.md)：提取产品入口和使用说明，保留“探索使用”等原始措辞；不提取联系人邮箱。
- 官方 [registry.json](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json)：初始只发现 `hyperframes:example`，避免组件索引淹没审核队列。可通过 `types` 增加 `hyperframes:block`、`hyperframes:component`。
- 官方 [hyperframes-launches](https://github.com/heygen-com/hyperframes-launches)：提取作品工程及 README 提供的成片入口。

仓库搜索结果每天最多读取每个查询 2 页、每页 30 项；超过单次预算时保存分页进度，下次续查。README 补充读取最多 15 个项目；每周推荐最多 15 项。旧候选轮流进入推荐和补充读取队列。资源类型为建议，Studio / 框架入口仍需审核。没有使用星标作质量排名，也没有调用 AI 或商业搜索服务。

此版本不覆盖全网、私有社区、登录后的 Studio 作品和全部闭源产品。外部资源仍可通过[投稿表单](../.github/ISSUE_TEMPLATE/submit-resource.yml)提供，人工按现有贡献流程处理。视频播放、外部官网访问、链接健康巡检、工程渲染及自动生成收录 PR 不属于本版已实现的验证。

## 工作流与启用

工作流为 [discover.yml](../.github/workflows/discover.yml)。合入 GitHub 默认分支后：

1. 确认仓库允许 GitHub Actions，组织规则允许工作流使用 `contents: write`、`issues: write`，并已启用 Issues。分支规则需允许机器人创建和更新 `automation/discovery-state`。
2. 在 Actions → 自动发现与每周审核 → Run workflow，首次选择 `discover-and-digest`。`full` 可勾选用于补查。
3. 查看运行摘要、名为 `[自动发现] HyperFrames 候选审核 YYYY-Www` 的 Issue，以及 `automation/discovery-state` 分支的 `state.json`。
4. 后续北京时间每天 09:23 采集，周一 10:17 生成周报。每月 1 日采集会忽略增量搜索检查点，补查旧项目。

认证只使用每次任务自动提供的 `GITHUB_TOKEN`，无需新增长期密钥或生产部署凭据。没有申请 PR 审批或合并权限。fork 默认不执行定时写入，但其维护者可以手动触发。

日常任务不需要本地电脑开机。GitHub 的定时任务可能延迟或丢弃；公开仓库长期无活动可能自动停用，维护者需留意 Actions 记录并在需要时手动补跑。工作流文件仅放在本地、未合入默认分支时不会开始定时运行。

模式说明：

| 模式 | 读取外部来源 | 保存远程状态 | 发布每周 Issue |
| --- | --- | --- | --- |
| `discover` | 是 | 是 | 否 |
| `digest` | 否 | 是，应用最新审核决定 | 是 |
| `discover-and-digest` | 是 | 是 | 是 |

表中的写入仅在传入 `--publish` 时发生。`digest` 要求已经存在采集记录。

## 审核与正式收录

审核 Issue 提供来源、原作者自述、工程与演示入口、信息缺口和记录 ID。勾选任务框或关闭 Issue 只用于沟通，不会自动批准资源。

维护者通过 PR 修改 [reviews.json](reviews.json)，例如：

```json
{
  "schema_version": 1,
  "decisions": [
    {
      "id": "url:https://github.com/example/project",
      "status": "rejected",
      "reason": "仅列出工具名称，没有具体项目或使用说明。",
      "reviewed_at": "2026-11-25"
    }
  ]
}
```

请从候选清单复制完整 ID；也可用 `url` 代替 `id`，填写原始入口。仓库改名时优先使用 ID，已发现的 GitHub 仓库通过数字 ID 保留身份。不同工程子目录保持为独立候选。

| 状态 | 含义 |
| --- | --- |
| `accepted` | 维护者认可收录，退出自动推荐；仍需按贡献格式添加正式条目 |
| `rejected` | 拒绝并保留原因，后续不会因再次搜索命中而重复推荐 |
| `watch` | 暂缓推荐，等待信息补齐；维护者主动移除该决定后重新进入队列 |

审核决定不应包含密钥、账号凭据或私人素材。正式收录按 [CONTRIBUTING.md](../CONTRIBUTING.md) 和[案例格式](../examples/README.md)提交同一个或后续 PR。目录中已有的原始入口会被标为 `listed`，不再推荐；相同产品的不同入口仍可能需要维护者判断是否重复。审核决定优先于自动检测，普通文字编辑不会刷新已有实测记录。

同一周再次运行时保留已有周报正文、勾选和评论，不覆盖人工操作；新候选留到下周。若发布 Issue 后保存推荐状态失败，重跑会从原 Issue 恢复推荐 ID，减少重复推荐。已关闭周报也不会被重新创建。请勿删除正文首行的机器标记；需要重新生成时，先明确处理旧 Issue，避免破坏去重依据。

## 状态、异常与边界

正式候选记录保存在独立的 `automation/discovery-state` 分支，由工作流创建为仅包含 `state.json` 的分支。它是持久维护数据，不是网站或部署分支；默认分支只存采集规则、脚本、审核决定及规范。状态记录包括入口、来源文字的短摘录、来源 blob SHA、读取日期、首次发现、信息变化、最近推荐和审核状态；不保存完整第三方 README、工程、视频、字体或安装包。

搜索在上次完整查询日期前回退 3 天，按日期重叠补查并去重。达到单次分页预算时保存进度并在摘要中提示；查询完整结束后，检查点使用本轮开始时间，下一轮补查扫描期间的变化。`full` 会重置续查进度。GitHub 搜索索引和排序会变化，分页结果不是静态快照，不承诺无遗漏。

API 报告结果不完整、超过单个查询 1000 项或请求失败时，不推进该查询的检查点；已获得的候选仍会保存，工作流以失败状态提醒维护者。不完整页在下一次重试。超过 1000 项时需按 `created:` 日期等条件拆分配置中的查询；仅增加分页预算无法绕过平台上限。默认不设置最低星标门槛。

来源改版导致解析不到条目时记录异常，保留旧数据。单个来源失败不清空其他候选；403、429、404 或登录限制不被转换成资源删除或工程不可用结论。当前流程不自动删除失联、迁移或已拒绝资源。状态分支已经存在却丢失 `state.json` 时拒绝重建，需人工恢复文件。

采集任务通过统一并发组串行运行，状态更新使用文件 SHA 防止覆盖冲突。API 读取有有界重试和超时，写请求不自动重试，以免重复创建 Issue。令牌只发送到 GitHub API；资源页面中的命令不会执行，来源文字会转义后放入 Issue。

候选规模较大时可增加查询分页、拆分查询或调整周报数量。状态与 Issue 查询也有大小上限，超限会报错而不静默丢弃记录；届时应迁移或分片。AI 摘要、外部订阅源、链接巡检及批准后自动生成 PR 可在规则稳定后另行扩展。

## 本地预览与检查

需要 Python 3.11 或更新版本，采集脚本只依赖标准库。以下命令不写远程仓库：

```powershell
python -m unittest discover -s tests -v
python scripts/discover.py --mode discover-and-digest --full
python scripts/discover.py --mode digest
```

预览和本地状态默认输出到已忽略的 `artifacts/discovery/`；它们不是正式验证报告，请勿提交。默认本地状态与远程状态分开，预览会复用该目录中的本地状态。`--state` 可指定其他本地状态文件，`--output` 可指定输出目录。

未提供令牌时使用公开 API，可能很快限流；需要较高读取配额时可由环境提供已有的 `GH_TOKEN` 或 `GITHUB_TOKEN`，不要把值写入代码或终端记录。认证读取的结果仍只接受公开仓库。公司网络若有自定义证书，应按其规范配置可信 CA，不要关闭 TLS 验证。

`--replay <文件>` 可回放捕获的公开 API 响应进行离线预览，格式是“API 路径 → JSON 响应”的对象，不允许发布。自动化测试使用合成来源，覆盖来源解析、改名去重、审核保留、检查点失败、周报轮换和状态分支保护；不等于已在线创建 Issue 或渲染任何作品。

相关依据：[GitHub 搜索限制](https://docs.github.com/en/rest/search/search)、[定时触发说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[GITHUB_TOKEN 权限与事件行为](https://docs.github.com/en/actions/concepts/security/github_token)。这些链接说明平台行为，不构成本仓库已成功运行的证明。
