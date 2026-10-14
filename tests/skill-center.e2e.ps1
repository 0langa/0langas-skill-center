param(
  # -CI skips the machine-local assertions (registry-driven home-dir
  # junctions) so the harness can run on a clean CI checkout. All
  # repo-content checks (frontmatter, evals, README catalog rows, dependency
  # order, and docs-cache records when present) still run.
  [switch]$CI
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
# SKILLCTL_HOME redirects "~" the same way tools/skillctl.py does, so the
# user-level checks can run against a sandbox install instead of the real home.
$UserHome = if ($env:SKILLCTL_HOME) { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($env:SKILLCTL_HOME) } else { $HOME }

# The workflow skills are held to the full tri-client frontmatter contract and
# the stricter eval thresholds; every other repo skill gets the shape checks.
$WorkflowSkills = @(
  "official-docs-citation-cache",
  "tri-client-skill-port",
  "skill-trigger-evalsmith",
  "agent-install-sync",
  "skill-center-curator"
)

# Legacy user install roots ($HOME\.codex\skills, $HOME\.kimi-code\skills) are
# intentionally empty: Codex reads only ~/.agents/skills at user scope, and Kimi
# reads ~/.kimi-code/skills then ~/.agents/skills. User-level link assertions are
# driven from registry/skills.json below instead of hardcoded roots.

$Failures = New-Object System.Collections.Generic.List[string]

function Add-Failure {
  param([string]$Message)
  [void]$Failures.Add($Message)
}

function Read-JsonFile {
  param([string]$Path)

  try {
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
  }
  catch {
    Add-Failure "Invalid JSON: $Path ($($_.Exception.Message))"
    return $null
  }
}

# Like Read-JsonFile, but an eval file that parses to nothing ([] or null)
# is a failure too: ConvertFrom-Json turns both into $null, which used to
# skip every check that follows.
function Read-EvalFile {
  param([string]$Path)

  $before = $Failures.Count
  $json = Read-JsonFile $Path
  if ($null -eq $json -and $Failures.Count -eq $before) {
    Add-Failure "Eval file is empty or null: $Path"
  }
  return $json
}

# Number of real items in a JSON array property; @($x.evals).Count is 1 when
# the property is missing.
function Get-ItemCount {
  param([object]$Items)
  return @($Items | Where-Object { $null -ne $_ }).Count
}

function Get-FrontmatterMap {
  param([string]$Path)

  $text = Get-Content -LiteralPath $Path -Raw
  if (-not $text.StartsWith("---")) {
    Add-Failure "Missing frontmatter fence: $Path"
    return @{}
  }

  $match = [regex]::Match($text, "(?s)^---\r?\n(.*?)\r?\n---")
  if (-not $match.Success) {
    Add-Failure "Malformed frontmatter fence: $Path"
    return @{}
  }

  $map = @{}
  foreach ($line in ($match.Groups[1].Value -split "\r?\n")) {
    if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)\s*$") {
      $map[$matches[1]] = $matches[2].Trim()
    }
  }

  return $map
}

function Resolve-LinkTarget {
  param([System.IO.FileSystemInfo]$Item)

  $target = $Item.Target
  if ($target -is [array]) {
    $target = $target[0]
  }

  if ([string]::IsNullOrWhiteSpace($target)) {
    return $null
  }

  if ([System.IO.Path]::IsPathRooted($target)) {
    $candidate = $target
  }
  else {
    $candidate = Join-Path $Item.Parent.FullName $target
  }

  try {
    return (Resolve-Path -LiteralPath $candidate).Path
  }
  catch {
    return $null
  }
}

function Test-UserSkillLink {
  param(
    [string]$LinkPath,
    [string]$Expected
  )

  if (-not (Test-Path -LiteralPath $LinkPath)) {
    Add-Failure "Missing user skill link: $LinkPath"
    return
  }

  $item = Get-Item -LiteralPath $LinkPath -Force
  if ($item.LinkType -ne "SymbolicLink" -and $item.LinkType -ne "Junction") {
    Add-Failure "User skill entry is not a symlink or junction: $LinkPath"
    return
  }

  $resolved = Resolve-LinkTarget $item
  if ($resolved -ne $Expected) {
    Add-Failure "User skill link target mismatch: $LinkPath -> $resolved expected $Expected"
  }
}

function Test-TriggerEvalShape {
  param(
    [string]$Skill,
    [object]$Json
  )

  $cases = @($Json)
  if (@($cases | Where-Object { $_.should_trigger -eq $true }).Count -lt 1 -or
      @($cases | Where-Object { $_.should_trigger -eq $false }).Count -lt 1) {
    Add-Failure "Trigger evals need should_trigger=true and should_trigger=false cases: $Skill"
  }

  foreach ($case in $cases) {
    foreach ($field in @("id", "query", "reason", "expected_routing")) {
      if ([string]::IsNullOrWhiteSpace([string]$case.$field)) {
        Add-Failure "Trigger eval case missing ${field}: $Skill"
      }
    }
  }
}

function Test-TriggerEvalThresholds {
  param(
    [string]$Skill,
    [object]$Json
  )

  $cases = @($Json)
  if ($cases.Count -lt 6) {
    Add-Failure "Trigger evals need at least 6 cases: $Skill"
    return
  }

  if (@($cases | Where-Object { $_.should_trigger -eq $true }).Count -lt 3) {
    Add-Failure "Trigger evals need at least 3 should_trigger=true cases: $Skill"
  }

  if (@($cases | Where-Object { $_.should_trigger -eq $false }).Count -lt 3) {
    Add-Failure "Trigger evals need at least 3 should_trigger=false cases: $Skill"
  }
}

$Readme = Get-Content -LiteralPath (Join-Path $RepoRoot "README.md") -Raw
$registryPath = Join-Path $RepoRoot "registry\skills.json"
$Registry = Read-JsonFile $registryPath
$RepoSkills = @()
if ($null -eq $Registry) {
  Add-Failure "Missing or invalid registry: $registryPath"
}
else {
  $RepoSkills = @($Registry.skills | Where-Object { $_.canonical.type -eq "repo" })
}

# Every skill that lives in this repo, as the registry lists them.
$EvalsBySkill = @{}
$TriggersBySkill = @{}
foreach ($entry in $RepoSkills) {
  $skill = [string]$entry.name
  $skillDir = Join-Path $RepoRoot $entry.canonical.path
  $skillPath = Join-Path $skillDir "SKILL.md"

  if (-not (Test-Path -LiteralPath $skillPath)) {
    Add-Failure "Missing SKILL.md: $skillPath"
    continue
  }

  $frontmatter = Get-FrontmatterMap $skillPath
  if ($frontmatter["name"] -ne $skill) {
    Add-Failure "Frontmatter name mismatch: $skillPath has '$($frontmatter["name"])'"
  }
  if ([string]::IsNullOrWhiteSpace($frontmatter["description"])) {
    Add-Failure "Missing frontmatter field 'description': $skillPath"
  }

  $evalPath = Join-Path $skillDir "evals\evals.json"
  if (-not (Test-Path -LiteralPath $evalPath)) {
    Add-Failure "Missing evals.json: $skill"
  }
  else {
    $evalJson = Read-EvalFile $evalPath
    $EvalsBySkill[$skill] = $evalJson
    if ($null -ne $evalJson -and $evalJson.skill_name -ne $skill) {
      Add-Failure "evals.json skill_name mismatch: $skill"
    }
    if ($null -ne $evalJson -and (Get-ItemCount $evalJson.evals) -lt 1) {
      Add-Failure "evals.json has no eval prompts: $skill"
    }
  }

  $triggerPath = Join-Path $skillDir "evals\trigger-evals.json"
  if (-not (Test-Path -LiteralPath $triggerPath)) {
    Add-Failure "Missing trigger-evals.json: $skill"
  }
  else {
    $triggerJson = Read-EvalFile $triggerPath
    $TriggersBySkill[$skill] = $triggerJson
    if ($null -ne $triggerJson) {
      Test-TriggerEvalShape $skill $triggerJson
    }
  }

  $readmeRowNeedle = "| ``$skill`` |"
  if ($Readme -notmatch [regex]::Escape($readmeRowNeedle)) {
    Add-Failure "README skill table missing row for $skill"
  }

  $candidateNeedle = "- ``$skill``:"
  if ($Readme -match [regex]::Escape($candidateNeedle)) {
    Add-Failure "README still lists implemented skill as candidate: $skill"
  }
}

$RequiredFields = @("name", "description", "when_to_use", "type", "whenToUse", "disableModelInvocation")
$RepoSkillNames = @($RepoSkills | ForEach-Object { [string]$_.name })

foreach ($skill in $WorkflowSkills) {
  $entry = @($RepoSkills | Where-Object { [string]$_.name -eq $skill })[0]
  if ($null -eq $entry) {
    Add-Failure "Workflow skill is not registered as a repo skill: $skill"
    continue
  }
  $skillPath = Join-Path (Join-Path $RepoRoot $entry.canonical.path) "SKILL.md"
  if (-not (Test-Path -LiteralPath $skillPath)) {
    continue  # reported as "Missing SKILL.md" by the per-skill loop above
  }

  $frontmatter = Get-FrontmatterMap $skillPath
  foreach ($field in $RequiredFields) {
    if (-not $frontmatter.ContainsKey($field) -or [string]::IsNullOrWhiteSpace($frontmatter[$field])) {
      Add-Failure "Missing frontmatter field '$field': $skillPath"
    }
  }

  if ($frontmatter.ContainsKey("type") -and $frontmatter["type"] -ne "prompt") {
    Add-Failure "Unexpected type for ${skill}: $($frontmatter["type"])"
  }

  if ($frontmatter.ContainsKey("disableModelInvocation") -and $frontmatter["disableModelInvocation"] -ne "false") {
    Add-Failure "Unexpected disableModelInvocation for ${skill}: $($frontmatter["disableModelInvocation"])"
  }

  if ($null -ne $EvalsBySkill[$skill] -and (Get-ItemCount $EvalsBySkill[$skill].evals) -lt 3) {
    Add-Failure "evals.json needs at least 3 eval prompts: $skill"
  }

  if ($null -ne $TriggersBySkill[$skill]) {
    Test-TriggerEvalThresholds $skill $TriggersBySkill[$skill]
  }
}

if ($CI) {
  Write-Host "[CI] skipping user-level link checks (home-dir junctions)" -ForegroundColor Yellow
}
elseif ($null -ne $Registry) {
  # User-level junction assertions driven from registry/skills.json: every
  # repo-canonical skill with an install method of "junction:<path>" must have a
  # junction at <path> resolving to its canonical repo directory. This asserts the
  # current layout (~/.agents/skills for codex/kimi/vscode, ~/.claude/skills for
  # claude) without hardcoding provider roots.
  $checkedLinks = @{}
  foreach ($entry in $RepoSkills) {
    $canonicalDir = Join-Path $RepoRoot $entry.canonical.path
    if (-not (Test-Path -LiteralPath $canonicalDir)) { continue }  # reported above
    $expected = (Resolve-Path -LiteralPath $canonicalDir).Path
    foreach ($prop in $entry.install.PSObject.Properties) {
      $method = [string]$prop.Value
      if (-not $method.StartsWith("junction:")) { continue }
      $linkPath = $method.Substring("junction:".Length)
      if ($linkPath.StartsWith("~/") -or $linkPath.StartsWith("~\")) {
        $linkPath = Join-Path $UserHome $linkPath.Substring(2)
      }
      $linkPath = [System.IO.Path]::GetFullPath($linkPath)
      $key = $linkPath.ToLowerInvariant()
      if ($checkedLinks.ContainsKey($key)) { continue }
      $checkedLinks[$key] = $true
      Test-UserSkillLink $linkPath $expected
    }
  }
}

# Evidence notes written by the official-docs-citation-cache skill. They are
# working data, so the records are validated when the cache exists rather
# than required.
$cacheIndexPath = Join-Path $RepoRoot ".ai\official-docs-cache\index.json"
if (Test-Path -LiteralPath $cacheIndexPath) {
  $cache = Read-JsonFile $cacheIndexPath
  if ($null -ne $cache) {
    foreach ($note in @($cache.notes)) {
      if ([string]::IsNullOrWhiteSpace([string]$note.path)) {
        Add-Failure "Docs cache record without a path: provider=$($note.provider) topic=$($note.topic)"
      }
      elseif (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $note.path))) {
        Add-Failure "Docs cache note path missing for $($note.provider)/$($note.topic): $($note.path)"
      }
    }
  }
}

$DependencyChecks = @{
  "tri-client-skill-port\SKILL.md" = @("official-docs-citation-cache")
  "skill-trigger-evalsmith\SKILL.md" = @("tri-client-skill-port", "official-docs-citation-cache")
  "agent-install-sync\SKILL.md" = @("tri-client-skill-port", "skill-trigger-evalsmith")
  "skill-center-curator\SKILL.md" = @("official-docs-citation-cache", "tri-client-skill-port", "skill-trigger-evalsmith", "agent-install-sync")
}

foreach ($relativePath in $DependencyChecks.Keys) {
  $path = Join-Path $RepoRoot $relativePath
  if (-not (Test-Path -LiteralPath $path)) {
    Add-Failure "Dependency order check target missing: $relativePath"
    continue
  }
  $text = Get-Content -LiteralPath $path -Raw
  foreach ($needle in $DependencyChecks[$relativePath]) {
    if ($text -notmatch [regex]::Escape($needle)) {
      Add-Failure "Dependency order missing '$needle' in $relativePath"
    }
  }
}

if ($Failures.Count -gt 0) {
  Write-Host "skill-center E2E failed:" -ForegroundColor Red
  foreach ($failure in $Failures) {
    Write-Host " - $failure" -ForegroundColor Red
  }
  exit 1
}

Write-Host "skill-center E2E passed for $($RepoSkills.Count) repo skills ($($WorkflowSkills.Count) workflow skills held to the full contract)." -ForegroundColor Green
