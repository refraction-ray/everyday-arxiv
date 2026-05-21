# arXiv Daily PRD

Last updated: 2026-05-21

## 1. Product Goal

构建一个面向量子信息研究者的每日 arXiv 阅读助手。它每天抓取指定日期和类别的 arXiv 新论文，根据用户过往论文、研究兴趣、技术能力和偏好筛选出最值得阅读的论文，并支持后续精读、科研想法生成和引用遗漏检查。

项目本身不是一个科研项目仓库，而是一个可复用、可开源的日常科研信息流工作台。公开仓库只保留通用代码、模板和流程说明；用户画像、论文列表、报告、缓存和 Google Scholar 抓取结果保留在本地私有文件中。

## 2. Primary Users

目标用户是希望每天高效跟踪 arXiv、尤其是量子信息相关论文的研究者。用户有自己的过往论文、研究兴趣、擅长的解析或数值方法，以及明确的科研品味。

## 3. Core Requirements

### 3.1 Agent Guidance

项目需要一个 `agents.md`，记录整个项目运行框架、注意事项、文件边界和 agent 应遵循的科研判断标准。每次 agent 工作前都应优先读取该文件。

### 3.2 User Profile

项目需要维护用户画像目录 `user_profile/`，包括：

- 用户以前文章的题目、摘要、arXiv ID、DOI、关键词和备注。
- 用户当前 research interests。
- 用户擅长的 skills，例如解析推导、数值方法、特定理论工具或代码能力。
- 用户对推荐和 idea 的反馈，用于持续更新画像。
- 用户不喜欢的低价值方向或平庸扩展。
- 稀疏高价值 idea 可维护为本地私有结构化日志，便于去重、反馈和后续推进。

用户画像需要区分公开模板和本地私有文件。公开模板可开源，本地用户文件不可开源。

### 3.3 arXiv Fetching

项目需要固化一个 Python 工具，用于抓取 arXiv 元数据。

功能要求：

- 默认抓取当天论文。
- 用户可指定日期。
- 默认类别为量子相关类别，初始为 `quant-ph`。
- 用户可指定一个或多个 arXiv category。
- 抓取结果落盘为稳定 JSON 缓存，供 agent 后续读取。
- 抓取代码应是确定性工具，不承担复杂科研判断。

### 3.4 Interest Recommendation

Agent 读取 arXiv 缓存和用户画像后，筛选出最相关、最值得用户阅读的论文。

要求：

- 默认推荐最多 10 篇。
- 如果当天强相关论文不足 10 篇，不强行凑满。
- 每篇推荐都应给出具体推荐理由。
- 推荐标准应结合用户过往论文、当前兴趣、方法能力和科研偏好。
- 排序应优先考虑“值得用户花时间读”的程度，而不是只做关键词匹配。

### 3.5 Close Reading

在推荐后，Agent 可以进一步下载或在线读取论文，做有针对性的精读和分析。

精读输出应包括：

- 论文核心贡献。
- 与用户兴趣和过往工作的具体关系。
- 用户为什么需要读它。
- 有哪些技术细节值得关注。
- 是否可能启发后续研究方向。

### 3.6 Research Idea Generation

Idea 生成属于兴趣推荐/精读流程的一部分，但必须稀疏。

要求：

- 不要求每篇推荐论文都生成 idea。
- 只有当论文非常 promising 时才生成 idea。
- 目标是保持科研想法高价值、低频、非平庸。
- 避免“加噪声”“换系统”“做更大数值”等泛泛扩展。
- 好 idea 应该是非平庸的 A + B 组合：新论文的技术、setup 或观察与用户过往工作、某个著名 setup 或用户擅长方法发生独特结合，从而打开一个具体且可操作的新问题。

好 idea 的形式应接近：

> 这篇论文的技术 A 可以和用户之前工作的 setup B 结合，用来研究 C；这个组合非平庸是因为 D，使得问题 E 变得可做。

### 3.7 Citation Check

系统需要支持引用检查模式：发现新论文是否与用户之前论文强相关，并检查它是否引用了用户相应论文。

要求：

- 只对强相关论文触发 citation check。
- Agent 应仔细检索论文正文和参考文献。
- 如果明显应引用但未引用用户论文，应主动提示。
- 输出应包括相关用户论文、相关性理由、检查依据和风险判断。
- 如果适合联系作者，应准备一封礼貌、事实性、非指责性的邮件草稿。

Citation check 不是独立取代推荐的流程，而是可附加在每日推荐流程上的模式。

## 4. Skill Design

未来计划固化为两个 Skill。

### 4.1 User Bootstrap

目标：初始化和持续维护用户画像。

输入可以包括：

- Google Scholar profile。
- 用户提供的论文列表。
- 论文题目和摘要。
- 用户手写研究兴趣。
- 用户对推荐和 idea 的反馈。

输出包括：

- `user_profile/papers.local.jsonl`
- `user_profile/research_interests.local.md`
- `user_profile/ideas.local.jsonl`，可选，用于持久化高价值 idea。

该 Skill 应能从用户论文中提取研究主题、方法能力、关键词、引用检查锚点和负面偏好。

Google Scholar 中可能包含 APS March Meeting 摘要、专利、空 venue 条目等非正式论文记录。默认应从推荐画像 `papers.local.jsonl` 中排除这些条目，但在原始私有导出中完整保留，以便用户需要时手动恢复或单独分析。

Google Scholar 会对自动访问进行限流。User Bootstrap 应把 HTTP 429 或 unusual-traffic 页面视为正常失败模式，并给出明确降级路径：降低请求频率、只导出列表页、等待后重试，或让用户手动保存公开 profile HTML 再用 `--from-html` 离线解析。

### 4.2 ArXiv Daily

目标：运行每日 arXiv 阅读流程。

输入包括：

- 日期，默认当天。
- arXiv categories，默认 `quant-ph`。
- 模式。
- 用户画像。

模式至少包括：

- `recommend`: 兴趣匹配、推荐、必要精读、稀疏 idea 生成。
- `recommend+citation_check`: 在 `recommend` 基础上增加强相关论文的引用检查和邮件草稿。

## 5. Open-Source Boundary

应维护一个可开源的通用部分。

可开源：

- `agents.md`
- `README.md`
- `docs/`
- `src/`
- `config/default.toml`
- `config/local.example.toml`
- `user_profile/*.template.*`
- `user_profile/*.example.*`
- `user_profile/ideas.example.jsonl`
- `environment.yml`
- `pyproject.toml`

不可开源：

- `config/local.toml`
- `user_profile/*.local.*`
- Google Scholar 抓取结果。
- 用户真实论文列表、摘要和研究兴趣。
- 用户本地 idea 日志。
- arXiv 原始缓存。
- Agent 生成的每日报告。
- 下载的 PDF、提取出的正文和引用列表。

本地私有文件应通过 `.gitignore` 保护。逻辑上，本地文件覆盖或补充公开模板。

## 6. Quality Requirements

Python 代码应通过：

- Black。
- Pylint。

项目应有 Conda 环境配置，便于复现运行工具链。

## 7. Initial Implementation Scope

当前阶段先实现：

- 项目文件结构。
- agent 运行说明。
- 用户画像模板和本地文件约定。
- arXiv 元数据抓取 CLI。
- Google Scholar 用户论文初始化 CLI。
- JSON 缓存格式。
- 未来 Skill 设计文档。
- Black/Pylint 环境和检查配置。

暂不强制实现：

- 自动全文下载和 PDF 解析。
- 自动推荐排序算法。
- 自动引用列表解析。
- 自动 Skill 打包。

这些应在工作流稳定后再逐步固化。

## 8. Open Questions

- Google Scholar 初始化是否使用浏览器自动化、第三方库，还是用户导出数据。
- 推荐阶段是否需要维护历史推荐日志，避免重复推荐已读论文。
- 是否需要支持除 arXiv 外的 Semantic Scholar、INSPIRE、OpenReview 或出版社页面。
- Citation check 的证据阈值需要用户进一步校准。
- 是否需要将 daily reports 进一步结构化为 JSON，便于长期统计。
