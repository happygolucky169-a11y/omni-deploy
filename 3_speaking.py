import streamlit as st
import uuid
import hashlib
import tempfile
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tts_utils import generate_audio, VOICES
from openai import OpenAI
import whisper

st.set_page_config(page_title="口语练习", page_icon="💬", layout="centered")
st.title("💬 自由对话模式")
st.markdown("随便聊聊！AI 会陪你练习口语。")

@st.cache_resource
def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        st.error("❌ 请在项目根目录新建 .env 文件，写入 DEEPSEEK_API_KEY=sk-你的key")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

client = get_deepseek_client()
whisper_model = load_whisper_model()

SYSTEM_PROMPT = """You are an encouraging English speaking coach for children aged 3-12.
- Keep responses SHORT (2-3 sentences max) and age-appropriate
- Gently correct grammar by naturally using the correct form in your reply
- Ask ONE simple follow-up question to keep conversation going
- Be warm, patient, encouraging like a kind foreign friend
Never explicitly mention grammar mistakes."""

with st.sidebar:
    st.header("⚙️ 设置")
    accent_options = list(VOICES.keys())
    selected_accent = st.selectbox("🗣️ AI 发音口音", accent_options, index=0)
    age_group = st.selectbox("👤 孩子年龄段",
        ["3-6岁 (启蒙)", "7-9岁 (初级)", "10-12岁 (中级)"], index=1)
    if st.button("🗑️ 清空对话"):
        st.session_state.chat_messages = []
        st.session_state.last_processed_audio_hash = None
        st.rerun()
    st.divider()
    st.caption("🤖 LLM: DeepSeek V3")
    st.caption("🔊 TTS: Edge TTS（免费）")
    st.caption("🎧 STT: Whisper（本地免费）")

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "last_processed_audio_hash" not in st.session_state:
    st.session_state.last_processed_audio_hash = None

def transcribe_audio(audio_bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes.getvalue())
        tmp_path = tmp.name
    try:
        result = whisper_model.transcribe(tmp_path, language="en")
        return result["text"].strip()
    except Exception as e:
        st.error(f"语音识别失败: {e}")
        return ""
    finally:
        os.remove(tmp_path)

def get_ai_reply(user_text: str, age_group: str) -> str:
    age_hint = f"\nStudent age group: {age_group}. Adjust vocabulary accordingly."
    history = st.session_state.chat_messages[-20:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT + age_hint}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_text})
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=120,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI 回复失败: {e}")
        return "That's great! Can you tell me more?"

for msg in st.session_state.chat_messages:
    avatar = "🧒" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "assistant" and msg.get("audio_path"):
            st.audio(msg["audio_path"], autoplay=False)
        st.write(msg["content"])

user_audio_bytes = st.audio_input("🎤 点击开始录音")

if user_audio_bytes:
    current_audio_hash = hashlib.md5(user_audio_bytes.getvalue()).hexdigest()
    if current_audio_hash != st.session_state.last_processed_audio_hash:
        st.session_state.last_processed_audio_hash = current_audio_hash
        with st.spinner("🎧 识别语音中..."):
            user_text = transcribe_audio(user_audio_bytes)
        if not user_text:
            st.warning("未能识别，请重试。")
            st.stop()
        st.session_state.chat_messages.append({"role": "user", "content": user_text})
        with st.chat_message("user", avatar="🧒"):
            st.write(user_text)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("AI 思考中..."):
                ai_text = get_ai_reply(user_text, age_group)
                msg_id = f"chat_{uuid.uuid4().hex[:8]}"
                audio_path = generate_audio(msg_id, ai_text, "sentence", selected_accent)
            if audio_path:
                st.audio(audio_path, autoplay=True)
            st.write(ai_text)
            st.session_state.chat_messages.append({
                "role": "assistant", "content": ai_text, "audio_path": audio_path})

with st.expander("⌨️ 文字输入（测试模式）"):
    text_input = st.text_input("直接输入文字对话")
    if st.button("发送") and text_input:
        st.session_state.chat_messages.append({"role": "user", "content": text_input})
        ai_text = get_ai_reply(text_input, age_group)
        msg_id = f"chat_{uuid.uuid4().hex[:8]}"
        audio_path = generate_audio(msg_id, ai_text, "sentence", selected_accent)
        st.session_state.chat_messages.append({
            "role": "assistant", "content": ai_text, "audio_path": audio_path})
        st.rerun()
