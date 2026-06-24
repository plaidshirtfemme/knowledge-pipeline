"""
Knowledge Pipeline Dashboard
Run: streamlit run dashboard.py
"""

import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import yaml

from config import VAULT_PATH, VAULT_FOLDERS

# ── Global Plotly theme ───────────────────────────────────────────────────────
_COLORS = ["#58a6ff", "#3fb950", "#f85149", "#8b949e", "#a5d6ff", "#56d364", "#ffa198"]
pio.templates["kp_dark"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#13161c",
        font=dict(family="sans-serif", color="#8b949e", size=11),
        colorway=_COLORS,
        xaxis=dict(gridcolor="#1e2330", linecolor="#1e2330", zerolinecolor="#1e2330",
                   tickfont=dict(color="#6e7681", size=10)),
        yaxis=dict(gridcolor="#1e2330", linecolor="#1e2330", zerolinecolor="#1e2330",
                   tickfont=dict(color="#6e7681", size=10)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#8b949e")),
        margin=dict(t=24, b=32, l=8, r=8),
        hoverlabel=dict(bgcolor="#1e2330", font_color="#c9d1d9", bordercolor="#30363d"),
    )
)
pio.templates.default = "kp_dark"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Knowledge Pipeline Dashboard",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* ── Reset & base ── */
[data-testid="stSidebarNav"] { display: none; }
[data-testid="stAppViewContainer"] > .main { background-color: #0a0c10; }
.block-container { padding-top: 0.75rem; padding-bottom: 1rem; max-width: 1400px; }
body, .stMarkdown, p, span, div { color: #c9d1d9; }
h1 { font-size: 1.35rem !important; font-weight: 700; letter-spacing: -0.3px; color: #f0f6fc !important; }
h2 { font-size: 1rem !important; font-weight: 600; color: #f0f6fc !important; }
h3 { font-size: 0.82rem !important; font-weight: 500; color: #8b949e !important; }

/* ── Tabs — pill style как на референсе ── */
div[data-testid="stTabs"] [role="tablist"] {
    background: #13161c;
    border-radius: 8px;
    padding: 3px;
    border: 1px solid #1e2330;
    gap: 2px;
    flex-wrap: wrap;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.76rem;
    font-weight: 500;
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    color: #6e7681;
    border: none;
    background: transparent;
    transition: all 0.15s ease;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #c9d1d9;
    background: #1e2330;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: #1f3460 !important;
    color: #58a6ff !important;
    font-weight: 600;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none; }
div[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #13161c;
    border: 1px solid #1e2330;
    border-radius: 8px;
    padding: 1rem 1.2rem;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    color: #6e7681 !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    font-weight: 500;
}
[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #f0f6fc !important; }
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] > div { font-size: 0.72rem !important; }
div[data-testid="stMetricDelta"] [data-testid="stMetricDeltaPositive"] { color: #3fb950 !important; }
div[data-testid="stMetricDelta"] [data-testid="stMetricDeltaNegative"] { color: #f85149 !important; }

/* ── Dataframe / таблицы ── */
[data-testid="stDataFrame"] { border: 1px solid #1e2330; border-radius: 8px; overflow: hidden; }
[data-testid="stDataFrame"] table { background: #13161c; }
[data-testid="stDataFrame"] th {
    background: #0d0f14 !important;
    color: #8b949e !important;
    font-size: 0.75rem !important;
    font-weight: 500;
    border-bottom: 1px solid #1e2330 !important;
    padding: 0.5rem 0.75rem !important;
}
[data-testid="stDataFrame"] td {
    font-size: 0.82rem !important;
    color: #c9d1d9 !important;
    border-bottom: 1px solid #1a1e27 !important;
    padding: 0.45rem 0.75rem !important;
    background: #13161c !important;
}
[data-testid="stDataFrame"] tr:hover td { background: #1a1e27 !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #13161c;
    border: 1px solid #1e2330 !important;
    border-radius: 8px;
}
[data-testid="stExpander"] summary { color: #6e7681; font-size: 0.82rem; }

/* ── Selectbox / multiselect ── */
[data-baseweb="select"] { background: #13161c !important; border-color: #1e2330 !important; border-radius: 6px; }
[data-baseweb="tag"] { background: #1e2330 !important; color: #c9d1d9 !important; border-radius: 4px; font-size: 0.7rem; }

/* ── Divider ── */
hr { border-color: #1e2330 !important; margin: 0.75rem 0; }

/* ── Caption / small text ── */
.stCaption, [data-testid="stCaptionContainer"] { color: #6e7681 !important; font-size: 0.72rem !important; }

/* ── Code block ── */
[data-testid="stCode"] { background: #13161c !important; border: 1px solid #1e2330; border-radius: 6px; }

/* ── Plotly charts ── */
.js-plotly-plot .plotly, .js-plotly-plot .plotly .svg-container { background: transparent !important; }

/* ── Info / warning boxes ── */
[data-testid="stInfo"] { background: #13161c; border-left: 3px solid #1e2330; border-radius: 6px; color: #6e7681; }
[data-testid="stSuccess"] { background: #0d1f12; border-left: 3px solid #3fb950; border-radius: 6px; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0a0c10; }
::-webkit-scrollbar-thumb { background: #1e2330; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #30363d; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_notes() -> pd.DataFrame:
    records = []
    for md_file in VAULT_PATH.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
            if not m:
                continue
            fm = yaml.safe_load(m.group(1)) or {}
            if not fm.get("note_id"):
                continue
            folder_key = next(
                (k for k, v in VAULT_FOLDERS.items() if VAULT_PATH / v == md_file.parent),
                "inbox"
            )
            added_raw = str(fm.get("added", ""))[:10]
            pub_raw   = str(fm.get("published", ""))[:10]
            records.append({
                "note_id":      fm.get("note_id", ""),
                "title":        fm.get("title", md_file.stem),
                "source_type":  fm.get("source_type", "unknown"),
                "published":    pub_raw or None,
                "added":        added_raw or None,
                "folder":       folder_key,
                "tags":         fm.get("tags") or [],
                "needs_review": bool(fm.get("needs_review")),
                "no_subtitles": bool(fm.get("no_subtitles")),
                "channel":      fm.get("channel") or "",
                "author":       fm.get("author") or "",
            })
        except Exception:
            continue
    df = pd.DataFrame(records)
    if not df.empty:
        df["added_dt"] = pd.to_datetime(df["added"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_events() -> pd.DataFrame:
    """Load manual event log (events.yml) for timeline overlay."""
    path = Path(__file__).parent / "events.yml"
    if not path.exists():
        return pd.DataFrame(columns=["date", "label", "team", "type"])
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return pd.DataFrame(data)


df_all = load_notes()

if df_all.empty:
    st.error("Заметки не найдены. Проверь VAULT_PATH в .env")
    st.stop()

# ── Global filters (above tabs) ───────────────────────────────────────────────

st.title("🧠 Knowledge Pipeline Dashboard")

with st.expander("🔧 Глобальные фильтры", expanded=False):
    col_f1, col_f2, col_f3 = st.columns(3)

    min_date = df_all["added_dt"].min().date() if df_all["added_dt"].notna().any() else date(2024, 1, 1)
    max_date = df_all["added_dt"].max().date() if df_all["added_dt"].notna().any() else date.today()

    with col_f1:
        date_from = st.date_input("С даты", value=min_date, min_value=min_date, max_value=max_date)
    with col_f2:
        date_to = st.date_input("По дату", value=max_date, min_value=min_date, max_value=max_date)
    with col_f3:
        src_filter = st.multiselect("Тип источника", options=sorted(df_all.source_type.unique()),
                                    default=sorted(df_all.source_type.unique()))

# Apply global filters
df = df_all.copy()
if df["added_dt"].notna().any():
    df = df[df["added_dt"].dt.date.between(date_from, date_to)]
if src_filter:
    df = df[df.source_type.isin(src_filter)]

st.caption(f"Показано {len(df)} из {len(df_all)} заметок · фильтр: {date_from} — {date_to}")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tabs = st.tabs([
    "🏠 PM / Overview",
    "🔬 Research",
    "🏗️ Architecture",
    "📋 BA / SA",
    "🎨 Design",
    "⚙️ Dev & Pipeline",
    "✅ Quality",
    "🚀 Release",
    "📡 Monitoring",
    "📈 Growth",
    "⏱ Timeline",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 0 — PM / Overview
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("PM / Overview")
    st.caption("Velocity, покрытие тем, health команды, спринты")

    # KPI row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Всего заметок", len(df))
    c2.metric("Видео", (df.source_type == "video").sum())
    c3.metric("Статьи", (df.source_type == "article").sum())
    c4.metric("Needs review", df.needs_review.sum(),
              delta=f"{df.needs_review.mean()*100:.0f}%", delta_color="inverse")
    c5.metric("Папок заполнено",
              df[df.folder != "inbox"].folder.nunique(),
              delta=f"из {len(VAULT_FOLDERS)}")

    st.divider()

    # Velocity: notes per week
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Velocity — заметок в неделю**")
        vel = df[df["added_dt"].notna()].copy()
        if not vel.empty:
            vel["week"] = vel["added_dt"].dt.to_period("W").astype(str)
            by_week = vel.groupby("week").size().reset_index(name="count")
            by_week["cumulative"] = by_week["count"].cumsum()
            fig = go.Figure()
            fig.add_bar(x=by_week.week, y=by_week["count"], name="За неделю",
                        marker_color="#6366f1")
            fig.add_scatter(x=by_week.week, y=by_week["cumulative"], name="Накопительно",
                            line=dict(color="#f59e0b", width=2), yaxis="y2")
            fig.update_layout(
                height=300,
                yaxis=dict(title="Заметок/неделю"),
                yaxis2=dict(title="Всего", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1),
                margin=dict(t=10, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных о датах добавления")

    with col_r:
        st.markdown("**Покрытие по папкам**")
        folder_counts = df.folder.value_counts().reset_index()
        folder_counts.columns = ["folder", "count"]
        fig2 = px.bar(folder_counts.head(15), x="count", y="folder",
                      orientation="h", color="count",
                      color_continuous_scale="Blues",
                      labels={"count": "Заметок", "folder": ""})
        fig2.update_layout(height=300, showlegend=False,
                           coloraxis_showscale=False,
                           yaxis={"categoryorder": "total ascending"},
                           margin=dict(t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Spotify squad health placeholder
    st.markdown("**Spotify Squad Health — статус команд**")
    st.caption("🟡 Placeholder — подключи источник задач (Jira / Linear / GitHub Projects)")
    health_data = {
        "Команда":    ["Pipeline / Dev", "Enrichment / AI", "Vault / Notes", "Dashboard"],
        "Velocity":   ["🟢 Хорошо",      "🟢 Хорошо",       "🟡 ОК",          "🟡 ОК"],
        "Quality":    ["🟡 ОК",          "🟡 ОК",            "🟠 Требует внимания", "🟢 Хорошо"],
        "Delivery":   ["🟢 Хорошо",      "🟢 Хорошо",       "🟢 Хорошо",      "🔴 В процессе"],
    }
    st.dataframe(pd.DataFrame(health_data), use_container_width=True, hide_index=True)

    st.divider()

    # Sprint placeholder
    st.markdown("**Спринты**")
    st.caption("🟡 Placeholder — настрой спринты в events.yml")
    sprint_df = pd.DataFrame([
        {"Спринт": "Sprint 1", "Команда": "Pipeline", "Старт": "2026-06-01", "Конец": "2026-06-14", "Статус": "✅ Завершён"},
        {"Спринт": "Sprint 1", "Команда": "Dashboard", "Старт": "2026-06-15", "Конец": "2026-06-28", "Статус": "🔄 В процессе"},
        {"Спринт": "Sprint 2", "Команда": "Pipeline",  "Старт": "2026-06-15", "Конец": "2026-06-28", "Статус": "🔄 В процессе"},
    ])
    st.dataframe(sprint_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — UX Research
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Research — UX & Content")
    st.caption("Покрытие тем, пробелы в знаниях, топ тегов")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Топ тегов**")
        all_tags = [t for tags in df.tags for t in (tags if isinstance(tags, list) else [])]
        tag_counts = Counter(all_tags).most_common(30)
        tag_df = pd.DataFrame(tag_counts, columns=["tag", "count"])
        fig = px.bar(tag_df, x="count", y="tag", orientation="h",
                     color="count", color_continuous_scale="Greens",
                     labels={"count": "", "tag": ""})
        fig.update_layout(height=500, coloraxis_showscale=False,
                          yaxis={"categoryorder": "total ascending"},
                          margin=dict(t=5, b=5))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Пробелы — папки с малым покрытием**")
        folder_counts = df.folder.value_counts().reset_index()
        folder_counts.columns = ["folder", "count"]
        all_folders = pd.DataFrame({"folder": list(VAULT_FOLDERS.keys())})
        merged = all_folders.merge(folder_counts, on="folder", how="left").fillna(0)
        merged["count"] = merged["count"].astype(int)
        gaps = merged[merged["count"] < 5].sort_values("count")
        fig2 = px.bar(gaps, x="count", y="folder", orientation="h",
                      color="count", color_continuous_scale="Reds_r",
                      labels={"count": "Заметок", "folder": ""},
                      title=f"Папок с <5 заметок: {len(gaps)}")
        fig2.update_layout(height=500, coloraxis_showscale=False,
                           yaxis={"categoryorder": "total ascending"},
                           margin=dict(t=30, b=5))
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("**Alpha / Прототип-тестирование**")
    st.caption("🟡 Placeholder — Task Success Rate, SUS score, session count (Nielsen Norman)")
    st.info("Подключи: результаты юзабилити-тестов, Maze/UserTesting экспорт")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Architecture
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Architecture — Tech Lead + DevOps")
    st.caption("ADR, компоненты системы, tech debt, инфраструктура")

    st.markdown("**Architecture Decision Records (ADR)**")
    adrs = pd.DataFrame([
        {"#": 1, "Решение": "youtube-transcript-api → primary (yt-dlp — fallback)",
         "Причина": "Разные rate-limit эндпоинты, меньше блоков", "Статус": "✅ Принято"},
        {"#": 2, "Решение": "DuckDB для векторного хранилища",
         "Причина": "Zero-config, локально, поддержка float32 vectors", "Статус": "✅ Принято"},
        {"#": 3, "Решение": "Идемпотентность через source_url lookup",
         "Причина": "Safe restart после сбоя без дублей", "Статус": "✅ Принято"},
        {"#": 4, "Решение": "Claude Haiku (не Sonnet) для обогащения",
         "Причина": "10x дешевле, достаточно для JSON extraction", "Статус": "✅ Принято"},
        {"#": 5, "Решение": "folder_examples.yml для few-shot классификации",
         "Причина": "Итерируем примеры без правки промпта", "Статус": "✅ Принято"},
        {"#": 6, "Решение": "ThreadPoolExecutor для статей (YouTube — последовательно)",
         "Причина": "Статьи IO-bound без rate-limit; YouTube блокирует параллельные IP", "Статус": "✅ Принято"},
    ])
    st.dataframe(adrs, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Схема компонентов**")
    st.code("""
URL Input
    │
    ▼
router.py  ──────────────────────────────────────┐
    │  "video"                                    │ "article"
    ▼                                             ▼
extractors/video.py                    extractors/article.py
  youtube-transcript-api (primary)       trafilatura + markdownify
  yt-dlp (fallback)                      Jina Reader (fallback)
  description-only (fallback)
    │                                             │
    └──────────────────┬──────────────────────────┘
                       ▼
                  enrich.py  ←── folder_examples.yml
                  Claude Haiku API
                  (title, summary, tags, folder, concepts...)
                       │
                       ▼
                 note_writer.py
                 YAML frontmatter + Markdown body
                 → Obsidian vault subfolder
                       │
                       ▼
                   store.py
                 sentence-transformers embeddings
                 → DuckDB (local vector store)
    """, language="text")

    st.divider()
    st.markdown("**Tech Debt**")
    debt_df = pd.DataFrame([
        {"Пункт": "Chunking длинных транскриптов (>40 мин)", "Приоритет": "🔴 Высокий", "Статус": "📋 Запланировано"},
        {"Пункт": "Async обработка (asyncio + aiohttp)", "Приоритет": "🟡 Средний", "Статус": "📋 Запланировано"},
        {"Пункт": "CI/CD GitHub Actions", "Приоритет": "🟡 Средний", "Статус": "📋 Запланировано"},
        {"Пункт": "Поддержка Twitter/Instagram через Whisper OCR", "Приоритет": "🟠 Низкий", "Статус": "💡 Идея"},
    ])
    st.dataframe(debt_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BA / SA
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Business & System Analysis")
    st.caption("Требования, спецификации, API контракты")
    st.info("🟡 Placeholder — для solo-проекта роли BA/SA выполняет PM. "
            "Подключи: Jira/Linear (реестр требований), Confluence (спецификации), "
            "OpenAPI spec (API контракты)")

    st.markdown("**Реестр требований (пример)**")
    req_df = pd.DataFrame([
        {"ID": "REQ-01", "Требование": "Обработка YouTube URL с субтитрами",
         "Источник": "PM", "Статус": "✅ Готово", "Стабильность": "🟢"},
        {"ID": "REQ-02", "Требование": "Обработка статей (trafilatura)",
         "Источник": "PM", "Статус": "✅ Готово", "Стабильность": "🟢"},
        {"ID": "REQ-03", "Требование": "Классификация в папки через Claude",
         "Источник": "PM", "Статус": "✅ Готово", "Стабильность": "🟡"},
        {"ID": "REQ-04", "Требование": "Видео длиннее 40 минут",
         "Источник": "PM", "Статус": "🔄 В работе", "Стабильность": "🟡"},
        {"ID": "REQ-05", "Требование": "Дашборд для мониторинга",
         "Источник": "PM", "Статус": "🔄 В работе", "Стабильность": "🟢"},
    ])
    st.dataframe(req_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Design
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Product Design")
    st.caption("HEART метрики (post-release), Design System, итерации")
    st.info("🟡 Placeholder — применимо при наличии UI-продукта. "
            "Подключи: Figma API (компоненты), результаты HEART-опросов")

    st.markdown("**HEART framework (Google) — post-release**")
    heart_df = pd.DataFrame([
        {"Метрика": "Happiness",   "Описание": "Удовлетворённость пользователя",    "Значение": "—", "Источник": "Опросы / NPS"},
        {"Метрика": "Engagement",  "Описание": "Частота использования",             "Значение": "—", "Источник": "Analytics"},
        {"Метрика": "Adoption",    "Описание": "% освоивших новую фичу",            "Значение": "—", "Источник": "Analytics"},
        {"Метрика": "Retention",   "Описание": "Возвращаемость",                    "Значение": "—", "Источник": "Analytics"},
        {"Метрика": "Task Success", "Описание": "% задач выполнен успешно",         "Значение": "—", "Источник": "Юзабилити-тесты"},
    ])
    st.dataframe(heart_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Dev & Pipeline
# ══════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("Development & Pipeline")
    st.caption("DORA metrics, ошибки по типу, тренды всех batch runs, тесты")

    # Source type breakdown
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Тип источника**")
        src = df.source_type.value_counts().reset_index()
        src.columns = ["type", "count"]
        fig = px.pie(src, names="type", values="count",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(height=250, margin=dict(t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("**No subtitles rate**")
        no_subs_pct = df.no_subtitles.mean() * 100
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=no_subs_pct,
            number={"suffix": "%"},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": "#ef4444" if no_subs_pct > 30 else "#f59e0b"},
                   "steps": [{"range": [0, 20], "color": "#dcfce7"},
                              {"range": [20, 40], "color": "#fef9c3"},
                              {"range": [40, 100], "color": "#fee2e2"}]},
            title={"text": "Без субтитров"},
        ))
        fig2.update_layout(height=250, margin=dict(t=20, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    with col_c:
        st.markdown("**Тесты**")
        st.metric("Unit tests", "13 / 13", delta="100% pass", delta_color="normal")
        st.metric("Coverage", "enrich.py, note_writer.py", delta=None)
        st.caption("Запуск: `python -m pytest tests/ -v`")

    st.divider()
    st.markdown("**DORA Metrics**")
    st.caption("🟡 Частично — подключи GitHub API для полных данных")
    dora_df = pd.DataFrame([
        {"Метрика": "Deployment Frequency", "Значение": "По запросу (ручной batch)",
         "Цель": "On-demand", "Статус": "🟡"},
        {"Метрика": "Lead Time (commit→prod)", "Значение": "~0 мин (local)",
         "Цель": "<1 час",    "Статус": "🟢"},
        {"Метрика": "Change Failure Rate",    "Значение": "—",
         "Цель": "<15%",      "Статус": "⬜ Нет данных"},
        {"Метрика": "MTTR",                   "Значение": "~5 мин (перезапуск batch)",
         "Цель": "<1 часа",   "Статус": "🟢"},
    ])
    st.dataframe(dora_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Тренд создания заметок по неделям**")
    vel = df[df["added_dt"].notna()].copy()
    if not vel.empty:
        vel["week"] = vel["added_dt"].dt.to_period("W").astype(str)
        by_week = vel.groupby(["week", "source_type"]).size().reset_index(name="count")
        fig3 = px.bar(by_week, x="week", y="count", color="source_type", barmode="stack",
                      labels={"week": "Неделя", "count": "Заметок", "source_type": "Тип"},
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        fig3.update_layout(height=280, margin=dict(t=5, b=40))
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Quality
# ══════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("Quality — QA + Beta")
    st.caption("Needs review rate, ошибки классификации, inbox overflow, beta placeholder")

    col_l, col_r = st.columns(2)

    with col_l:
        needs_rev = df.needs_review.sum()
        no_subs   = df.no_subtitles.sum()
        inbox_n   = (df.folder == "inbox").sum()
        ready_n   = len(df) - needs_rev

        st.markdown("**Статус заметок**")
        status_df = pd.DataFrame({
            "Статус": ["Готовы", "Needs review", "Без субтитров", "В inbox"],
            "Кол-во": [ready_n, needs_rev, no_subs, inbox_n],
        })
        fig = px.bar(status_df, x="Статус", y="Кол-во",
                     color="Статус",
                     color_discrete_map={
                         "Готовы": "#22c55e",
                         "Needs review": "#f59e0b",
                         "Без субтитров": "#f97316",
                         "В inbox": "#ef4444",
                     })
        fig.update_layout(height=300, showlegend=False, margin=dict(t=5, b=5))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Needs review — какие папки**")
        nr_by_folder = (
            df[df.needs_review]
            .folder.value_counts()
            .reset_index()
        )
        nr_by_folder.columns = ["folder", "count"]
        if not nr_by_folder.empty:
            fig2 = px.bar(nr_by_folder.head(10), x="count", y="folder",
                          orientation="h", color="count",
                          color_continuous_scale="Oranges",
                          labels={"count": "", "folder": ""})
            fig2.update_layout(height=300, coloraxis_showscale=False,
                               yaxis={"categoryorder": "total ascending"},
                               margin=dict(t=5, b=5))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.success("Нет заметок с needs_review!")

    st.divider()

    # Inbox overflow — misclassification signal
    st.markdown("**Inbox overflow — сигнал ошибок классификации**")
    st.caption("Много заметок в inbox = Claude не нашёл подходящую папку → "
               "нужно расширить folder_examples.yml")
    st.metric("Заметок в inbox", inbox_n,
              delta=f"{inbox_n/len(df)*100:.1f}% от всех",
              delta_color="inverse" if inbox_n > len(df)*0.1 else "off")

    st.divider()
    st.markdown("**Beta-тестирование**")
    st.info("🟡 Placeholder — Beta применима после деплоя продукта. "
            "Метрики: retention в бете, crash rate, time-to-first-value, кол-во бета-пользователей")

    st.divider()
    st.markdown("**Просмотр заметок needs_review**")
    nr_df = df[df.needs_review][["title", "folder", "source_type", "added"]].copy()
    if not nr_df.empty:
        folder_opt = ["Все"] + sorted(nr_df.folder.unique().tolist())
        sel = st.selectbox("Фильтр по папке", folder_opt, key="qa_folder")
        if sel != "Все":
            nr_df = nr_df[nr_df.folder == sel]
        st.dataframe(nr_df.head(50), use_container_width=True, hide_index=True)
    else:
        st.success("Нет заметок с needs_review!")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — Release
# ══════════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.subheader("Release & Instructions")
    st.caption("История релизов, changelog, статус документации")

    st.markdown("**История релизов**")
    rel_df = pd.DataFrame([
        {"Версия": "v0.1.0 — Initial commit", "Дата": "2026-06-23",
         "Что вошло": "Pipeline, enrich, note_writer, store, dashboard skeleton",
         "Статус": "✅"},
        {"Версия": "v0.2.0 — Reliability",    "Дата": "2026-06-23",
         "Что вошло": "Typed exceptions, retries, token logging, parallel articles",
         "Статус": "✅"},
        {"Версия": "v0.3.0 — Dashboard",      "Дата": "В работе",
         "Что вошло": "10-page Streamlit dashboard, README_RU, screenshots",
         "Статус": "🔄"},
    ])
    st.dataframe(rel_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Статус документации**")
    docs_df = pd.DataFrame([
        {"Документ": "README.md (EN)",     "Статус": "✅ Готово",    "Обновлён": "2026-06-23"},
        {"Документ": "README_RU.md",       "Статус": "📋 Планируется", "Обновлён": "—"},
        {"Документ": ".env.example",       "Статус": "✅ Готово",    "Обновлён": "2026-06-23"},
        {"Документ": "folder_examples.yml","Статус": "✅ Готово",    "Обновлён": "2026-06-18"},
        {"Документ": "CHANGELOG",          "Статус": "📋 Планируется", "Обновлён": "—"},
    ])
    st.dataframe(docs_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — Monitoring
# ══════════════════════════════════════════════════════════════════════════════
with tabs[8]:
    st.subheader("Monitoring & Support")
    st.caption("Ошибки по типу, тренды всех batch runs, MTTR, нагрузка на саппорт")

    # Notes added over all time
    st.markdown("**Все batch runs — заметки по времени**")
    vel = df_all[df_all["added_dt"].notna()].copy()   # используем df_all, не отфильтрованный
    if not vel.empty:
        vel["day"] = vel["added_dt"].dt.date
        by_day = vel.groupby("day").size().reset_index(name="count")
        by_day["cumulative"] = by_day["count"].cumsum()
        fig = go.Figure()
        fig.add_bar(x=by_day.day, y=by_day["count"], name="За день",
                    marker_color="#6366f1")
        fig.add_scatter(x=by_day.day, y=by_day["cumulative"], name="Накопительно",
                        line=dict(color="#f59e0b", width=2), yaxis="y2")
        fig.update_layout(
            height=300,
            yaxis=dict(title="Заметок/день"),
            yaxis2=dict(title="Всего", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=10, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Статус заметок — весь vault**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Готовы",        int((~df_all.needs_review).sum()))
        m2.metric("Needs review",  int(df_all.needs_review.sum()))
        m3.metric("Без субтитров", int(df_all.no_subtitles.sum()))

    with col_r:
        st.markdown("**DORA — MTTR**")
        st.metric("MTTR (Mean Time to Recovery)",
                  "~5 мин",
                  help="Время перезапуска batch после сбоя — идемпотентность обеспечивает skip уже обработанных")

    st.divider()
    st.markdown("**Ошибки по типу (из логов последнего batch)**")
    st.info("🟡 Подключи парсер logs/ для автоматического чтения статистики ошибок из файлов")
    err_placeholder = pd.DataFrame([
        {"Тип ошибки": "IP Block (YouTube)",       "Кол-во": 96,  "% от total": "13.6%"},
        {"Тип ошибки": "Видео > 40 мин",           "Кол-во": 205, "% от total": "29.1%"},
        {"Тип ошибки": "Нет субтитров + описания", "Кол-во": 48,  "% от total": "6.8%"},
        {"Тип ошибки": "Уже обработаны (skip)",    "Кол-во": 97,  "% от total": "13.8%"},
    ])
    st.dataframe(err_placeholder, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — Growth
# ══════════════════════════════════════════════════════════════════════════════
with tabs[9]:
    st.subheader("Growth — Marketing & Sales")
    st.caption("AARRR воронка, контент-потенциал, pipeline продаж")
    st.info("🟡 Placeholder — применимо при публичном продукте / SaaS. "
            "Подключи: Google Analytics, CRM, рекламные кабинеты")

    st.markdown("**AARRR воронка**")
    aarrr_df = pd.DataFrame([
        {"Этап": "Acquisition",  "Описание": "Откуда узнают о продукте",         "Метрика": "Трафик, CAC",       "Данные": "—"},
        {"Этап": "Activation",   "Описание": "Первый успешный опыт",              "Метрика": "Time to first note", "Данные": "—"},
        {"Этап": "Retention",    "Описание": "Возвращаются ли пользователи",       "Метрика": "DAU/WAU, churn",    "Данные": "—"},
        {"Этап": "Revenue",      "Описание": "Монетизация",                       "Метрика": "MRR, ARPU, LTV",    "Данные": "—"},
        {"Этап": "Referral",     "Описание": "Рекомендуют ли продукт другим",     "Метрика": "NPS, viral coeff",  "Данные": "—"},
    ])
    st.dataframe(aarrr_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Контент-потенциал — топ тем для маркетинга**")
    all_tags = [t for tags in df.tags for t in (tags if isinstance(tags, list) else [])]
    top_tags = Counter(all_tags).most_common(10)
    if top_tags:
        tdf = pd.DataFrame(top_tags, columns=["Тема", "Заметок в базе"])
        tdf["Потенциал контента"] = tdf["Заметок в базе"].apply(
            lambda x: "🔴 Высокий" if x > 20 else ("🟡 Средний" if x > 10 else "⚪ Низкий")
        )
        st.dataframe(tdf, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 10 — Timeline
# ══════════════════════════════════════════════════════════════════════════════
with tabs[10]:
    st.subheader("⏱ Timeline — Event Overlay")
    st.caption("События всех команд на одной оси. Добавляй события в events.yml")

    events_df = load_events()

    # Notes per day as base chart
    vel = df_all[df_all["added_dt"].notna()].copy()
    if not vel.empty:
        vel["day"] = vel["added_dt"].dt.date
        by_day = vel.groupby("day").size().reset_index(name="count")

        fig = go.Figure()
        fig.add_bar(x=by_day.day, y=by_day["count"],
                    name="Заметок за день", marker_color="#c7d2fe")

        # Overlay events
        if not events_df.empty:
            colors = {"PM": "#6366f1", "Dev": "#22c55e", "QA": "#f59e0b",
                      "Release": "#ef4444", "Research": "#8b5cf6"}
            for _, ev in events_df.iterrows():
                color = colors.get(ev.get("team", ""), "#6b7280")
                fig.add_vline(x=str(ev["date"]), line_dash="dash",
                              line_color=color, opacity=0.7)
                fig.add_annotation(x=str(ev["date"]), y=by_day["count"].max(),
                                   text=ev.get("label", ""), showarrow=False,
                                   textangle=-45, font=dict(size=10, color=color))
        else:
            st.caption("💡 Создай events.yml в папке проекта чтобы добавить события на график")

        fig.update_layout(
            height=400,
            xaxis_title="Дата",
            yaxis_title="Заметок за день",
            margin=dict(t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("**Формат events.yml**")
    st.code("""
# events.yml — добавляй сюда события команд
- date: "2026-06-18"
  label: "folder_examples.yml добавлен"
  team: Dev
  type: improvement

- date: "2026-06-19"
  label: "Batch 704 URLs запущен"
  team: PM
  type: milestone

- date: "2026-06-23"
  label: "v0.2.0 Release"
  team: Release
  type: release
""", language="yaml")

    if not events_df.empty:
        st.markdown("**Загруженные события**")
        st.dataframe(events_df, use_container_width=True, hide_index=True)
