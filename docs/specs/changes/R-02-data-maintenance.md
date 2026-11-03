# R-02 — Цілісність, резервування й відновлення

Дата: 20.10.2026. Статус: реалізовано; повний offline pytest — 256 passed, 1 skipped (створення symlink недоступне в цьому Windows-середовищі). Архітектуру відображено у кореневій SPEC.MD.
Джерела: [SPEC.MD](../../../SPEC.MD), [беклог](../../superpowers/plans/2026-10-20-remediation-backlog.md).

## Межі

Локальні CLI-команди без моделей, dotenv і вебсервера. Діагностика не змінює дані й не застосовує міграцій. Backup і restore не перезаписують існуючі каталоги. Авторські дані у цій розробці не обробляються: приймання на синтетичних fixtures.

### Requirement: R02-001 — Read-only fsck

`storygen fsck --data-dir PATH [--json]` SHALL відкривати наявну SQLite через URI `mode=ro` і перевіряти схему 2, SQLite integrity/FK, payload/колонки версій і сцен, власників/типи головних версій, джерела, dependency edges та SHA-256 файлів. Архівні матеріали SHALL перевірятися нарівні з активними. Відсутня БД SHALL не створюватися.

#### Scenario: Пошкодження або сирота
- GIVEN відсутній blob, змінений hash, некоректна голова або незареєстрований immutable файл
- WHEN виконується fsck
- THEN звіт містить окремий код проблеми й exit code 1
- AND жоден файл/рядок не виправляється й не видаляється.

#### Scenario: Непідтримувана схема
- GIVEN наявна БД має іншу schema version
- WHEN виконується fsck
- THEN повертається діагностика без запуску Database/Repository чи міграції.

### Requirement: R02-002 — Перевірений холодний backup

`storygen backup --data-dir PATH --destination PATH [--json]` SHALL вимагати зупиненого сервера, захоплювати той самий exclusive worker lock і відхиляти зайнятий каталог. Destination SHALL бути новим і поза джерелом, не його предком. Джерело SHALL пройти fsck до створення destination.

#### Scenario: Зайняте джерело
- GIVEN worker утримує lock каталогу
- WHEN запитується backup
- THEN команда відмовляє без створення destination і без зупинки worker.

#### Scenario: Успішний резерв
- GIVEN коректний холодний каталог
- WHEN створюється backup
- THEN destination містить `data/`, SQLite backup API-знімок та manifest із версією формату, UTC, переліком шляхів/розмірів/SHA-256
- AND manifest набуває `complete` лише після fsck копії та перевірки її inventory.

### Requirement: R02-003 — Відновлення без перезапису

`storygen restore --backup-dir PATH --destination PATH [--json]` SHALL перевіряти complete manifest, точний inventory, кожен hash і fsck резерву до створення нового destination. Відновлення SHALL зберігати незмінні версії, голови, SQL-стани й UUID без inference/recovery/migration.

#### Scenario: Неповний або змінений резерв
- GIVEN manifest incomplete або будь-який файл змінено/додано/видалено
- WHEN запитується restore
- THEN команда відмовляє й не створює destination.

#### Scenario: Перерване копіювання
- GIVEN destination вже створено, але операція завершується помилкою
- WHEN користувач переглядає результат
- THEN backup лишається з incomplete manifest або restore — з `.restore-incomplete.json`
- AND команда повертає помилку, не видаляючи ні джерело, ні незавершений результат.

## Технічний контракт

- `storage/locking.py`: чинний AppInstanceLock переноситься без зміни протоколу; import із generation.worker лишається сумісним.
- `storage/integrity.py`: `check_integrity(root: Path) -> IntegrityReport`, `ok`, `issues`, лічильники версій/джерел/допоміжних файлів. Шляхи замкнені в root; symlink/junction/reparse-point в дереві відхиляються до читання їхнього вмісту. Stale/needs_review самі по собі не є пошкодженням.
- `storage/backup.py`: `create_backup(source, destination) -> Path`, `restore_backup(backup, destination) -> Path`. Формат 1: `manifest.json`, `data/`; резерв зберігає всі звичайні файли data-dir, крім worker.lock та SQLite WAL/SHM/journal. Сама SQLite копіюється через backup API. Mutable partial/exports/calibration reports зберігаються й покриваються manifest, але не видаються за immutable версії.
- `maintenance.py`: argparse, JSON або короткий підсумок; fsck exit 0/1, operational error 1, argument syntax 2. `server.main` диспетчеризує підкоманди до імпорту web/uvicorn і читання .env. Запуск вебсервера без підкоманди зберігається.
- Немає спільної FS/SQL-транзакції: гарантія backup спирається на холодне джерело й кооперативний lock. Прямі зовнішні записи поза протоколом не підтримуються. fsck живого каталогу є лише діагностикою знімка SQL і файлів у момент читання; для остаточного висновку потрібне холодне джерело.
- Порожній worker.lock може бути створений кооперативним блокуванням backup; це службова операція, не зміна авторських матеріалів. fsck lock не створює.
- Відновлення не стартує worker: interrupted/recovery виконується лише при наступному звичайному запуску за чинним контрактом.
- Repository відхиляє каталог із `.restore-incomplete.json` до відкриття/міграції БД. Маркер знімає лише успішне завершення restore.
- Backup також відхиляє такий каталог до створення destination; restore перевіряє відсутність зайвих файлів як у `data/`, так і поруч із manifest. Будь-який незареєстрований файл у `versions/` або `sources/`, незалежно від розширення, є orphan_blob.
- Для холодної checkpointed БД без непорожнього WAL read-only відкриття використовує `immutable=1`, щоб не створювати WAL/SHM. Для наявного непорожнього WAL SQLite читає актуальний журнал через `mode=ro` й може створювати/оновлювати службовий SHM; авторські рядки й blobs не записуються. Це не гарантія побайтової незмінності службових файлів живої БД.

## Приймання

Read-only/відсутня/стара БД; missing/hash/orphan/head/edge/source corruption; архівні дані; зайнятий lock; nested/existing destination; symlink; перерване копіювання; змінений inventory; round-trip з головами/порядком/хешами/допоміжними файлами; CLI без web/model calls. Сфокусовані тести, повний pytest, оновлення SPEC і runbook.
