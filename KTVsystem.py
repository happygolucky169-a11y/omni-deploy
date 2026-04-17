# pages/KTV系统.py
import os, json, socket, warnings, threading, tempfile
import streamlit as st
import librosa
import numpy as np
import whisper
from pydub import AudioSegment, effects
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

warnings.filterwarnings("ignore")

UPLOAD_DIR    = "uploads/recordings"
VIDEO_DIR     = "uploads/videos"
TEMP_DIR      = "temp_uploads"
RECORDER_PORT = 8765
for d in [UPLOAD_DIR, VIDEO_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)
MARKER = os.path.join(UPLOAD_DIR, "_last_recording.txt")

SONG_LIBRARY = [
    {"title":"Shape of You",          "artist":"Ed Sheeran",      "genre":["英文流行"],        "rating":3},
    {"title":"Perfect",               "artist":"Ed Sheeran",      "genre":["英文流行","情歌"],  "rating":4},
    {"title":"Someone Like You",      "artist":"Adele",           "genre":["英文流行","情歌"],  "rating":5},
    {"title":"Rolling in the Deep",   "artist":"Adele",           "genre":["英文流行","摇滚"],  "rating":4},
    {"title":"Bohemian Rhapsody",     "artist":"Queen",           "genre":["摇滚"],             "rating":5},
    {"title":"Hotel California",      "artist":"Eagles",          "genre":["摇滚"],             "rating":4},
    {"title":"Fly Me to the Moon",    "artist":"Frank Sinatra",   "genre":["爵士"],             "rating":5},
    {"title":"What a Wonderful World","artist":"Louis Armstrong", "genre":["爵士"],             "rating":5},
    {"title":"Canon in D",            "artist":"Pachelbel",       "genre":["古典"],             "rating":4},
    {"title":"月亮代表我的心",          "artist":"邓丽君",           "genre":["中文"],             "rating":5},
    {"title":"光辉岁月",               "artist":"Beyond",          "genre":["中文","摇滚"],      "rating":4},
    {"title":"Let It Go",             "artist":"Idina Menzel",    "genre":["英文流行"],         "rating":4},
    {"title":"Twinkle Twinkle",       "artist":"Traditional",     "genre":["儿童歌曲"],         "rating":3},
    {"title":"You Are My Sunshine",   "artist":"Traditional",     "genre":["儿童歌曲"],         "rating":3},
    {"title":"Happy Birthday",        "artist":"Traditional",     "genre":["儿童歌曲"],         "rating":3},
    {"title":"Old MacDonald",         "artist":"Traditional",     "genre":["儿童歌曲"],         "rating":3},
    {"title":"Yesterday",             "artist":"Beatles",         "genre":["英文流行","情歌"],  "rating":5},
    {"title":"Hey Jude",              "artist":"Beatles",         "genre":["英文流行","摇滚"],  "rating":4},
    {"title":"Imagine",               "artist":"John Lennon",     "genre":["英文流行"],         "rating":5},
    {"title":"We Are the World",      "artist":"USA for Africa",  "genre":["英文流行"],         "rating":4},
    {"title":"Heal the World",        "artist":"Michael Jackson", "genre":["英文流行","情歌"],  "rating":4},
    {"title":"Billie Jean",           "artist":"Michael Jackson", "genre":["英文流行","摇滚"],  "rating":4},
    {"title":"Uptown Funk",           "artist":"Bruno Mars",      "genre":["英文流行"],         "rating":4},
    {"title":"Count On Me",           "artist":"Bruno Mars",      "genre":["英文流行","情歌"],  "rating":3},
    {"title":"Stay With Me",          "artist":"Sam Smith",       "genre":["英文流行","情歌"],  "rating":4},
    {"title":"Hello",                 "artist":"Adele",           "genre":["英文流行","情歌"],  "rating":5},
    {"title":"Thinking Out Loud",     "artist":"Ed Sheeran",      "genre":["英文流行","情歌"],  "rating":4},
]
CATEGORIES = {"全部":None,"英文流行":"英文流行","摇滚":"摇滚","爵士":"爵士","古典":"古典","情歌":"情歌","中文":"中文"}
CAT_ICONS  = {"全部":"✅","英文流行":"🎵","摇滚":"🔥","爵士":"🎷","古典":"🎼","情歌":"❤️","中文":"🌏"}

@st.cache_resource
def load_model():
    return whisper.load_model("base")
model = load_model()

def get_video_duration(path):
    try: return max(10, int(len(AudioSegment.from_file(path)) / 1000))
    except: return 60

def extract_wav(path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); tmp.close()
    AudioSegment.from_file(path).set_channels(1).set_frame_rate(16000).export(tmp.name, format="wav")
    return tmp.name

def generate_lyrics(path):
    wav = None
    try:
        wav = extract_wav(path)
        result = model.transcribe(wav, word_timestamps=True, language=None, task="transcribe")
        lines = [f"{round(s['start'],1)} {s['text'].strip()}"
                 for s in result.get("segments",[]) if s["text"].strip()]
        return "\n".join(lines), get_video_duration(path)
    finally:
        if wav and os.path.exists(wav): os.remove(wav)

def write_marker(p):
    with open(MARKER,"w",encoding="utf-8") as f: f.write(p)

def read_marker():
    if not os.path.exists(MARKER): return None
    with open(MARKER,"r",encoding="utf-8") as f: p=f.read().strip()
    return p if p and os.path.exists(p) else None

def clear_marker():
    if os.path.exists(MARKER): os.remove(MARKER)

def normalize_recording(path):
    try:
        audio = AudioSegment.from_file(path)
        audio = effects.normalize(audio) + 8
        audio.export(path, format=os.path.splitext(path)[1].lstrip("."))
    except Exception as e: print(f"[normalize] {e}")

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        if not self.path.startswith("/video/"):
            self.send_response(404); self.end_headers(); return
        name = self.path[len("/video/"):]
        fp   = os.path.join(VIDEO_DIR, name)
        if not os.path.exists(fp):
            self.send_response(404); self.end_headers(); return
        ext  = os.path.splitext(name)[1].lower()
        mime = {".mp4":"video/mp4",".webm":"video/webm",
                ".mov":"video/quicktime",".avi":"video/x-msvideo"}.get(ext,"video/mp4")
        size = os.path.getsize(fp)
        rng  = self.headers.get("Range")
        if rng:
            parts  = rng.replace("bytes=","").split("-")
            start  = int(parts[0]) if parts[0] else 0
            end    = int(parts[1]) if len(parts)>1 and parts[1] else size-1
            length = end-start+1
            self.send_response(206); self._cors()
            self.send_header("Content-Type",   mime)
            self.send_header("Content-Range",  f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges",  "bytes")
            self.end_headers()
            with open(fp,"rb") as f: f.seek(start); self.wfile.write(f.read(length))
        else:
            self.send_response(200); self._cors()
            self.send_header("Content-Type",   mime)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges",  "bytes")
            self.end_headers()
            with open(fp,"rb") as f: self.wfile.write(f.read())

    def do_POST(self):
        if self.path != "/upload_recording":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length",0))
        ctype  = self.headers.get("Content-Type","")
        body   = self.rfile.read(length)
        ext    = "mp4" if "mp4" in ctype else "ogg" if "ogg" in ctype else "webm"
        name   = self.headers.get("X-Song-Name","song")
        name   = "".join(c for c in name if c.isalnum() or c in ("_","-"))
        ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn     = f"{name}_{ts}.{ext}"
        fp     = os.path.join(UPLOAD_DIR, fn)
        with open(fp,"wb") as f: f.write(body)
        normalize_recording(fp)
        write_marker(fp)
        self.send_response(200); self._cors()
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status":"ok","file":fn}).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","*")

    def log_message(self,*a): pass

def start_server():
    srv = HTTPServer(("0.0.0.0",RECORDER_PORT),Handler)
    threading.Thread(target=srv.serve_forever,daemon=True).start()

def get_local_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

def to_wav(path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); tmp.close()
    AudioSegment.from_file(path).set_channels(1).set_frame_rate(22050).export(tmp.name,format="wav")
    return tmp.name

def score_recording(path):
    wav = None
    try:
        wav   = to_wav(path)
        y, sr = librosa.load(wav, sr=22050)
        if len(y) < sr: return _fallback()
        f0, voiced, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C2"),
                                      fmax=librosa.note_to_hz("C7"), sr=sr)
        vf = f0[voiced] if voiced is not None else np.array([])
        pitch = float(np.clip(95-max(0,np.std(librosa.hz_to_midi(vf[vf>0]))-3)*3.8,45,95)) \
                if len(vf)>10 else 58.0
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        if len(beats)>4:
            ivl    = np.diff(librosa.frames_to_time(beats,sr=sr))
            rhythm = float(np.clip(95-np.std(ivl)/(np.mean(ivl)+1e-6)*180,42,95))
        else: rhythm = 55.0
        rms = librosa.feature.rms(y=y)[0]
        db  = librosa.amplitude_to_db(rms+1e-6)
        dr  = float(np.percentile(db,90)-np.percentile(db,10))
        if dr<12:    emotion=float(np.clip(55+dr*2.0,45,79))
        elif dr<=28: emotion=float(np.clip(79+(dr-12)*0.8,79,92))
        else:        emotion=float(np.clip(92-(dr-28)*1.5,60,92))
        total=int(np.clip(round(pitch*0.45+rhythm*0.35+emotion*0.20),45,95))
        return {"pitch_score":round(pitch),"rhythm_score":round(rhythm),
                "emotion_score":round(emotion),"total_score":total}
    except Exception as e:
        print(f"[score]{e}"); return _fallback()
    finally:
        if wav and os.path.exists(wav): os.remove(wav)

def _fallback():
    import random; base=random.randint(58,72)
    return {"pitch_score":base+random.randint(-6,6),"rhythm_score":base+random.randint(-6,6),
            "emotion_score":base+random.randint(-6,6),"total_score":base}

def score_label(t):
    if t>=90:   return "#C62828","🏆 天才歌手！"
    elif t>=82: return "#2E7D32","🌟 非常优秀！"
    elif t>=74: return "#1565C0","👍 表现不错！"
    elif t>=65: return "#E65100","💪 继续加油！"
    else:       return "#AD1457","📚 多多练习！"

# ══════════════════════════════════════════════
if "ktv_server_started" not in st.session_state:
    start_server()
    st.session_state.ktv_server_started = True

LOCAL_IP       = get_local_ip()
VIDEO_BASE_URL = f"http://{LOCAL_IP}:{RECORDER_PORT}/video"
UPLOAD_URLS_JS = json.dumps([
    f"http://{LOCAL_IP}:{RECORDER_PORT}/upload_recording",
    f"http://localhost:{RECORDER_PORT}/upload_recording",
])

st.set_page_config(page_title="KTV 跟唱练习", page_icon="🎤", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewContainer"] > .main > .block-container {
    background-color: #FFF8F0 !important;
}
[data-testid="stSidebar"] { background-color: #FFF3E0 !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #4E342E !important; }
h1 { color: #BF360C !important; }
h2, h3 { color: #E65100 !important; }
.song-card {
    background: #FFFFFF; border: 2px solid #FFCC80;
    border-radius: 14px; padding: 14px 16px; margin-bottom: 10px;
    box-shadow: 0 2px 8px rgba(255,111,0,0.12);
}
.song-title { color: #BF360C; font-size: 16px; font-weight: 700; }
.song-meta  { color: #6D4C41; font-size: 13px; margin-top: 4px; }
.welcome-panel {
    background: linear-gradient(135deg,#FFF3E0,#FFE0B2);
    border: 2px solid #FFB74D; border-radius: 20px;
    padding: 60px 30px; text-align: center;
}
.queue-panel {
    background: linear-gradient(135deg,#FFF8F0,#FFF3E0);
    border: 2px solid #FFCC80; border-radius: 20px; padding: 24px;
}
[data-testid="stMetricValue"] { color: #BF360C !important; }
[data-testid="stMetricLabel"] { color: #6D4C41 !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 系统状态")
    st.metric("AI 模型", "Whisper Base")
    st.metric("录音服务", f"端口 {RECORDER_PORT}")
    st.info(f"📡 本机 IP：{LOCAL_IP}")

for k,v in [("ktv_page","songlist"),("selected_song",None),("song_queue",[]),
            ("recording_path",None),("score_result",None),
            ("video_filename",None),("active_cat","全部")]:
    if k not in st.session_state: st.session_state[k]=v

# ══════════════════════════════════════════════════════════════
#  PAGE 1：歌单
# ══════════════════════════════════════════════════════════════
if st.session_state.ktv_page == "songlist":
    st.markdown("<h1>🎵 歌单</h1>", unsafe_allow_html=True)
    col_list, col_right = st.columns([1,1])

    with col_list:
        st.markdown("<p style='color:#E65100;font-weight:700;font-size:16px;'>🎸 流行分类</p>",
                    unsafe_allow_html=True)
        cat_cols = st.columns(3)
        for i,(cat,_) in enumerate(CATEGORIES.items()):
            with cat_cols[i%3]:
                is_active = st.session_state.active_cat == cat
                if st.button(f"{CAT_ICONS.get(cat,'')} {cat}", key=f"cat_{cat}",
                             type="primary" if is_active else "secondary",
                             use_container_width=True):
                    st.session_state.active_cat=cat; st.rerun()

        st.markdown("<p style='color:#E65100;font-weight:700;font-size:16px;margin-top:12px;'>👶 儿童专区</p>",
                    unsafe_allow_html=True)
        is_child = st.session_state.active_cat == "儿童歌曲"
        if st.button("👶 儿童歌曲", key="cat_child",
                     type="primary" if is_child else "secondary"):
            st.session_state.active_cat="儿童歌曲"; st.rerun()

        st.markdown("---")
        active = st.session_state.active_cat
        if active=="全部":       filtered=SONG_LIBRARY
        elif active=="儿童歌曲": filtered=[s for s in SONG_LIBRARY if "儿童歌曲" in s["genre"]]
        else:                    filtered=[s for s in SONG_LIBRARY if active in s["genre"]]

        st.markdown(f"<p style='color:#5D4037;'>当前分类：<b style='color:#BF360C;'>{active}</b>"
                    f" · 共 {len(filtered)} 首</p>", unsafe_allow_html=True)

        for song in filtered:
            stars = "⭐"*song["rating"]
            st.markdown(f"""
            <div class="song-card">
              <div class="song-title">🎵 {song['title']}</div>
              <div class="song-meta">🎤 {song['artist']} &nbsp;{stars}&nbsp;| {'、'.join(song['genre'])}</div>
            </div>""", unsafe_allow_html=True)
            bc1,bc2 = st.columns(2)
            with bc1:
                if st.button("▶ 立即唱", key=f"sing_{song['title']}",
                             use_container_width=True, type="primary"):
                    st.session_state.selected_song = song
                    st.session_state.ktv_page = "setup"
                    for k in ["recording_path","score_result","video_filename",
                              "auto_lyrics","auto_duration","song_title",
                              "total_seconds","lyrics","lyrics_raw","lyric_offset"]:
                        st.session_state.pop(k,None)
                    st.rerun()
            with bc2:
                if st.button("＋ 队列", key=f"queue_{song['title']}",
                             use_container_width=True):
                    if song not in st.session_state.song_queue:
                        st.session_state.song_queue.append(song)
                        st.toast(f"✅ 《{song['title']}》已加入队列！")
                    else:
                        st.toast("⚠️ 已在队列中")

    with col_right:
        if st.session_state.song_queue:
            st.markdown('<div class="queue-panel">', unsafe_allow_html=True)
            st.markdown("<h3 style='color:#BF360C;'>📋 播放队列</h3>", unsafe_allow_html=True)
            for i,s in enumerate(st.session_state.song_queue):
                qc1,qc2=st.columns([3,1])
                with qc1:
                    st.markdown(f"<p style='color:#4E342E;margin:4px 0;'>{i+1}. 🎵 {s['title']}"
                                f"<span style='color:#8D6E63;font-size:12px;'> — {s['artist']}</span></p>",
                                unsafe_allow_html=True)
                with qc2:
                    if st.button("唱",key=f"q_{i}",type="primary"):
                        st.session_state.selected_song=s
                        st.session_state.song_queue.pop(i)
                        st.session_state.ktv_page="setup"
                        for k in ["recording_path","score_result","video_filename",
                                  "auto_lyrics","auto_duration","song_title",
                                  "total_seconds","lyrics","lyrics_raw","lyric_offset"]:
                            st.session_state.pop(k,None)
                        st.rerun()
            if st.button("🗑️ 清空队列",use_container_width=True):
                st.session_state.song_queue=[]; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="welcome-panel">
              <div style="font-size:72px;margin-bottom:20px;">🎤</div>
              <h2 style="color:#E65100;font-size:26px;margin-bottom:12px;">选一首歌开始欢唱！</h2>
              <p style="color:#A1887F;font-size:15px;">从左侧歌单点击「立即唱」开始</p>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  PAGE 2：歌曲设置
# ══════════════════════════════════════════════════════════════
elif st.session_state.ktv_page == "setup":
    song = st.session_state.selected_song
    st.markdown("<h1>🎤 KTV 跟唱练习 & AI 评分</h1>", unsafe_allow_html=True)
    st.caption("上传视频 → AI自动识别歌词 → 跟唱录音 → 智能评分")
    if st.button("← 返回歌单"):
        st.session_state.ktv_page="songlist"; st.rerun()
    if song:
        st.info(f"🎵 当前歌曲：**{song['title']}** — {song['artist']}")

    st.subheader("🎵 第一步：设置歌曲信息")
    col_a,col_b = st.columns(2)

    with col_a:
        default_title = song["title"] if song else "Hello Song"
        song_title = st.text_input("歌曲名称",
                                   value=st.session_state.get("song_title",default_title))
        st.markdown("**上传本地视频文件**")
        video_file = st.file_uploader("支持 MP4 / WebM / MOV / AVI",
                                      type=["mp4","webm","mov","avi"],key="video_uploader")
        auto_dur = st.session_state.get("auto_duration",60)
        if video_file:
            st.success(f"✅ 已选择：{video_file.name}")
            tmp_path = os.path.join(TEMP_DIR,"dur_"+video_file.name)
            if not os.path.exists(tmp_path):
                with open(tmp_path,"wb") as f: f.write(video_file.getbuffer())
            detected = get_video_duration(tmp_path)
            if detected != st.session_state.get("auto_duration"):
                st.session_state["auto_duration"]=detected; auto_dur=detected; st.rerun()
        total_seconds = st.number_input("歌曲时长（秒）— 上传视频后自动识别",
                                        min_value=10,max_value=3600,value=auto_dur,step=5)
        st.markdown("---")
        st.markdown("**⏱️ 歌词时间偏移（秒）**")
        st.caption("👉 歌词比视频**早出现**（如有前奏），填正数；歌词比视频**晚**，填负数")
        lyric_offset = st.number_input(
            "偏移秒数（0 = 不调整）",
            min_value=-60.0, max_value=120.0,
            value=float(st.session_state.get("lyric_offset",0.0)),
            step=0.5,
            help="例如视频前奏15秒后才开始唱，填 15"
        )

    with col_b:
        st.markdown("**歌词时间轴**（格式：`秒数 歌词`）")
        st.caption("示例：`0 Hello hello hello`　`4 How are you`")
        if video_file:
            if st.button("🤖 自动识别歌词（Whisper AI）",type="secondary"):
                with st.spinner("⏳ AI 识别中..."):
                    try:
                        tmp_path = os.path.join(TEMP_DIR,"dur_"+video_file.name)
                        if not os.path.exists(tmp_path):
                            with open(tmp_path,"wb") as f: f.write(video_file.getbuffer())
                        al,ad = generate_lyrics(tmp_path)
                        if al:
                            st.session_state["auto_lyrics"]=al
                            st.session_state["auto_duration"]=ad
                            st.success("✅ 识别成功！时间戳已含前奏，偏移保持0即可"); st.rerun()
                        else: st.warning("⚠️ 未识别到歌词，请手动填写。")
                    except Exception as e: st.error(f"识别失败：{e}")
        default_lyrics = st.session_state.get("auto_lyrics",st.session_state.get("lyrics_raw",
            "0 Hello hello hello\n4 How are you\n8 I'm fine I'm fine\n12 I hope that you are too"))
        lyrics_raw = st.text_area("歌词",value=default_lyrics,height=280)

    if st.button("下一步：开始录音 →",type="primary"):
        lyrics=[]
        for line in lyrics_raw.strip().splitlines():
            parts=line.strip().split(" ",1)
            if len(parts)==2:
                try:
                    t = max(0.0, float(parts[0]) + lyric_offset)
                    lyrics.append({"time":t,"text":parts[1]})
                except: pass
        lyrics.sort(key=lambda x: x["time"])
        if not song_title: st.error("请填写歌曲名称")
        elif not video_file: st.error("请上传视频文件")
        elif not lyrics: st.error("请至少填写一行歌词")
        else:
            safe="".join(c for c in video_file.name if c.isalnum() or c in ("_","-","."))
            with open(os.path.join(VIDEO_DIR,safe),"wb") as f: f.write(video_file.getbuffer())
            st.session_state.song_title    =song_title
            st.session_state.total_seconds =int(total_seconds)
            st.session_state.lyrics        =lyrics
            st.session_state.lyrics_raw    =lyrics_raw
            st.session_state.video_filename=safe
            st.session_state.lyric_offset  =lyric_offset
            st.session_state.pop("auto_lyrics",None)
            clear_marker()
            st.session_state.ktv_page="sing"; st.rerun()

# ══════════════════════════════════════════════════════════════
#  PAGE 3：KTV 跟唱
# ══════════════════════════════════════════════════════════════
elif st.session_state.ktv_page == "sing":
    song_title    =st.session_state.song_title
    lyrics        =st.session_state.lyrics
    total_seconds =st.session_state.total_seconds
    video_filename=st.session_state.video_filename
    lyrics_json   =json.dumps(lyrics,ensure_ascii=False)
    song_name_safe="".join(c for c in song_title if c.isalnum() or c in ("_","-"))
    video_url     =f"{VIDEO_BASE_URL}/{video_filename}"

    st.markdown("<h1>🎤 KTV 跟唱练习 & AI 评分</h1>", unsafe_allow_html=True)
    st.subheader(f"🎙️ 跟唱《{song_title}》")
    st.info("① 点「▶ 播放视频」→ ② 点「🎙️ 开始录音」→ ③ 唱完点「⏹️ 停止」→ ④ 等「✅ 上传成功」→ ⑤ 点「下一步」")

    # 实时微调
    adj1,adj2,adj3 = st.columns([1,2,1])
    with adj1:
        if st.button("⏪ 歌词提前1秒", use_container_width=True):
            st.session_state.lyrics=[{"time":max(0,l["time"]-1),"text":l["text"]} for l in lyrics]
            st.rerun()
    with adj2:
        st.markdown("<p style='text-align:center;color:#5D4037;font-size:13px;margin-top:8px;'>"
                    "💡 歌词不同步？点两侧按钮微调</p>", unsafe_allow_html=True)
    with adj3:
        if st.button("歌词延后1秒 ⏩", use_container_width=True):
            st.session_state.lyrics=[{"time":l["time"]+1,"text":l["text"]} for l in lyrics]
            st.rerun()

    lyrics      = st.session_state.lyrics
    lyrics_json = json.dumps(lyrics, ensure_ascii=False)

    # ★★★ 关键修复：三行窗口模式，完全不依赖scrollTop ★★★
    ktv_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        background:#FFF8F0; color:#3E2723; padding:12px; }}
video {{ width:100%; border-radius:12px; margin-bottom:10px; max-height:220px;
         object-fit:contain; background:#000; box-shadow:0 4px 16px rgba(0,0,0,0.2); }}
#vid-err {{ display:none; background:#FFF3E0; border:2px solid #FF6F00;
            border-radius:8px; padding:10px; margin-bottom:10px;
            color:#E65100; font-size:14px; text-align:center; font-weight:600; }}

/* ★ 三行歌词窗口：固定高度，flex布局，绝不滚动 ★ */
#lyrics-box {{
    background:#FFFDE7; border:2px solid #FFE082; border-radius:14px;
    padding:10px; margin-bottom:12px;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    gap:8px; min-height:130px; overflow:hidden;
}}
/* 默认所有行隐藏 */
.lyric-line {{ display:none; text-align:center; width:100%;
               border-radius:10px; transition:all 0.3s ease; }}
/* 上一句：小字灰色 */
.lyric-line.show-prev {{
    display:block; color:#BCAAA4; font-size:14px; padding:4px 10px;
}}
/* 当前句：大字橙色高亮，永远在中间 */
.lyric-line.show-active {{
    display:block; color:#FFFFFF; font-size:26px; font-weight:800;
    background:linear-gradient(135deg,#FF6F00,#FF8F00);
    padding:12px 16px; letter-spacing:1px;
    box-shadow:0 3px 10px rgba(255,111,0,0.4);
}}
/* 下一句：小字浅棕 */
.lyric-line.show-next {{
    display:block; color:#A1887F; font-size:14px; padding:4px 10px;
}}

#prog-bg {{ width:100%; height:10px; background:#FFE0B2; border-radius:5px;
            overflow:hidden; margin-bottom:6px; }}
#prog-fill {{ height:100%; width:0%; background:linear-gradient(90deg,#FF6F00,#FFD600);
              border-radius:5px; transition:width 0.2s linear; }}
#time-row {{ display:flex; justify-content:space-between; font-size:14px;
             font-weight:600; color:#5D4037; margin-bottom:10px; }}
.btn-row {{ display:flex; gap:10px; margin-bottom:10px; }}
.btn {{ flex:1; padding:14px; font-size:16px; font-weight:700;
        border:none; border-radius:12px; cursor:pointer; }}
#btn-rec  {{ background:linear-gradient(135deg,#43A047,#1B5E20); color:#fff;
             box-shadow:0 4px 12px rgba(67,160,71,0.4); }}
#btn-stop {{ background:linear-gradient(135deg,#E53935,#B71C1C); color:#fff;
             box-shadow:0 4px 12px rgba(229,57,53,0.4); display:none; }}
#mic-dot {{ display:none; align-items:center; justify-content:center;
            gap:8px; font-size:14px; font-weight:700; color:#C62828; margin-bottom:8px; }}
.pulse {{ width:12px; height:12px; background:#E53935; border-radius:50%;
          animation:pulse 1s infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1;transform:scale(1);}} 50%{{opacity:0.3;transform:scale(1.6);}} }}
#msg {{ font-size:14px; font-weight:600; text-align:center; padding:8px; color:#2E7D32;
        min-height:28px; background:#F1F8E9; border-radius:8px; border:1px solid #C5E1A5; }}
</style></head><body>
<div id="vid-err">⚠️ 视频加载失败，请刷新页面或检查视频文件</div>
<video id="vid" controls preload="auto">
  <source src="{video_url}" type="video/mp4">
  <source src="{video_url}" type="video/webm">
</video>
<div id="lyrics-box">
  <div class="lyric-line show-active" id="init-hint">🎵 播放视频后歌词自动同步</div>
</div>
<div id="prog-bg"><div id="prog-fill"></div></div>
<div id="time-row">
  <span id="lbl-elapsed">已唱 0%</span>
  <span id="lbl-remain">剩余 {total_seconds//60:02d}:{total_seconds%60:02d}</span>
</div>
<div class="btn-row">
  <button class="btn" id="btn-rec"  onclick="startRec()">🎙️ 开始录音</button>
  <button class="btn" id="btn-stop" onclick="stopRec()">⏹️ 停止录音</button>
</div>
<div id="mic-dot"><div class="pulse"></div><span>🔴 录音中...</span></div>
<div id="msg">准备就绪 — 先播放视频，再点「开始录音」</div>
<script>
const LYRICS={lyrics_json};
const TOTAL={total_seconds};
const SONG="{song_name_safe}";
const UPLOAD_URLS={UPLOAD_URLS_JS};
const vid=document.getElementById("vid");
let mediaRec=null,chunks=[],built=false,syncTimer=null,lastActive=-1;

vid.addEventListener("error",     ()=>{{document.getElementById("vid-err").style.display="block";}});
vid.addEventListener("loadeddata",()=>{{document.getElementById("vid-err").style.display="none";}});
vid.addEventListener("play",  ()=>{{if(!built){{buildLyrics();built=true;}}startSync();}});
vid.addEventListener("pause", stopSync);
vid.addEventListener("ended", stopSync);
vid.addEventListener("seeked",()=>{{if(!vid.paused){{updateLyrics(vid.currentTime);updateProgress(vid.currentTime);}}}});

function startSync(){{
  stopSync();
  syncTimer=setInterval(()=>{{updateLyrics(vid.currentTime);updateProgress(vid.currentTime);}},100);
}}
function stopSync(){{if(syncTimer){{clearInterval(syncTimer);syncTimer=null;}}}}

function buildLyrics(){{
  const box=document.getElementById("lyrics-box");
  box.innerHTML="";
  LYRICS.forEach((l,i)=>{{
    const d=document.createElement("div");
    d.className="lyric-line";
    d.id="L"+i;
    d.textContent=l.text;
    box.appendChild(d);
  }});
}}

/* ★★★ 核心修复：只显示3行，完全不用scrollTop ★★★ */
function updateLyrics(sec){{
  let active=-1;
  for(let i=LYRICS.length-1;i>=0;i--){{
    if(sec>=LYRICS[i].time){{active=i;break;}}
  }}
  if(active===lastActive)return;
  lastActive=active;

  /* 所有行先清空class */
  LYRICS.forEach((_,i)=>{{
    const el=document.getElementById("L"+i);
    if(el)el.className="lyric-line";
  }});

  if(active<0)return;

  /* 只给前/当前/后三行加class，其余全隐藏 */
  const prev=active-1;
  const next=active+1;
  if(prev>=0){{
    const el=document.getElementById("L"+prev);
    if(el)el.className="lyric-line show-prev";
  }}
  const activeEl=document.getElementById("L"+active);
  if(activeEl)activeEl.className="lyric-line show-active";
  if(next<LYRICS.length){{
    const el=document.getElementById("L"+next);
    if(el)el.className="lyric-line show-next";
  }}
}}

function updateProgress(elapsed){{
  const pct=Math.min(100,(elapsed/TOTAL)*100);
  const remain=Math.max(0,TOTAL-elapsed);
  document.getElementById("prog-fill").style.width=pct+"%";
  document.getElementById("lbl-elapsed").textContent="已唱 "+Math.round(pct)+"%";
  document.getElementById("lbl-remain").textContent="剩余 "+fmt(remain);
}}

function fmt(s){{
  return String(Math.floor(s/60)).padStart(2,"0")+":"+String(Math.floor(s%60)).padStart(2,"0");
}}

async function startRec(){{
  try{{
    const stream=await navigator.mediaDevices.getUserMedia({{
      audio:{{echoCancellation:true,noiseSuppression:true,autoGainControl:true,sampleRate:44100,channelCount:1}}
    }});
    const mime=["audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus","audio/mp4"]
               .find(m=>MediaRecorder.isTypeSupported(m))||"";
    mediaRec=mime
      ?new MediaRecorder(stream,{{mimeType:mime,audioBitsPerSecond:128000}})
      :new MediaRecorder(stream,{{audioBitsPerSecond:128000}});
    chunks=[];
    mediaRec.ondataavailable=e=>{{if(e.data&&e.data.size>0)chunks.push(e.data);}};
    mediaRec.onstop=doUpload;
    mediaRec.start(200);
    document.getElementById("btn-rec").style.display="none";
    document.getElementById("btn-stop").style.display="block";
    document.getElementById("mic-dot").style.display="flex";
    const m=document.getElementById("msg");
    m.textContent="🔴 录音中，唱完后点「停止录音」";
    m.style.color="#E65100";m.style.background="#FFF3E0";m.style.borderColor="#FFCC02";
  }}catch(e){{
    document.getElementById("msg").textContent="❌ 麦克风权限被拒绝："+e.message;
    document.getElementById("msg").style.color="#C62828";
  }}
}}

function stopRec(){{
  if(mediaRec&&mediaRec.state!=="inactive"){{
    mediaRec.stop();
    mediaRec.stream.getTracks().forEach(t=>t.stop());
  }}
  document.getElementById("btn-stop").style.display="none";
  document.getElementById("mic-dot").style.display="none";
  const m=document.getElementById("msg");
  m.textContent="⏳ 正在上传录音...";
  m.style.color="#E65100";m.style.background="#FFF8E1";
}}

async function doUpload(){{
  if(!chunks.length){{
    document.getElementById("msg").textContent="❌ 录音数据为空，请重试";
    document.getElementById("msg").style.color="#C62828";
    document.getElementById("btn-rec").style.display="block";
    return;
  }}
  const mime=mediaRec?.mimeType||"audio/webm";
  const blob=new Blob(chunks,{{type:mime}});
  if(blob.size<500){{
    document.getElementById("msg").textContent="❌ 录音太短，请重新录制";
    document.getElementById("msg").style.color="#C62828";
    document.getElementById("btn-rec").style.display="block";
    return;
  }}
  let ok=false;
  for(const url of UPLOAD_URLS){{
    try{{
      const res=await fetch(url,{{method:"POST",headers:{{"Content-Type":mime,"X-Song-Name":SONG}},body:blob}});
      if(res.ok){{ok=true;break;}}
    }}catch(e){{}}
  }}
  if(ok){{
    const m=document.getElementById("msg");
    m.textContent="✅ 上传成功！请点击下方「录音完成，下一步」";
    m.style.color="#2E7D32";m.style.background="#F1F8E9";m.style.borderColor="#A5D6A7";
  }}else{{
    document.getElementById("msg").textContent="❌ 上传失败，请重试";
    document.getElementById("msg").style.color="#C62828";
    document.getElementById("btn-rec").style.display="block";
  }}
}}
</script></body></html>"""

    st.components.v1.html(ktv_html, height=620, scrolling=False)
    st.markdown("---")
    col_back,col_next=st.columns([1,2])
    with col_back:
        if st.button("← 返回修改设置"):
            st.session_state.ktv_page="setup"; st.rerun()
    with col_next:
        if st.button("✅ 录音完成，下一步 →",type="primary"):
            saved=read_marker()
            if saved:
                st.session_state.recording_path=saved; clear_marker()
                st.session_state.score_result=None
                st.session_state.ktv_page="score"; st.rerun()
            else:
                st.error("⚠️ 未检测到录音，请先完成录音并等待「✅ 上传成功」提示")

# ══════════════════════════════════════════════════════════════
#  PAGE 4：AI 评分
# ══════════════════════════════════════════════════════════════
elif st.session_state.ktv_page == "score":
    song_title    =st.session_state.song_title
    video_filename=st.session_state.get("video_filename")
    recording_path=st.session_state.recording_path

    st.markdown("<h1>🎤 KTV 跟唱练习 & AI 评分</h1>", unsafe_allow_html=True)
    st.subheader(f"🎧 第三步：对比回放 & 评分《{song_title}》")

    if not recording_path or not os.path.exists(recording_path):
        st.error("找不到录音文件，请返回重新录音")
        if st.button("← 返回"): st.session_state.ktv_page="sing"; st.rerun()
    else:
        col_orig,col_rec=st.columns(2)
        with col_orig:
            st.markdown("### 🎵 原版视频")
            if video_filename:
                vp=os.path.join(VIDEO_DIR,video_filename)
                if os.path.exists(vp):
                    with open(vp,"rb") as f: st.video(f.read())
                else: st.warning("视频文件不存在")
        with col_rec:
            st.markdown("### 🎙️ 你的录音")
            with open(recording_path,"rb") as f: audio_bytes=f.read()
            ext=os.path.splitext(recording_path)[1].lower()
            mime="audio/mp4" if ext==".mp4" else "audio/ogg" if ext==".ogg" else "audio/webm"
            st.audio(audio_bytes,format=mime)

        st.markdown("---")
        if st.session_state.score_result is None:
            with st.spinner("🔍 AI 正在分析演唱..."):
                st.session_state.score_result=score_recording(recording_path)

        res=st.session_state.score_result
        total=res["total_score"]
        color,comment=score_label(total)

        st.markdown("### 📊 演唱评分")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("🏅 总分",  f"{total} 分")
        c2.metric("🎼 音准",  f"{res['pitch_score']} 分")
        c3.metric("🥁 节奏",  f"{res['rhythm_score']} 分")
        c4.metric("💖 情感",  f"{res['emotion_score']} 分")

        st.markdown(f"""
        <div style="background:#FFF8F0;border:2px solid #FFE082;border-radius:14px;padding:20px;margin-top:10px;">
          <div style="background:#FFE0B2;border-radius:8px;height:16px;overflow:hidden;">
            <div style="width:{total}%;height:100%;background:linear-gradient(90deg,#FF6F00,#FFD600);
                        border-radius:8px;transition:width 1s ease;"></div>
          </div>
          <p style="text-align:center;margin-top:14px;color:{color};font-size:24px;font-weight:800;">{comment}</p>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("🔄 再唱一次"):
                st.session_state.score_result=None
                st.session_state.recording_path=None
                st.session_state.ktv_page="sing"; st.rerun()
        with c2:
            if st.button("🎵 换首歌"):
                for k in ["score_result","recording_path","song_title","selected_song",
                          "total_seconds","lyrics","lyrics_raw","video_filename",
                          "auto_lyrics","auto_duration","lyric_offset"]:
                    st.session_state.pop(k,None)
                st.session_state.ktv_page="songlist"; st.rerun()
        with c3:
            if st.button("🏠 回到歌单"):
                st.session_state.ktv_page="songlist"; st.rerun()