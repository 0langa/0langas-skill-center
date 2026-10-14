# Plants the skill-doctor trap suite (13 decoys) for provider acceptance testing.
# Idempotent: safe to re-run before each test round. See remove-traps.ps1 for cleanup.
# Decoys use innocuous names on purpose. Never touches real skill CONTENT;
# the one exception is the tri-client-skill-port claude JUNCTION (repointed; restored by remove-traps.ps1 or `skillctl sync --apply`).
# Set SKILLCTL_HOME to plant into a sandbox home instead of the real one; tools/skillctl.py honours the same variable.
$ErrorActionPreference = 'Stop'
$UserHome = if ($env:SKILLCTL_HOME) { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($env:SKILLCTL_HOME) } else { $HOME }
$A = "$UserHome\.agents\skills"
# Repo location is derived, never hardcoded: the repo has moved before and
# hardcoded paths silently broke traps 12 and 13.
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:SKILLCTL_REGISTRY = Join-Path $RepoRoot 'registry\skills.json'

function Write-Skill($dir, $fmName, $desc) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $body = @"
---
name: $fmName
description: $desc
---

# $fmName

Decoy skill for acceptance testing.
"@
  if (-not $desc) { $body = "---`nname: $fmName`n---`n`n# $fmName`n`nDecoy (no description).`n" }
  # UTF-8 WITHOUT BOM: Set-Content -Encoding UTF8 emits a BOM under PS5.1,
  # which breaks byte-0-anchored frontmatter parsers (found in Codex test round).
  [System.IO.File]::WriteAllText((Join-Path $dir 'SKILL.md'), $body, (New-Object System.Text.UTF8Encoding($false)))
}

# Native commands do not honour $ErrorActionPreference, so check the exit code:
# a trap that silently failed to plant makes the whole test round meaningless.
function New-Junction($link, $target) {
  New-Item -ItemType Directory -Force -Path (Split-Path $link) | Out-Null
  cmd /c mklink /J "$link" "$target" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "mklink /J failed: $link -> $target" }
}

# 1+2 registerable strays
Write-Skill "$A\markdown-toolbox" 'markdown-toolbox' 'Utilities for linting and formatting Markdown files, fixing heading levels, tables, and link references.'
Write-Skill "$A\pr-review-buddy" 'pr-review-buddy' 'Checklist-driven pull request review helper that summarizes diffs and drafts review comments.'
# 3 stray dir without SKILL.md
New-Item -ItemType Directory -Force -Path "$A\old-python-scripts" | Out-Null
Set-Content "$A\old-python-scripts\README.txt" '# misc old scripts'
# 4 non-skill file
Set-Content "$A\notes-backup.zip" 'PK fake zip placeholder'
# 5 nested container stray
Write-Skill "$A\skills\web-scraper-utils" 'web-scraper-utils' 'Helpers for fetching and parsing HTML pages into structured data.'
# 6 invalid frontmatter (no description)
Write-Skill "$A\draft-formatter" 'draft-formatter' $null
# 7 name != dir
Write-Skill "$A\json-fixer" 'quick-json' 'Repair and reformat broken JSON documents.'
# 8 broken junction
if (Test-Path "$A\legacy-link") { cmd /c rmdir "$A\legacy-link" | Out-Null }
New-Junction "$A\legacy-link" "$A\_does-not-exist-anymore"
# 9 claude-scope stray
Write-Skill "$UserHome\.claude\skills\pdf-tools" 'pdf-tools' 'Merge, split, and extract text from PDF files.'
# 10 vscode-scope stray
Write-Skill "$UserHome\.copilot\skills\snippet-vault" 'snippet-vault' 'Store and retrieve reusable code snippets by language and tag.'
# 11 duplicate-name decoy (registry skill pulse:usage-report, different target)
Write-Skill "$A\usage-report" 'pulse:usage-report' 'Older copy of the usage report skill kept around after a manual sync experiment.'
# 12 wrong-target junction on an expected registry location
if (Test-Path "$UserHome\.claude\skills\tri-client-skill-port") { cmd /c rmdir "$UserHome\.claude\skills\tri-client-skill-port" | Out-Null }
New-Junction "$UserHome\.claude\skills\tri-client-skill-port" (Join-Path $RepoRoot "muteman")
# 13 ghost registry entry
python -c @"
import json, os
p = os.environ['SKILLCTL_REGISTRY']
r = json.load(open(p, encoding='utf-8'))
if not any(s['name'] == 'ghost-ledger' for s in r['skills']):
    r['skills'].append({'name': 'ghost-ledger', 'origin': 'unknown', 'canonical': {'type': 'path', 'path': '~/.agents/skills/ghost-ledger'}, 'upstream': None, 'install': {'codex': 'agents', 'kimi': 'agents', 'claude': 'none', 'vscode': 'agents'}})
    tmp = p + '.tmp'
    json.dump(r, open(tmp, 'w', encoding='utf-8', newline='\n'), indent=2, ensure_ascii=False)
    open(tmp, 'a', encoding='utf-8', newline='\n').write('\n')
    os.replace(tmp, p)
print('ghost-ledger planted')
"@
if ($LASTEXITCODE -ne 0) { throw "planting the ghost registry entry failed" }
Write-Output "trap suite planted (13 decoys) under $UserHome"
