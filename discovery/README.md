# 定时采集与自动入库

每周三、周日采集公开来源、去重、生成 AI 整理结果，并直接提交默认分支 `main`。**不再按周创建 Issue，不需要人工逐项合并日常更新。** 首页和完整目录同时提供英文、简体中文、日语、西班牙语、法语、德语、巴西葡萄牙语与韩语。

自动目录与人工精选并列展示。自动条目表示来源支持相关性并通过字段检查，不表示维护者已运行工程、观看成片、登录 Studio 或确认复用授权。人工精选与外部投稿仍按[贡献指南](../CONTRIBUTING.md)维护。

## 日常流程

[工作流](../.github/workflows/discover.yml)配置北京时间每周三、周日 **08:00** 执行：

1. 采集官方来源与 GitHub 公开仓库，按规范化原始入口及仓库数字 ID 去重。
2. 轮换补充 README 片段，保存来源、信息缺口与分页进度。
3. AI 整理相关性、分类、参考价值、核实清单及八语种简介。
4. 有原始来源依据、判断为 `supported`、八语种字段完整的条目自动发布；仅搜索命中、证据不足、无关、拒绝及暂缓项不自动发布。
5. 读取最新默认分支快照，合并已有自动目录，排除人工精选的重复入口。
6. **一次非强制提交同步全部语言**。内容无变化不重复提交；不会生成待人工合并的日常 PR。

| 手动模式 | 采集来源 | 保存候选 | 更新默认分支 |
| --- | --- | --- | --- |
| `daily`（默认） | 是 | 是 | 是 |
| `discover` | 是 | 是 | 否 |
| `publish` | 否，使用已有记录 | 是 | 是 |

远程写入需要 `--publish`。旧的每周 `digest` 模式已从 CLI 与工作流移除；旧 Issue 保留历史。GitHub 定时任务可能延迟，不需要本地电脑开机。只允许在默认分支运行；fork 默认不定时写入，可在其默认分支手动启动。

## 成果位置与编辑范围

- 八个首页的 `AUTO-CATALOG:START` / `AUTO-CATALOG:END` 之间：最近十项和完整目录入口。
- [catalog/README.md](../catalog/README.md)及七个译版：全部自动条目、原始链接、简介、作者或仓库所有者、许可元数据、来源和 AI 日期。
- [catalog/resources.json](../catalog/resources.json)：八语种简介与引用证据的结构化记录，保留原资源名和持久 ID。
- `automation/discovery-state` 分支的 `state.json`：完整候选、来源、分页检查点和 AI 缓存，不等于全部已发布。
- Actions 摘要：本次采集、AI 调用、入库数量、变更文件数和自动提交链接。`unchanged` 表示无变化，没有新提交。

不要直接修改受管区域或 `catalog/` 生成文件。手写介绍和人工精选放在标记之外；自动条目转为手工精选后，发布器按原始入口移除自动区域的重复项。目录翻译不表示视频、工程或源文档已本地化。

## 来源与单次额度

[config.json](config.json)配置 GitHub 公开仓库搜索、官方 [ADOPTERS.md](https://github.com/heygen-com/hyperframes/blob/main/ADOPTERS.md)、[registry.json](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json) 的 `hyperframes:example` 和 [hyperframes-launches](https://github.com/heygen-com/hyperframes-launches)。不提取联系人邮箱，保留作者“探索、计划”等限定。

每个查询每次最多 2 页、每页 30 项；最多补充 15 个 README。按日期回退 3 天补查，未完成分页则保存续查进度，不推进完整检查点；每月 1 日补查重置续查范围。搜索索引与排序会变化，不能保证无遗漏。

流程不覆盖全网、私有社区、登录后的 Studio 或全部闭源产品；不自动执行第三方工程、观看成片、镜像媒体或安装软件。搜索结果不完整、请求失败或超过单查询 1000 项时保留检查点并报错；超过 1000 项需按 `created:` 日期等拆分查询，不能靠增加分页绕过限制。

## AI 配置与行为

沿用现有兼容 Chat Completions 服务，不新增供应商账号或 SDK：

| 名称 | Actions 存放位置 | 内容 |
| --- | --- | --- |
| `AI_ENDPOINT` | Variables | 完整 HTTPS `.../chat/completions` 地址 |
| `AI_MODEL` | Variables | 已开通的模型 |
| `AI_API_KEY` | Secrets | 现有 API Key，不写入代码或日志 |
| `AI_MAX_OUTPUT_TOKENS` | Variables，可选 | 单次输出上限 256–12,000，未配置时 6,000 |
| `AI_ENABLE_THINKING` | Variables，可选 | `false`、`true` 或 `auto`，工作流默认 `false` |

默认 `ai: required`，配置缺失明确失败；`auto` 在配置齐全时调用，否则保留规则采集；`off` 不调用。另一个仓库的 repository Secret 不会自动继承，也不能读回明文；组织 Secret 需已允许本仓库访问。现有思考参数沿用[阿里云 DeepSeek 约定](https://help.aliyun.com/zh/model-studio/deepseek-api)，不支持时设 `auto` 不发送该参数。

每批最多 **2 项**，每次最多 **3 次 HTTP 请求**（含重试和格式修正），保守总预算 **60,000**。每批开始前预留首次请求及一次完整修正的次数和预算；通常无须重试时处理两批、共 4 项。剩余候选后续继续，不因正常排队使任务失败；优先分析有 README 或官方片段的候选。

保守预算为输入 UTF-8 字节数加输出 Token 上限，不是实际账单 Token；上下文容量也不等于单次输出上限。超时 60 秒；网络、429、5xx 或格式错误最多重试或修正一次，鉴权、配置和截断错误不重试。真实成本以供应商账单为准。

输入只有公开标题、入口、作者自述和来源短片段，不含凭据、完整第三方文件或私人素材。短编号严格映射回原候选与来源，未知、重复、缺失编号或不存在的引用均拒绝。输出须含八语种单行简介，不接受新增链接、执行结论或许可承诺。来源、模型、提示词版本或思考选项变化会重新排队；读取日期变化不重复调用。

记录模型、日期、输入哈希、来源 ID、安全响应诊断与服务用量，不保存思考正文或不合格输出。AI 没有浏览器或执行工具，其判断不改变人工审核状态。

## 排除与人工精选

维护者可通过 [reviews.json](reviews.json)记录决定，例如：

```json
{
  "schema_version": 1,
  "decisions": [
    {"id": "url:https://github.com/example/project", "status": "rejected", "reason": "只有工具名单，缺少实际使用依据。", "reviewed_at": "2026-11-25"}
  ]
}
```

`rejected` 与 `watch` 在下一次成功发布时移除对应自动条目并保留原因。`accepted` 记录人工认可，但自动发布仍需满足来源与字段要求；人工精选按贡献格式维护。入口已在手工精选中的 `listed` 项不重复发布。可用 `url` 替代 `id`；仓库改名保留数字 ID 对应的原记录，不同工程子目录保留独立入口。自动流程不合并任意外部代码或投稿 PR。

## 写入与异常保护

只需 `contents: write`，已取消 `issues: write`。默认分支规则需允许工作流机器人提交；不允许时明确报错，不强推、不绕过保护，不擅自改成待合并 PR。

发布器只允许改八个首页受管区域、八个目录页和 `catalog/resources.json`。先固定默认分支 SHA，再读取该快照的手写内容，创建提交并非强制快进更新。期间若有维护者提交，则拒绝覆盖，下次从新快照重新整理。不会用过期 checkout 覆盖整个首页。

标记缺失、自动数据损坏、仓库树截断或写入路径越界时停止写入。相同内容重跑不产生重复条目和提交。来源暂时不可读或等待新 AI 结果时，保留此前发布记录及其生成日期；明确排除、转入手工精选或新的有效分析不再支持相关性时才移除。

完整候选先保存到状态分支。主要来源或 AI 出错时，保留已采集候选和此前目录，本次不更新 `main`，以失败状态提示原因。单个 README 补充失败只记录警告，保留候选与 `enrichment_error`，后续轮换重试；403、429、404 或登录限制不直接视为资源失效。

状态或来源超过 Contents API 的 1 MiB 内联范围时按精确 blob SHA 读取 Git Blobs API；状态更新仍使用原文件 SHA。已有状态分支丢失文件时拒绝重建。单次 API 响应上限 4 MiB，超限须分片，不截断记录。令牌只发给 `api.github.com`，写请求不自动重试。

## 本地检查与预览

需要 Python 3.11 或更新版本，仅依赖标准库：

```powershell
python -m unittest discover -s tests -v
python scripts/discover.py --mode daily --ai off
python scripts/discover.py --mode publish --ai off
```

未传 `--publish` 不写远程。预览和本地状态在已忽略的 `artifacts/discovery/`，不是正式验证记录；`run-summary.md` 是当前摘要，`weekly-review.md` 仅保留旧版离线预览文件名，不发布成 Issue。`--state` 与 `--output` 可指定本地路径，不能用本地状态发布。

`--replay <文件>` 回放“API 路径 → JSON 响应”对象，不能发布且始终关闭 AI 网络。测试覆盖来源、八语种、编号绑定、缓存、预算、排除、去重、无变化重跑、并发更新及手写内容保留；不等于调用真实服务或渲染作品。本地认证使用已有环境变量，不将密钥写入命令或历史；自定义证书应配置可信 CA，不关闭 TLS 校验。

依据：[搜索限制](https://docs.github.com/en/rest/search/search)、[定时触发](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[Git refs 更新](https://docs.github.com/en/rest/git/refs#update-a-reference)、[GITHUB_TOKEN 事件行为](https://docs.github.com/en/actions/concepts/security/github_token)。`GITHUB_TOKEN` 提交通常不会再次触发 push 工作流，因此本工作流在发布前运行测试并校验生成数据，不依赖自动提交后另起的 CI。
