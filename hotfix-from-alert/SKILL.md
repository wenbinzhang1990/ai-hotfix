---
name: hotfix-from-alert
description: |
  Process production environment alert information. Use this skill when user provides alert data.

  Trigger conditions:
  - User input contains alert fields like "environment", "app_name", "monitor_item_name"
  - Formatted alert message text

  This skill: Extracts app name from alert as logstore to query logs, clones code repository, analyzes error root cause, determines if code fix is needed. If fix needed and [AUTOFIX] flag present, executes bugfix automatically, otherwise provides fix suggestions.

  Flag descriptions:
  - `[AUTOFIX]` - Auto commit code and create PR (for automated production runs)
  - `[TEST_MODE]` - Skip duplicate detection, execute full flow (for testing)

  Without flags: Only provide fix suggestions without auto-commit (for manual analysis)
---

# Hotfix from Alert

Process production environment alert information, query logs, analyze root cause, and decide whether to auto-commit based on flags.

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

[TEST_MODE]
environment: prod
app_name: demo-app
...

[AUTOFIX][TEST_MODE]
environment: prod
app_name: demo-app
...
```

## Configuration

Common configuration file located at `~/.claude/skills/hotfix-common/config.json`

## Workflow

### Step 1: Load Configuration

```bash
CONFIG_FILE="$HOME/.claude/skills/hotfix-common/config.json"
```

### Step 2: Parse Alert Information + Check Flags

Extract from alert:

| Field | Description | Example |
|-------|-------------|---------|
| environment | Environment | prod |
| app_name | Used as SLS logstore | demo-app |
| monitor_item_name | API endpoint | /api/demo-app/users |
| trigger_time | For time range query | 2026-03-12 11:28:22 |

**Also check flags:**
- If alert contains `[AUTOFIX]` flag, set `autoFix = true`
- If alert contains `[TEST_MODE]` flag, set `testMode = true`
- `autoFix = true`: Auto commit code and create PR
- `autoFix = false`: Only provide fix suggestions

**Example alert format:**
```
environment: prod
app_name: demo-app
monitor_item_name: error_rate-/api/demo-app/users
assignee: John Doe
current_value: PERCENT: 100%
error_description: non-200 responses in one minute: 1
trigger_time: 2026-03-12 11:28:22
```

### Step 3: Check Duplicate Fix (Important! Check early)

**Before querying logs, clone repository and check for recent hotfix commits!**

**Detection logic:**

1. **Check test mode** - Skip this step if `[TEST_MODE]` flag present
2. **Clone/enter code repository** - Need repo first to check git history
3. **Check today's hotfix commits**

```bash
# Get today's hotfix commits
git log --all --format="%h %ad %s" --date=format:"%Y-%m-%d %H:%M:%S" \
  --since="$(date +%Y-%m-%d) 00:00:00" \
  --grep="hotfix"
```

**Decision rules:**
- If hotfix commit exists today, and commit time is within **1 hour** from now
- Then consider it as **duplicate fix trigger**

**Handling for duplicate trigger:**
1. **Don't query logs**
2. **Don't create new branch**
3. **Return report directly**, setting:
   - `needFix: false`
   - `fixStatus: "skipped"`
   - `skipReason: "Duplicate fix trigger, hotfix commit within 1 hour"`

**Example output:**
```json
{
  "appName": "demo-app",
  "alertInfo": "error_rate-/api/demo-app/users",
  "error": "...",
  "needFix": false,
  "fixStatus": "skipped",
  "skipReason": "Duplicate fix trigger, hotfix commit within 1 hour (17:08:49)",
  "existingHotfix": {
    "commit": "abc1234",
    "time": "2026-03-16 17:08:49",
    "branch": "hotfix/bugfix-20260316170651"
  }
}
```

### Step 4: Query Logs

Query 5 minutes before and after alert trigger time:

```bash
SCRIPT_PATH="$HOME/.claude/skills/hotfix-common/scripts/query_sls_logs.py"

# Calculate time range (±5 minutes)
FROM_TIME=$(date -j -f "%Y-%m-%d %H:%M:%S" "trigger_time - 5min" +%s)
TO_TIME=$(date -j -f "%Y-%m-%d %H:%M:%S" "trigger_time + 5min" +%s)

python3 "$SCRIPT_PATH" \
  --config "$CONFIG_FILE" \
  --logstore "app_name" \
  --query "ERROR" \
  --from $FROM_TIME \
  --to $TO_TIME \
  --line 100
```

### Step 5: Get Repository URL and Clone

Find and clone from configured mapping file (if not cloned in Step 3):
```bash
REPO_URL=$(grep "^${APP_NAME}:" $appRepoMappingFile | cut -d':' -f2-)

export GIT_SSH_COMMAND="ssh -i $sshKeyPath -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"
git clone $REPO_URL
```

Record the local path after cloning: `$repoPath`.

### Step 6: Analyze Error

Analyze from Java stack trace and source code:
1. Error location: Find code under `com.example.{app-name}` package
2. Error type: NullPointerException, business exception, etc.
3. Root cause analysis: Why did it happen
4. Fix approach: Determine best fix strategy

### Step 7: Determine if Fix Needed

**needFix: true** - Code fix needed:
- NullPointerException missing null check
- Business logic error
- Missing necessary validation

**needFix: false** - No code fix needed:
- Business exception (expected behavior)
- Data issue
- Configuration issue
- External service issue

### Step 8: Execute Auto Fix (when needFix is true and autoFix is true)

**Important: Only call hotfix-perform-bugfix skill when `needFix = true` AND `autoFix = true`!**

**Decision logic:**
- `needFix = true` AND `autoFix = true` → Execute code fix (call hotfix-perform-bugfix)
- `needFix = true` AND `autoFix = false` → Only output fix suggestions
- `needFix = false` → No fix needed, output analysis report

Use Skill tool to call:

```
Skill tool with skill="hotfix-perform-bugfix"
```

Parameters passed to bugfix skill:
- `repoPath`: Local path of code repository
- `errorLocation`: Error location (file:line)
- `errorType`: Error type
- `fixApproach`: Fix approach
- `fixDesc`: Fix description

**Fix flow:**
1. Create fix branch from master (format: hotfix/bugfix-YYYYMMDDHHmmss)
2. Execute code fix (minimal changes)
3. Commit with `(hotfix) [auto-fix]` prefix
4. Push branch and create PR for manual review
5. Return fix result

### Step 9: Output JSON Report

```json
{
  "appName": "app-name",
  "alertInfo": "alert summary",
  "error": "specific error message",
  "cause": "root cause analysis",
  "needFix": true/false,
  "fix": "fix suggestion",
  "fixBranch": "fix branch name (if fixed)",
  "fixDesc": "fix description",
  "fixCommit": "commit hash (if fixed)",
  "fixStatus": "success/skipped (if needFix is false)"
}
```

---

## Complete Flow Diagram

```
Alert Input
    ↓
Step 1: Load configuration
    ↓
Step 2: Parse alert info + Check flags [AUTOFIX] [TEST_MODE]
    ↓
Step 3: Check duplicate fix (clone repo then check git history)
    ├─ Yes (hotfix within 1 hour) → Output report (needFix: false, skipReason: duplicate)
    └─ No → Continue
    ↓
Step 4: Query logs
    ↓
Step 5: Get repo URL and clone (if not cloned in Step 3)
    ↓
Step 6: Analyze error root cause
    ↓
Step 7: needFix?
    ├─ false → Output report (no fix needed)
    └─ true  → Step 8: autoFix?
                    ├─ true  → Call hotfix-perform-bugfix
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
Step 9: Output report (with fix results)
```

**Flag descriptions:**
- `[AUTOFIX]` - Auto commit code and create PR
- `[TEST_MODE]` - Skip Step 3 duplicate check
- No flag - Only provide fix suggestions without auto-commit