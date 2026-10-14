# Removes the skill-doctor trap suite and restores the original healthy state.
# Also safe to run if a test round archived the decoys (missing paths are skipped).
# Honours SKILLCTL_HOME like plant-traps.ps1, so a sandbox round cleans up the sandbox.
$ErrorActionPreference = 'Continue'
$UserHome = if ($env:SKILLCTL_HOME) { $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($env:SKILLCTL_HOME) } else { $HOME }
$A = "$UserHome\.agents\skills"
# Derived, never hardcoded - see plant-traps.ps1.
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:SKILLCTL_REGISTRY = Join-Path $RepoRoot 'registry\skills.json'

foreach ($p in @("$A\markdown-toolbox", "$A\pr-review-buddy", "$A\old-python-scripts",
                 "$A\notes-backup.zip", "$A\skills\web-scraper-utils", "$A\draft-formatter",
                 "$A\json-fixer", "$A\usage-report",
                 "$UserHome\.claude\skills\pdf-tools", "$UserHome\.copilot\skills\snippet-vault")) {
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
}
# trap 5's container: removed once empty, never with anything else in it
if ((Test-Path -LiteralPath "$A\skills") -and -not (Get-ChildItem -LiteralPath "$A\skills" -Force)) {
  Remove-Item -LiteralPath "$A\skills" -Force
}

# No cmd.exe here: PowerShell hands it a path without spaces unquoted, so a
# home such as C:\R&D split the command at the "&". Found by listing the
# folder, since Test-Path is false for a dead link.
function Remove-Junction($link) {
  $leaf = Split-Path $link -Leaf
  $item = Get-ChildItem -LiteralPath (Split-Path $link) -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq $leaf }
  if ($item -and $item.LinkType) { [System.IO.Directory]::Delete($link) }  # the link only
}
# broken junction (remove the link itself only)
Remove-Junction "$A\legacy-link"
# restore the tri-client-skill-port claude junction to its correct target
$triClient = "$UserHome\.claude\skills\tri-client-skill-port"
Remove-Junction $triClient
if (-not (Test-Path -LiteralPath $triClient)) {
  New-Item -ItemType Directory -Force -Path (Split-Path $triClient) | Out-Null
  New-Item -ItemType Junction -Path $triClient -Target (Join-Path $RepoRoot "tri-client-skill-port") | Out-Null
}
# remove ghost registry entry + any decoy registrations the agent may have added
python -c @"
import json, os
p = os.environ['SKILLCTL_REGISTRY']
r = json.load(open(p, encoding='utf-8'))
drop = {'ghost-ledger', 'markdown-toolbox', 'pr-review-buddy', 'web-scraper-utils', 'pdf-tools', 'snippet-vault',
        'quick-json'}
before = len(r['skills'])
r['skills'] = [s for s in r['skills'] if s['name'] not in drop]
tmp = p + '.tmp'
json.dump(r, open(tmp, 'w', encoding='utf-8', newline='\n'), indent=2, ensure_ascii=False)
open(tmp, 'a', encoding='utf-8', newline='\n').write('\n')
os.replace(tmp, p)
print(f'registry cleaned: {before} -> ' + str(len(r['skills'])))
"@
Write-Output 'trap suite removed; tri-client junction restored'
Write-Output 'note: if a test round archived decoys, they are safe in _archive/ (can be purged manually)'
