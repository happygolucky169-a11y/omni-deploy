"""
OMNI-LEARN OS — 行为埋点集成说明
integration_guide.py

把这个文件里的代码片段复制到对应模块文件的指定位置即可。
"""

# ══════════════════════════════════════════════════════════════════
# STEP 1：所有模块文件顶部加一行 import
# ══════════════════════════════════════════════════════════════════
STEP1_IMPORT = """
from behavior_logger import BLogger
"""

# ══════════════════════════════════════════════════════════════════
# STEP 2：在 omni_dashboard.py 的 _admin() 函数里加 行为数据 Tab
# 找到这行：
#   tab1,tab2,tab3,tab4 = st.tabs(["👤 学员管理","🏫 班级管理","📚 内容库","📊 全局看板"])
# 替换为：
# ══════════════════════════════════════════════════════════════════
STEP2_ADMIN_TAB = """
from admin_behavior_panel import render_behavior_tab

# 在 _admin() 函数内，找到 tabs 定义，改为：
tab1,tab2,tab3,tab4,tab5 = st.tabs(
    ["👤 学员管理","🏫 班级管理","📚 内容库","📊 全局看板","🔍 行为数据"]
)
with tab1: _a_students(pm)
with tab2: _a_classes(pm,cm)
with tab3: _a_content(matcher)
with tab4: _a_stats(pm)
with tab5: render_behavior_tab(pm)
"""

# ══════════════════════════════════════════════════════════════════
# STEP 3：各模块埋点位置
# ══════════════════════════════════════════════════════════════════

# ── 1_words.py ─────────────────────────────────────────────────
WORDS_EMBED = """
# 【1_words.py】
# ① 文件顶部：
from behavior_logger import BLogger

# ② 在模块入口函数开头（如 show_words() 或主渲染函数）：
username = st.session_state.get("user", {}).get("name", "")
if username:
    BLogger.page_enter(username, "words")

# ③ 每道词汇题展示时（在 st.radio / st.button 渲染前）：
if username:
    BLogger.question_shown(username, "words", q_id=f"w_{word_index}")

# ④ 学生提交答案后（在判断 correct 的代码块内）：
if username:
    BLogger.question_answered(username, "words",
        q_id=f"w_{word_index}", correct=is_correct, score=1.0 if is_correct else 0.0)

# ⑤ 模块退出时（在返回主页的 button 回调里，或 st.rerun() 前）：
if username:
    BLogger.page_leave(username, "words")
"""

# ── 2_listening.py ──────────────────────────────────────────────
LISTENING_EMBED = """
# 【2_listening.py】
# ① 顶部 import（同上）

# ② 模块入口：
BLogger.page_enter(username, "listening")

# ③ 音频播放按钮被点击时（在生成 TTS / 播放 audio 的代码旁）：
BLogger.audio_play(username, "listening",
    audio_id=f"l_{question_id}", duration_sec=estimated_duration)
# 注：如果拿不到精确时长，duration_sec 传 0 即可

# ④ 用户点击"下一题"或答题后（视为音频听完）：
BLogger.audio_end(username, "listening",
    audio_id=f"l_{question_id}", listened_sec=estimated_duration, total_sec=estimated_duration)

# ⑤ 答题：
BLogger.question_answered(username, "listening",
    q_id=f"l_{question_id}", correct=is_correct, score=1.0 if is_correct else 0.0)

# ⑥ 离开：
BLogger.page_leave(username, "listening")
"""

# ── 3_speaking.py ───────────────────────────────────────────────
SPEAKING_EMBED = """
# 【3_speaking.py】
# ① 顶部 import

# ② 入口：
BLogger.page_enter(username, "speaking")

# ③ 每道口语题展示时：
BLogger.question_shown(username, "speaking", q_id=f"sp_{prompt_index}")

# ④ 用户提交录音/回答后（AI 评分返回时）：
BLogger.question_answered(username, "speaking",
    q_id=f"sp_{prompt_index}",
    correct=ai_score >= 60,      # 60分以上视为通过
    score=ai_score / 100.0)

# ⑤ 离开：
BLogger.page_leave(username, "speaking")
"""

# ── 4_reading.py ────────────────────────────────────────────────
READING_EMBED = """
# 【4_reading.py】
# ① 顶部 import

# ② 入口：
BLogger.page_enter(username, "reading")

# ③ 文章/段落展示时：
BLogger.question_shown(username, "reading", q_id=f"r_{article_id}")

# ④ 理解题答题后：
BLogger.question_answered(username, "reading",
    q_id=f"r_{article_id}_q{q_num}", correct=is_correct, score=1.0 if is_correct else 0.0)

# ⑤ 离开：
BLogger.page_leave(username, "reading")
"""

# ── 5_writing.py ────────────────────────────────────────────────
WRITING_EMBED = """
# 【5_writing.py】
# ① 顶部 import

# ② 入口：
BLogger.page_enter(username, "writing")

# ③ 写作题目展示时：
BLogger.question_shown(username, "writing", q_id=f"wr_{prompt_id}")

# ④ 提交写作后（AI 批改返回时）：
BLogger.question_answered(username, "writing",
    q_id=f"wr_{prompt_id}",
    correct=ai_score >= 60,
    score=ai_score / 100.0)

# ⑤ 离开：
BLogger.page_leave(username, "writing")
"""

# ── KTVsystem.py ────────────────────────────────────────────────
KTV_EMBED = """
# 【KTVsystem.py】
# ① 顶部 import

# ② 入口：
BLogger.page_enter(username, "ktv")

# ③ 歌曲播放开始时：
BLogger.audio_play(username, "ktv",
    audio_id=song_id, duration_sec=song_duration_sec)

# ④ 歌曲播放结束/切歌时：
BLogger.audio_end(username, "ktv",
    audio_id=song_id,
    listened_sec=actual_listened_sec,   # 如拿不到，传 song_duration_sec
    total_sec=song_duration_sec)

# ⑤ 离开：
BLogger.page_leave(username, "ktv")
"""

# ══════════════════════════════════════════════════════════════════
# STEP 4：获取当前用户名的统一方式
# ══════════════════════════════════════════════════════════════════
GET_USERNAME = """
# 在各模块顶部，获取当前登录用户名：
username = st.session_state.get("user", {}).get("name", "")
# 或者如果用的是 nickname：
username = st.session_state.get("current_user", {}).get("nickname", "")
# 包一层保护，防止未登录时报错：
if not username:
    return  # 或 pass
"""

if __name__ == "__main__":
    print("=== OMNI 行为埋点集成说明 ===\n")
    print("STEP 1 - 每个模块顶部加:", STEP1_IMPORT)
    print("STEP 2 - Admin Tab:", STEP2_ADMIN_TAB)
    print("STEP 3 - 各模块埋点位置见上方注释")
    print("STEP 4 - 获取用户名:", GET_USERNAME)
