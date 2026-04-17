import streamlit as st
import os
import sys
import json
import tempfile

from dotenv import load_dotenv
load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

ffmpeg_path = os.path.join(root_dir, "ffmpeg", "bin")
os.environ["PATH"] += os.pathsep + ffmpeg_path

from openai import OpenAI
import whisper
from content_pipeline import ContentPipeline

st.set_page_config(page_title="AI 听力练习", page_icon="🎧", layout="wide")
st.title("🎧 AI 智能听力 · 内容流水线")
st.markdown("支持音频和视频，自动转录 → 分级 → 出题 → 同步阅读书库")

# ── 初始化 ──────────────────────────────────────
@st.cache_resource
def get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        st.error("❌ 请在 .env 文件写入 DEEPSEEK_API_KEY")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

@st.cache_resource
def get_whisper():
    return whisper.load_model("base")

@st.cache_resource
def get_pipeline():
    return ContentPipeline(get_client(), get_whisper(), root_dir)

client = get_client()
pipeline = get_pipeline()

# ── 侧边栏 ──────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 设置")
    level = st.selectbox("学生等级", ["A0 启蒙", "A1 初级", "A2 中级", "B1 进阶"], index=1)
    question_types = st.multiselect("题型", ["填空题", "选择题", "判断正误", "简答题"],
                                    default=["填空题", "选择题"])
    num_questions = st.slider("每个文件题目数", 2, 8, 3)
    auto_questions = st.toggle("自动出题", value=True,
                               help="关闭后只转录，不生成题目（适合有原题的KET/PET）")
    save_to_library = st.toggle("同步到阅读书库", value=True,
                                help="转录结果自动进入4_reading.py的分级书库")
    st.divider()
    st.caption("🎧 STT: Whisper（本地）")
    st.caption("🤖 分析+出题: DeepSeek V3")
    st.caption("📚 打通阅读模块: reading_library.json")

# ── Session State ────────────────────────────────
for k, v in {
    "results": {},
    "current": None,
    "answers": {},
    "submitted": set(),
    "questions_cache": {}
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 出题函数 ─────────────────────────────────────
def generate_questions(transcript, level, types, num):
    type_str = "、".join(types)
    prompt = f"""Create {num} listening comprehension exercises for level {level}.
Types: {type_str}. Transcript: {transcript[:1500]}

Return ONLY JSON array:
[
  {{"type":"填空题","question":"She likes to ___ on weekends.","answer":"read","options":null,"hint":"hobby"}},
  {{"type":"选择题","question":"Where is she from?","answer":"B","options":["A. Beijing","B. Shanghai","C. Shenzhen","D. Guangzhou"],"hint":null}},
  {{"type":"判断正误","question":"She has a cat.","answer":"True","options":["True","False"],"hint":null}}
]"""
    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000, temperature=0.4)
        raw = r.choices[0].message.content.strip().replace("```json","").replace("```","")
        return json.loads(raw)
    except Exception as e:
        return [{"type":"简答题","question":f"出题失败:{e}","answer":"","options":None,"hint":None}]

def evaluate(question, correct, student, qtype):
    if qtype in ["选择题","判断正误"]:
        ok = str(student).strip().upper() == str(correct).strip().upper()
        return {"correct":ok,"feedback":"✅ 正确！" if ok else f"❌ 正确答案：{correct}"}
    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":
                f"Q: {question}\nCorrect: {correct}\nStudent: {student}\n"
                f"JSON only: {{\"correct\":true/false,\"feedback\":\"brief Chinese\"}}"}],
            max_tokens=80, temperature=0.3)
        raw = r.choices[0].message.content.strip().replace("```json","").replace("```","")
        return json.loads(raw)
    except:
        ok = str(correct).lower() in str(student).lower()
        return {"correct":ok,"feedback":"✅ 不错！" if ok else f"参考：{correct}"}

# ════════════════════════════════════════════════
# 上传区
# ════════════════════════════════════════════════
upload_mode = st.radio("上传方式", ["单个文件", "批量上传"],
                       horizontal=True, label_visibility="collapsed")
st.markdown("---")

col_left, col_right = st.columns([1, 1])

with col_left:
    AUDIO_TYPES = ["mp3", "wav", "m4a", "aac"]
    VIDEO_TYPES = ["mp4", "mov", "avi", "mkv", "webm"]
    ALL_TYPES = AUDIO_TYPES + VIDEO_TYPES

    if upload_mode == "单个文件":
        st.subheader("📁 上传文件")
        st.caption("支持音频：mp3 / wav / m4a　|　视频：mp4 / mov / avi / mkv")
        f = st.file_uploader("选择文件", type=ALL_TYPES, key="single")
        if f:
            ext = os.path.splitext(f.name)[1].lower()
            if ext in ["."+t for t in VIDEO_TYPES]:
                st.video(f)
            else:
                st.audio(f)

            if st.button("🚀 开始处理", type="primary", use_container_width=True):
                bar = st.progress(0, text=f"📥 处理中：{f.name}")
                with st.spinner(""):
                    result = pipeline.process(
                        f.getvalue(), f.name,
                        save_to_library=save_to_library)
                bar.progress(70, text="🤖 生成题目中...")
                if auto_questions:
                    qs = generate_questions(
                        result["transcript"], level, question_types, num_questions)
                    st.session_state.questions_cache[f.name] = qs
                bar.progress(100, text="✅ 完成！")
                import time; time.sleep(0.3); bar.empty()
                st.session_state.results[f.name] = result
                st.session_state.current = f.name
                st.session_state.answers = {}
                st.session_state.submitted = set()
                st.rerun()

    else:
        st.subheader("📂 批量上传")
        st.caption("按住 Ctrl 多选文件，音频和视频都支持")
        files = st.file_uploader("选择多个文件", type=ALL_TYPES,
                                 accept_multiple_files=True, key="batch")
        if files:
            st.success(f"已选择 {len(files)} 个文件")
            for f in files:
                done = f.name in st.session_state.results
                st.caption(f"{'✅' if done else '⏳'} {f.name}")

            if st.button(f"🚀 批量处理全部 {len(files)} 个",
                         type="primary", use_container_width=True):
                bar = st.progress(0)
                status = st.empty()
                for i, f in enumerate(files):
                    if f.name in st.session_state.results:
                        continue
                    status.text(f"处理 {i+1}/{len(files)}：{f.name}")
                    result = pipeline.process(
                        f.getvalue(), f.name,
                        save_to_library=save_to_library)
                    if auto_questions:
                        qs = generate_questions(
                            result["transcript"], level, question_types, num_questions)
                        st.session_state.questions_cache[f.name] = qs
                    st.session_state.results[f.name] = result
                    bar.progress((i+1)/len(files))
                status.text("✅ 全部完成！")
                import time; time.sleep(0.5)
                status.empty(); bar.empty()
                if files:
                    st.session_state.current = files[0].name
                st.rerun()

    # ── 文件列表 ──
    if st.session_state.results:
        st.divider()
        st.subheader("📋 已处理文件")
        for fname, data in st.session_state.results.items():
            a = data.get("analysis", {})
            is_cur = fname == st.session_state.current
            done = fname in st.session_state.submitted
            c1, c2 = st.columns([3, 1])
            with c1:
                icon = "🎬" if data.get("file_type") == "video" else "🎧"
                st.caption(
                    f"{'🔵 ' if is_cur else ''}{icon} {fname}　"
                    f"{a.get('cefr_level','')} | {data['wpm']} WPM | {data['duration']}秒"
                    f"{'　✅' if done else ''}"
                )
            with c2:
                if st.button("练习", key=f"sel_{fname}", use_container_width=True):
                    st.session_state.current = fname
                    st.session_state.answers = {}
                    st.rerun()

        # ── 导出按钮 ──
        st.divider()
        st.subheader("💾 导出转录结果")
        results_list = list(st.session_state.results.values())
        c1, c2 = st.columns(2)
        with c1:
            txt_path = os.path.join(root_dir, "temp_uploads", "transcripts.txt")
            pipeline.export_txt(results_list, txt_path)
            with open(txt_path, "rb") as f:
                st.download_button("📄 下载 TXT", f.read(),
                                   "transcripts.txt", "text/plain",
                                   use_container_width=True)
        with c2:
            csv_path = os.path.join(root_dir, "temp_uploads", "transcripts.csv")
            pipeline.export_csv(results_list, csv_path)
            with open(csv_path, "rb") as f:
                st.download_button("📊 下载 CSV", f.read(),
                                   "transcripts.csv", "text/csv",
                                   use_container_width=True)

        if st.button("🗑️ 清空所有", use_container_width=True):
            st.session_state.results = {}
            st.session_state.current = None
            st.session_state.answers = {}
            st.session_state.submitted = set()
            st.session_state.questions_cache = {}
            st.rerun()

# ════════════════════════════════════════════════
# 右侧：练习区
# ════════════════════════════════════════════════
with col_right:
    current = st.session_state.current
    data = st.session_state.results.get(current)

    if not data:
        st.subheader("📋 练习区")
        st.info("👈 上传文件后点击「练习」开始。")
    else:
        a = data.get("analysis", {})
        icon = "🎬" if data.get("file_type") == "video" else "🎧"
        st.subheader(f"{icon} {current}")

        # 分析卡片
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("等级", a.get("cefr_level", ""))
        c2.metric("语速", f"{data['wpm']} WPM")
        c3.metric("时长", f"{data['duration']}秒")
        c4.metric("适合", a.get("suitable_age", ""))

        if a.get("summary"):
            st.info(f"📝 {a['summary']}")

        if a.get("key_vocabulary"):
            st.caption("🔑 核心词汇：" + "　".join(a["key_vocabulary"]))

        if save_to_library:
            st.success(f"✅ 已同步到阅读书库（{a.get('cefr_level','')} 级别）")

        with st.expander("📄 查看完整转录原文"):
            st.write(data["transcript"])

        st.divider()

        # ── 练习题 ──
        questions = st.session_state.questions_cache.get(current, [])
        already_done = current in st.session_state.submitted

        if not auto_questions:
            st.info("已关闭自动出题。转录文本已保存，可对照原题练习。")
        elif not questions:
            st.info("暂无题目。")
        elif not already_done:
            st.subheader("📋 听力练习题")
            with st.form(f"quiz_{current}"):
                ans = {}
                for i, q in enumerate(questions):
                    st.markdown(f"**Q{i+1}. [{q.get('type','')}] {q['question']}**")
                    if q.get("hint"):
                        st.caption(f"💡 {q['hint']}")
                    opts = q.get("options")
                    if opts:
                        ans[i] = st.radio(f"r_{i}", opts,
                                          key=f"r_{current}_{i}",
                                          label_visibility="collapsed")
                    else:
                        ans[i] = st.text_input(f"t_{i}",
                                               key=f"t_{current}_{i}",
                                               placeholder="输入答案...",
                                               label_visibility="collapsed")
                    st.markdown("---")
                if st.form_submit_button("✅ 提交", use_container_width=True):
                    st.session_state.answers[current] = ans
                    st.session_state.submitted.add(current)
                    st.rerun()
        else:
            ans = st.session_state.answers.get(current, {})
            correct_count = 0
            st.subheader("📊 批改结果")
            for i, q in enumerate(questions):
                s = ans.get(i, "")
                if not s:
                    continue
                r = evaluate(q["question"], q["answer"], s, q.get("type",""))
                if r.get("correct"):
                    correct_count += 1
                    st.success(f"Q{i+1} ✅ {r['feedback']}")
                else:
                    st.error(f"Q{i+1} ❌ {r['feedback']}")

            total = len(questions)
            score = round(correct_count/total*100) if total else 0
            st.divider()
            if score == 100: st.balloons(); st.success(f"🏆 满分！")
            elif score >= 80: st.success(f"🌟 {score}分（{correct_count}/{total}）")
            elif score >= 60: st.warning(f"💪 {score}分（{correct_count}/{total}）")
            else: st.error(f"📚 {score}分（{correct_count}/{total}）")

            all_files = list(st.session_state.results.keys())
            cur_idx = all_files.index(current) if current in all_files else -1
            remaining = [f for f in all_files if f not in st.session_state.submitted]

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 重做", use_container_width=True):
                    st.session_state.submitted.discard(current)
                    st.session_state.answers.pop(current, None)
                    st.rerun()
            with c2:
                next_f = next((f for f in all_files[cur_idx+1:]
                               if f not in st.session_state.submitted), None)
                if next_f:
                    if st.button(f"▶ 下一个", use_container_width=True):
                        st.session_state.current = next_f
                        st.rerun()
                elif not remaining:
                    st.success("🎉 全部完成！")
