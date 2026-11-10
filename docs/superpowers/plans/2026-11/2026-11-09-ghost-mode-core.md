# Ghost Mode — PR 1: ядро (#55)

Дизайн: `docs/superpowers/specs/2026-11/2026-11-09-ghost-mode-design.md` (затверджено 09.11.2026 з поправкою до рішення 2).
Гілка: `claude/ghost-core-55`, від `claude/brief-link-44` (потрібен `author_lineage` з #44; PR відкривається на `main`).

Обсяг PR 1 — ядро без інтерфейсу: поділ на блоки (Python і дзеркало JS зі спільними векторами), частка збігів, метадані `ghost_rewrite`, `POST /api/scenes/{id}/ghost-rewrite`. Режим редактора, статистика в UI, користувацька документація й Playwright — PR 2 (сценарії S02, S03, S06, S08 додаються туди).

## Задача 1. Поділ на блоки й частка збігів (inline)

Файли: `src/storygen/authoring/ghost.py`, `src/storygen/web/static/ghost-blocks.js`, `tests/fixtures/ghost_blocks.json`, `tests/authoring/test_ghost.py`, `tests/web/js/ghost_blocks.mjs`.

- `ghost_blocks(text) -> list[GhostBlock{kind:'text'|'separator', start, end}]` за правилами дизайну; зміщення в LF-тексті, `start` — початок першого абзацу (після strip), `end` — кінець останнього.
- Уточнення до дизайну: короткий залишок (< 160) на будь-якій межі (розділювач, заголовок, кінець) приєднується до попереднього текстового блоку того самого фрагмента, якщо сам залишок не починається із заголовка; інакше лишається окремим блоком. Так заголовок завжди починає блок.
- `overlap_4gram(author, draft) -> float | None` (округлення до 4 знаків).
- JS `ghostBlocks(text)` дає ті самі блоки; pytest запускає node-тест на спільних векторах.

## Задача 2. Метадані й збереження (inline)

Файли: `src/storygen/domain.py`, `src/storygen/storage/repository.py`, `src/storygen/generation/dependencies.py`, `src/storygen/web/routes_versions.py`, `tests/web/test_ghost_rewrite_api.py`.

- `GhostRewriteStats` на `VersionRef.ghost_rewrite` (payload, без міграції, поза sha/залежностями).
- `save_manual_draft(..., author_lineage=None, ghost_rewrite=None)`: явний родовід замінює голову; з `ghost_rewrite` перевірка «текст не змінився» не застосовується.
- `save_ghost_rewrite(repo, scene_id, body)`: перевірка джерела (404/400/409), `blocks` рахує сервер, `blocks_skipped ≤ blocks`, `overlap_4gram` із текстів.
- Тести: родовід до AI-чернетки, незмінність AI-чернетки, `input_refs`/знімок/ребра як у звичайної ручної чернетки, родовід прози з авторської чернетки досягає brief, 404/400/409, конфлікт лишає версію в історії, частка збігів.

## Задача 3. SPEC і перевірки (inline)

- SPEC.MD: Requirement GHOST-REWRITE (технічний опис, інваріанти, обмеження), S01, S04, S05, S07; згадка в PLANNER-ACQUAINTANCE; Source map.
- traceability, журнал виконання, `scripts/check_docs.py`, `scripts/verify.py` → `docs/STATUS.md`.
- Користувацька документація в PR 1 не змінюється: режим ще не має інтерфейсу; інструкції UA/EN і знімки — PR 2.
