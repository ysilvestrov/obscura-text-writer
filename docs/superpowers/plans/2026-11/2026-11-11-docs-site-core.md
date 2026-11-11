# Сайт інструкцій: ядро (#29, R-25, PR 1) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Власний збирач двомовного сайту з `docs/site/`, перевірка синхронізації мов і посилань, workflow GitHub Pages і дві перші сторінки UA/EN.

**Architecture:** `scripts/site_common.py` — спільні правила (маніфест, `heading_id`, хеші); `scripts/build_site.py` рендерить markdown-it-py у `_site/`; `scripts/check_site.py` перевіряє дерево й викликається з `check_docs.check()`; `.github/workflows/site.yml` збирає на PR і публікує з `main`.

**Tech Stack:** Python 3.10+, markdown-it-py (уже залежність), GitHub Actions (`actions/configure-pages@v5`, `upload-pages-artifact@v3`, `deploy-pages@v4`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-10-docs-site-design.md`

## Global Constraints

- Маніфест `docs/site/site.json`: `{"languages":["uk","en"],"pages":[{"slug":…,"title":{"uk":…,"en":…}}]}`; сторінка `docs/site/<lang>/<slug>.md`; порядок маніфесту — порядок навігації.
- `id` заголовка: нижній регістр, кирилиця зберігається, пробіли → `-`, решта розділових знаків вилучається, повтори → `-2`, `-3`.
- Посилання `<slug>.md` / `<slug>.md#якір` у межах маніфесту → `<slug>.html` / `<slug>.html#якір`. Усі шляхи відносні (підшлях `/obscura-text-writer/`). Вихід детермінований.
- Зображення сайту лише з `docs/images/site/`; кожне має alt.
- Заборонені посилання: `docs/superpowers/`, `docs/research/`, `docs/diagnostics/`, `docs/specs/`, `SPEC.MD`, `docs/STATUS.md`.
- `docs/site/sync.json`: `{"<slug>":{"uk":"<sha256>","en":"<sha256>"}}`; `python scripts/check_site.py --rehash <slug>`.
- Workflow: PR — build+check без deploy; push у `main` з path-фільтром `docs/site/**`, `docs/images/site/**`, `scripts/build_site.py`, `scripts/site_common.py`, `scripts/check_site.py`, `.github/workflows/site.yml` — deploy + `curl --fail`; `concurrency: {group: pages, cancel-in-progress: false}` у задачі deploy; права `contents: read`, `pages: write`/`id-token: write` лише в deploy.
- Без мережі й модельних викликів у збирачі та перевірці. Документація українською.

## Review Focus

1. Якір із кирилицею й апострофом (`вимоги`, `пам’ять`) — однаковий `id` у збирачі й перевірці.
2. Посилання на зовнішній URL або `mailto:` не переписується й не перевіряється як локальне.
3. Посилання на `.md` поза маніфестом (наприклад `../../README.md`) — помилка перевірки, а не тихе 404 на сайті.
4. CRLF у джерелі: хеш береться з байтів файлу; зміна лише закінчень рядків теж вимагає `--rehash` (чесна поведінка, задокументована в повідомленні).
5. Навігація й перемикач мови працюють з будь-якої сторінки під підшляхом (лише відносні `href`).

---

### Task 1: Збирач

**Files:** Create `scripts/site_common.py`, `scripts/build_site.py`, `docs/site/template.html`, `docs/site/site.css`; Test `tests/test_docs_site.py`.

**Interfaces — Produces:** `load_manifest(root)->dict`; `heading_id(text:str, seen:dict)->str`; `page_hash(path)->str`; `build(root, out)->list[Path]`; `rewrite_href(href, slugs)->str`.

- [ ] Тести (req DOCS-SITE): `test_heading_ids_keep_cyrillic_and_number_repeats` (`Вимоги` → `вимоги`, повтор → `вимоги-2`, `Пам’ять і «сцени»!` → `память-і-сцени`); `test_section_link_is_rewritten_and_target_has_id` (S06: `[x](install.md#вимоги)` → `href="install.html#вимоги"`, у `install.html` є `id="вимоги"`); `test_build_is_relative_and_deterministic` (S03: усі `href`/`src` у `_site` не починаються з `/` або `http` для локальних; дві збірки дають однакові байти; `en/install.html` має `lang="en"` і перемикач на `../install.html`); зовнішній URL лишається.
- [ ] RED → реалізація → GREEN; коміт.

### Task 2: Перевірка

**Files:** Create `scripts/check_site.py`; Modify `scripts/check_docs.py` (виклик `check_site.check(root)`, якщо `docs/site/site.json` існує); Test `tests/test_docs_site.py`.

**Interfaces — Produces:** `check(root)->list[str]`; `rehash(root, slug)->None`; CLI `--rehash <slug>`.

- [ ] Тести: `test_changed_uk_only_fails_with_rehash_hint` і `test_changed_en_only_fails_with_rehash_hint` (S01); `test_internal_material_link_fails` (S02, кожен заборонений префікс); `test_missing_anchor_fails` (S06); `test_missing_pair_image_and_alt` ; `test_md_outside_manifest_fails`; `test_rehash_records_both_hashes`; `test_check_docs_includes_site_errors`.
- [ ] RED → реалізація → GREEN; коміт.

### Task 3: Workflow

**Files:** Create `.github/workflows/site.yml`; Modify `.gitignore` (`_site/`); Test `tests/test_docs_site.py::test_workflow_publishes_only_from_main` (S04: задача deploy має `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, `concurrency.group == 'pages'`, `cancel-in-progress: false`; верхні права лише `contents: read`; `pages: write` лише в deploy; на `pull_request` немає кроку `deploy-pages` поза цією умовою).

- [ ] Тест читає YAML простим розбором тексту (PyYAML не залежність — перевірити; якщо немає, перевіряти рядки). RED → файл → GREEN; коміт.

### Task 4: Сторінки, SPEC, документація

**Files:** Create `docs/site/site.json`, `docs/site/{uk,en}/{index,install,first-story}.md`, `docs/site/sync.json`; Modify `SPEC.MD` (Requirement DOCS-SITE S01–S06, розділ запуску), `docs/verification/traceability.json`, `docs/verification/manual.md#docs-site-publish`, `AGENTS.md` (правило документації посилається на `docs/site/`), `README.md` (посилання на сайт), журнал виконання, беклог R-25.

- [ ] Сторінки: «Встановлення й запуск» (Windows, Python, `.env`, ключі, порт, data-dir, резервне копіювання, розділ «Інсталятор — з'явиться в #30»), «Перший твір» (за новим інтерфейсом #89), головна з навігацією. `--rehash` для кожної.
- [ ] `python scripts/build_site.py` і `python scripts/check_docs.py` — OK; повний pytest; коміт.
