[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$RepoPath,[switch]$IncludeReviewAgents,[switch]$NoBackup)
$ErrorActionPreference="Stop";$Repo=(Resolve-Path $RepoPath).Path;$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path);$TS=Get-Date -Format "yyyyMMdd-HHmmss";$Backup=Join-Path $Repo (".codex-assistant-backup-"+$TS);$Target=Join-Path (Join-Path $Repo ".agents") "skills";New-Item -ItemType Directory -Force -Path $Target|Out-Null
$Old=Join-Path $Target "vue-frontend-engineering";if(Test-Path $Old){if(-not$NoBackup){New-Item -ItemType Directory -Force -Path (Join-Path $Backup "deprecated-skills")|Out-Null;Copy-Item $Old (Join-Path (Join-Path $Backup "deprecated-skills") "vue-frontend-engineering") -Recurse -Force};Remove-Item $Old -Recurse -Force}
Get-ChildItem (Join-Path $Root "skills") -Directory|ForEach-Object{$T=Join-Path $Target $_.Name;if(Test-Path $T){Remove-Item $T -Recurse -Force};Copy-Item $_.FullName $T -Recurse -Force}
if($IncludeReviewAgents){$A=Join-Path (Join-Path $Repo ".codex") "agents";New-Item -ItemType Directory -Force -Path $A|Out-Null;Copy-Item (Join-Path $Root "custom-agents\*.toml") $A -Force}
Write-Host '仓库级资源已安装。'
