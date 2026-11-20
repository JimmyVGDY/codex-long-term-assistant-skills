<!-- Generated from locales/en/docs/releases/v7.18.1/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.18.1 Validation Report

The stable release was published at 2026-11-20 10:51:37 UTC from commit `4f905b823ef2d2932006616e618d7f888100639a`. [GitHub Release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.18.1)

PR checks and the tag workflow passed. Windows and Ubuntu built both ZIPs with the same Python patch version and passed cross-platform comparison before signing. [PR checks](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44683838094) · [Tag run](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013)

One late-receipt regression failed on Windows 3.11 in the first tag run. The same test passed on master at the identical commit and in 12 consecutive local Windows runs. An injected 300 ms read delay deferred processing to the next callback, which settled the record once. The hosted log recorded the test outcome without the assertion detail. Only the failed job and its dependents were rerun on the original tag. [First attempt](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013/job/136143771873) · [Same-commit master check](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693136099/job/136143480336)

The late-receipt test passed on attempt two. A different Node permission-denial test exceeded its 10-second subprocess deadline (TimeoutExpired) after passing on attempt one and on master at the same commit. Both original tests passed 12 paired rounds on each of Windows Python 3.11.18 and 3.12.14. The third run repeated the Windows job on the original tag with runner debugging enabled. [Second attempt](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013/job/136173743661)

| Platform and Python | Package passed / skipped | Runtime passed / skipped |
| --- | ---: | ---: |
| ubuntu-latest, Python 3.11 | 1408 / 45 | 260 / 6 |
| ubuntu-latest, Python 3.13 | 1408 / 45 | 260 / 6 |
| windows-latest, Python 3.11 | 1450 / 3 | 266 / 0 |
| windows-latest, Python 3.13 | 1451 / 2 | 266 / 0 |

All six public assets were downloaded anonymously and checked by SHA-256.

| Asset | SHA-256 |
| --- | --- |
| `Codex-Skills-V7.18.1-en.zip` | `39f890705e6ded6b44428d276c96dea4fd7141d74814ce4990e880bd2b18e678` |
| `Codex-Skills-V7.18.1-provenance.json` | `f446d7557134516d4f9e49fd1de8485e854f9749fcff89b8ccc643e5572551b7` |
| `Codex-Skills-V7.18.1-zh-CN.zip` | `44c76242d8f7ccba639557958094e57feae4e28223d3896271ec2c69c3f407c3` |
| `SHA256SUMS.txt` | `dcf56e780857ea49368ff0181baa2e8a8844edef6a0ea7e8f63612d17b7f2c29` |
| `witness-en.json` | `b43adbd1457020d0c69a4a08f4fbec992c0fe50b28566e8774fc277917f46bcf` |
| `witness-zh-CN.json` | `e4d62e2071dc11a4d4dbd77facd4b443960f4e3b7381040f58d26dec79846441` |

## Pre-release evidence

Pin release builds to Python 3.13.17, available for both Windows x64 and Ubuntu 24.04 x64. CI installs the same patch before tagging. [Prior tag run](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44673559113)

Before release versioning, the runtime candidate ran 1,716 regression cases per platform. Windows passed 1,705 and Ubuntu on WSL passed 1,665, with the remainder skipped by environment. A fresh Windows daily-account session loaded ten skills and twelve project hooks. Real GPT-6.2 Sol and Astra medium child tasks settled at four and eight planning units respectively.

The release workflow subsequently passed 48 related tests per platform on Python 3.13.9. Both locales reproduced twice on each platform and matched across systems. Local service fixtures covered first draft creation, reruns, changed or missing assets, obsolete notes and query failures.
