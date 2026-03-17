# Claude Code Hotfix Skills

A collection of Claude Code Skills for automated production error handling and code fixes.

## Overview

This is a set of skills for Claude Code that automates processing of production error alerts and log analysis, with optional automatic code fix capabilities.

## Features

- **Automatic Error Analysis**: Parse alert information and raw logs, automatically analyze error root causes
- **TraceId Tracking**: Support for tracking complete error chains via traceId
- **Cross-Application Analysis**: Support for analyzing error propagation across applications
- **Automatic Code Fix**: Optional automatic code fix feature that creates branches from master, fixes code, and creates PRs
- **Duplicate Fix Detection**: Prevents repeated triggers of the same fix within short time periods
- **Minimal Changes**: Code fixes follow the minimal change principle

## Skills Structure

```
ai-hotfix/
├── hotfix-dispatcher/          # Entry dispatcher - auto-identify input type and dispatch
│   └── SKILL.md
├── hotfix-from-alert/          # Process alert information
│   └── SKILL.md
├── hotfix-from-raw-log/        # Process raw logs
│   └── SKILL.md
├── hotfix-perform-bugfix/      # Execute code fix
│   └── SKILL.md
├── hotfix-common/              # Common config and scripts
│   ├── config.json             # Configuration file (configure yourself)
│   ├── app-repo-mapping.txt.example  # App repo mapping example
│   └── scripts/
│       ├── query_sls_logs.py   # SLS log query script
│       └── requirements.txt    # Python dependencies
└── README.md
```

## Installation

### 1. Clone to Claude Code skills directory

```bash
# Clone the repository
git clone https://github.com/your-org/ai-hotfix.git

# Copy to Claude Code skills directory
cp -r ai-hotfix/* ~/.claude/skills/
```

### 2. Install Python dependencies

```bash
cd ~/.claude/skills/hotfix-common/scripts

# Create virtual environment
python3 -m venv .venv

# Install dependencies
.venv/bin/pip install -r requirements.txt
```

### 3. Configuration

Create configuration file `~/.claude/skills/hotfix-common/config.json`:

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

Create app repository mapping file:

```
# Format: app-name:git@your-git-server.com:org/repo.git
demo-app:git@github.com:your-org/demo-app.git
user-service:git@github.com:your-org/user-service.git
```

## Usage

### Method 1: Process Alert Information

Provide alert information to Claude Code:

```
[AUTOFIX]
environment: prod
app_name: demo-app
monitor_item_name: error_rate-/api/demo-app/users
trigger_time: 2026-03-12 11:28:22
```

### Method 2: Process Raw Logs

Provide raw logs to Claude Code:

```
[AUTOFIX]
_container_name_: demo-app
_time_: 2026-03-13T15:22:36+08:00
content: 2026-03-13 15:22:35 ERROR [trace-id-123] com.example.demo.Service - error...
```

### Flag Descriptions

| Flag | Purpose | Use Case |
|------|---------|----------|
| `[AUTOFIX]` | Auto commit code and create PR | Automated production runs |
| `[TEST_MODE]` | Skip duplicate detection | Testing full flow |
| No flag | Only provide fix suggestions | Manual analysis by staff |

## Workflow

```
Input (alert or log)
    ↓
Identify input type
    ├─ Alert info → hotfix-from-alert
    └─ Raw log → hotfix-from-raw-log
           ↓
      Check duplicate fix
           ↓
      Query logs
           ↓
      Clone code repository
           ↓
      Analyze error root cause
           ↓
      needFix?
           ├─ false → Output report
           └─ true  → autoFix?
                         ├─ true  → Execute auto fix
                         └─ false → Output fix suggestions
```

## Output Example

```json
{
  "appName": "demo-app",
  "error": "NullPointerException at DemoClient.java:162",
  "cause": "dto.getStatus() returns null",
  "needFix": true,
  "fix": "Use constant.equals(variable) pattern to avoid NPE",
  "fixBranch": "hotfix/bugfix-20260316170000",
  "fixCommit": "abc1234",
  "fixStatus": "success"
}
```

## Requirements

- Python 3.8+
- Git
- GitHub CLI (optional, for creating PRs)
- Alibaba Cloud SLS SDK

## Notes

1. **Security**: Auto-fix only handles simple, clear code issues. Complex issues require manual intervention
2. **Review**: Auto-committed code must undergo manual review
3. **Minimal Changes**: Follow minimal change principle, no extra modifications
4. **Permissions**: Requires configured Git SSH keys and repository access permissions

## License

MIT License