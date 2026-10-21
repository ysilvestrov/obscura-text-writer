---
name: Obscura Text Writer
description: Літературний нуар для авторського робочого простору.
colors:
  bg-app: "#F7F4EF"
  bg-surface: "#FFFFFF"
  bg-subtle: "#EFECE6"
  accent-primary: "#6B1D2F"
  accent-hover: "#521523"
  accent-soft: "#F2E6E8"
  accent-text: "#6B1D2F"
  text-primary: "#1C1917"
  text-secondary: "#57534E"
  text-muted: "#78716C"
  border-color: "#E5E0D8"
  status-local: "#D97706"
  success: "#31634C"
  error: "#A12E36"
  warning: "#86520D"
  info: "#345A75"
  notice-text: "#FFFFFF"
  dark-bg-app: "#121110"
  dark-bg-surface: "#1C1917"
  dark-bg-subtle: "#26221F"
  dark-accent-primary: "#9E2A40"
  dark-accent-hover: "#B8324B"
  dark-accent-soft: "#2A181C"
  dark-accent-text: "#E7A7B5"
  dark-text-primary: "#E7E2DD"
  dark-text-secondary: "#A8A096"
  dark-text-muted: "#A8A096"
  dark-border-color: "#2E2925"
  dark-status-local: "#F59E0B"
  dark-success: "#90BEA4"
  dark-error: "#EF9DA4"
  dark-warning: "#E8BA77"
  dark-info: "#A8C6DF"
typography:
  headline:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "38px"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: "-.02em"
  title:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "25px"
    fontWeight: 400
    lineHeight: 1.25
  body:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    lineHeight: 1.6
  writing:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "17px"
    lineHeight: 1.95
  button:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  label:
    fontFamily: "'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
  brand:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontSize: "25px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-.01em"
rounded:
  control: "6px"
  panel: "12px"
  badge: "4px"
spacing:
  actions: "8px"
  controls: "12px"
  toolbar: "16px"
  cards: "20px"
  panel: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent-primary}"
    textColor: "{colors.notice-text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 15px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.control}"
    padding: "9px 15px"
  input:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  scene-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.text-primary}"
    padding: "12px"
  tab-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-text}"
    padding: "6px 12px"
  card:
    backgroundColor: "{colors.bg-surface}"
    rounded: "{rounded.panel}"
    padding: "28px"
  badge:
    backgroundColor: "{colors.bg-subtle}"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
---

# Design System: Obscura Text Writer

## Overview

**Creative North Star: "Літературний нуар"**

Теплий пергамент, білий аркуш і винний акцент формують стриману авторську майстерню. Georgia надає заголовкам і рукопису літературного характеру; системний шрифт зберігає читабельність керування та станів.

Бренд Obscura використовує точну надану користувачем SVG-іконку пера із замковою шпариною. Іконка спільна для шапки й favicon та постачається разом із застосунком.

**Key Characteristics:**
- Пергаментні бокові поверхні й білий редактор.
- Винні дії та вибір, бурштинова крапка локальної роботи.
- Щільне керування навколо просторого рукопису.

Джерела: `src/storygen/web/static/app.css`, `src/storygen/web/templates/{base,library,story,settings}.html`, `src/storygen/web/static/favicon.svg`. Оформлення та іконка відповідають погодженим матеріалам власника. Продуктовий контекст — `PRODUCT.md`; контракт — `SPEC.MD`, UI-006. Локальні знімки перевірки не входять до публічного пакета.

## Colors

Основний винний акцент позначає кнопки дій і активну сцену; його м’який відтінок — вибір сцени та матеріалу. Текстовий акцент окремий від заливки, щоб підтримувати читабельність темної палітри.

Бурштин використовується для крапки «Локальна робота». Семантичні success/error/warning/info залишаються кольорами станів. Повідомлення мають білі написи та сталу темну заливку відповідного стану навіть у темній темі.

Пергамент — загальний фон, білий — редактор, картки й поля, subtle — другорядні поверхні. Межі теплі та тонкі; основний текст чорнильний, допоміжний — теплий сірий.

Атрибут `[data-theme="dark"]` активує темні токени з префіксом `dark-`; CSS-змінні зберігають базові назви. Допоміжний текст і текстовий акцент освітлені для контрасту. Перемикача теми й автоматичного вибору за ОС немає.

## Typography

Georgia з резервним Times New Roman використовується в заголовках, назві бренду, редакторі й потоковому тексті. Segoe UI із системним резервом — у керуванні, підписах і допоміжних даних. Шрифти локальні; нових залежностей або мережевих ресурсів немає.

Заголовок бібліотеки використовує headline; заголовки секцій — title. Заголовок твору компактніший (29px), підписи панелей — малі (11px), напівжирні, з розрядкою (.12em). Дескриптор Text Writer — верхній регістр (10px, .12em). Рукопис має просторий міжрядковий інтервал, визначений writing.

## Layout

Широкий робочий простір зберігає три колонки: сцени (235px), гнучкий редактор, контекст (265px). За ширини до 1100px сцени звужуються (205px), контекст переходить під обидві колонки. До 650px блоки стають послідовними; список сцен обмежено висотою (240px) зі скролом, дескриптор бренду приховано.

Бібліотека обмежена шириною (1120px), налаштування — (960px). Картки бібліотеки адаптивні з мінімальною шириною до (260px). Основний відступ панелей — panel; дії групуються з інтервалом actions. Кнопки мають мінімальну висоту (42px), вкладки — (36px), на мобільному — (42px). Редактор має мінімальну висоту (54vh), на мобільному — (45vh); розмір рукопису там зменшується (16px).

## Elevation & Depth

Поверхні відділені фоном і однопіксельними межами. Тінь є лише під іконкою бренду та спливним повідомленням; їхні точні значення збережені в sidecar. CSS не задає анімацій або переходів.

## Shapes

Контроли мають м’які кути control, панелі — panel, бейджі — badge. Активна сцена має прямий лівий край і округлений правий.

**The Scene Marker Rule.** Лівий індикатор активної сцени має товщину (4px), прямо погоджену бріфом.

## Components

- Основна кнопка: винна заливка, білий текст, темніший hover; вимкнений стан має прозорість (.48).
- Другорядна кнопка: прозорий фон, сіра межа; hover додає м’який винний фон і текстовий акцент.
- Поля: біла поверхня, тепла межа, акцентний caret; focus змінює межу. Спільний focus-visible має контур (2px) із відступом (3px).
- Навігація сцен: активний рядок поєднує м’який фон, лівий індикатор і `aria-current`; другорядні дані йдуть нижче назви.
- Вкладки матеріалів: активна вкладка має м’який фон, акцентну межу й напівжирний текст; стан передається через `aria-pressed`.
- Картки: біла поверхня, тонка межа, літературний заголовок і системний допоміжний текст. Бейджі — компактні позначки на subtle.
- Заголовки сцен показуються без технічних Markdown-маркерів; редактор зберігає вихідний текст.

## Do's and Don'ts

### Do:
- Використовуйте спільні CSS-токени для кольорів, шрифтів і радіусів.
- Зберігайте триколонковий робочий простір і реалізовану адаптацію до вузьких екранів.
- Використовуйте точну надану SVG-іконку для бренду та favicon.
- Зберігайте видимі фокус і вибір разом із семантичними атрибутами.

### Don't:
- Не повертайте зелений як основний акцент бренду.
- Не додавайте мережеві шрифти, зовнішні асети або залежності для цього оформлення.
- Не застосовуйте очищення UI-заголовків до тексту рукопису.
