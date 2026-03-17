# Claude Code Hotfix Skills

生产环境自动化错误处理和代码修复的 Claude Code Skills 集合。

## 简介

这是一套用于 Claude Code 的 skills，用于自动化处理生产环境的错误告警和日志分析，并能自动执行代码修复。

## 功能特性

- **自动错误分析**: 解析告警信息和原始日志，自动分析错误根因
- **traceId 追踪**: 支持通过 traceId 追踪完整的错误链路
- **跨应用分析**: 支持分析跨应用的错误传播链
- **自动代码修复**: 可选的自动代码修复功能，从 master 创建分支、修复代码、创建 PR
- **重复修复检测**: 防止短时间内重复触发相同修复
- **最小化修改**: 代码修复遵循最小化修改原则

## Skills 结构

```
ai-hotfix/
├── hotfix-dispatcher/          # 入口调度器 - 自动识别输入类型并分发
│   └── SKILL.md
├── hotfix-from-alert/          # 处理告警信息
│   └── SKILL.md
├── hotfix-from-raw-log/        # 处理原始日志
│   └── SKILL.md
├── hotfix-perform-bugfix/      # 执行代码修复
│   └── SKILL.md
├── hotfix-common/              # 公共配置和脚本
│   ├── config.json             # 配置文件 (需自行配置)
│   ├── app-repo-mapping.txt.example  # 应用仓库映射示例
│   └── scripts/
│       ├── query_sls_logs.py   # SLS 日志查询脚本
│       └── requirements.txt    # Python 依赖
└── README.md
```

## 安装

### 1. 克隆到 Claude Code skills 目录

```bash
# 克隆仓库
git clone https://github.com/your-org/ai-hotfix.git

# 复制到 Claude Code skills 目录
cp -r ai-hotfix/* ~/.claude/skills/
```

### 2. 安装 Python 依赖

```bash
cd ~/.claude/skills/hotfix-common/scripts

# 创建虚拟环境
python3 -m venv .venv

# 安装依赖
.venv/bin/pip install -r requirements.txt
```

### 3. 配置

创建配置文件 `~/.claude/skills/hotfix-common/config.json`:

```json
{
  "appRepoMappingFile": "/path/to/your/app-repo-mapping.txt",
  "sshKeyPath": "~/.ssh/id_rsa",
  "localWorkDir": "~/hotfix-workspace",
  "sls": {
    "project": "your-sls-project-name"
  }
}
```

创建应用仓库映射文件:

```
# 格式: app-name:git@your-git-server.com:org/repo.git
demo-app:git@github.com:your-org/demo-app.git
user-service:git@github.com:your-org/user-service.git
```

## 使用方法

### 方式一：处理告警信息

向 Claude Code 提供告警信息:

```
[AUTOFIX]
环境: prod
应用名称: demo-app
监控项名称: 错误率-/api/demo-app/users
触发时间: 2026-03-12 11:28:22
```

### 方式二：处理原始日志

向 Claude Code 提供原始日志:

```
[AUTOFIX]
_container_name_: demo-app
_time_: 2026-03-13T15:22:36+08:00
content: 2026-03-13 15:22:35 ERROR [trace-id-123] com.example.demo.Service - error...
```

### 标识说明

| 标识 | 作用 | 使用场景 |
|------|------|----------|
| `[AUTOFIX]` | 自动提交代码、创建 PR | 线上自动化运行 |
| `[TEST_MODE]` | 跳过重复检测 | 测试时完整执行流程 |
| 无标识 | 只给出修复建议 | 工作人员手动分析 |

## 工作流程

```
输入（告警或日志）
    ↓
识别输入类型
    ├─ 告警信息 → hotfix-from-alert
    └─ 原始日志 → hotfix-from-raw-log
           ↓
      检测重复修复
           ↓
      查询日志
           ↓
      克隆代码仓库
           ↓
      分析错误根因
           ↓
      needFix?
           ├─ false → 输出报告
           └─ true  → autoFix?
                         ├─ true  → 执行自动修复
                         └─ false → 输出修复建议
```

## 输出示例

```json
{
  "appName": "demo-app",
  "error": "NullPointerException at DemoClient.java:162",
  "cause": "dto.getStatus() 返回 null",
  "needFix": true,
  "fix": "使用常量.equals(variable)模式避免NPE",
  "fixBranch": "hotfix/bugfix-20260316170000",
  "fixCommit": "abc1234",
  "fixStatus": "success"
}
```

## 依赖

- Python 3.8+
- Git
- GitHub CLI (可选，用于创建 PR)
- 阿里云 SLS SDK

## 注意事项

1. **安全性**: 自动修复仅处理简单明确的代码问题，复杂问题需要人工介入
2. **审核**: 自动提交的代码必须经过人工 review
3. **最小化修改**: 遵循最小化修改原则，不做额外改动
4. **权限**: 需要配置 Git SSH 密钥和相关仓库访问权限

## 许可证

MIT License