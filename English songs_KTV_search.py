# pages/🔍_KTV搜索.py
import streamlit as st
import json
import os
import yt_dlp

st.set_page_config(page_title="KTV 搜索添加", page_icon="🔍", layout="wide")
st.title("🔍 搜索并添加 KTV 歌曲")

# ── 自定义歌曲存储 ──────────────────────────────
CUSTOM_SONGS_FILE = "custom_songs.json"

def load_custom_songs():
    if os.path.exists(CUSTOM_SONGS_FILE):
        with open(CUSTOM_SONGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_custom_songs(songs):
    with open(CUSTOM_SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)

def search_youtube(query, max_results=6):
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        return info.get("entries", [])

# ════════════════════════════════════════════════
# ① 添加表单 —— 放在最顶部，点完按钮立刻看到
# ════════════════════════════════════════════════
if "adding" in st.session_state:
    info = st.session_state["adding"]

    st.success(f"✅ 正在添加：**{info['title']}**")
    st.markdown("### ✏️ 填写歌曲信息")

    with st.form("add_song_form"):
        song_name  = st.text_input("歌曲名称", value=info["title"])
        artist     = st.text_input("歌手",     value=info["artist"])
        youtube_id = st.text_input("YouTube ID", value=info["youtube_id"])

        col_a, col_b = st.columns(2)
        with col_a:
            difficulty = st.select_slider(
                "难度",
                options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
            )
        with col_b:
            language = st.selectbox("语言", ["英语", "中文", "日语", "韩语", "其他"])

        tags_input = st.text_input("标签（用逗号分隔）", placeholder="流行, 欢快, 现代")

        col_s, col_c = st.columns(2)
        with col_s:
            submitted = st.form_submit_button("✅ 确认添加", use_container_width=True)
        with col_c:
            cancelled = st.form_submit_button("❌ 取消",     use_container_width=True)

        if submitted and song_name:
            custom = load_custom_songs()
            tags   = [t.strip() for t in tags_input.split(",") if t.strip()]
            custom[song_name] = {
                "artist":     artist,
                "youtube_id": youtube_id,
                "tags":       tags,
                "difficulty": difficulty,
                "language":   language,
                "cover":      "🎵",
                "lyrics":     [{"time": 0, "text": "🎵 暂无歌词"}],
            }
            save_custom_songs(custom)
            del st.session_state["adding"]
            st.success(f"🎉《{song_name}》已添加！")
            st.balloons()
            st.rerun()

        if cancelled:
            del st.session_state["adding"]
            st.rerun()

    st.markdown("---")

# ════════════════════════════════════════════════
# ② 搜索区域
# ════════════════════════════════════════════════
st.markdown("### 🎵 搜索 YouTube 歌曲")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("输入歌名或歌手", placeholder="例如：Let It Be Beatles")
with col2:
    search_btn = st.button("🔍 搜索", use_container_width=True)

if search_btn and query:
    with st.spinner("搜索中，请稍候..."):
        try:
            st.session_state["search_results"] = search_youtube(query)
        except Exception as e:
            st.error(f"搜索失败：{e}")

# ════════════════════════════════════════════════
# ③ 搜索结果
# ════════════════════════════════════════════════
if "search_results" in st.session_state:
    results = st.session_state["search_results"]

    if not results:
        st.warning("没有找到结果，换个关键词试试！")
    else:
        st.markdown("### 📋 搜索结果")

        for i, video in enumerate(results):
            title    = video.get("title", "未知标题")
            channel  = video.get("channel") or video.get("uploader") or "未知频道"
            duration = video.get("duration")
            vid_id   = video.get("id", "")
            thumb    = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"

            if duration:
                duration_str = f"{int(duration)//60}:{int(duration)%60:02d}"
            else:
                duration_str = "未知"

            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    st.image(thumb, width=160)
                with c2:
                    st.markdown(f"**{title}**")
                    st.caption(f"🎤 {channel}　⏱ {duration_str}")
                    st.markdown(f"[▶ 在 YouTube 预览](https://www.youtube.com/watch?v={vid_id})")
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("➕ 添加到歌单", key=f"add_{i}", use_container_width=True):
                        st.session_state["adding"] = {
                            "title":      title,
                            "youtube_id": vid_id,
                            "artist":     channel,
                        }
                        st.rerun()   # ← 关键！立刻刷新到页面顶部显示表单
                st.divider()

# ════════════════════════════════════════════════
# ④ 我的自定义歌单
# ════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📂 我的自定义歌单")

custom_songs = load_custom_songs()

if custom_songs:
    for name, data in custom_songs.items():
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            st.markdown(f"**{data.get('cover','🎵')} {name}** — {data.get('artist','')}")
        with c2:
            st.caption(data.get("difficulty", ""))
        with c3:
            st.caption(data.get("language", ""))
        with c4:
            if st.button("🗑 删除", key=f"del_{name}"):
                del custom_songs[name]
                save_custom_songs(custom_songs)
                st.rerun()
else:
    st.info("还没有自定义歌曲，搜索并添加吧！")