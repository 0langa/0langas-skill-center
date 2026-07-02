$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkflowSkills = @(
  "official-docs-citation-cache",
  "tri-client-skill-port",
  "skill-trigger-evalsmith",
  "agent-install-sync",
  "skill-center-curator"
)

$InstalledSkills = @(
  "official-ai-devdocs",
  "muteman",
  "official-docs-citation-cache",
  "tri-client-skill-port",
  "skill-trigger-evalsmith",
  "agent-install-sync",
  "skill-center-curator"
)

$ProviderRoots = @(
  ".codex\skills",
  ".claude\skills",
  ".kimi-code\skills"
)

$UserInstallRoots = @(
  "$HOME\.codex\skills",
  "$HOME\.claude\skills",
  "$HOME\.kimi-code\skills"
)

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

function Test-ProviderLink {
  param(
    [string]$Skill,
    [string]$Root
  )

  $linkPath = Join-Path (Join-Path $RepoRoot $Root) $Skill
  $expected = (Resolve-Path -LiteralPath (Join-Path $RepoRoot $Skill)).Path

  if (-not (Test-Path -LiteralPath $linkPath)) {
    Add-Failure "Missing provider link: $linkPath"
    return
  }

  $item = Get-Item -LiteralPath $linkPath -Force
  if ($item.LinkType -ne "SymbolicLink" -and $item.LinkType -ne "Junction") {
    Add-Failure "Provider entry is not a symlink or junction: $linkPath"
    return
  }

  $resolved = Resolve-LinkTarget $item
  if ($resolved -ne $expected) {
    Add-Failure "Provider link target mismatch: $linkPath -> $resolved expected $expected"
  }
}

function Test-UserSkillLink {
  param(
    [string]$Skill,
    [string]$Root
  )

  $linkPath = Join-Path $Root $Skill
  $expected = (Resolve-Path -LiteralPath (Join-Path $RepoRoot $Skill)).Path

  if (-not (Test-Path -LiteralPath $linkPath)) {
    Add-Failure "Missing user skill link: $linkPath"
    return
  }

  $item = Get-Item -LiteralPath $linkPath -Force
  if ($item.LinkType -ne "SymbolicLink" -and $item.LinkType -ne "Junction") {
    Add-Failure "User skill entry is not a symlink or junction: $linkPath"
    return
  }

  $resolved = Resolve-LinkTarget $item
  if ($resolved -ne $expected) {
    Add-Failure "User skill link target mismatch: $linkPath -> $resolved expected $expected"
  }
}

function Test-TriggerEvals {
  param(
    [string]$Skill,
    [object]$Json
  )

  if ($null -eq $Json -or $Json.Count -lt 6) {
    Add-Failure "Trigger evals need at least 6 cases: $Skill"
    return
  }

  $positive = @($Json | Where-Object { $_.should_trigger -eq $true }).Count
  $negative = @($Json | Where-Object { $_.should_trigger -eq $false }).Count

  if ($positive -lt 3) {
    Add-Failure "Trigger evals need at least 3 should_trigger=true cases: $Skill"
  }

  if ($negative -lt 3) {
    Add-Failure "Trigger evals need at least 3 should_trigger=false cases: $Skill"
  }

  foreach ($case in $Json) {
    foreach ($field in @("id", "query", "reason", "expected_routing")) {
      if ([string]::IsNullOrWhiteSpace([string]$case.$field)) {
        Add-Failure "Trigger eval case missing ${field}: $Skill"
      }
    }
  }
}

$RequiredFields = @("name", "description", "when_to_use", "type", "whenToUse", "disableModelInvocation")
$Readme = Get-Content -LiteralPath (Join-Path $RepoRoot "README.md") -Raw

foreach ($skill in $WorkflowSkills) {
  $skillDir = Join-Path $RepoRoot $skill
  $skillPath = Join-Path $skillDir "SKILL.md"

  if (-not (Test-Path -LiteralPath $skillPath)) {
    Add-Failure "Missing SKILL.md: $skillPath"
    continue
  }

  $frontmatter = Get-FrontmatterMap $skillPath
  foreach ($field in $RequiredFields) {
    if (-not $frontmatter.ContainsKey($field) -or [string]::IsNullOrWhiteSpace($frontmatter[$field])) {
      Add-Failure "Missing frontmatter field '$field': $skillPath"
    }
  }

  if ($frontmatter.ContainsKey("name") -and $frontmatter["name"] -ne $skill) {
    Add-Failure "Frontmatter name mismatch: $skillPath has '$($frontmatter["name"])'"
  }

  if ($frontmatter.ContainsKey("type") -and $frontmatter["type"] -ne "prompt") {
    Add-Failure "Unexpected type for ${skill}: $($frontmatter["type"])"
  }

  if ($frontmatter.ContainsKey("disableModelInvocation") -and $frontmatter["disableModelInvocation"] -ne "false") {
    Add-Failure "Unexpected disableModelInvocation for ${skill}: $($frontmatter["disableModelInvocation"])"
  }

  $evalPath = Join-Path $skillDir "evals\evals.json"
  if (-not (Test-Path -LiteralPath $evalPath)) {
    Add-Failure "Missing evals.json: $skill"
  }
  else {
    $evalJson = Read-JsonFile $evalPath
    if ($null -ne $evalJson -and $evalJson.skill_name -ne $skill) {
      Add-Failure "evals.json skill_name mismatch: $skill"
    }
    if ($null -ne $evalJson -and @($evalJson.evals).Count -lt 3) {
      Add-Failure "evals.json needs at least 3 eval prompts: $skill"
    }
  }

  $triggerPath = Join-Path $skillDir "evals\trigger-evals.json"
  if (-not (Test-Path -LiteralPath $triggerPath)) {
    Add-Failure "Missing trigger-evals.json: $skill"
  }
  else {
    Test-TriggerEvals $skill (Read-JsonFile $triggerPath)
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

foreach ($skill in $InstalledSkills) {
  foreach ($root in $ProviderRoots) {
    Test-ProviderLink $skill $root
  }

  foreach ($root in $UserInstallRoots) {
    Test-UserSkillLink $skill $root
  }
}

$cacheIndexPath = Join-Path $RepoRoot ".ai\official-docs-cache\index.json"
if (-not (Test-Path -LiteralPath $cacheIndexPath)) {
  Add-Failure "Missing official docs cache index"
}
else {
  $cache = Read-JsonFile $cacheIndexPath
  if ($null -ne $cache) {
    foreach ($provider in @("codex", "claude-code", "kimi-code")) {
      $note = @($cache.notes | Where-Object { $_.provider -eq $provider -and $_.topic -eq "skill-discovery" })[0]
      if ($null -eq $note) {
        Add-Failure "Docs cache missing skill-discovery note for $provider"
      }
      else {
        $notePath = Join-Path $RepoRoot $note.path
        if (-not (Test-Path -LiteralPath $notePath)) {
          Add-Failure "Docs cache note path missing for ${provider}: $($note.path)"
        }
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

Write-Host "skill-center E2E passed for $($WorkflowSkills.Count) workflow skills and $($InstalledSkills.Count) installed skills." -ForegroundColor Green
