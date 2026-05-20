## Agent skills

### Issue tracker

本地 Markdown 问题追踪器，问题文件存放在 `.scratch/` 目录下。See `docs/agents/issue-tracker.md`.

### Triage labels

使用五个标准分类标签。See `docs/agents/triage-labels.md`.

### Domain docs

单上下文布局 — 根目录下 `CONTEXT.md` + `docs/adr/`。See `docs/agents/domain.md`.

## OpenCode Commands

已从 Claude Code 移植 75 个斜杠命令到 OpenCode，在全局 `~/.config/opencode/opencode.json` 中注册。核心命令包括：

| 命令 | 用途 |
|---|---|
| `/plan` | 创建分步实施计划 |
| `/plan-prd` | 生成 PRD 文档 |
| `/code-review` | 代码审查（本地或 PR） |
| `/review-pr` | GitHub PR 审查 |
| `/build-fix` | 修复构建/类型错误 |
| `/pr` | 创建 GitHub PR |
| `/cost-report` | 成本报告 |
| `/python-review` | Python 代码审查 |
| `/fastapi-review` | FastAPI 专项审查 |
| `/refactor-clean` | 安全删除死代码 |
| `/test-coverage` | 分析测试覆盖率 |
| `/checkpoint` | 工作流检查点 |
| `/feature-dev` | 功能开发工作流 |
| `/aside` | 不中断当前任务快速提问 |
| `/quality-gate` | 运行质量流水线 |
| `/security-scan` | Agent 安全扫描 |
| `/skill-create` | 从 Git 历史提取技能 |
| `/skill-health` | 技能健康检查 |
| `/evolve` | 进化本能为技能/命令 |
| `/learn` / `/learn-eval` | 从会话提取模式 |
| `/save-session` / `/resume-session` | 会话管理 |
| `/sessions` | 管理会话历史 |
| `/project-init` | 项目栈检测与 ECC 引导 |
| `/harness-audit` | 仓库评估评分 |
| `/multi-*` | 多模型协作开发 |
| `/gan-*` | 生成器/评估器构建循环 |
| `/santa-loop` | 双模型对抗审查 |
| `/loop-start` / `/loop-status` | 自治循环管理 |
| `/model-route` | 模型分层推荐 |
| `/prp-*` | PRP 工作流系列 |
| `/hookify*` | Hook 规则管理 |
| `/instinct-*` / `/prune` / `/promote` | 本能系统管理 |
| `/jira` | Jira 工单操作 |
| `/pm2` | PM2 服务配置 |
| `/update-codemaps` / `/update-docs` | 文档同步 |
| `/setup-pm` | 配置包管理器 |
| `/ecc-guide` | ECC 功能导航 |
| `/auto-update` | ECC 更新 |
| `/cpp-*` `/rust-*` `/go-*` `/flutter-*` `/kotlin-*` | 语言专项工具 |

**技能 (Skills)** 已自动从 `~/.claude/skills/` 加载，包括 ECC 全系列技能、Matt Pocock 技能等。

使用 `/command-name` 即可调用。
