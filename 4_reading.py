import streamlit as st
import os
import sys
import json
import time
import random

from dotenv import load_dotenv
load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from openai import OpenAI

st.set_page_config(page_title="OMNI-EFL 分级阅读", page_icon="📚", layout="wide")

st.markdown("""
<style>
.level-badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:.8rem;
  font-weight:700; margin-right:6px; }
.book-card { background:white; border-radius:12px; padding:16px; margin-bottom:12px;
  border:1px solid #e8f0fe; transition:.25s; }
.book-card:hover { border-color:#3b82f6; box-shadow:0 6px 16px rgba(59,130,246,.15);
  transform:translateY(-2px); }
.locked-card { background:#f8fafc; border-radius:12px; padding:20px; margin-bottom:12px;
  border:1px dashed #cbd5e1; color:#94a3b8; text-align:center; }
.reading-text { background:#fafbff; border-radius:12px; padding:24px 28px; line-height:2;
  font-size:1.05rem; border-left:4px solid #3b82f6; margin-bottom:20px; }
.vocab-pill { display:inline-block; background:#fef3c7; color:#92400e; padding:2px 8px;
  border-radius:10px; font-size:.82rem; margin:2px; font-weight:500; }
.omni-box { background:linear-gradient(135deg,#eff6ff,#f0fdf4); border-radius:12px;
  padding:14px 18px; margin-bottom:14px; border-left:4px solid #10b981; }
.phase-header { background:linear-gradient(90deg,#1e3a8a,#1d4ed8); color:white;
  padding:12px 20px; border-radius:10px; margin-bottom:16px; }
.cse-tag { background:#dbeafe; color:#1e40af; padding:2px 8px; border-radius:8px;
  font-size:.75rem; margin-right:4px; }
.lexile-tag { background:#dcfce7; color:#166534; padding:2px 8px; border-radius:8px;
  font-size:.75rem; margin-right:4px; }
.can-do { background:#f0fdf4; border-left:3px solid #22c55e; padding:10px 14px;
  border-radius:0 8px 8px 0; margin-bottom:8px; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

# ── 客户端 ──────────────────────────────────────
@st.cache_resource
def get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        st.error("❌ 请在 .env 文件写入 DEEPSEEK_API_KEY")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

client = get_client()

# ══════════════════════════════════════════════════
# OMNI-EFL 100级体系定义
# ══════════════════════════════════════════════════
PHASES = [
    {"range":(1,15),  "name":"感官唤醒与前文本期",    "color":"#84cc16", "bg":"#f7fee7",
     "desc":"消除母语干扰，建立纯正音素感知，构建感官链接",
     "cefr":"Pre-A1 (A0)", "lexile":"BR400L–200L", "cn_std":"预备级–小二", "icon":"🍼"},
    {"range":(16,35), "name":"意群防伪与认知桥接期",  "color":"#10b981", "bg":"#f0fdf4",
     "desc":"强化流利度，开启限制性输出，对接基础AI知识与初级人文社科",
     "cefr":"A1–A2", "lexile":"240L–850L", "cn_std":"小三–小六", "icon":"🚶"},
    {"range":(36,65), "name":"跨界逻辑与文化博弈期", "color":"#0ea5e9", "bg":"#f0f9ff",
     "desc":"打破母语者崇拜，建立中国文化输出自信，防范化石化",
     "cefr":"B1–B2", "lexile":"870L–1350L", "cn_std":"初中–高三", "icon":"🌍"},
    {"range":(66,90), "name":"高维学术与批判重构期", "color":"#8b5cf6", "bg":"#faf5ff",
     "desc":"对接真实学术语境，预留100个专业领域接口",
     "cefr":"C1–C2", "lexile":"1360L–1600L", "cn_std":"大学四六级–雅思8.0", "icon":"🎓"},
    {"range":(91,100),"name":"原典全息解锁终极境界", "color":"#f43f5e", "bg":"#fff1f2",
     "desc":"语言彻底化为无感介质，认知封神，向世界输出大国智慧",
     "cefr":"超越母语者", "lexile":"1620L–1800L+", "cn_std":"学术顶流–全知归一", "icon":"🚀"},
]

# 关键等级的详细信息（can-do + OMNI映射）
LEVEL_DETAILS = {
    1:  {"can_do":"能在多模态画面辅助下，听懂并点击对应基础自然名词（如 sun, tree）",
         "omni":"婴幼感官觉醒——看、听、摸的基础视觉书，感知真实世界的色彩",
         "cse":"CSE1", "lexile":"BR400L"},
    5:  {"can_do":"能将前10个超高频视觉词字形与画面直接绑定，不拼读",
         "omni":"全宇宙之钥：数学——数字1-10英文具象化点数启蒙",
         "cse":"CSE1", "lexile":"BR250L"},
    10: {"can_do":"能不间断跟读包含3个词的句子，感受英语连续语流的节奏",
         "omni":"[AI不可替代] 全生命周期游戏疗愈——用英文表达家庭成员间的基础爱意",
         "cse":"CSE1", "lexile":"0L"},
    15: {"can_do":"能在AI高亮提示下，以意群（Chunks）为单位正确断句朗读",
         "omni":"[AI不可替代] 积极心理学——用英文认知坚持与韧性的基础概念",
         "cse":"CSE2", "lexile":"200L"},
    20: {"can_do":"能将短篇故事准确拆分为开端、发展、结局三个结构层次",
         "omni":"[AI不可替代] 关系解剖学——处理朋友之间分享玩具引发的微小心理冲突",
         "cse":"CSE3", "lexile":"400L"},
    30: {"can_do":"能运用上下文线索猜测生词，并用英文完整复述段落大意",
         "omni":"[AI不可替代] 青春期情感与价值观——阅读同伴压力下做出正确选择的故事",
         "cse":"CSE4", "lexile":"650L"},
    35: {"can_do":"能在科学报告中识别假设、证据与结论三者的逻辑关系",
         "omni":"大数据与智慧城市——阅读关于城市交通数据如何优化出行的科普图表",
         "cse":"CSE4", "lexile":"850L"},
    45: {"can_do":"能跳出字面意思，概括文学作品中隐含的深层道德或社会主旨",
         "omni":"AI人工智能终极书单——《通用人工智能》降维版，理解AGI演化对人类社会的冲击",
         "cse":"CSE5", "lexile":"1050L"},
    50: {"can_do":"能识别文本中刻板印象或带有强烈情感倾向的引导性词语",
         "omni":"[AI不可替代] 国际政治学——阅读外媒社论，识别报道中外贸易摩擦时的遣词偏见",
         "cse":"CSE5", "lexile":"1150L"},
    60: {"can_do":"能理解由于中西方底层哲学差异导致的涉华报道中的深层文化错位",
         "omni":"海外汉学视角——阅读海外学者对中国人情社会与西方契约社会的对比文献",
         "cse":"CSE6", "lexile":"1300L"},
    70: {"can_do":"能深入解剖顶级政要演讲，拆解其排比、节奏等情感操控修辞",
         "omni":"[AI不可替代] 领袖传记——拆解300位政坛风云人物演讲稿中的情感杠杆",
         "cse":"CSE7", "lexile":"1400L"},
    80: {"can_do":"能综合十份英文智库报告，撰写关于全球能源格局的战略研判论文",
         "omni":"宏观历史与大国推演——全英文战略研判论文写作",
         "cse":"CSE8", "lexile":"1500L"},
    90: {"can_do":"彻底摆脱字典，完全依靠工作记忆无损处理Nature、Science级别原版顶刊",
         "omni":"生命科学、高维拓扑学、地缘政治学原典矩阵，语言降维为透明介质",
         "cse":"CSE9", "lexile":"1600L"},
    100:{"can_do":"在OMNI 18189本知识大系及无限新知中自由穿梭，向全世界输出中国大国方案",
         "omni":"[AI终极不可替代] 同理心、审美创造、哲学信仰、韧性与爱——0-150岁全生命周期觉醒",
         "cse":"CSE9+", "lexile":"1800L+"},
}

def get_phase(lv):
    for p in PHASES:
        if p["range"][0] <= lv <= p["range"][1]:
            return p
    return PHASES[-1]

def get_level_detail(lv):
    # 找最近的详细定义
    keys = sorted(LEVEL_DETAILS.keys())
    best = keys[0]
    for k in keys:
        if k <= lv:
            best = k
    return LEVEL_DETAILS[best]

def level_to_cefr(lv):
    p = get_phase(lv)
    return p["cefr"].split("(")[-1].rstrip(")")

def score_to_level(score):
    """0-100分 → Level 1-100"""
    return max(1, min(100, int(score * 1.0)))

def update_ability(score, correct):
    delta = 8 if correct else -5
    return max(0, min(100, score + delta))

# ── Session State ────────────────────────────────
defaults = {
    "view": "home",
    "user_level": 0,
    "cat_questions": [],
    "cat_answers": [],
    "cat_index": 0,
    "cat_score": 35,       # 初始预设A1水平
    "reading_content": None,
    "reading_answers": {},
    "reading_submitted": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════
# AI 自适应测评（CAT）
# ══════════════════════════════════════════════════
def generate_cat_question(ability_score):
    lv = score_to_level(ability_score)
    phase = get_phase(lv)
    detail = get_level_detail(lv)

    if lv <= 15:
        difficulty = "very basic (Pre-A1): simple nouns, animals, colors, family members"
        task = "picture matching or listening comprehension with very simple words"
    elif lv <= 35:
        difficulty = f"elementary (A1-A2, Lexile ~{detail['lexile']}): basic sentences about daily life"
        task = "reading a 3-5 sentence passage and answering a simple question"
    elif lv <= 65:
        difficulty = f"intermediate (B1-B2, Lexile ~{detail['lexile']}): paragraphs about science, history, culture"
        task = "reading a short article and identifying main idea or making inference"
    elif lv <= 90:
        difficulty = f"advanced (C1, Lexile ~{detail['lexile']}): academic texts, critical thinking"
        task = "analyzing argument structure or identifying logical fallacies"
    else:
        difficulty = "expert (C2+, Lexile 1600L+): philosophical or scientific discourse"
        task = "deep comprehension of complex academic or literary text"

    prompt = f"""Create ONE reading comprehension question for OMNI-EFL Level {lv}.
Difficulty: {difficulty}
Task type: {task}

Return ONLY valid JSON:
{{
  "passage": "Appropriate reading passage for Level {lv}.",
  "question": "Comprehension question.",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": "A",
  "explanation": "Why A is correct.",
  "level": {lv},
  "skill": "main idea / detail / inference / vocabulary / critical thinking"
}}"""

    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            max_tokens=600, temperature=0.6
        )
        raw = r.choices[0].message.content.strip().replace("```json","").replace("```","")
        return json.loads(raw)
    except:
        return {
            "passage": "The sun is a star at the center of our solar system. It provides heat and light.",
            "question": "What does the sun provide?",
            "options": ["A. Heat and light", "B. Water and food", "C. Wind and rain", "D. Snow and ice"],
            "answer": "A",
            "explanation": "The passage states the sun provides heat and light.",
            "level": lv, "skill": "detail"
        }

# ══════════════════════════════════════════════════
# AI 生成 OMNI 分级阅读文章
# ══════════════════════════════════════════════════
def generate_reading(level, topic=""):
    phase = get_phase(level)
    detail = get_level_detail(level)

    if not topic:
        # OMNI 知识映射主题库
        if level <= 15:
            topics = ["animals and nature", "colors and shapes", "family and emotions",
                      "numbers and counting", "classical music and art"]
        elif level <= 35:
            topics = ["robots and technology", "ancient history", "how plants grow",
                      "financial literacy for kids", "evolution and dinosaurs"]
        elif level <= 65:
            topics = ["artificial intelligence", "geopolitics", "climate science",
                      "cultural differences East and West", "psychology of decision making"]
        elif level <= 90:
            topics = ["academic research methodology", "philosophy and ethics",
                      "machine learning algorithms", "global economic systems",
                      "neuroscience and consciousness"]
        else:
            topics = ["AGI alignment problem", "cross-disciplinary innovation",
                      "Chinese civilization in global context",
                      "frontier physics and cosmology", "language and cognition"]
        topic = random.choice(topics)

    omni_note = detail.get("omni", "")
    can_do = detail.get("can_do", "")
    lexile = detail.get("lexile", "")
    cse = detail.get("cse", "")

    if level <= 15:
        length_guide = "40-80 words, extremely simple sentences (3-5 words each), concrete nouns only"
        output_guide = "Use very simple present tense. No complex grammar."
    elif level <= 35:
        length_guide = "100-160 words, simple compound sentences, familiar vocabulary"
        output_guide = "A1-A2 vocabulary. Include a few slightly challenging words with context clues."
    elif level <= 65:
        length_guide = "180-260 words, varied sentence structures, some academic vocabulary"
        output_guide = "B1-B2 level. Include topic-specific terminology. Engage critical thinking."
    elif level <= 90:
        length_guide = "260-350 words, complex sentences, academic register"
        output_guide = "C1 level. Dense information. Require inference and analysis."
    else:
        length_guide = "300-400 words, sophisticated discourse, nuanced argumentation"
        output_guide = "Expert level. Philosophical depth. Cross-disciplinary connections."

    prompt = f"""Generate an OMNI-EFL graded reading passage.

OMNI-EFL Level: {level}/100
Phase: {phase["name"]}
Lexile: {lexile} | CSE: {cse}
Can-Do Standard: {can_do}
OMNI Knowledge Mapping: {omni_note}
Topic: {topic}

Length guide: {length_guide}
Style guide: {output_guide}

Hi-Lo Principle: Match COGNITIVE LEVEL to learner's age/intellect while keeping LANGUAGE LEVEL appropriate for Level {level}.

Return ONLY valid JSON:
{{
  "title": "Engaging title",
  "text": "Full reading passage.",
  "topic": "{topic}",
  "word_count": 150,
  "lexile_approx": "{lexile}",
  "key_vocabulary": ["word1","word2","word3","word4","word5"],
  "chinese_summary": "一句话中文摘要",
  "omni_note": "{omni_note[:60]}",
  "can_do": "{can_do[:80]}",
  "questions": [
    {{"q":"Main idea question?","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","type":"main_idea"}},
    {{"q":"Detail question?","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"B","type":"detail"}},
    {{"q":"Inference or vocabulary question?","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"C","type":"inference"}}
  ]
}}"""

    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            max_tokens=1400, temperature=0.7
        )
        raw = r.choices[0].message.content.strip().replace("```json","").replace("```","")
        return json.loads(raw)
    except Exception as e:
        return {
            "title": f"OMNI Level {level} Reading",
            "text": "Content generation in progress. Please check your DeepSeek API connection.",
            "topic": topic, "word_count": 10,
            "lexile_approx": lexile,
            "key_vocabulary": [],
            "chinese_summary": "内容生成中",
            "omni_note": omni_note,
            "can_do": can_do,
            "questions": [],
            "error": str(e)
        }

# ══════════════════════════════════════════════════
# 书库读取
# ══════════════════════════════════════════════════
def load_library():
    lib_path = os.path.join(root_dir, "reading_library.json")
    if os.path.exists(lib_path):
        try:
            with open(lib_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# ══════════════════════════════════════════════════
# 视图：首页
# ══════════════════════════════════════════════════
if st.session_state.view == "home":
    st.title("📚 OMNI-EFL 全生命周期分级阅读")
    st.markdown("**100级双标尺体系** · 中国CSE/新课标 × 美国CCSS/Lexile · 0岁–终身学习")
    st.divider()

    # 五大阶段概览
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🗺️ 五大阶段全景")
        for p in PHASES:
            lo, hi = p["range"]
            st.markdown(f"""
<div style="background:{p["bg"]};border-left:5px solid {p["color"]};
  padding:14px 18px;border-radius:0 10px 10px 0;margin-bottom:10px;">
  <div style="font-size:1.1rem;font-weight:700;color:{p["color"]};">
    {p["icon"]} Level {lo}–{hi} · {p["name"]}</div>
  <div style="font-size:.82rem;color:#475569;margin-top:4px;">
    <span class="cse-tag">{p["cn_std"]}</span>
    <span class="lexile-tag">Lexile {p["lexile"]}</span>
    <span class="cse-tag">{p["cefr"]}</span>
  </div>
  <div style="font-size:.88rem;color:#64748b;margin-top:6px;">{p["desc"]}</div>
</div>
""", unsafe_allow_html=True)

    with col2:
        st.subheader("🎯 我的状态")

        if st.session_state.user_level > 0:
            lv = st.session_state.user_level
            phase = get_phase(lv)
            detail = get_level_detail(lv)

            st.markdown(f"""
<div style="background:{phase["bg"]};border:2px solid {phase["color"]};
  border-radius:14px;padding:18px;text-align:center;margin-bottom:14px;">
  <div style="font-size:2.5rem;font-weight:800;color:{phase["color"]};">L{lv}</div>
  <div style="font-size:1rem;font-weight:600;color:#1e293b;">{phase["name"]}</div>
  <div style="font-size:.82rem;color:#64748b;margin-top:6px;">
    {detail.get("cse","")} · {detail.get("lexile","")}
  </div>
</div>
""", unsafe_allow_html=True)

            st.progress(lv/100, text=f"Level {lv}/100")

            st.markdown('<div class="can-do">✅ ' + detail.get("can_do","")[:100] + '</div>',
                       unsafe_allow_html=True)
            st.markdown(f"""
<div class="omni-box"><b>🌟 OMNI 知识映射</b><br>
<span style="font-size:.85rem;">{detail.get("omni","")[:120]}</span></div>
""", unsafe_allow_html=True)

            if st.button("📚 进入书库", type="primary", use_container_width=True):
                st.session_state.view = "catalog"
                st.rerun()
            if st.button("🔄 重新测评", use_container_width=True):
                for k in ["user_level","cat_questions","cat_answers","cat_index"]:
                    st.session_state[k] = 0 if k != "cat_questions" and k != "cat_answers" else []
                st.session_state.cat_score = 35
                st.session_state.view = "assessment"
                st.rerun()
        else:
            st.info("完成 AI 自适应测评，精准定位你在 100 级体系中的坐标。")
            st.markdown("""
<div style="background:#eff6ff;padding:14px;border-radius:10px;font-size:.88rem;margin-bottom:14px;">
<b>🧠 OMNI CAT 测评特点</b><br>
• 5题精准定位 Level 1–100<br>
• 中美双标尺同时校准<br>
• 根据答题表现实时调整难度<br>
• 防范流利度假象（Barking at print）
</div>
""", unsafe_allow_html=True)
            if st.button("🚀 开始 AI 自适应测评", type="primary", use_container_width=True):
                st.session_state.view = "assessment"
                st.session_state.cat_score = 35
                st.rerun()

# ══════════════════════════════════════════════════
# 视图：AI 自适应测评 (CAT)
# ══════════════════════════════════════════════════
elif st.session_state.view == "assessment":
    TOTAL = 6
    qi = st.session_state.cat_index
    cur_lv = score_to_level(st.session_state.cat_score)
    phase = get_phase(cur_lv)

    st.title("🧠 OMNI-EFL AI 自适应测评")
    st.progress(qi/TOTAL, text=f"第 {qi+1}/{TOTAL} 题 · 当前估算 Level ~{cur_lv}")

    if qi >= TOTAL:
        final_lv = score_to_level(st.session_state.cat_score)
        st.session_state.user_level = final_lv
        phase = get_phase(final_lv)
        detail = get_level_detail(final_lv)
        st.balloons()

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("OMNI-EFL 等级", f"Level {final_lv}/100")
        col_r2.metric("CSE 标准", detail.get("cse",""))
        col_r3.metric("Lexile 蓝思值", detail.get("lexile",""))

        st.markdown(f"""
<div class="phase-header">
  {phase["icon"]} 阶段：{phase["name"]} · {phase["cefr"]} · {phase["cn_std"]}
</div>
""", unsafe_allow_html=True)

        st.markdown('<div class="can-do">✅ Can-Do：' + detail.get("can_do","") + '</div>',
                   unsafe_allow_html=True)
        st.markdown(f"""
<div class="omni-box">🌟 <b>OMNI 知识映射：</b>{detail.get("omni","")}</div>
""", unsafe_allow_html=True)

        correct = sum(1 for a in st.session_state.cat_answers if a["correct"])
        st.info(f"答对 {correct}/{TOTAL} 题")

        with st.expander("📋 查看答题回顾"):
            for i, rec in enumerate(st.session_state.cat_answers):
                icon = "✅" if rec["correct"] else "❌"
                st.markdown(f"**{icon} 第{i+1}题（Level ~{rec.get('level','')}）**")
                st.caption(rec["passage"][:150] + "...")
                st.caption(f"正确答案：{rec['answer']} | 你选：{rec['student']}")

        if st.button("📚 进入我的 OMNI 书库", type="primary", use_container_width=True):
            st.session_state.view = "catalog"
            st.rerun()
    else:
        if qi >= len(st.session_state.cat_questions):
            with st.spinner(f"🤖 AI 正在为 Level ~{cur_lv} 出题..."):
                q = generate_cat_question(st.session_state.cat_score)
                st.session_state.cat_questions.append(q)
        else:
            q = st.session_state.cat_questions[qi]

        lv_q = q.get("level", cur_lv)
        phase_q = get_phase(lv_q)

        st.markdown(f"""
<div style="background:{phase_q["bg"]};border-left:4px solid {phase_q["color"]};
  padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:14px;font-size:.85rem;">
  <b>Level {lv_q}</b> · {phase_q["name"]} · 技能：{q.get("skill","")}
</div>
""", unsafe_allow_html=True)

        st.subheader("📖 阅读材料")
        st.markdown(f'<div class="reading-text">{q["passage"]}</div>', unsafe_allow_html=True)

        st.subheader("❓ 问题")
        st.write(q["question"])

        selected = st.radio("选择答案：", q["options"],
                            key=f"cat_{qi}", label_visibility="collapsed")

        if st.button("确认 →", type="primary", use_container_width=True):
            letter = selected[0] if selected else "A"
            correct = letter == q["answer"]
            st.session_state.cat_answers.append({
                "passage": q["passage"],
                "question": q["question"],
                "student": selected,
                "answer": q["answer"],
                "correct": correct,
                "level": lv_q,
                "explanation": q.get("explanation","")
            })
            st.session_state.cat_score = update_ability(st.session_state.cat_score, correct)
            st.session_state.cat_index += 1
            st.rerun()

# ══════════════════════════════════════════════════
# 视图：书库
# ══════════════════════════════════════════════════
elif st.session_state.view == "catalog":
    lv = st.session_state.user_level
    phase = get_phase(lv)
    detail = get_level_detail(lv)
    library = load_library()

    col_h1, col_h2 = st.columns([5, 2])
    with col_h1:
        st.title("📚 OMNI-EFL 书库")
        st.markdown(f"当前：**Level {lv}/100** · {phase['name']} · {detail.get('cse','')} · Lexile {detail.get('lexile','')}")
    with col_h2:
        st.write("")
        if st.button("🏠 首页", use_container_width=True):
            st.session_state.view = "home"; st.rerun()
        if st.button("🔄 重测", use_container_width=True):
            for k in ["user_level","cat_questions","cat_answers","cat_index"]:
                st.session_state[k] = 0 if k != "cat_questions" and k != "cat_answers" else []
            st.session_state.cat_score = 35
            st.session_state.view = "assessment"; st.rerun()

    st.divider()

    tab1, tab2, tab3 = st.tabs([
        f"⭐ 我的等级 Level {lv}",
        "📥 听力库内容",
        "🔭 探索其他等级"
    ])

    # ── Tab 1 ──
    with tab1:
        st.markdown(f"""
<div class="omni-box"><b>🌟 OMNI 知识映射</b>：{detail.get("omni","")}<br>
<b>✅ Can-Do</b>：{detail.get("can_do","")}</div>
""", unsafe_allow_html=True)

        topics_by_phase = {
            "1-15": ["Animals & Nature","Colors & Shapes","Family & Emotions",
                     "Numbers & Counting","Classical Music","Basic Science"],
            "16-35": ["Robots & Technology","Ancient History","Plant Growth",
                      "Money & Finance","Dinosaurs & Evolution","Geography"],
            "36-65": ["Artificial Intelligence","Geopolitics","Climate Science",
                      "East meets West Culture","Psychology","Chinese Civilization"],
            "66-90": ["Academic Research","Philosophy & Ethics","Machine Learning",
                      "Global Economy","Neuroscience","Legal Studies"],
            "91-100": ["AGI & Alignment","Cross-disciplinary Innovation",
                       "China in Global Context","Frontier Physics","Cognitive Science"],
        }
        phase_key = next((k for k in topics_by_phase if
                          int(k.split("-")[0]) <= lv <= int(k.split("-")[1])), "36-65")
        topics = topics_by_phase[phase_key]

        col_t, col_g = st.columns([2, 1])
        with col_t:
            topic = st.selectbox("选择 OMNI 知识话题", topics)
        with col_g:
            st.write("")
            if st.button("✨ AI 生成 OMNI 阅读", type="primary", use_container_width=True):
                with st.spinner(f"DeepSeek 生成 Level {lv} · {topic} 阅读材料..."):
                    content = generate_reading(lv, topic)
                st.session_state.reading_content = content
                st.session_state.reading_answers = {}
                st.session_state.reading_submitted = False
                st.session_state.view = "reading"
                st.rerun()

        if st.session_state.reading_content:
            rc = st.session_state.reading_content
            st.markdown(f"---
**上次阅读：** {rc.get('title','')}　"
                        f"<span style='color:#64748b;font-size:.85rem;'>{rc.get('chinese_summary','')}</span>",
                        unsafe_allow_html=True)
            if st.button("📖 继续阅读", use_container_width=True):
                st.session_state.view = "reading"; st.rerun()

    # ── Tab 2 ──
    with tab2:
        st.subheader("📥 听力转录内容")
        st.caption("来自「听力练习」模块上传并转录的音视频，已按 CEFR 等级自动分类")

        if not library:
            st.info("📭 暂无内容。请在「听力练习」模块上传音频并开启「同步到阅读书库」。")
        else:
            for lv_key, items in sorted(library.items()):
                with st.expander(f"{lv_key} — {len(items)} 篇", expanded=False):
                    for item in items:
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**{item.get('title', item.get('source_file',''))}**")
                            st.caption(f"{item.get('summary','')} · {item.get('wpm',0)} WPM")
                        with c2:
                            if st.button("📖", key=f"lib_{item.get('source_file','')}",
                                         use_container_width=True):
                                st.session_state.reading_content = {
                                    "title": item.get("title",""),
                                    "text": item.get("transcript",""),
                                    "topic": item.get("topic",""),
                                    "word_count": len(item.get("transcript","").split()),
                                    "key_vocabulary": item.get("key_vocabulary",[]),
                                    "questions": [],
                                    "chinese_summary": item.get("summary",""),
                                    "omni_note": "听力转录内容",
                                    "can_do": detail.get("can_do",""),
                                    "source": "library",
                                }
                                st.session_state.reading_answers = {}
                                st.session_state.reading_submitted = False
                                st.session_state.view = "reading"; st.rerun()

    # ── Tab 3 ──
    with tab3:
        st.subheader("🔭 探索所有等级")
        explore_lv = st.slider("选择等级", 1, 100, lv)
        ep = get_phase(explore_lv)
        ed = get_level_detail(explore_lv)

        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        col_e1.metric("阶段", ep["name"][:6])
        col_e2.metric("CSE", ed.get("cse",""))
        col_e3.metric("Lexile", ed.get("lexile",""))
        col_e4.metric("CEFR", ep["cefr"][:6])

        st.markdown(f'<div class="omni-box">{ed.get("omni","")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="can-do">✅ {ed.get("can_do","")}</div>', unsafe_allow_html=True)

        if explore_lv > lv + 10:
            st.warning(f"⚠️ Level {explore_lv} 比你当前高很多，先巩固 Level {lv} 再挑战。")

        ex_topic = st.text_input("话题（留空随机）", "", key="ex_topic")
        if st.button(f"✨ 生成 Level {explore_lv} OMNI 阅读", use_container_width=True):
            with st.spinner("生成中..."):
                content = generate_reading(explore_lv, ex_topic or "")
            st.session_state.reading_content = content
            st.session_state.reading_answers = {}
            st.session_state.reading_submitted = False
            st.session_state.view = "reading"; st.rerun()

# ══════════════════════════════════════════════════
# 视图：阅读体验
# ══════════════════════════════════════════════════
elif st.session_state.view == "reading":
    rc = st.session_state.reading_content
    if not rc:
        st.session_state.view = "catalog"; st.rerun()

    lv = st.session_state.user_level or 20
    phase = get_phase(lv)

    col_b, col_ti = st.columns([1, 6])
    with col_b:
        if st.button("← 返回", use_container_width=True):
            st.session_state.view = "catalog"; st.rerun()
    with col_ti:
        st.title(rc.get("title","阅读"))

    # 信息栏
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lexile", rc.get("lexile_approx", detail.get("lexile","") if "detail" in dir() else ""))
    c2.metric("词数", rc.get("word_count", len(rc.get("text","").split())))
    c3.metric("话题", rc.get("topic","")[:10])
    c4.metric("摘要", rc.get("chinese_summary","")[:8]+"..." if rc.get("chinese_summary") else "—")

    if rc.get("omni_note"):
        st.markdown(f'<div class="omni-box">🌟 <b>OMNI 映射：</b>{rc["omni_note"]}</div>',
                   unsafe_allow_html=True)
    if rc.get("can_do"):
        st.markdown(f'<div class="can-do">✅ <b>Can-Do：</b>{rc["can_do"]}</div>',
                   unsafe_allow_html=True)

    st.divider()
    col_left, col_right = st.columns([3, 1])

    with col_left:
        st.subheader("📖 阅读文章")
        st.markdown(f'<div class="reading-text">{rc.get("text","")}</div>',
                   unsafe_allow_html=True)

        kvs = rc.get("key_vocabulary",[])
        if kvs:
            st.markdown("**🔑 核心词汇：** " + " ".join(
                f'<span class="vocab-pill">{w}</span>' for w in kvs),
                unsafe_allow_html=True)

        st.divider()
        questions = rc.get("questions",[])

        if not questions and rc.get("source") == "library":
            if st.button("🤖 AI 生成理解题", type="primary"):
                with st.spinner("生成理解题..."):
                    gen = generate_reading(lv, rc.get("topic",""))
                    rc["questions"] = gen.get("questions",[])
                    st.session_state.reading_content = rc; st.rerun()
        elif questions:
            st.subheader("📝 阅读理解")
            if not st.session_state.reading_submitted:
                with st.form("rf"):
                    ans = {}
                    for i, q in enumerate(questions):
                        st.markdown(f'<div class="q-card"><b>Q{i+1}. {q["q"]}</b></div>',
                                   unsafe_allow_html=True)
                        ans[i] = st.radio(f"q{i}", q.get("options",[]),
                                          key=f"rq_{i}", label_visibility="collapsed")
                    if st.form_submit_button("✅ 提交", use_container_width=True):
                        st.session_state.reading_answers = ans
                        st.session_state.reading_submitted = True; st.rerun()
            else:
                correct = 0
                for i, q in enumerate(questions):
                    s = st.session_state.reading_answers.get(i,"")
                    ok = (s[0] if s else "") == q.get("answer","")
                    if ok: correct += 1; st.success(f"Q{i+1} ✅ {q['q']}")
                    else: st.error(f"Q{i+1} ❌ {q['q']}　正确：{q.get('answer','')}")

                score = round(correct/len(questions)*100)
                st.divider()
                if score==100: st.balloons(); st.success("🏆 满分！")
                elif score>=70: st.success(f"🌟 {score}分")
                else: st.warning(f"💪 {score}分，建议再读一遍")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔄 重做", use_container_width=True):
                        st.session_state.reading_submitted = False
                        st.session_state.reading_answers = {}; st.rerun()
                with c2:
                    if st.button("📚 返回书库", use_container_width=True):
                        st.session_state.view = "catalog"; st.rerun()

    with col_right:
        st.subheader("📊 我的进度")
        st.progress(lv/100, text=f"Level {lv}/100")

        p = get_phase(lv)
        st.markdown(f"""
<div style="background:{p["bg"]};border:1.5px solid {p["color"]};
  border-radius:10px;padding:12px;text-align:center;margin-bottom:12px;">
  <div style="font-size:1.8rem;font-weight:800;color:{p["color"]};">L{lv}</div>
  <div style="font-size:.85rem;color:#475569;">{p["name"]}</div>
</div>""", unsafe_allow_html=True)

        if kvs:
            st.subheader("📌 词汇")
            for w in kvs[:6]:
                st.markdown(f"`{w}`")

        st.subheader("🔄 换一篇")
        new_topic = st.text_input("话题", rc.get("topic",""), key="new_t",
                                  label_visibility="collapsed")
        if st.button("✨ 生成新文章", use_container_width=True):
            with st.spinner("生成中..."):
                nc = generate_reading(lv, new_topic)
            st.session_state.reading_content = nc
            st.session_state.reading_answers = {}
            st.session_state.reading_submitted = False; st.rerun()
