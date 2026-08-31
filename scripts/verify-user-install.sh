#!/usr/bin/env bash
set -euo pipefail
ch="${CODEX_HOME:-$HOME/.codex}";sh="$HOME/.agents/skills";failed=0;skills=(java-backend-engineering python-backend-ai-engineering frontend-engineering data-middleware-ai-infrastructure log-observability-analysis engineering-quality-delivery multi-agent-independent-review technical-document-writing long-running-task-memory);agents=(cp-review-functional-business.toml cp-review-compatibility-regression.toml cp-review-security-access.toml cp-review-performance-resources.toml cp-review-data-contract.toml cp-review-state-concurrency.toml cp-review-test-delivery.toml)
[[ -f "$ch/AGENTS.md" && $(grep -cF 'codex-cross-project-assistant:begin' "$ch/AGENTS.md"||true) -eq 1 && $(grep -cF 'codex-cross-project-assistant:end' "$ch/AGENTS.md"||true) -eq 1 ]]||failed=1
for n in "${skills[@]}";do [[ -f "$sh/$n/SKILL.md" ]]&&grep -Eq "^name: $n$" "$sh/$n/SKILL.md"||failed=1;done
[[ ! -e "$sh/vue-frontend-engineering" ]]||failed=1
for n in "${agents[@]}";do [[ -f "$ch/agents/$n" ]]||failed=1;done
for r in frontend-core-rules.md frontend-security-runtime-rules.md frontend-quality-performance-rules.md vue-nuxt-rules.md react-next-remix-rules.md angular-rules.md svelte-sveltekit-rules.md other-modern-frameworks-rules.md legacy-frontend-rules.md microfrontend-monorepo-rules.md;do [[ -f "$sh/frontend-engineering/references/$r" ]]||failed=1;done
[[ $failed -eq 0 ]]||{ echo '验证失败';exit 1;};echo '文件级验证通过。请重启 Codex 后运行 /skills。'
