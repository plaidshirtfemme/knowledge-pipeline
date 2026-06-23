"""
Knowledge Pipeline Dashboard
Run: streamlit run dashboard.py
"""

import re
from collections import Counter
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import yaml

from config import VAULT_PATH, VAULT_FOLDERS

st.set_page_config(page_title="Knowledge Pipeline", layout="wide", page_icon="🧠")
st.title("🧠 Knowledge Pipeline — Dashboard")

# ── Load all notes ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_notes() -> pd.DataFrame:
    records = []
    folder_by_path = {str(VAULT_PATH / v): k for k, v in VAULT_FOLDERS.items()}

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
            records.append({
                "note_id":    fm.get("note_id", ""),
                "title":      fm.get("title", md_file.stem),
                "source_type": fm.get("source_type", "unknown"),
                "published":  str(fm.get("published", ""))[:10] or None,
                "added":      str(fm.get("added", ""))[:10] or None,
                "folder":     folder_key,
                "tags":       fm.get("tags") or [],
                "needs_review": bool(fm.get("needs_review")),
                "no_subtitles": bool(fm.get("no_subtitles")),
                "path":       str(md_file),
            })
        except Exception:
            continue

    return pd.DataFrame(records)


df = load_notes()

if df.empty:
    st.warning("Заметки не найдены. Проверь VAULT_PATH в .env")
    st.stop()

# ── Top metrics ───────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Всего заметок", len(df))
col2.metric("YouTube", (df.source_type == "youtube").sum())
col3.metric("Статьи", (df.source_type == "article").sum())
col4.metric("Требуют ревью", df.needs_review.sum())

st.divider()

# ── Notes by folder ───────────────────────────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("Заметки по папкам")
    folder_counts = df.folder.value_counts().reset_index()
    folder_counts.columns = ["folder", "count"]
    fig = px.bar(
        folder_counts.head(20), x="count", y="folder", orientation="h",
        color="count", color_continuous_scale="Blues",
        labels={"count": "Заметок", "folder": "Папка"},
    )
    fig.update_layout(height=500, showlegend=False, coloraxis_showscale=False,
                      yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

# ── Top tags ──────────────────────────────────────────────────────────────────

with right:
    st.subheader("Топ тегов")
    all_tags = [tag for tags in df.tags for tag in (tags if isinstance(tags, list) else [])]
    tag_counts = Counter(all_tags).most_common(25)
    tag_df = pd.DataFrame(tag_counts, columns=["tag", "count"])
    fig2 = px.bar(
        tag_df, x="count", y="tag", orientation="h",
        color="count", color_continuous_scale="Greens",
        labels={"count": "Заметок", "tag": "Тег"},
    )
    fig2.update_layout(height=500, showlegend=False, coloraxis_showscale=False,
                       yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Notes over time ───────────────────────────────────────────────────────────

st.subheader("Динамика создания заметок")
date_df = df[df.added.notna()].copy()
if not date_df.empty:
    date_df["added"] = pd.to_datetime(date_df["added"], errors="coerce")
    date_df = date_df.dropna(subset=["added"])
    by_date = date_df.groupby(date_df["added"].dt.to_period("W").astype(str)).size().reset_index()
    by_date.columns = ["week", "count"]
    by_date["cumulative"] = by_date["count"].cumsum()
    fig3 = px.area(by_date, x="week", y="cumulative",
                   labels={"week": "Неделя", "cumulative": "Всего заметок"},
                   color_discrete_sequence=["#6366f1"])
    fig3.update_layout(height=300)
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Нет данных о дате добавления заметок")

st.divider()

# ── Source type breakdown ─────────────────────────────────────────────────────

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.subheader("Тип источника")
    src_counts = df.source_type.value_counts().reset_index()
    src_counts.columns = ["type", "count"]
    fig4 = px.pie(src_counts, names="type", values="count",
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    fig4.update_layout(height=280)
    st.plotly_chart(fig4, use_container_width=True)

with col_b:
    st.subheader("Статус заметок")
    status_data = {
        "Готовы": int((~df.needs_review).sum()),
        "Требуют ревью": int(df.needs_review.sum()),
        "Без субтитров": int(df.no_subtitles.sum()),
    }
    fig5 = px.bar(
        x=list(status_data.keys()), y=list(status_data.values()),
        color=list(status_data.keys()),
        color_discrete_sequence=["#22c55e", "#f59e0b", "#ef4444"],
        labels={"x": "", "y": "Заметок"},
    )
    fig5.update_layout(height=280, showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)

with col_c:
    st.subheader("Топ-5 папок")
    top5 = df.folder.value_counts().head(5)
    for folder, count in top5.items():
        pct = count / len(df) * 100
        st.metric(folder, f"{count} заметок", f"{pct:.1f}%")

st.divider()

# ── Browse notes ──────────────────────────────────────────────────────────────

st.subheader("Просмотр заметок")
col_filter1, col_filter2, col_filter3 = st.columns(3)

with col_filter1:
    folders = ["Все"] + sorted(df.folder.unique().tolist())
    selected_folder = st.selectbox("Папка", folders)

with col_filter2:
    source_types = ["Все"] + sorted(df.source_type.unique().tolist())
    selected_type = st.selectbox("Тип источника", source_types)

with col_filter3:
    show_review_only = st.checkbox("Только needs_review")

filtered = df.copy()
if selected_folder != "Все":
    filtered = filtered[filtered.folder == selected_folder]
if selected_type != "Все":
    filtered = filtered[filtered.source_type == selected_type]
if show_review_only:
    filtered = filtered[filtered.needs_review]

st.dataframe(
    filtered[["title", "folder", "source_type", "published", "needs_review"]].head(100),
    use_container_width=True,
    hide_index=True,
)
st.caption(f"Показано {min(len(filtered), 100)} из {len(filtered)} заметок")
