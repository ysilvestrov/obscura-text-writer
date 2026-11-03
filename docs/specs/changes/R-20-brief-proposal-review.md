# Видиме прийняття пропозиції завдання

25.10.2026. Дефект: planner brief із proposed_changes збережений як needs_review, але вкладка показує старий head; Save старого тексту не приймає нову пропозицію, draft readiness блокований stale brief.

Зберегти чинний явний accept-brief gate. Вкладка brief показує найновішу complete/fresh пропозицію, новішу за selected brief head, якщо її JSON містить proposed_changes. Історичні/застарілі/alternative без proposed_changes не підставляти автоматично. Після генерації чистий відкритий brief оновлюється навіть без зміни head; новий ввід/Save не перезаписується. Поруч із завданням показати proposed_changes і явне «Прийняти завдання»; Save лишається лише збереженням. Кнопка приймає саме показаний saved version ID з чинним scene revision, недоступна для dirty/saving/stale/history/активного виклику. Після accept draft readiness оновлюється без inference. API/SQL/семантика прийняття незмінні.

Перевірити на synthetic fixture зі stale current brief і fresh proposed brief: показ нового тексту, no-op Save не приймає, явний accept перемикає head і відкриває draft action; dirty edit вимагає Save; CAS-конфлікт лишає текст. Реальні авторські версії автоматично не приймати.
