---
name: hotfix-from-raw-log
description: |
  Process production environment raw log errors, supporting traceId tracking and cross-application error chain analysis.

  Trigger conditions:
  - User input contains log fields like "_container_name_", "content", "_time_"
  - Raw log format

  This skill: Extracts traceId from log to query related logs, analyzes error chain (including cross-app errors), clones code repository, analyzes root cause. If fix needed and [AUTOFIX] flag present, executes bugfix automatically, otherwise provides fix suggestions.

  Flag descriptions:
  - `[AUTOFIX]` - Auto commit code and create PR (for automated production runs)
  - `[TEST_MODE]` - Skip duplicate detection, execute full flow (for testing)

  Without flags: Only provide fix suggestions without auto-commit (for manual analysis)
---

# Hotfix from Raw Log

Process production environment raw log errors, supporting traceId tracking and cross-application error chain analysis. Decides whether to auto-commit based on flags.

## Flag Descriptions

| Flag | Purpose | Use Case |
|------|---------|----------|
| `[AUTOFIX]` | Auto commit code and create PR | Automated production runs |
| `[TEST_MODE]` | Skip duplicate detection | Testing full flow |
| No flag | Only provide fix suggestions | Manual analysis by staff |

**Flag Usage Examples:**

```
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

Common configuration file located at `~/.claude/skills/hotfix-common/config.json`

## Input Format

Example raw log provided by user:
```
_container_ip_: 10.0.0.100
_container_name_: demo-app
_image_name_: your-registry.example.com/demo-app:test-478
_namespace_: demo-namespace
_pod_name_: demo-app-c7b77d6dd-abc12
_time_: 2026-03-13T15:22:36.001334555+08:00
content: 2026-03-13 15:22:35.998 [Handler-thread-1] ERROR [trace-id-123] com.example.demo.service.impl.DemoServiceImpl:94 - error...
```

---

## Workflow

### Step 1: Load Configuration

```bash
CONFIG_FILE="$HOME/.claude/skills/hotfix-common/config.json"
SCRIPT_PATH="$HOME/.claude/skills/hotfix-common/scripts/query_sls_logs.py"
```

### Step 2: Parse Raw Log + Check Flags

Extract from log:

| Field | Purpose |
|-------|---------|
| `_container_name_` | App name, used as SLS logstore |
| `_time_` | Error time, for time range query |
| `content` | Log content, for extracting traceId and error info |

**Also check flags:**
- If log contains `[AUTOFIX]` flag, set `autoFix = true`
- If log contains `[TEST_MODE]` flag, set `testMode = true`
- `autoFix = true`: Auto commit code and create PR
- `autoFix = false`: Only provide fix suggestions

### Step 3: Check Duplicate Fix (Important! Check early)

**Before querying logs and cloning repository, check for recent hotfix commits!**

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
  "logTime": "2026-03-16T13:05:19",
  "traceId": "trace-id-123",
  "error": "NullPointerException at DemoClient.java:162",
  "cause": "dto.getStatus() returns null",
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

### Step 4: Extract traceId

Extract traceId from log content in following priority:

1. **Brackets after log level** - Like `ERROR [trace-id-123]`
   ```
   Regex: (ERROR|INFO|WARN|DEBUG)\s+\[([^\]]+)\]
   ```

2. **Field name traceid** - Log may have `traceid: xxx` or `"traceid":"xxx"`

3. **Field name eagleid** - Log may have `eagleid: xxx` or `"eagleid":"xxx"`

4. **Field name tid** - Log may have `tid: xxx` or `"tid":"xxx"`

### Step 5: Query Related Logs

**Important: Time Parameter Format**

`--from` and `--to` parameters must be **Unix timestamps (seconds)**, not ISO 8601 format strings.

```bash
# macOS timestamp conversion
FROM_TIME=$(date -j -f "%Y-%m-%dT%H:%M:%S" "2026-03-16T12:35:19" +%s)
TO_TIME=$(date -j -f "%Y-%m-%dT%H:%M:%S" "2026-03-16T13:35:19" +%s)

# Linux timestamp conversion
FROM_TIME=$(date -d "2026-03-16T12:35:19" +%s)
TO_TIME=$(date -d "2026-03-16T13:35:19" +%s)
```

**Strategy 1: Query using traceId**

```bash
python3 "$SCRIPT_PATH" \
  --config "$CONFIG_FILE" \
  --logstore "$APP_NAME" \
  --query "$TRACE_ID" \
  --from $FROM_TIME \
  --to $TO_TIME \
  --line 200
```

Time range: 30 minutes before and after error time

**Strategy 2: Fallback to time range query**

If traceId query returns no results, use time range query:
```bash
# ±5 minutes from error time
FROM_TIME = error_timestamp - 300
TO_TIME = error_timestamp + 300

python3 "$SCRIPT_PATH" \
  --config "$CONFIG_FILE" \
  --logstore "$APP_NAME" \
  --query "ERROR" \
  --from $FROM_TIME \
  --to $TO_TIME \
  --line 100
```

### Step 6: Detect Cross-Application Errors

Analyze error logs to check if other applications are involved:

**Cross-app error indicators:**
- Error message contains other app names (like `ProductIntegration` calling product-service)
- Stack trace contains `com.example.{other-app}` package
- Error description mentions external service failure

**If cross-app error detected:**
1. Extract target app name
2. Recursively execute same processing flow:
   - Query target app's logs (using same traceId)
   - Clone target app's code repository
   - Analyze target app's error
3. Build error chain

**Termination conditions:**
- Root cause found
- Target app not in code repository mapping
- Target app is third-party service

### Step 7: Analyze Error Root Cause

Analyze from Java stack trace and source code:
1. Error location: Find code under `com.example.{app-name}` package
2. Error type: NullPointerException, business exception, etc.
3. Root cause analysis: Why did it happen
4. Fix approach: Determine best fix strategy

### Step 8: Determine if Fix Needed

**needFix: true** - Code fix needed:
- NullPointerException missing null check
- Business logic error
- Missing necessary validation

**needFix: false** - No code fix needed:
- Business exception (expected behavior)
- Data issue
- Configuration issue
- External service issue

### Step 9: Execute Auto Fix (when needFix is true and autoFix is true)

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

### Step 10: Output JSON Report

```json
{
  "appName": "app-name",
  "logTime": "log time",
  "traceId": "trace id",
  "error": "specific error message",
  "cause": "root cause analysis",
  "needFix": true/false,
  "fix": "fix suggestion",
  "fixBranch": "fix branch name (if fixed)",
  "fixDesc": "fix description",
  "fixCommit": "commit hash (if fixed)",
  "fixStatus": "success/skipped (if needFix is false)",
  "errorChain": [
    {
      "app": "demo-app",
      "error": "product not found",
      "cause": "product-service returned 2004"
    },
    {
      "app": "product-service",
      "error": "product not found",
      "cause": "product code 123 not configured"
    }
  ]
}
```

**Error chain description:**
- `errorChain` array is ordered by call sequence, from current app to root cause app
- If error involves only one app, `errorChain` has only one element

---

## Complete Flow Diagram

```
Raw Log Input
    ↓
Step 1: Load configuration
    ↓
Step 2: Parse log info + Check flags [AUTOFIX] [TEST_MODE]
    ↓
Step 3: Check duplicate fix (clone repo then check git history)
    ├─ Yes (hotfix within 1 hour) → Output report (needFix: false, skipReason: duplicate)
    └─ No → Continue
    ↓
Step 4: Extract traceId
    ↓
Step 5: Query related logs
    ↓
Step 6: Detect cross-app error?
    ├─ Yes → Recursively analyze target app
    └─ No → Continue
    ↓
Step 7: Analyze error root cause
    ↓
Step 8: needFix?
    ├─ false → Output report (no fix needed)
    └─ true  → Step 9: autoFix?
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
Step 10: Output report (with fix results and error chain)
```

**Flag descriptions:**
- `[AUTOFIX]` - Auto commit code and create PR
- `[TEST_MODE]` - Skip Step 3 duplicate check
- No flag - Only provide fix suggestions without auto-commit

---

## Cross-Application Error Handling Example

**Scenario:** demo-app calls product-service, product not found

**Processing flow:**

1. Parse demo-app log, find error:
   ```
   DemoException: Product service request succeeded but response status failed#2004#product not found#
   at ProductIntegration.queryProductByCode
   ```

2. Identify this as cross-app error (called product-service)

3. Extract traceId, query product-service logs

4. Find in product-service logs:
   ```
   Product code 123 query returned empty
   ```

5. Build error chain:
   ```
   demo-app → product-service → Product data not found
   ```

6. Output report, `needFix: false` (data issue, not code issue), skip bugfix