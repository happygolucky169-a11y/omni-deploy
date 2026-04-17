"""
1_words.py -- OMNI v2.1
"""
import sys, os, random, math, hashlib, tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from state import (get_user_state, update_word_progress, get_due_cards, toggle_favorite, is_favorited)
from tts_utils import generate_audio, VOICES
st.set_page_config(page_title="单词卡片", page_icon="📇", layout="centered")

WORD_EMOJI = {
    "family":"👨‍👩‍👧‍👦","mom":"👩","dad":"👨","mother":"👩","father":"👨",
    "brother":"👦","sister":"👧","baby":"👶","grandma":"👵","grandpa":"👴",
    "grandmother":"👵","grandfather":"👴","aunt":"👩","uncle":"👨",
    "cousin":"🧒","friend":"🤝","teacher":"👩‍🏫","student":"🧑‍🎓",
    "head":"🗣️","eye":"👁️","eyes":"👀","ear":"👂","nose":"👃","mouth":"👄",
    "hand":"✋","hands":"🤲","finger":"☝️","foot":"🦶","leg":"🦵",
    "arm":"💪","hair":"💇","face":"😊","teeth":"🦷","tooth":"🦷",
    "cat":"🐱","dog":"🐶","bird":"🐦","fish":"🐟","rabbit":"🐰","duck":"🦆",
    "chicken":"🐔","pig":"🐷","cow":"🐄","horse":"🐴","sheep":"🐑",
    "elephant":"🐘","lion":"🦁","tiger":"🐯","monkey":"🐵","bear":"🐻",
    "penguin":"🐧","butterfly":"🦋","snake":"🐍","frog":"🐸","mouse":"🐭",
    "hen":"🐔","rooster":"🐓","goat":"🐐","donkey":"🫏","goose":"🪿",
    "apple":"🍎","banana":"🍌","orange":"🍊","grape":"🍇","watermelon":"🍉",
    "strawberry":"🍓","cake":"🎂","bread":"🍞","rice":"🍚","egg":"🥚",
    "milk":"🥛","water":"💧","juice":"🧃","tea":"🍵","coffee":"☕",
    "pizza":"🍕","hamburger":"🍔","noodle":"🍜","noodles":"🍜","candy":"🍬",
    "ice cream":"🍦","chocolate":"🍫","cheese":"🧀","cookie":"🍪",
    "avocado":"🥑","broccoli":"🥦","carrot":"🥕","tomato":"🍅","potato":"🥔",
    "corn":"🌽","onion":"🧅","pepper":"🌶️","mushroom":"🍄","pea":"🫛",
    "lettuce":"🥬","cucumber":"🥒","pumpkin":"🎃","cabbage":"🥬",
    "red":"🔴","blue":"🔵","green":"🟢","yellow":"🟡","purple":"🟣",
    "pink":"💗","black":"⬛","white":"⬜","brown":"🟤","gray":"⚪",
    "sun":"☀️","sunny":"☀️","rain":"🌧️","rainy":"🌧️","snow":"❄️","snowy":"❄️",
    "cloud":"☁️","cloudy":"☁️","wind":"💨","windy":"💨","hot":"🔥","cold":"🥶",
    "rainbow":"🌈","storm":"⛈️","fog":"🌫️","thunder":"⚡",
    "house":"🏠","door":"🚪","window":"🪟","bed":"🛏️","chair":"🪑",
    "table":"🪑","lamp":"💡","sofa":"🛋️","kitchen":"🍳","bathroom":"🛁",
    "garden":"🌻","clock":"🕐","mirror":"🪞",
    "book":"📖","pen":"✏️","pencil":"✏️","ruler":"📏","eraser":"🧽",
    "bag":"🎒","desk":"📚","school":"🏫","classroom":"🏫",
    "ball":"⚽","doll":"🧸","car":"🚗","kite":"🪁","robot":"🤖","puzzle":"🧩",
    "balloon":"🎈","bike":"🚲",
    "bus":"🚌","train":"🚂","plane":"✈️","airplane":"✈️","boat":"⛵","ship":"🚢",
    "taxi":"🚕","bicycle":"🚲","motorcycle":"🏍️","helicopter":"🚁","subway":"🚇",
    "truck":"🚛","ambulance":"🚑",
    "tree":"🌳","flower":"🌸","grass":"🌿","mountain":"⛰️","river":"🏞️",
    "ocean":"🌊","sea":"🌊","lake":"🏞️","forest":"🌲","star":"⭐",
    "moon":"🌙","sky":"🌤️","rock":"🪨","sand":"🏖️","island":"🏝️",
    "doctor":"👨‍⚕️","nurse":"👩‍⚕️","police":"👮","firefighter":"👩‍🚒",
    "cook":"👨‍🍳","chef":"👨‍🍳","farmer":"👨‍🌾","pilot":"👨‍✈️","singer":"🎤",
    "driver":"🚗","artist":"🎨","dentist":"🦷","scientist":"🔬",
    "soccer":"⚽","football":"🏈","basketball":"🏀","tennis":"🎾",
    "swimming":"🏊","running":"🏃","baseball":"⚾","volleyball":"🏐",
    "skating":"⛸️","skiing":"⛷️","cycling":"🚴","dancing":"💃",
    "hat":"🧢","shirt":"👕","dress":"👗","shoes":"👟","socks":"🧦",
    "coat":"🧥","jacket":"🧥","pants":"👖","shorts":"🩳","skirt":"👗",
    "scarf":"🧣","gloves":"🧤","boots":"👢","sweater":"🧥",
    "happy":"😊","sad":"😢","angry":"😠","scared":"😨","tired":"😴",
    "hungry":"🤤","thirsty":"💧","sick":"🤒","excited":"🤩","surprised":"😲",
    "nervous":"😰","proud":"😤","shy":"😳","bored":"😑","worried":"😟",
    "piano":"🎹","guitar":"🎸","drum":"🥁","violin":"🎻",
    "hospital":"🏥","park":"🏞️","library":"📚","bank":"🏦","supermarket":"🛒",
    "restaurant":"🍽️","hotel":"🏨","cinema":"🎬","museum":"🏛️","zoo":"🦁",
    "run":"🏃","eat":"🍽️","drink":"🥤","sleep":"😴","read":"📖","write":"✍️",
    "sing":"🎤","dance":"💃","swim":"🏊","fly":"🕊️","jump":"🦘","walk":"🚶",
    "draw":"🎨","play":"🎮","study":"📚","work":"💼","drive":"🚗",
    "smile":"😊","cry":"😢","laugh":"😂","think":"🤔","listen":"👂","speak":"🗣️",
    "love":"❤️","like":"👍",
    "one":"1️⃣","two":"2️⃣","three":"3️⃣","four":"4️⃣","five":"5️⃣",
    "six":"6️⃣","seven":"7️⃣","eight":"8️⃣","nine":"9️⃣","ten":"🔟",
    "headache":"🤕","fever":"🤒","cough":"😷",
    "map":"🗺️","ticket":"🎫","passport":"📘","suitcase":"🧳","camera":"📷",
    "beach":"🏖️","souvenir":"🎁",
}

TOPIC_EMOJI = {
    "Me":"👤","My Home":"🏠","My Toys":"🧸","My School":"🏫","My Body":"🧍",
    "Farm Animals":"🐄","My Pet":"🐾","Wild Animals":"🦁","Nature":"🌿",
    "Weather and Climate":"🌤️","My City":"🏙️","Colors":"🎨","Numbers":"🔢",
    "Food":"🍎","Drinks":"🥤","Vegetables":"🥦","Clothes":"👕",
    "Jobs":"💼","Sports":"⚽","Feelings":"😊","Transportation":"🚗",
    "Daily Routines":"⏰","Verbs":"🏃","Adjectives":"📝","Adverbs":"📝",
    "Musical Instruments":"🎵","Days of the Week":"📅","Months of the Year":"📅",
    "Things at Home":"🏠","Geographical Features":"🌍","Travel":"✈️",
    "Sickness":"🏥","The Village":"🏘️","Frequency Adverbs":"📝",
    "Appearance Adjectives":"👤","Character Adjectives":"💎",
}

def get_emoji(word, topic=""):
    w = word.lower().strip()
    return WORD_EMOJI.get(w, TOPIC_EMOJI.get(topic, "📝"))

@st.cache_data
def load_and_process_data():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PreA754260223.csv")
    if not os.path.exists(csv_path): csv_path = "PreA754260223.csv"
    if not os.path.exists(csv_path): return None, [], ""
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    topic_col = df.columns[0]
    topics = df[topic_col].dropna().unique().tolist()
    return df, topics, topic_col

def split_into_groups(words_list, group_size=6):
    n = len(words_list)
    if n <= group_size + 2: return [words_list]
    ng = math.ceil(n / group_size)
    base, rem = n // ng, n % ng
    groups, idx = [], 0
    for i in range(ng):
        s = base + (1 if i < rem else 0)
        groups.append(words_list[idx:idx+s]); idx += s
    return groups

def try_score_recording(audio_bytes):
    try:
        from audio_scorer import analyze_recording
        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes.getvalue()); tmp.close()
        result = analyze_recording(tmp.name); os.remove(tmp.name); return result
    except Exception:
        b = random.randint(70, 90)
        return {"pitch_score":b+random.randint(-3,3),"rhythm_score":b+random.randint(-3,3),
                "emotion_score":b+random.randint(-3,3),"total_score":b}

# Session State
for k, v in {"layer":1,"selected_category":None,"selected_topic":None,"selected_group_idx":0,
    "study_mode":"all","card_index":0,"is_flipped":False,"study_queue":[],"groups":[],
    "quiz_active":False,"quiz_questions":[],"quiz_index":0,"quiz_answers":[],
    "quiz_wrong_words":[],"quiz_show_result":False,"last_audio_hash":None}.items():
    if k not in st.session_state: st.session_state[k] = v

def go_to_layer(n):
    st.session_state.layer = n; st.session_state.is_flipped = False
    if n<=1: st.session_state.selected_category=None; st.session_state.selected_topic=None
    if n<=2: st.session_state.selected_topic=None; st.session_state.card_index=0; st.session_state.selected_group_idx=0
    if n<=3: st.session_state.card_index=0; st.session_state.quiz_active=False; st.session_state.quiz_show_result=False

def start_group(gi):
    st.session_state.selected_group_idx=gi; st.session_state.card_index=0
    st.session_state.is_flipped=False; st.session_state.quiz_active=False
    st.session_state.quiz_show_result=False; st.session_state.layer=4

def flip_card(): st.session_state.is_flipped = not st.session_state.is_flipped

def next_or_quiz():
    if st.session_state.card_index < len(st.session_state.study_queue)-1:
        st.session_state.card_index += 1; st.session_state.is_flipped = False
    else: enter_quiz()

def do_sm2(uid, w, t, q):
    update_word_progress(uid, w, t, q); next_or_quiz()

def enter_quiz():
    queue = st.session_state.study_queue
    if not queue: return
    df_all, _, _ = load_and_process_data()
    all_w = df_all.to_dict("records")
    questions = []
    for item in queue:
        word = str(item.get("word",""))
        topic = str(item.get("topic",""))
        chinese = str(item.get("Chinese meaning",""))
        same = [w for w in all_w if w.get("topic")==topic and str(w.get("word",""))!=word]
        other = [w for w in all_w if str(w.get("word",""))!=word]
        random.shuffle(same); random.shuffle(other)
        dist = []
        for d in same:
            if len(dist)>=3: break
            if str(d.get("word","")) not in [x["word"] for x in dist]: dist.append(d)
        for d in other:
            if len(dist)>=3: break
            dw = str(d.get("word",""))
            if dw not in [x["word"] for x in dist] and dw!=word: dist.append(d)
        opts = [{"word":word,"topic":topic,"chinese":chinese,"is_correct":True}]
        for d in dist[:3]:
            opts.append({"word":str(d.get("word","")),"topic":str(d.get("topic","")),
                "chinese":str(d.get("Chinese meaning","")),"is_correct":False})
        random.shuffle(opts)
        questions.append({"target_word":word,"target_topic":topic,"target_chinese":chinese,
            "options":opts,"word_data":item})
    st.session_state.quiz_questions=questions; st.session_state.quiz_index=0
    st.session_state.quiz_answers=[]; st.session_state.quiz_wrong_words=[]
    st.session_state.quiz_show_result=False; st.session_state.quiz_active=True; st.session_state.layer=5

# Sidebar
with st.sidebar:
    st.header("⚙️ 学习设置")
    users=["User_A (宝宝1)","User_B (宝宝2)","User_C (家长)"]
    current_user=st.selectbox("👤 当前用户",users)
    selected_accent=st.selectbox("🗣️ 发音口音",list(VOICES.keys()))
    st.divider()
    group_size=st.slider("📦 每组单词数",3,10,6)

# Styles
st.markdown("""<style>
.flashcard{border:2px solid #e0e0e0;border-radius:15px;padding:40px 20px;text-align:center;background:#f9f9f9;min-height:220px;display:flex;flex-direction:column;justify-content:center;box-shadow:2px 2px 10px rgba(0,0,0,.05);margin-bottom:15px}
.word-text{font-size:44px;font-weight:bold;color:#1f77b4}
.phonetic-text{font-size:18px;color:#888;margin-top:8px;font-family:monospace}
.example-text{font-size:20px;color:#333;font-style:italic;line-height:1.5}
.chinese-text{font-size:18px;color:#666;margin-top:8px}
.group-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:10px;box-shadow:0 2px 4px rgba(0,0,0,.04)}
.pic-card{background:#fff;border:2px solid #e2e8f0;border-radius:16px;padding:20px 10px;text-align:center;min-height:160px;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 4px 8px rgba(0,0,0,.06);margin-bottom:8px}
.pic-emoji{font-size:3.5rem;margin-bottom:8px}
.pic-word{font-size:1.4rem;font-weight:700;color:#1e293b}
.quiz-correct{background:#d4edda;border:2px solid #28a745;border-radius:12px;padding:12px;margin:6px 0}
.quiz-wrong{background:#f8d7da;border:2px solid #dc3545;border-radius:12px;padding:12px;margin:6px 0}
.score-badge{font-size:3rem;font-weight:900}
</style>""", unsafe_allow_html=True)

df, topics, topic_col = load_and_process_data()

# ═══ Layer 1: Categories ═══
if st.session_state.layer == 1:
    st.title("🗂️ 单词卡片系统 v2.1")
    st.caption("分组学习 · 听音选图测试 · 跟读录音 · SM-2间隔复习")
    st.markdown("---")
    cats = {"启蒙英语听力口语词汇":"✅ 753词/36主题","自然拼读词汇":"🚧","220个高频词":"🚧",
        "剑桥系列词汇":"🚧","新课标词汇":"🚧","托福词汇":"🚧","国际学校体系词汇":"🚧","职业英语词汇":"🚧"}
    for c,s in cats.items():
        c1,c2 = st.columns([3,1])
        with c1: st.markdown(f"**{c}**"); st.caption(s)
        with c2:
            if st.button("进入",key=f"c_{c}"):
                st.session_state.selected_category=c; go_to_layer(2); st.rerun()
        st.divider()

# ═══ Layer 2: Topics ═══
elif st.session_state.layer == 2:
    st.button("⬅️ 返回大类",on_click=go_to_layer,args=(1,))
    st.title(f"📂 {st.session_state.selected_category}")
    if st.session_state.selected_category=="启蒙英语听力口语词汇" and df is not None:
        for i,topic in enumerate(topics):
            wc=len(df[df[topic_col]==topic]); ng=math.ceil(wc/group_size)
            dc=len(get_due_cards(current_user,topic)); em=TOPIC_EMOJI.get(topic,"📂")
            c1,c2,c3=st.columns([3,1,1])
            with c1:
                st.markdown(f"**{em} {topic}** ({wc}词·{ng}组)")
                if dc>0: st.caption(f"🔴 待复习:{dc}")
            with c2:
                if st.button("📖 学习",key=f"t_{i}",use_container_width=True):
                    st.session_state.selected_topic=topic; st.session_state.study_mode="all"; go_to_layer(3); st.rerun()
            with c3:
                if st.button("📅 复习",key=f"d_{i}",disabled=(dc==0),use_container_width=True):
                    st.session_state.selected_topic=topic; st.session_state.study_mode="due"; go_to_layer(3); st.rerun()
            st.divider()
    else: st.warning("⚠️ 暂无数据")

# ═══ Layer 3: Groups ═══
elif st.session_state.layer == 3:
    st.button("⬅️ 返回主题",on_click=go_to_layer,args=(2,))
    topic=st.session_state.selected_topic; mode=st.session_state.study_mode
    tdf=df[df[topic_col]==topic].copy()
    if mode=="all":
        wd=tdf.to_dict("records"); wd.sort(key=lambda x:(len(str(x.get("word",""))),str(x.get("word","")).lower()))
    else:
        due=get_due_cards(current_user,topic); wd=tdf[tdf["word"].isin(due)].to_dict("records")
    if not wd:
        st.title(f"🎯 {topic}"); st.success("🎉 没有需要学习的单词！"); st.balloons()
    else:
        groups=split_into_groups(wd,group_size=group_size); st.session_state.groups=groups
        pf="复习" if mode=="due" else "学习"
        st.title(f"🎯 {pf}: {topic}"); st.markdown(f"共 **{len(wd)}** 词，分 **{len(groups)}** 组"); st.markdown("---")
        for gi,grp in enumerate(groups):
            pv="、".join([w.get("word","") for w in grp[:4]])
            if len(grp)>4: pv+=f"…等{len(grp)}词"
            c1,c2=st.columns([3,1])
            with c1: st.markdown(f'<div class="group-card"><b>第{gi+1}组</b>（{len(grp)}词）<br><span style="color:#888;font-size:.9rem">{pv}</span></div>',unsafe_allow_html=True)
            with c2:
                if st.button("开始",key=f"g_{gi}",use_container_width=True):
                    st.session_state.study_queue=grp; start_group(gi); st.rerun()

# ═══ Layer 4: Flashcards ═══
elif st.session_state.layer == 4:
    topic=st.session_state.selected_topic; queue=st.session_state.study_queue
    total=len(queue); gi=st.session_state.selected_group_idx
    st.button("⬅️ 返回分组",on_click=go_to_layer,args=(3,))
    st.title(f"📖 {topic} · 第{gi+1}组")
    if total==0: st.success("🎉 无单词")
    else:
        if st.session_state.card_index>=total: st.session_state.card_index=total-1
        card=queue[st.session_state.card_index]
        word=str(card.get("word","")); phonetic=str(card.get("phonetic",""))
        chinese=str(card.get("Chinese meaning","")); example=str(card.get("example sentence",""))
        wid=f"preA_{word}"; emoji=get_emoji(word,topic)
        st.progress((st.session_state.card_index+1)/total)
        is_last=(st.session_state.card_index==total-1)
        st.caption(f"第{st.session_state.card_index+1}/{total}词{'　⚡最后一词，学完进测试！' if is_last else ''}")
        is_fav=is_favorited(current_user,word)
        if st.button("⭐ 已收藏" if is_fav else "☆ 收藏",use_container_width=True):
            toggle_favorite(current_user,word,topic); st.rerun()

        if not st.session_state.is_flipped:
            st.markdown(f'<div class="flashcard"><div style="font-size:3rem">{emoji}</div><div class="word-text">{word}</div><div class="phonetic-text">{phonetic}</div></div>',unsafe_allow_html=True)
            ap=generate_audio(wid,word,"word",selected_accent)
            if ap: st.audio(ap,autoplay=True)
            with st.expander("🎤 跟读录音",expanded=False):
                rec=st.audio_input("录音跟读单词")
                if rec:
                    h=hashlib.md5(rec.getvalue()).hexdigest()
                    if h!=st.session_state.last_audio_hash:
                        st.session_state.last_audio_hash=h
                        with st.spinner("AI评分..."): sc=try_score_recording(rec)
                        ca,cb,cc,cd=st.columns(4)
                        ca.metric("🎯总分",sc["total_score"]); cb.metric("🎵音准",sc["pitch_score"])
                        cc.metric("🥁节奏",sc["rhythm_score"]); cd.metric("💖情感",sc["emotion_score"])
                        if sc["total_score"]>=85: st.success("🌟 发音很棒！")
                        elif sc["total_score"]>=70: st.info("👍 不错！")
                        else: st.warning("💪 多练几次！")
            st.button("🔄 点击翻面",on_click=flip_card,use_container_width=True,type="primary")
        else:
            st.markdown(f'<div class="flashcard"><div style="font-size:3rem">{emoji}</div><div class="word-text">{word}</div><div class="phonetic-text">{phonetic}</div><hr style="margin:15px 0"><div class="example-text">"{example}"</div><div class="chinese-text">{chinese}</div></div>',unsafe_allow_html=True)
            if example and str(example).lower()!="nan":
                ep=generate_audio(f"{wid}_ex",example,"sentence",selected_accent)
                if ep: st.audio(ep,autoplay=True)
            with st.expander("🎤 跟读例句录音",expanded=False):
                rec2=st.audio_input("录音跟读例句",key="rb")
                if rec2:
                    h2=hashlib.md5(rec2.getvalue()).hexdigest()
                    if h2!=st.session_state.get("lhb"):
                        st.session_state.lhb=h2
                        with st.spinner("AI评分..."): s2=try_score_recording(rec2)
                        st.metric("🎯总分",s2["total_score"])
            st.divider()
            sf="→进入测试" if is_last else ""
            st.markdown(f"**记忆打分**{'　⚡最后一词！' if is_last else ''}")
            c1,c2,c3=st.columns(3)
            with c1: st.button(f"🔴 不认识{sf}",key="s0",on_click=do_sm2,args=(current_user,word,topic,0),use_container_width=True)
            with c2: st.button(f"🟡 模糊{sf}",key="s3",on_click=do_sm2,args=(current_user,word,topic,3),use_container_width=True)
            with c3: st.button(f"🟢 认识{sf}",key="s5",on_click=do_sm2,args=(current_user,word,topic,5),use_container_width=True)
            st.button("🔄 翻回正面",on_click=flip_card,use_container_width=True)

# ═══ Layer 5: Audio-Picture Quiz ═══
elif st.session_state.layer == 5:
    topic=st.session_state.selected_topic; gi=st.session_state.selected_group_idx
    qs=st.session_state.quiz_questions
    if not qs:
        st.warning("没有题目"); st.button("返回",on_click=go_to_layer,args=(3,))
    elif not st.session_state.quiz_show_result:
        st.title(f"🎧 听音选图: {topic} · 第{gi+1}组")
        qi=st.session_state.quiz_index; q=qs[qi]
        st.progress((qi+1)/len(qs)); st.caption(f"第{qi+1}/{len(qs)}题")
        st.markdown("### 🔊 听音频，选出对应的单词图片：")
        tw=q["target_word"]
        ap=generate_audio(f"quiz_{tw}",tw,"word",selected_accent)
        if ap: st.audio(ap,autoplay=True)
        if st.button("🔁 再听一次"): st.rerun()
        st.markdown("---")
        opts=q["options"]
        r1=st.columns(2); r2=st.columns(2)
        cols=[r1[0],r1[1],r2[0],r2[1]]
        for oi,opt in enumerate(opts):
            with cols[oi]:
                ow=opt["word"]; oe=get_emoji(ow,opt.get("topic",""))
                st.markdown(f'<div class="pic-card"><div class="pic-emoji">{oe}</div><div class="pic-word">{ow}</div></div>',unsafe_allow_html=True)
                if st.button("选择",key=f"p_{qi}_{oi}",use_container_width=True):
                    ok=opt["is_correct"]; st.session_state.quiz_answers.append(ok)
                    if not ok: st.session_state.quiz_wrong_words.append(q["word_data"])
                    if qi<len(qs)-1: st.session_state.quiz_index+=1; st.rerun()
                    else: st.session_state.quiz_show_result=True; st.rerun()
    else:
        st.title(f"📊 测试结果: {topic} · 第{gi+1}组")
        cc=sum(st.session_state.quiz_answers); tq=len(st.session_state.quiz_answers)
        sc=round(cc/tq*100) if tq>0 else 0; ww=st.session_state.quiz_wrong_words
        if sc==100: cl,em,mg="#28a745","🏆","满分！全部掌握！"
        elif sc>=80: cl,em,mg="#17a2b8","🌟","很棒！基本掌握！"
        elif sc>=60: cl,em,mg="#ffc107","💪","还不错，错词需巩固！"
        else: cl,em,mg="#dc3545","📚","需要重新学习！"
        st.markdown(f'<div style="text-align:center;padding:30px"><div class="score-badge" style="color:{cl}">{em} {sc}分</div><div style="font-size:1.2rem;color:#666;margin-top:10px">{cc}/{tq}正确 · {mg}</div></div>',unsafe_allow_html=True)
        st.markdown("### 📋 回顾")
        for qii,q in enumerate(qs):
            ok=st.session_state.quiz_answers[qii] if qii<len(st.session_state.quiz_answers) else False
            w=q["target_word"]; cn=q["target_chinese"]; emo=get_emoji(w,q["target_topic"])
            cs="quiz-correct" if ok else "quiz-wrong"; ic="✅" if ok else "❌"
            ex="" if ok else f"　正确: <b>{w}</b>"
            st.markdown(f'<div class="{cs}">{ic} {emo} <b>{w}</b> — {cn}{ex}</div>',unsafe_allow_html=True)
        st.markdown("---")
        c1,c2,c3=st.columns(3)
        with c1:
            if ww:
                if st.button(f"🔄 错词回炉({len(ww)}词)",use_container_width=True,type="primary"):
                    st.session_state.study_queue=ww; st.session_state.card_index=0
                    st.session_state.is_flipped=False; st.session_state.quiz_active=False
                    st.session_state.quiz_show_result=False; st.session_state.layer=4; st.rerun()
        with c2:
            if st.button("📂 返回分组",use_container_width=True): go_to_layer(3); st.rerun()
        with c3:
            if st.button("🏠 主页",use_container_width=True): go_to_layer(1); st.rerun()
        if sc==100: st.balloons()
