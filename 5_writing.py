import streamlit as st
import os
import sys
import json

from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openai import OpenAI

st.set_page_config(page_title="写作批改", page_icon="✍️", layout="wide")

@st.cache_resource
def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        st.error("❌ 请在项目根目录新建 .env 文件，写入 DEEPSEEK_API_KEY=sk-你的key")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

client = get_deepseek_client()

GRADING_PROMPTS = {
    "通用写作 (General)": "You are an encouraging English writing teacher for children aged 3-12. Grade on Grammar (30%), Vocabulary (25%), Coherence (25%), Content (20%). Be warm and constructive. Point out 2-3 specific improvements.",
    "IELTS 雅思大作文": "You are an expert IELTS examiner. Grade Task 2 on Task Achievement (25%), Coherence & Cohesion (25%), Lexical Resource (25%), Grammatical Range & Accuracy (25%). Provide band score 0-9 for each and overall.",
    "TOEFL 托福": "You are a TOEFL writing examiner. Grade on Development (30%), Organization (30%), Language Use (40%). Score 0-30.",
    "CET-4/6 四六级": "You are a CET examiner. Grade on Content (40%), Organization (30%), Language (30%). Score 0-15.",
    "高考英语": "你是高考英语阅卷老师。按内容（10分）、语言（10分）、组织（5分）批改，总分25分。用中文给出详细批改意见。"
}

RESPONSE_FORMAT = """
Return ONLY valid JSON (no markdown, no extra text):
{
  "overall_score": "7.5/10",
  "dimensions": [
    {"name": "Grammar", "score": 8.0, "max": 10, "comment": "..."},
    {"name": "Vocabulary", "score": 7.0, "max": 10, "comment": "..."},
    {"name": "Coherence", "score": 7.5, "max": 10, "comment": "..."},
    {"name": "Content", "score": 8.0, "max": 10, "comment": "..."}
  ],
  "corrections": [
    {"original": "exact phrase", "corrected": "corrected version", "explanation": "why"}
  ],
  "strengths": "What the student did well...",
  "improvements": "Key areas to improve...",
  "encouragement": "Warm closing message..."
}"""

def grade_essay(essay_text: str, essay_type: str) -> dict:
    system_prompt = GRADING_PROMPTS.get(essay_type, GRADING_PROMPTS["通用写作 (General)"])
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt + "\n\n" + RESPONSE_FORMAT},
                {"role": "user", "content": f"Please grade this essay:\n\n{essay_text}"}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_feedback": raw}
    except Exception as e:
        return {"error": str(e)}

st.title("✍️ 智能写作批改 (AI Writing Grader)")
st.markdown("输入英语作文，AI 批改老师将给出详细评分和修改建议。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 作文输入")
    essay_type = st.selectbox("选择考试类型", list(GRADING_PROMPTS.keys()))
    age_level = st.select_slider("学生英语水平",
        options=["A0 启蒙", "A1 初级", "A2 中级", "B1 进阶", "B2 高级"],
        value="A1 初级")
    essay_input = st.text_area("在此粘贴或输入作文：", height=380,
        placeholder="My favorite animal is a dog. I have a dog. His name is Mochi...")
    word_count = len(essay_input.split()) if essay_input.strip() else 0
    st.caption(f"字数：{word_count} 词　　🤖 批改引擎：DeepSeek V3")
    btn_submit = st.button("🚀 开始批改", type="primary",
        use_container_width=True, disabled=(word_count < 10))
    if 0 < word_count < 10:
        st.caption("⚠️ 请至少输入 10 个单词")

with col2:
    st.subheader("📊 批改报告")
    if btn_submit and essay_input.strip():
        with st.spinner("🖊️ AI 老师批改中..."):
            result = grade_essay(essay_input, essay_type)

        if "error" in result:
            st.error(f"批改失败：{result['error']}")
        elif "raw_feedback" in result:
            st.warning("收到反馈：")
            st.write(result["raw_feedback"])
        else:
            st.success(f"✅ 批改完成！总分：**{result.get('overall_score', 'N/A')}**")
            dims = result.get("dimensions", [])
            if dims:
                cols = st.columns(len(dims))
                for i, dim in enumerate(dims):
                    cols[i].metric(dim.get("name", ""), f"{dim.get('score')}/{dim.get('max')}")
            st.divider()
            corrections = result.get("corrections", [])
            if corrections:
                st.markdown("### 🔴 具体修改")
                for i, c in enumerate(corrections, 1):
                    with st.expander(f"{i}. {c.get('original', '')[:40]}", expanded=(i <= 2)):
                        st.markdown(f"> **原文：** *{c.get('original', '')}*")
                        st.markdown(f"> **修改：** *{c.get('corrected', '')}*")
                        st.info(c.get("explanation", ""))
            if result.get("strengths"):
                st.markdown("### 🌟 做得好的地方")
                st.success(result["strengths"])
            if result.get("improvements"):
                st.markdown("### 📈 改进方向")
                st.warning(result["improvements"])
            if result.get("encouragement"):
                st.markdown("### 💬 老师寄语")
                st.markdown(f"*{result['encouragement']}*")
            if dims:
                st.divider()
                st.markdown("### 📋 分项点评")
                for dim in dims:
                    with st.expander(f"{dim.get('name')} — {dim.get('score')}/{dim.get('max')}"):
                        st.write(dim.get("comment", ""))
    elif btn_submit:
        st.warning("⚠️ 请先输入作文内容！")
    else:
        st.info("👈 在左侧输入作文，点击批改按钮开始。")
        st.markdown("""
**支持批改类型：** 通用写作 / 雅思 / 托福 / 四六级 / 高考

**AI 会给你：**
- 分项评分（语法/词汇/逻辑/内容）
- 逐句具体修改建议
- 优点 + 改进方向 + 鼓励语
        """)
