import json
import re
import time
import random
from pathlib import Path
import anthropic
import yaml
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, ALLOWED_TAGS, VAULT_FOLDERS, TRUNCATE_CHARS, MAX_RETRIES

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_RETRYABLE = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)

SYSTEM_PROMPT = (
    "Ты извлекаешь структуру из текста статей и расшифровок видео. "
    "Отвечай ТОЛЬКО валидным JSON-объектом, без пояснений и без markdown-ограждений. "
    "Если какого-то поля в тексте нет — ставь null или пустой список. "
    "Поля title, summary, concepts, instructions, insights — всегда на русском языке, "
    "независимо от языка исходного материала. "
    "Термины, названия инструментов, программ и аббревиатуры оставляй на языке оригинала (AI, Figma, UX, CSS и т.д.). "
    "Теги (tags) — всегда на английском языке, в snake_case."
)

FOLDER_DESCRIPTIONS = """Выбери ОДИН ключ папки из списка ниже. Читай описания внимательно.

ИНСТРУМЕНТЫ (выбирай только если материал именно об этом инструменте):
- "figma" — только Figma (плагины, фичи, туториалы по Figma)
- "photoshop" — только Adobe Photoshop
- "tilda" — только конструктор Tilda
- "wordpress" — только WordPress
- "notion" — только Notion
- "obsidian" — только Obsidian
- "claude" — только Claude AI (Anthropic)
- "cursor" — только Cursor IDE
- "others_AI" — другие AI-инструменты (ChatGPT, Midjourney, Stable Diffusion, Runway и т.д.)
- "programms_motion_design" — программы для моушн-дизайна и 3D: After Effects, Blender, Cinema 4D, DaVinci Resolve и подобные

РАБОТА И КАРЬЕРА:
- "interview_prep" — подготовка к собеседованиям: вопросы, кейсы, что спрашивают на интервью
- "career" — карьера в целом: резюме, поиск работы, смена профессии, грейды, зарплаты, опыт работы за рубежом
- "linkedin" — LinkedIn: как вести профиль, алгоритмы, нетворкинг через LinkedIn
- "portfolio" — портфолио дизайнера: как собирать, разборы чужих портфолио, советы по презентации работ
- "freelance" — фриланс: как находить клиентов, договоры, ценообразование, работа на себя
- "talks_with_designers" — интервью с дизайнерами, подкасты, разговорный контент о профессии

ПРОДУКТОВЫЕ ДИСЦИПЛИНЫ:
- "organize_my_workday" — личная продуктивность, тайм-менеджмент, организация рабочего дня
- "team_workflows" — командные процессы, agile, scrum, ретроспективы, взаимодействие в команде
- "product_management" — продуктовый менеджмент: роадмап, приоритизация, работа с беклогом, метрики продукта
- "ux_research" — market research, конкурентный анализ, изучение рынка, Jobs-to-be-done, персоны пользователей
- "brand_design" — брендинг: логотипы, фирменный стиль, айдентика, brand guidelines
- "tech_leading" — техническое лидерство, системная архитектура, tech lead, engineering management
- "devops" — DevOps, CI/CD, деплой, инфраструктура, docker, kubernetes
- "analysis" — бизнес-анализ, системный анализ, написание спецификаций, UML-схемы, постановка задач для разработки
- "data_analysis" — аналитика данных: SQL, Python для анализа, дашборды, BI-инструменты, работа с данными
- "prod_analysis" — продуктовая аналитика: метрики, воронки, A/B тесты, retention, аналитика поведения пользователей
- "product_design" — product design как профессия и процесс: если в материале явно говорится про product designer или product design
- "design_system" — дизайн-системы, компонентные библиотеки, токены, гайдлайны, атомарный дизайн
- "ux_ui_design" — UX/UI дизайн в целом: если материал про дизайн интерфейсов без чёткой привязки к product_design; разборы интерфейсов, принципы UX, паттерны UI
- "graphic_design" — графический дизайн в целом: если нет более точной подпапки ниже
- "beautiful_youtube_covers" — обложки для YouTube: как делать превью, thumbnail design, кликбейт-обложки
- "references" — референсы, мудборды, источники вдохновения, подборки визуала
- "mockups" — мокапы: как делать, где брать, презентация дизайна на макетах
- "typography" — типографика: шрифты, леттеринг, типографские приёмы, подбор шрифтов
- "colors" — цвет: цветовые палитры, теория цвета, колористика, подбор цветов
- "print_design" — дизайн для печати: постеры, афиши, флаеры, упаковка, полиграфия
- "prepress" — допечатная подготовка: цветопроба, технические требования к печати, CMYK, растрирование
- "motion_design" — моушн-дизайн, анимация интерфейсов, видеографика, transitions
- "ux_research_users" — пользовательское тестирование: когда кликабельный прототип тестируют с реальными юзерами, юзабилити-тесты, интервью с пользователями по прототипу
- "html_css" — HTML, CSS, вёрстка, веб-технологии для дизайнеров
- "development" — разработка ПО, программирование (не дизайн)
- "qa" — тестирование продукта, QA, бета-тестирование
- "marketing" — маркетинг, продвижение, SMM, контент-маркетинг
- "sales" — продажи, переговоры, работа с клиентами

ПРОЧЕЕ:
- "tablet_for_design" — графические планшеты для рисования (Wacom, iPad для дизайна)
- "DIY" — самодельные проекты, хобби, "сделай сам"
- "psychology" — психология: когнитивные искажения, поведение людей, психология восприятия, мотивация, эмоции
- "architecture" — архитектура зданий и пространств: стили архитектуры, окружающая среда, интерьеры, городская среда (не системная архитектура ПО!)
- "inbox" — если ни одна папка выше не подходит"""

USER_TEMPLATE = """\
Извлеки структуру из следующего текста.

Верни JSON строго в таком виде:
{{
  "title": "заголовок или null",
  "summary": "2-4 предложения о чём материал и почему полезен",
  "concepts": ["ключевая идея 1", "ключевая идея 2"],
  "instructions": ["шаг 1", "шаг 2"],
  "entities": ["конкретный человек/инструмент/алгоритм"],
  "tags": ["тег1", "тег2"],
  "insights": ["важная мысль 1, заслуживающая особого внимания"],
  "published_date": "YYYY-MM-DD или null",
  "author": "автор или null",
  "folder": "ключ_папки"
}}

Теги — это значимые сущности материала: инструменты, процессы, концепции, предметные области, которые есть в этом материале. Тегов может быть много. Не ставь тег если понятие просто упоминается вскользь или является лишь контекстом — ставь только если это реально присутствующая значимая сущность материала.
Для ориентира — примеры хороших тегов из похожих материалов: {allowed_tags}

Для поля instructions: если материал обучающий (туториал, урок, пошаговое руководство) — перечисли конкретные шаги/действия которым учит материал. Если не обучающий — верни пустой список [].

Для поля insights: выдели 1-3 мысли, которые заслуживают особого внимания — идеи которые автор специально подчёркивает, неожиданные выводы, или то что ИИ считает особенно ценным для читателя. Если материал поверхностный и таких мыслей нет — верни пустой список [].

{folder_descriptions}

Текст:
{text}
"""


def _load_folder_examples() -> str:
    path = Path(__file__).parent / "folder_examples.yml"
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return ""
    lines = ["\nПримеры правильного и неправильного распределения по папкам:"]
    for folder, content in data.items():
        if content.get("YES"):
            for ex in content["YES"]:
                lines.append(f'  ✓ "{ex}" → {folder}')
        if content.get("NOT"):
            for ex in content["NOT"]:
                lines.append(f'  ✗ "{ex}"')
    return "\n".join(lines)


def enrich(text: str, hint_title: str | None = None) -> dict:
    truncated = text[:TRUNCATE_CHARS]
    user_msg = USER_TEMPLATE.format(
        allowed_tags=", ".join(ALLOWED_TAGS),
        folder_descriptions=FOLDER_DESCRIPTIONS + "\n" + _load_folder_examples(),
        text=truncated,
    )

    data = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = _client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            raw = _strip_markdown_fences(raw)
            data = json.loads(raw)
            data["_usage"] = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            break
        except json.JSONDecodeError as e:
            # Model returned malformed JSON — retry up to MAX_RETRIES
            last_error = e
        except _RETRYABLE as e:
            last_error = e

        if attempt < MAX_RETRIES - 1:
            pause = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(pause)

    if data is None:
        raise RuntimeError(f"enrich() не смог получить ответ за {MAX_RETRIES} попыток") from last_error

    if not data.get("title") and hint_title:
        data["title"] = hint_title

    if data.get("folder") not in VAULT_FOLDERS:
        data["folder"] = "inbox"

    return data


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
