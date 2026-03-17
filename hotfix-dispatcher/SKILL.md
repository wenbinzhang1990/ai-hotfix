---
name: hotfix-dispatcher
description: |
  Production environment error handling entry point. Analyzes error types and dispatches to corresponding processing workflows, supporting automatic code fixes.

  Use cases:
  - User provides alert information (containing fields like "environment", "app name", etc.)
  - User provides raw error logs (containing fields like _container_name_, content, etc.)
  - User mentions "hotfix", "production error", "alert", "error analysis", "log error"

  This skill automatically identifies input type and dispatches:
  - Alert information → hotfix-from-alert
  - Raw logs → hotfix-from-raw-log

  Flag descriptions:
  - `[AUTOFIX]` - Auto commit code and create PR (for automated production runs)
  - `[TEST_MODE]` - Skip duplicate detection, execute full flow (for testing)

  Without flags: If analysis confirms code issue, only provide fix suggestions without auto-commit (for manual analysis)
---

# Hotfix Dispatcher

Production environment error handling orchestrator. Automatically identifies input type, dispatches to corresponding processing skill, and decides whether to execute automatic code fixes based on flags.

## Flag Descriptions

| Flag | Purpose | Use Case |
|------|---------|----------|
| `[AUTOFIX]` | Auto commit code and create PR | Automated production runs |
| `[TEST_MODE]` | Skip duplicate detection | Testing full flow |
| No flag | Only provide fix suggestions | Manual analysis by staff |

**Flag Usage Examples:**

```
[AUTOFIX]
environment: prod
app_name: demo-app
...

[AUTOFIX]
_container_name_: demo-app
...

[TEST_MODE]
_container_name_: demo-app
...

[AUTOFIX][TEST_MODE]
_container_name_: demo-app
...
```

## Configuration

Configuration file location: `~/.claude/skills/hotfix-common/config.json`

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

## Input Type Recognition

### Type 1: Alert Information

Identification features: Contains fields like `environment`, `app_name`, `monitor_item_name`

```
environment: prod
app_name: demo-app
monitor_item_name: error_rate-/api/demo-app/users
assignee: John Doe
current_value: PERCENT: 100%
error_description: non-200 responses in one minute: 1
trigger_time: 2026-03-12 11:28:22
```

→ Dispatches to `hotfix-from-alert`

### Type 2: Raw Error Log

Identification features: Contains fields like `_container_name_`, `content`, `_time_`

```
_container_ip_: 10.0.0.100
_container_name_: demo-app
_time_: 2026-03-13T15:22:36.001334555+08:00
content: 2026-03-13 15:22:35.998 [Handler-thread-1] ERROR [trace-id-123] com.example.demo.ServiceImpl:94 - error...
```

→ Dispatches to `hotfix-from-raw-log`

---

## Workflow

1. **Parse Input** - Identify input type (alert or raw log) and check flags (`[AUTOFIX]`, `[TEST_MODE]`)
2. **Dispatch** - Call corresponding skill (hotfix-from-alert or hotfix-from-raw-log)
3. **Analyze Root Cause** - Determine error type and fix approach
4. **Check if Fix Needed** - Proceed to next step when needFix is true
5. **Check Auto Fix** - Call hotfix-perform-bugfix when autoFix is true
6. **Execute Fix** - Call hotfix-perform-bugfix to perform code fix
7. **Return Result** - Output JSON report

## Complete Flow Diagram

```
Input (alert or log) + Check flags [AUTOFIX] [TEST_MODE]
    ↓
Identify input type
    ├─ Alert info → hotfix-from-alert
    └─ Raw log → hotfix-from-raw-log
           ↓
      Check duplicate fix (non-test mode)
           ├─ Yes (hotfix within 1 hour) → Output report (needFix: false, skipReason: duplicate)
           └─ No → Continue
           ↓
      Query logs
           ↓
      Clone code repository
           ↓
      Analyze error root cause
           ↓
      needFix?
           ├─ false → Output report (no fix needed)
           └─ true  → autoFix?
                         ├─ true  → hotfix-perform-bugfix
                         │               ↓
                         │          Create fix branch from master
                         │               ↓
                         │          Execute code fix
                         │               ↓
                         │          Commit auto-fix
                         │               ↓
                         │          Push branch and create PR
                         │               ↓
                         └─ false → Output fix suggestions (no auto-commit)
                    ↓
              Output report (with fix results)
```

**Test Mode Description:**
- Adding `[TEST_MODE]` flag in input skips duplicate detection
- Used for testing to execute full flow

## Output Format

```json
{
  "appName": "app-name",
  "error": "error message",
  "cause": "root cause analysis",
  "needFix": true/false,
  "fix": "fix suggestion",
  "fixBranch": "branch name (if fixed)",
  "fixCommit": "commit hash (if fixed)",
  "fixDesc": "fix description",
  "fixStatus": "success/skipped",
  "errorChain": [...]  // Only in hotfix-from-raw-log
}
```

## Auto Fix Description

**Auto fix only executes when ALL conditions are met:**
1. `needFix` is true (analysis confirms code issue)
2. Input contains `[AUTOFIX]` flag (for automated production runs)

When above conditions are met, the system automatically:

1. **Create fix branch** - Create independent fix branch from master (format: `hotfix/bugfix-YYYYMMDDHHmmss`)
2. **Execute fix** - Modify code based on analysis (minimal changes)
3. **Commit code** - Auto commit with `(hotfix) [auto-fix]` prefix
4. **Push branch** - Push to remote repository
5. **Create PR** - Create Pull Request for manual review

**Note:** If `needFix` is true but no `[AUTOFIX]` flag, the system only outputs fix suggestions without auto-commit. This applies to manual analysis scenarios.

**Commit Message Example:**
```
(hotfix) [auto-fix] Fix NullPointerException

Problem:
- Location: DemoClient.java:162
- Type: NullPointerException
- Trigger: dto.getStatus() returns null when external API returns empty data

Fix:
- Use constant.equals(variable) pattern to avoid NPE
- Add validation for empty data

Auto-generated by Claude Code Hotfix Skill
```