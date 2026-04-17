"""
OMNI-LEARN OS — 入学问卷（逐步引导版）
omni_questionnaire.py

逐题展示（8步），每步独立 session_state，无 st.form 包裹，
所有按钮均可正常触发 st.rerun()。
"""

import streamlit as st

# ── 兴趣标签池 ────────────────────────────────────────
INTEREST_OPTIONS = [
    "🐾 动物", "🚀 太空", "⚽ 运动", "🎵 音乐", "📖 故事",
    "🔬 科学", "🎨 艺术", "🍕 美食", "🌍 旅行", "🎬 电影",
    "🦸 超级英雄", "🎮 游戏", "🌊 海洋", "🦕 恐龙", "🌿 自然",
]

TOTAL_STEPS = 8


# ══════════════════════════════════════════════════════
# 公开入口
# ══════════════════════════════════════════════════════
def render_questionnaire() -> dict | None:
    """
    逐步渲染问卷。
    全部 8 步完成后返回 prior dict；
    未完成返回 None。
    """
    # 初始化 session_state
    if "q_step" not in st.session_state:
        st.session_state.q_step    = 1
        st.session_state.q_data    = {}
        st.session_state.q_filler  = "parent"   # parent / child

    step = st.session_state.q_step
    data = st.session_state.q_data

    # ── 顶部进度条 ──────────────────────────────────
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
  <span style="font-size:.85rem;color:#6B7280;white-space:nowrap;">完成度 {step}/{TOTAL_STEPS}</span>
  <div style="flex:1;height:6px;background:#E5E7EB;border-radius:3px;">
    <div style="width:{step/TOTAL_STEPS*100:.0f}%;height:100%;
      background:linear-gradient(90deg,#7C3AED,#06B6D4);border-radius:3px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── 各步渲染 ────────────────────────────────────
    if step == 1:
        _step1_filler()
    elif step == 2:
        _step2_age(data)
    elif step == 3:
        _step3_experience(data)
    elif step == 4:
        _step4_self_level(data)
    elif step == 5:
        _step5_interests(data)
    elif step == 6:
        _step6_reading1(data)
    elif step == 7:
        _step7_reading2(data)
    elif step == 8:
        _step8_goal(data)

    # ── 全部完成 ────────────────────────────────────
    if st.session_state.q_step > TOTAL_STEPS:
        return _build_prior(data)

    return None


# ══════════════════════════════════════════════════════
# 内部：各步函数
# ══════════════════════════════════════════════════════

def _step1_filler():
    """步骤 1：谁来填写？"""
    st.markdown("### 👋 谁来填写这份问卷？")
    st.caption("让孩子自己填写更准确，也可以由家长代填。")
    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("👦 让孩子自己填", use_container_width=True, type="primary",
                     key="q_filler_child"):
            st.session_state.q_filler = "child"
            st.session_state.q_step   = 2
            st.rerun()
    with c2:
        if st.button("👩 我来帮填", use_container_width=True,
                     key="q_filler_parent"):
            st.session_state.q_filler = "parent"
            st.session_state.q_step   = 2
            st.rerun()

    filler = st.session_state.q_filler
    if filler == "child":
        st.info("💡 孩子你好！请认真回答下面的问题，帮系统了解你的英语水平。")
    else:
        st.info("💡 建议让孩子自己来填，会更准确哦！")


def _step2_age(data: dict):
    """步骤 2：年龄"""
    st.markdown("### 🐣 孩子现在几岁？")
    age = st.radio(
        "年龄",
        options=["4岁或以下", "5岁", "6岁", "7岁", "8岁或以上"],
        horizontal=True,
        label_visibility="collapsed",
        key="q_age_radio",
        index=data.get("_age_idx", 0),
    )
    st.markdown("")
    if st.button("下一步 →", type="primary", key="q_next_2"):
        data["age"]     = age
        data["_age_idx"] = ["4岁或以下","5岁","6岁","7岁","8岁或以上"].index(age)
        st.session_state.q_step = 3
        st.rerun()


def _step3_experience(data: dict):
    """步骤 3：学习时长"""
    st.markdown("### 📅 学英语多长时间了？")
    options = ["从来没学过", "不到 1 年", "1–3 年", "3 年以上"]
    exp = st.radio(
        "学习时长",
        options=options,
        horizontal=True,
        label_visibility="collapsed",
        key="q_exp_radio",
        index=data.get("_exp_idx", 0),
    )
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("下一步 →", type="primary", key="q_next_3", use_container_width=True):
            data["experience"]  = exp
            data["_exp_idx"]    = options.index(exp)
            st.session_state.q_step = 4
            st.rerun()


def _step4_self_level(data: dict):
    """步骤 4：自评水平"""
    st.markdown("### 🌟 英语水平自评")
    options = [
        "🌱 几乎不会，只认识几个字母",
        "🌿 认识一些单词，能说简单句子",
        "🌳 能读懂简单短文，会基本日常对话",
        "🦅 能读懂普通文章，能写简短段落",
        "⭐ 阅读流畅，语法基本正确",
        "🏆 英语非常好，接近母语水平",
    ]
    sel = st.radio(
        "自评",
        options=options,
        label_visibility="collapsed",
        key="q_level_radio",
        index=data.get("_level_idx", 0),
    )
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("下一步 →", type="primary", key="q_next_4", use_container_width=True):
            data["self_level"]   = sel
            data["_level_idx"]   = options.index(sel)
            st.session_state.q_step = 5
            st.rerun()


def _step5_interests(data: dict):
    """步骤 5：兴趣标签（多选）"""
    st.markdown("### ❤️ 你喜欢哪些话题？（可以多选）")
    selected = list(data.get("interests", []))
    cols = st.columns(5)
    for i, opt in enumerate(INTEREST_OPTIONS):
        with cols[i % 5]:
            checked = st.checkbox(opt, value=(opt in selected), key=f"q_int_{i}")
            if checked and opt not in selected:
                selected.append(opt)
            elif not checked and opt in selected:
                selected.remove(opt)
    data["interests"] = selected
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("下一步 →", type="primary", key="q_next_5", use_container_width=True):
            st.session_state.q_step = 6
            st.rerun()


def _step6_reading1(data: dict):
    """步骤 6：阅读小测 1（短句理解）"""
    st.markdown("### 📖 来试试！读句子，选答案")
    st.markdown("""
<div style="background:#F0F9FF;border-left:4px solid #0284C7;border-radius:8px;
     padding:14px 16px;margin:12px 0;font-size:1rem;line-height:1.8;">
  <b>Lisa has a cat. The cat is white. It likes to sleep all day.</b>
</div>""", unsafe_allow_html=True)
    st.markdown("**Lisa 的猫是什么颜色的？**")
    options = ["黑色", "白色", "橙色", "灰色"]
    ans = st.radio(
        "答案",
        options=options,
        label_visibility="collapsed",
        key="q_r1_radio",
        index=data.get("_r1_idx", 0),
    )
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("下一步 →", type="primary", key="q_next_6", use_container_width=True):
            data["reading1_ans"]    = ans
            data["reading1_correct"] = (ans == "白色")
            data["_r1_idx"]         = options.index(ans)
            st.session_state.q_step = 7
            st.rerun()


def _step7_reading2(data: dict):
    """步骤 7：阅读小测 2（稍长段落，已修复歧义）"""
    st.markdown("### 📝 再来一段，稍微长一点")
    st.markdown("""
<div style="background:#F0F9FF;border-left:4px solid #0284C7;border-radius:8px;
     padding:14px 16px;margin:12px 0;font-size:1rem;line-height:1.8;">
  Tom gets up at seven o'clock every morning.<br>
  He has breakfast and then goes to school.<br>
  <b>After school, Tom always plays football with his friends in the park.</b>
</div>""", unsafe_allow_html=True)

    # 问题明确指向"放学后"，与文章前两句信息不重叠
    st.markdown("**放学后，Tom 通常去做什么？**")
    options = ["和朋友一起踢足球", "在家看电视", "去图书馆学习", "和爸爸一起吃晚饭"]
    ans = st.radio(
        "答案",
        options=options,
        label_visibility="collapsed",
        key="q_r2_radio",
        index=data.get("_r2_idx", 0),
    )
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("下一步 →", type="primary", key="q_next_7", use_container_width=True):
            data["reading2_ans"]    = ans
            data["reading2_correct"] = (ans == "和朋友一起踢足球")
            data["_r2_idx"]         = options.index(ans)
            st.session_state.q_step = 8
            st.rerun()


def _step8_goal(data: dict):
    """步骤 8：学习目标（最后一步，点击直接完成）"""
    st.markdown("### 🎯 学习英语的主要目标是什么？")
    options = [
        "兴趣爱好 / 日常提升",
        "小学英语提升（作业 & 考试）",
        "初中备考（中考英语）",
        "高中备考（高考英语）",
        "出国留学（雅思 / 托福）",
        "职业发展",
        "其他",
    ]
    goal = st.radio(
        "目标",
        options=options,
        label_visibility="collapsed",
        key="q_goal_radio",
        index=data.get("_goal_idx", 0),
    )
    st.markdown("")
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("🚀 完成问卷，开始测试 →", type="primary",
                     key="q_finish", use_container_width=True):
            data["goal"]       = goal
            data["_goal_idx"]  = options.index(goal)
            # 标记完成
            st.session_state.q_step = TOTAL_STEPS + 1
            st.rerun()


# ══════════════════════════════════════════════════════
# 计算 prior
# ══════════════════════════════════════════════════════
def _build_prior(data: dict) -> dict:
    """将问卷数据转换为 estimated_level 和 prior dict。"""
    # 年龄推算基础等级
    age_base = {
        "4岁或以下": 2, "5岁": 4, "6岁": 6, "7岁": 8, "8岁或以上": 10,
    }.get(data.get("age","8岁或以上"), 10)

    # 学习时长加成
    exp_mod = {
        "从来没学过": -3, "不到 1 年": 0, "1–3 年": 4, "3 年以上": 8,
    }.get(data.get("experience","不到 1 年"), 0)

    # 自评加成
    level_map = {
        "🌱 几乎不会，只认识几个字母":       -4,
        "🌿 认识一些单词，能说简单句子":      -2,
        "🌳 能读懂简单短文，会基本日常对话":   0,
        "🦅 能读懂普通文章，能写简短段落":     4,
        "⭐ 阅读流畅，语法基本正确":           8,
        "🏆 英语非常好，接近母语水平":         14,
    }
    self_mod = level_map.get(data.get("self_level",""), 0)

    # 阅读题加成
    reading_bonus = 0
    if data.get("reading1_correct"): reading_bonus += 2
    if data.get("reading2_correct"): reading_bonus += 3

    estimated = max(1, min(40, age_base + exp_mod + self_mod + reading_bonus))

    return {
        "age":             data.get("age",""),
        "experience":      data.get("experience",""),
        "self_level":      data.get("self_level",""),
        "interests":       data.get("interests",[]),
        "goal":            data.get("goal",""),
        "reading_correct": data.get("reading1_correct",False) and data.get("reading2_correct",False),
        "estimated_level": estimated,
        "filler":          st.session_state.get("q_filler","parent"),
    }
