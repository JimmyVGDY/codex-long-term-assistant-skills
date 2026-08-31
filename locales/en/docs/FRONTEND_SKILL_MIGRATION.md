# Frontend Skill v4.0 Migration (Codex)

The former `vue-frontend-engineering` Skill was renamed directly to `frontend-engineering`; no compatibility alias is retained.

- Previous invocation: `$vue-frontend-engineering`
- Current invocation: `$frontend-engineering`

The upgrade script backs up and removes the previous directory before installing the new Skill. Unrelated third-party Skills are not affected. After upgrading, restart Codex and run `/skills`; confirm that `frontend-engineering` appears and the previous name does not.
