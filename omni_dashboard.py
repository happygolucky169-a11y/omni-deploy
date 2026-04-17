"""
OMNI-LEARN OS — 全功能主控面板 v5.0
omni_dashboard.py

✅ 所有听力题（含词汇题中的音频题）全部显示 TTS 播放按钮，听力维度自动播放
✅ 图片类选项：snake_case 转可读中文+emoji，无歧义
✅ IRT 答案判断修复（稳定键，彻底消除 qnum 偏移 bug）
✅ 口语/写作不参与 IRT 测试，结果不记录、不展示
✅ 默认路径改为 omni_data（脚本同目录）
✅ 字号全面放大
✅ ContentMatcher 调用签名全部修正
✅ 学习目标新增"剑桥系列考试""国际学校"两项

依赖：user_profile.py  content_matcher.py
运行：streamlit run omni_dashboard.py
"""

import json, math, os, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="OMNI-LEARN OS", page_icon="🦉",
                   layout="wide", initial_sidebar_state="expanded")
sys.path.insert(0, str(Path(__file__).parent))

try:
    from user_profile import (ProfileManager, ExplorationTracker, get_stage,
        get_scaffold_hint, level_to_cefr, SKILL_CN, SKILL_ICONS, SKILLS)
    _UP_OK = True
except ImportError as e:
    _UP_OK = False; _UP_ERR = str(e)

try:
    from content_matcher import ContentMatcher
    _CM_OK = True
except ImportError:
    _CM_OK = False

# ══════════════════════════════════════════════════════
# CSS（字号放大）
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
html,body,[class*="css"]{font-size:17px !important;}
[data-testid="stSidebar"]{background:#1E1B4B;}
[data-testid="stSidebar"] *{color:#E0E7FF !important;}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"],
[data-testid="stSidebar"] .stAlert *{color:#1F2937 !important;}
[data-testid="stSidebar"] .stButton>button{
  background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);
  border-radius:8px;margin-bottom:4px;font-size:1rem !important;}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,255,255,.18);}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#7C3AED;border-color:#7C3AED;}
.omni-card{background:white;border-radius:12px;padding:18px;margin-bottom:10px;
  box-shadow:0 1px 6px rgba(0,0,0,.08);border-left:4px solid #7C3AED;}
.level-chip{display:inline-block;padding:3px 12px;border-radius:20px;
  font-weight:700;background:#7C3AED;color:white;font-size:1rem;}
.stage-bar{background:linear-gradient(90deg,#7C3AED,#06B6D4);border-radius:8px;
  padding:12px 18px;color:white;margin-bottom:18px;font-size:1.05rem;}
.stat-card{background:white;border-radius:12px;padding:18px;
  border:1px solid #E5E7EB;text-align:center;}
.stat-num{font-size:2.2rem;font-weight:900;color:#0F4C81;}
.stat-label{font-size:.9rem;color:#6B7280;margin-top:4px;}
.task-card{background:#F0F9FF;border-radius:10px;padding:14px 16px;
  margin-bottom:8px;border-left:3px solid #0284C7;font-size:1rem;}
.skill-badge{display:inline-block;padding:3px 12px;border-radius:20px;
  font-size:.9rem;background:#EDE9FE;color:#5B21B6;margin-right:5px;}
.q-box{background:#F8F7FF;border-radius:14px;padding:26px 30px;
  border:2px solid #EDE9FE;margin-bottom:18px;}
.audio-box{background:#EFF6FF;border-left:4px solid #3B82F6;border-radius:10px;
  padding:16px 18px;margin:12px 0;font-size:1.1rem;line-height:1.9;font-style:italic;}
.reading-box{background:#F0FDF4;border-left:4px solid #22C55E;border-radius:10px;
  padding:16px 18px;margin:12px 0;font-size:1.1rem;line-height:1.9;}
div[data-testid="stRadio"] label{font-size:1.1rem !important;}
div[data-testid="stRadio"] label p{font-size:1.1rem !important;}
footer{visibility:hidden;}#MainMenu{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# Session State
# ══════════════════════════════════════════════════════
_DEF = {
    "portal": "login",
    "data_dir":      str(Path(__file__).parent / "omni_data"),
    "library_dir":   r"D:\v5mama",
    "current_user": None,
    "mode": "home",
    "daily_cards": None, "daily_date": "",
    "exp_strategy": "balanced", "exp_entry": None,
    "exp_results": [], "exp_search": "",
    "t_page": "home", "t_class": None,
    "p_page": "home", "parent_name": "",
    "a_page": "students",
    "q_step": 0, "q_data": {}, "q_filler": "parent",
    # IRT
    "irt_theta": 0.0, "irt_responses": [], "irt_used": [],
    "irt_wrong": 0, "irt_qnum": 0,
    "irt_item": None, "irt_answered": False, "irt_dim_scores": {},
    "irt_last_ok": False, "irt_last_ci": 0, "irt_last_opts": [],
    "placement_phase": "q", "placement_prior": None, "placement_result": None,
}
for _k, _v in _DEF.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ══════════════════════════════════════════════════════
# 缓存
# ══════════════════════════════════════════════════════
@st.cache_resource
def _pm(d):  return ProfileManager(data_dir=d) if _UP_OK else None
@st.cache_resource
def _mat(d): return ContentMatcher(library_dir=d) if _CM_OK else None
@st.cache_resource
def _cm(d):  return _ClassMgr(d)

TIERS = {"basic":"Basic（基础版）","pro":"Pro（全库版）","family":"Family（家庭版）",
         "teacher":"Teacher（教师版）","admin":"Admin（超级管理员）"}

# ══════════════════════════════════════════════════════
# 班级管理器
# ══════════════════════════════════════════════════════
class _ClassMgr:
    def __init__(self, d):
        self._dir=Path(d); self._dir.mkdir(parents=True,exist_ok=True)
        self._f=self._dir/"classes.json"; self._d=self._load()
    def _load(self):
        if self._f.exists():
            try:
                with open(self._f,encoding="utf-8") as f: return json.load(f)
            except: pass
        return {"classes":{},"parent_links":{}}
    def _save(self):
        with open(self._f,"w",encoding="utf-8") as f: json.dump(self._d,f,ensure_ascii=False,indent=2)
    def all(self): return list(self._d["classes"].values())
    def get(self,cid): return self._d["classes"].get(cid)
    def create(self,name,grade,teacher,goal=""):
        cid=f"cls_{int(time.time())}"
        obj={"class_id":cid,"name":name,"grade":grade,"teacher":teacher,"goal":goal,
             "created_at":datetime.now().strftime("%Y-%m-%d"),"students":[],"tasks":[],"textbook":""}
        self._d["classes"][cid]=obj; self._save(); return obj
    def update(self,cid,**kw):
        if cid in self._d["classes"]: self._d["classes"][cid].update(kw); self._save()
    def delete(self,cid): self._d["classes"].pop(cid,None); self._save()
    def add_student(self,cid,nick):
        c=self._d["classes"].get(cid)
        if c and nick not in c["students"]: c["students"].append(nick); self._save(); return True
        return False
    def rm_student(self,cid,nick):
        c=self._d["classes"].get(cid)
        if c and nick in c["students"]: c["students"].remove(nick); self._save()
    def assign_task(self,cid,task):
        c=self._d["classes"].get(cid)
        if c:
            task.update({"assigned_at":datetime.now().strftime("%Y-%m-%d %H:%M"),
                         "task_id":f"task_{int(time.time())}"})
            c["tasks"].append(task); c["tasks"]=c["tasks"][-50:]; self._save()
    def link_parent(self,pname,child):
        ch=self._d.setdefault("parent_links",{}).setdefault(pname,[])
        if child not in ch: ch.append(child); self._save()
    def children(self,pname): return self._d.get("parent_links",{}).get(pname,[])

# ══════════════════════════════════════════════════════
# IRT 数学
# ══════════════════════════════════════════════════════
def _p3pl(θ,a,b,c=0.25): return c+(1-c)/(1+math.exp(-a*(θ-b)))
def _lv2θ(lv): return (lv-13)/5.0
def _θ2lv(θ): return max(1,min(100,round(θ*5+13)))
def _fisher(θ,a,b,c=0.25):
    p=_p3pl(θ,a,b,c); q=1-p
    if p<=c or q<=0: return 0.0
    return (a**2*(p-c)**2*q)/(p*(1-c)**2)
def _mle(θ,responses):
    for _ in range(30):
        g=h=0.0
        for item,ok in responses:
            irt=item.get("irt",{}); a=irt.get("a",1.0); b=irt.get("b",0.0); c=irt.get("c",0.25)
            p=_p3pl(θ,a,b,c); q=1-p
            if p<=0 or q<=0: continue
            u=1 if ok else 0
            g+=a*(p-c)*(u-p)/(p*(1-c)); h-=a**2*(p-c)**2*q/(p**2*(1-c)**2)
        if abs(h)<1e-8: break
        d=g/h; θ=max(-4.5,min(4.5,θ-d))
        if abs(d)<0.0005: break
    return θ
def _se(responses,θ):
    ti=sum(_fisher(θ,it.get("irt",{}).get("a",1.0),it.get("irt",{}).get("b",0.0),
                    it.get("irt",{}).get("c",0.25)) for it,_ in responses)
    return 1.0/math.sqrt(ti) if ti>0.001 else 99.0

# ══════════════════════════════════════════════════════
# 题库
# ══════════════════════════════════════════════════════
_IRT_FILES = [
    "omni_irt_itembank_L1_L5_v2.json","omni_irt_itembank_L6_L10.json",
    "omni_irt_itembank_L11_L15.json","omni_irt_itembank_L16_L20.json",
    "omni_irt_itembank_L21_L25.json",
]
_DIM_W  = {"vocabulary":0.35,"listening":0.30,"reading":0.25,"grammar":0.10}
_DIM_CN = {"vocabulary":"词汇","listening":"听力","reading":"阅读","grammar":"语法"}
_DIM_IC = {"vocabulary":"📝","listening":"🎧","reading":"📖","grammar":"📐"}
MAX_Q=15; MIN_Q=8; SE_THR=0.42

@st.cache_resource
def _load_bank(ibd,dd):
    cands=[]
    if ibd and ibd.strip(): cands.append(ibd.strip())
    if dd: cands+=[os.path.join(dd,"item_banks"),dd]
    cands.append(str(Path(__file__).parent))
    for d in cands:
        if not os.path.isdir(d): continue
        items=[]
        for fn in _IRT_FILES:
            fp=os.path.join(d,fn)
            if os.path.exists(fp):
                try:
                    with open(fp,encoding="utf-8") as f: items.extend(json.load(f).get("items",[]))
                except: pass
        if items: return items,d
    return [],""

def _pick_item(items,θ,used_ids,wrong=0):
    role="confirm" if wrong>=2 else "primary"; tgt=_θ2lv(θ)
    pool=[it for it in items if it["item_id"] not in used_ids
          and it.get("role","primary")==role and abs(it.get("level",0)-tgt)<=4]
    if not pool: pool=[it for it in items if it["item_id"] not in used_ids and it.get("role","primary")==role]
    if not pool: pool=[it for it in items if it["item_id"] not in used_ids]
    if not pool: return None
    return max(pool,key=lambda it:_fisher(θ,it.get("irt",{}).get("a",1.0),
                                           it.get("irt",{}).get("b",0.0),
                                           it.get("irt",{}).get("c",0.25))
                                 *_DIM_W.get(it.get("dimension","vocabulary"),0.25))

def _irt_reset():
    for k,v in [("irt_responses",[]),("irt_used",[]),("irt_item",None),("irt_dim_scores",{}),
                ("irt_last_ok",False),("irt_last_ci",0),("irt_last_opts",[])]:
        st.session_state[k]=v
    for k,v in [("irt_theta",0.0),("irt_wrong",0),("irt_qnum",0),("irt_answered",False)]:
        st.session_state[k]=v

# ══════════════════════════════════════════════════════
# 选项文字 & 图片描述
# ══════════════════════════════════════════════════════
_W2CN = {
    "girl":"女孩","boy":"男孩","man":"男士","woman":"女士","child":"孩子",
    "woke":"醒来","up":"起床","late":"起晚了","early":"早起",
    "missed":"错过了","caught":"赶上了",
    "bus":"公共汽车","train":"火车","car":"汽车","bike":"自行车","walk":"步行",
    "school":"学校","park":"公园","home":"家","library":"图书馆",
    "football":"踢足球","swim":"游泳","read":"看书","sleep":"睡觉",
    "tv":"看电视","eat":"吃饭","cook":"做饭","play":"玩耍",
    "happy":"开心的","sad":"伤心的","angry":"生气的","tired":"疲惫的",
    "dog":"小狗","cat":"小猫","bird":"小鸟","fish":"小鱼",
    "often":"经常","always":"总是","never":"从不","together":"和朋友一起",
    "not":"没有","and":"并且","then":"然后","walked":"步行去了",
    # L16-L25 扩展
    "old":"旧的","new":"新的","built":"建成","still":"仍在","now":"现在",
    "before":"之前","after":"之后","next":"旁边","there":"那里",
    "shopping":"购物","centre":"中心","bridge":"桥","bridges":"桥",
    "chair":"椅子","coat":"外套","door":"门","window":"窗户","floor":"地板",
    "empty":"空的","longer":"更长","shorter":"更短","wider":"更宽","same":"一样",
    "morning":"早上","evening":"傍晚","outside":"室外","inside":"室内",
    "packed":"打包好","packing":"正在打包","unpacking":"正在拆包",
    "suitcase":"行李箱","ready":"准备好","put":"放置","took":"拿走",
    "piano":"钢琴","friends":"朋友们","looking":"看着","through":"穿过",
    "reading":"看书","reads":"看书","watching":"看着","on":"上面","off":"离开","out":"外面",
    "length":"长度",
}
_W2EMOJI = {
    "girl":"👧","boy":"👦","man":"👨","woman":"👩","child":"🧒",
    "bus":"🚌","train":"🚂","car":"🚗","bike":"🚲","walk":"🚶",
    "school":"🏫","park":"🌳","home":"🏠","library":"📚",
    "football":"⚽","swim":"🏊","read":"📖","sleep":"😴",
    "tv":"📺","eat":"🍽️","cook":"👨‍🍳","play":"🎮",
    "happy":"😊","sad":"😢","angry":"😠","tired":"😴",
    "dog":"🐕","cat":"🐱","bird":"🐦","fish":"🐟",
    "missed":"❌","caught":"✅","late":"🕗","early":"🌅",
    "together":"🤝",
    # L16-L25 扩展
    "old":"🏚️","new":"🆕","built":"🏗️","shopping":"🛒","centre":"🏬",
    "bridge":"🌉","chair":"🪑","coat":"🧥","door":"🚪","window":"🪟","floor":"🏠",
    "empty":"⬜","morning":"🌅","evening":"🌇","outside":"🌳","inside":"🏠",
    "packed":"🧳","packing":"🧳","unpacking":"📦","suitcase":"🧳","ready":"✅",
    "piano":"🎹","friends":"👫","watching":"👀","reading":"📖","reads":"📖",
}

def _prettify(s: str) -> str:
    if not s or " " in s: return s
    words = re.split(r"[_\-]", s.lower())
    words = [w for w in words if w not in ("a","the","an","of","in","at","to","is","was")]
    icon = next((_W2EMOJI[w] for w in words if w in _W2EMOJI), "🖼️")
    cn   = "，".join(_W2CN.get(w,w) for w in words if w in _W2CN)
    return f"{icon} {cn}" if cn else f"{icon} {s}"

def _opt_text(opt) -> str:
    if isinstance(opt,str): return opt
    t=opt.get("type","")
    if t in ("text_zh","text"): return opt.get("content","")
    if t=="picture": return _prettify(opt.get("content",opt.get("id","")))
    return opt.get("content",opt.get("text_zh",str(opt)))

def _letter2idx(letter,options) -> int:
    letter=str(letter).strip().upper()
    for i,o in enumerate(options):
        if isinstance(o,dict) and o.get("id","").upper()==letter: return i
    return "ABCD".index(letter) if letter in "ABCD" else 0

# ══════════════════════════════════════════════════════
# TTS — 浏览器 Web Speech API
# ══════════════════════════════════════════════════════
def _tts(text: str, uid: str, autoplay: bool = False):
    """
    渲染播放按钮。autoplay=True 时随页面加载自动朗读。
    uid 必须全局唯一，用 item_id 的哈希即可。
    """
    safe = text.replace("'","\\'").replace('"','\\"').replace("\n"," ").replace("\r","")
    auto = f"setTimeout(triggerTTS_{uid},350);" if autoplay else ""
    html = f"""
<div style="margin:8px 0;">
<button id="btn{uid}" onclick="triggerTTS_{uid}()"
  style="background:#2563EB;color:white;border:none;padding:11px 22px;
  border-radius:10px;font-size:1rem;cursor:pointer;">
  🔊 点击播放音频
</button></div>
<script>
function triggerTTS_{uid}(){{
  window.speechSynthesis.cancel();
  var u=new SpeechSynthesisUtterance('{safe}');
  u.lang='en-US';u.rate=0.75;u.pitch=1.0;
  var b=document.getElementById('btn{uid}');
  if(b){{b.innerHTML='⏸ 播放中...';b.style.background='#1D4ED8';}}
  u.onend=function(){{if(b){{b.innerHTML='🔊 再听一遍';b.style.background='#2563EB';}}}};
  window.speechSynthesis.speak(u);
}}
{auto}
</script>"""
    components.html(html, height=60)

# ══════════════════════════════════════════════════════
# IRT 题目渲染
# ══════════════════════════════════════════════════════
def _run_irt(pm) -> Optional[dict]:
    ibd=""
    dd=st.session_state.get("data_dir","")
    items,found=_load_bank(ibd,dd)
    if not items:
        searched=[]
        if ibd: searched.append(ibd)
        if dd: searched+=[os.path.join(dd,"item_banks"),dd]
        searched.append(str(Path(__file__).parent))
        st.error("❌ 未找到题库文件")
        st.markdown("**系统已搜索以下目录：**")
        for p in searched: st.markdown(f"- `{p}`")
        st.markdown("请将题库 JSON 放到上述任意目录中。")
        st.code("\n".join(_IRT_FILES))
        return None

    θ        = st.session_state.irt_theta
    responses= st.session_state.irt_responses
    used_ids = set(st.session_state.irt_used)
    qnum     = st.session_state.irt_qnum
    wrong    = st.session_state.irt_wrong

    def _stop():
        if qnum>=MAX_Q: return True
        if qnum>=MIN_Q and _se(responses,θ)<SE_THR: return True
        return False

    if _stop(): return _calc(θ,responses)

    if st.session_state.irt_item is None:
        item=_pick_item(items,θ,used_ids,wrong)
        if item is None:
            st.warning("题库题目已全部作答，测试提前结束。")
            return _calc(θ,responses)
        st.session_state.irt_item=item; st.session_state.irt_answered=False

    item=st.session_state.irt_item
    st.progress(min(qnum/MAX_Q,1.0), text=f"第 {qnum+1} 题（共约 {MAX_Q} 题）")

    if not st.session_state.irt_answered:
        _show_q(item,qnum)
    else:
        _show_fb(item)
    return None


def _show_q(item, qnum):
    dim      = item.get("dimension","vocabulary")
    level    = item.get("level",0)
    instr_zh = item.get("instruction_zh","请选择正确答案")
    instr_en = item.get("instruction_en","")
    q_zh     = item.get("question_zh","")
    options  = item.get("options",[])
    audio    = item.get("audio_content","")
    stimulus = item.get("stimulus_text","")

    # 维度标签
    st.markdown(f"""
<div style="display:flex;gap:8px;align-items:center;margin-bottom:14px;">
  <span style="background:#EDE9FE;color:#7C3AED;padding:4px 12px;border-radius:20px;
    font-size:.95rem;font-weight:700;">{_DIM_IC.get(dim,"📄")} {_DIM_CN.get(dim,dim)}</span>
  <span style="background:#F3F4F6;color:#6B7280;padding:4px 10px;border-radius:20px;
    font-size:.88rem;">L{level}</span>
</div>""", unsafe_allow_html=True)

    st.markdown(f"<p style='font-size:1.2rem;font-weight:700;margin-bottom:6px;'>{instr_zh}</p>",
                unsafe_allow_html=True)
    if instr_en: st.caption(instr_en)

    # ✅ 所有含 audio_content 的题都显示音频；听力维度自动播放
    if audio:
        st.markdown(f'<div class="audio-box">🔊 {audio}</div>', unsafe_allow_html=True)
        _tts(audio, f"q{abs(hash(item['item_id']))%9999999}", autoplay=(dim=="listening"))

    # 阅读语篇
    if stimulus:
        st.markdown(f'<div class="reading-box">{stimulus}</div>', unsafe_allow_html=True)

    if q_zh:
        st.markdown(f"<p style='font-size:1.15rem;font-weight:700;margin:10px 0;'>{q_zh}</p>",
                    unsafe_allow_html=True)

    if not options:
        st.error("⚠️ 题目选项数据缺失"); return

    opt_texts = [_opt_text(o) for o in options]
    sel = st.radio("选择答案", range(len(opt_texts)),
                   format_func=lambda i: f"{'ABCD'[i]}.  {opt_texts[i]}",
                   label_visibility="collapsed",
                   key=f"irt_r_{item['item_id']}_{qnum}")

    if st.button("✅ 确认答案", type="primary", use_container_width=True,
                 key=f"irt_c_{item['item_id']}_{qnum}"):
        correct_letter = str(item.get("correct","A")).strip().upper()
        correct_idx    = _letter2idx(correct_letter, options)
        is_ok          = (sel==correct_idx)

        # 更新 IRT 状态
        st.session_state.irt_responses.append((item,is_ok))
        st.session_state.irt_dim_scores.setdefault(dim,[]).append(1 if is_ok else 0)
        st.session_state.irt_theta  = _mle(st.session_state.irt_theta, st.session_state.irt_responses)
        st.session_state.irt_wrong  = 0 if is_ok else st.session_state.irt_wrong+1
        st.session_state.irt_used.append(item["item_id"])
        st.session_state.irt_qnum  += 1

        # ✅ 稳定键存储，不受 qnum 偏移影响
        st.session_state.irt_last_ok   = is_ok
        st.session_state.irt_last_ci   = correct_idx
        st.session_state.irt_last_opts = opt_texts
        st.session_state.irt_answered  = True
        st.rerun()


def _show_fb(item):
    """反馈页：读稳定键，彻底消除 qnum+1 查不到数据的 bug"""
    is_ok       = st.session_state.irt_last_ok
    correct_idx = st.session_state.irt_last_ci
    opt_texts   = st.session_state.irt_last_opts
    audio    = item.get("audio_content","")
    stimulus = item.get("stimulus_text","")
    q_zh     = item.get("question_zh","")

    if audio:
        st.markdown(f'<div class="audio-box">🔊 {audio}</div>', unsafe_allow_html=True)
    if stimulus:
        st.markdown(f'<div class="reading-box">{stimulus}</div>', unsafe_allow_html=True)
    if q_zh:
        st.markdown(f"<p style='font-size:1.15rem;font-weight:700;margin:10px 0;'>{q_zh}</p>",
                    unsafe_allow_html=True)

    if is_ok:
        st.success("✅ 回答正确！")
    else:
        ct = opt_texts[correct_idx] if correct_idx<len(opt_texts) else "—"
        st.error(f"❌ 正确答案是：**{'ABCD'[correct_idx]}.  {ct}**")
        sf = item.get("skill_focus","")
        if sf: st.caption(f"📌 知识点：{sf}")

    if st.button("➡️ 下一题", type="primary", use_container_width=True,
                 key=f"irt_n_{item['item_id']}_{st.session_state.irt_qnum}"):
        st.session_state.irt_item=None; st.session_state.irt_answered=False; st.rerun()


def _calc(θ,responses) -> dict:
    fl=_θ2lv(θ); ds=st.session_state.get("irt_dim_scores",{})
    dlv={}
    for dim in _DIM_W:
        sc=ds.get(dim,[])
        dlv[dim]=max(1,min(100,fl+round((sum(sc)/len(sc)-0.5)*8))) if sc else fl
    n=len(responses); acc=sum(1 for _,ok in responses if ok)/n if n else 0
    return {"final_level":fl,"theta":round(θ,3),"se":round(_se(responses,θ),3),
            "dimension_levels":dlv,"total_questions":n,"accuracy":round(acc,3)}


def _show_result(result):
    fl=result["final_level"]; cefr,cn=level_to_cefr(fl); stage=get_stage(fl)
    dlv=result.get("dimension_levels",{}); acc=result.get("accuracy",0)
    nq=result.get("total_questions",0); se=result.get("se",0)
    st.balloons()
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#7C3AED,#06B6D4);border-radius:20px;
  padding:30px 24px;color:white;text-align:center;margin-bottom:24px;">
  <div style="font-size:3.5rem;">{stage['icon']}</div>
  <div style="font-size:2.2rem;font-weight:900;margin-top:8px;">综合等级：L{fl}</div>
  <div style="font-size:1.3rem;opacity:.9;margin-top:6px;">{cefr} · {cn}</div>
  <div style="font-size:1rem;opacity:.75;margin-top:4px;">{stage['name']}</div>
  <div style="font-size:.9rem;opacity:.65;margin-top:10px;">
    共 {nq} 题 · 正确率 {acc:.0%} · 精度 ±{se:.2f}
  </div>
</div>""", unsafe_allow_html=True)
    # ✅ 只展示 IRT 实测的 4 个维度，不展示口语/写作
    tested={d:lv for d,lv in dlv.items() if d in _DIM_W}
    if tested:
        st.markdown("### 📊 各维度能力（IRT 实测）")
        dcols=st.columns(len(tested))
        for i,(dim,lv) in enumerate(tested.items()):
            c,_=level_to_cefr(lv)
            with dcols[i]: st.metric(f"{_DIM_IC.get(dim,'📄')} {_DIM_CN.get(dim,dim)}",f"L{lv}",c)
    st.info(f"**学习建议**：{stage['hint']}")
    st.caption("💡 口语和写作能力将在对应学习模块中逐步评估，不在本测试范围内。")


def _save_irt(pm,profile,result):
    fl=result["final_level"]; dlv=result.get("dimension_levels",{})
    # ✅ IRT 只测 vocabulary/listening/reading/grammar，不写 speaking/writing
    profile["omni_levels"].update({
        "overall":fl,
        "vocabulary":dlv.get("vocabulary",fl),
        "listening":dlv.get("listening",fl),
        "reading":dlv.get("reading",fl),
        "grammar":dlv.get("grammar",fl),
    })
    # speaking/writing 保留原值（0 就是 0）
    profile["diagnostic_done"]=True; pm.save_user(profile)


# ══════════════════════════════════════════════════════
# 入学测试流程（问卷 → IRT → 结果）
# ══════════════════════════════════════════════════════
def _render_placement(pm, profile):
    phase=st.session_state.get("placement_phase","q")
    if profile.get("diagnostic_done"):
        if st.sidebar.button("🔄 重新测试",key="sb_retest"):
            st.session_state.placement_phase="q"; st.session_state.q_step=0; _irt_reset(); st.rerun()

    if phase=="q":
        st.markdown("## 🧭 入学测试 · 第一步：背景问卷")
        prior=_render_q()
        if prior:
            for itm in prior.get("interests",[]):
                profile.setdefault("interests",[])
                if itm not in profile["interests"]: profile["interests"].append(itm)
            _irt_reset(); st.session_state.irt_theta=_lv2θ(prior["estimated_level"])
            st.session_state.placement_prior=prior; st.session_state.placement_phase="irt"
            pm.save_user(profile); st.rerun()

    elif phase=="irt":
        st.markdown("## 🧭 入学测试 · 第二步：能力定位")
        st.caption("系统根据你的每个回答自动调整下一题难度，通常 8-15 题完成。")
        result=_run_irt(pm)
        if result:
            st.session_state.placement_result=result; st.session_state.placement_phase="result"
            _save_irt(pm,profile,result); st.rerun()

    elif phase=="result":
        st.markdown("## 🎉 入学测试完成！")
        result=st.session_state.get("placement_result",{})
        if result: _show_result(result)
        st.divider()
        if st.button("🏠 进入今日主页",type="primary",use_container_width=True):
            st.session_state.mode="home"; st.session_state.daily_cards=None; st.rerun()


# ══════════════════════════════════════════════════════
# 问卷（逐步，全用独立 st.button，不用 st.form）
# ══════════════════════════════════════════════════════
_INTERESTS=["🐾 动物","🚀 太空","⚽ 运动","🎵 音乐","📖 故事","🔬 科学","🎨 艺术",
            "🍕 美食","🌍 旅行","🎬 电影","🦸 超级英雄","🎮 游戏","🌊 海洋","🦕 恐龙","🌿 自然"]
_QT=8

def _qbar():
    s=st.session_state.q_step; pct=max(0,(s-1)/_QT*100)
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;">
  <span style="font-size:1rem;color:#6B7280;white-space:nowrap;">完成度 {max(1,s)}/{_QT}</span>
  <div style="flex:1;height:10px;background:#E5E7EB;border-radius:5px;">
    <div style="width:{pct:.0f}%;height:100%;
      background:linear-gradient(90deg,#7C3AED,#06B6D4);border-radius:5px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

def _qnext(n): st.session_state.q_step=n; st.rerun()

def _render_q() -> Optional[dict]:
    if st.session_state.q_step==0:
        st.session_state.q_step=1; st.session_state.q_data={}; st.rerun()
    step=st.session_state.q_step; data=st.session_state.q_data
    if step>_QT: return _q_prior(data)
    _qbar()
    if step==1: _q1(data)
    elif step==2: _q2(data)
    elif step==3: _q3(data)
    elif step==4: _q4(data)
    elif step==5: _q5(data)
    elif step==6: _q6(data)
    elif step==7: _q7(data)
    elif step==8: _q8(data)
    return None

def _q1(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>👋 谁来填写这份问卷？</p>", unsafe_allow_html=True)
    st.caption("让孩子自己填会更准确，也可以由家长代填。")
    st.markdown("</div>", unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        if st.button("👦 让孩子自己填",use_container_width=True,type="primary",key="q1c"):
            data["filler"]="child"; st.session_state.q_filler="child"; _qnext(2)
    with c2:
        if st.button("👩 家长来帮填",use_container_width=True,key="q1p"):
            data["filler"]="parent"; st.session_state.q_filler="parent"; _qnext(2)
    st.info("💡 建议让孩子自己来填，系统定级会更准确哦！")

def _q2(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>🐣 孩子现在几岁？</p>", unsafe_allow_html=True)
    opts=["4岁或以下","5岁","6岁","7岁","8岁或以上"]
    age=st.radio("年龄",opts,horizontal=True,label_visibility="collapsed",key="q2r",index=data.get("_ai",4))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q2n"):
        data["age"]=age; data["_ai"]=opts.index(age); _qnext(3)

def _q3(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>📅 学英语多长时间了？</p>", unsafe_allow_html=True)
    opts=["从来没学过","不到 1 年","1–3 年","3 年以上"]
    exp=st.radio("时长",opts,horizontal=True,label_visibility="collapsed",key="q3r",index=data.get("_ei",1))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q3n"):
        data["experience"]=exp; data["_ei"]=opts.index(exp); _qnext(4)

def _q4(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>🌟 英语水平自评</p>", unsafe_allow_html=True)
    opts=["🌱 几乎不会，只认识几个字母","🌿 认识一些单词，能说简单句子",
          "🌳 能读懂简单短文，会基本日常对话","🦅 能读懂普通文章，能写简短段落",
          "⭐ 阅读流畅，语法基本正确","🏆 英语非常好，接近母语水平"]
    sel=st.radio("水平",opts,label_visibility="collapsed",key="q4r",index=data.get("_li",0))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q4n"):
        data["self_level"]=sel; data["_li"]=opts.index(sel); _qnext(5)

def _q5(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>❤️ 你喜欢哪些话题？（可多选）</p>", unsafe_allow_html=True)
    selected=list(data.get("interests",[]))
    cols=st.columns(5)
    for i,opt in enumerate(_INTERESTS):
        with cols[i%5]:
            if st.checkbox(opt,value=(opt in selected),key=f"q5i{i}"):
                if opt not in selected: selected.append(opt)
            else:
                if opt in selected: selected.remove(opt)
    data["interests"]=selected
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q5n"): _qnext(6)

def _q6(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>📖 来试试！读句子，选答案</p>", unsafe_allow_html=True)
    st.markdown('<div class="reading-box">Lisa has a cat.<br>The cat is white.<br>It likes to sleep all day.</div>',
                unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.15rem;font-weight:700;'>Lisa 的猫是什么颜色的？</p>",unsafe_allow_html=True)
    opts=["黑色","白色","橙色","灰色"]
    ans=st.radio("答案",opts,label_visibility="collapsed",key="q6r",index=data.get("_r1i",0))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q6n"):
        data["r1_correct"]=(ans=="白色"); data["_r1i"]=opts.index(ans); _qnext(7)

def _q7(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>📝 再来一段，稍微长一点</p>", unsafe_allow_html=True)
    st.markdown("""<div class="reading-box">
Tom gets up at seven o'clock every morning.<br>
He goes to school by bus.<br>
<b>After school, Tom always plays football with his friends in the park.</b>
</div>""", unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.15rem;font-weight:700;'>放学后，Tom 通常做什么？</p>",unsafe_allow_html=True)
    opts=["和朋友一起踢足球","在家看电视","去图书馆看书","和妈妈去超市"]
    ans=st.radio("答案",opts,label_visibility="collapsed",key="q7r",index=data.get("_r2i",0))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("下一步 →",type="primary",key="q7n"):
        data["r2_correct"]=(ans=="和朋友一起踢足球"); data["_r2i"]=opts.index(ans); _qnext(8)

def _q8(data):
    st.markdown('<div class="q-box">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:1.6rem;font-weight:900;'>🎯 学英语的主要目标是什么？</p>", unsafe_allow_html=True)
    opts=["兴趣爱好 / 日常提升","小学英语提升（作业 & 考试）","初中备考（中考英语）",
          "高中备考（高考英语）","出国留学（雅思 / 托福）",
          "参加剑桥系列考试（YLE / KET / PET / FCE）",  # ✅ 新增
          "读国际学校（IB / AP / A-Level）",             # ✅ 新增
          "职业发展","其他"]
    goal=st.radio("目标",opts,label_visibility="collapsed",key="q8r",index=data.get("_gi",0))
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("🚀 完成问卷，开始能力测试 →",type="primary",use_container_width=True,key="q8f"):
        data["goal"]=goal; data["_gi"]=opts.index(goal); _qnext(_QT+1)

def _q_prior(data) -> dict:
    ab={"4岁或以下":2,"5岁":4,"6岁":6,"7岁":8,"8岁或以上":10}.get(data.get("age",""),10)
    em={"从来没学过":-3,"不到 1 年":0,"1–3 年":4,"3 年以上":8}.get(data.get("experience",""),0)
    lm={"🌱 几乎不会，只认识几个字母":-4,"🌿 认识一些单词，能说简单句子":-2,
        "🌳 能读懂简单短文，会基本日常对话":0,"🦅 能读懂普通文章，能写简短段落":4,
        "⭐ 阅读流畅，语法基本正确":8,"🏆 英语非常好，接近母语水平":14}.get(data.get("self_level",""),0)
    rb=(2 if data.get("r1_correct") else 0)+(3 if data.get("r2_correct") else 0)
    return {"interests":data.get("interests",[]),"goal":data.get("goal",""),
            "estimated_level":max(1,min(40,ab+em+lm+rb))}

# ══════════════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════════════
def _skbar(lv,mx=90):
    pct=min(100,lv/mx*100)
    c=("#84cc16" if lv<=15 else "#10b981" if lv<=25 else "#3b82f6" if lv<=35
       else "#8b5cf6" if lv<=55 else "#f59e0b")
    return (f'<div style="height:7px;background:#E5E7EB;border-radius:4px;overflow:hidden;">'
            f'<div style="width:{pct:.0f}%;height:100%;background:{c};border-radius:4px;"></div></div>')

def _allp(pm): return {n:p for n in pm.list_users() if (p:=pm.load_user(n))}

EXPLORER_ENTRIES=[
    ("📖","故事","story",["listening","reading"]),("🎬","视频","video",["listening","speaking"]),
    ("🎵","音乐","music",["listening","speaking"]),("🎮","游戏化","game",["vocabulary","grammar"]),
    ("🌍","话题","topic",["reading","writing"]),("💼","职业","career",["reading","vocabulary"]),
    ("🔬","科学","science",["reading","listening"]),("✍️","写作","write",["writing","vocabulary"]),
]
STRATEGIES={
    "balanced":("⚖️","全面均衡","四技能均衡，稳步提升"),
    "interest":("❤️","兴趣优先","从你最感兴趣的内容出发"),
    "weakness":("💪","强化薄弱","专攻薄弱技能，弥补短板"),
    "strength":("⭐","发挥优势","深化强项，建立自信"),
}

# ══════════════════════════════════════════════════════
# 登录门户
# ══════════════════════════════════════════════════════
def _login():
    st.markdown("""
<div style="text-align:center;padding:48px 20px 24px;">
  <div style="font-size:4rem;">🦉</div>
  <h1 style="font-size:2.4rem;font-weight:900;margin:8px 0;">OMNI-LEARN OS</h1>
  <p style="color:#6B7280;font-size:1.1rem;">全阶英语学习系统 · 请选择你的身份</p>
</div>""", unsafe_allow_html=True)
    portals=[("🎓","学生","student","#7C3AED","完成入学测试<br>个性化学习路径<br>内容探索"),
             ("👩‍🏫","教师","teacher","#0F4C81","班级管理<br>发布学习任务<br>全班学情分析"),
             ("👨‍👩‍👧","家长","parent","#059669","绑定孩子账号<br>查看学习进度<br>布置今日任务"),
             ("🛡️","管理员","admin","#B45309","学员账户管理<br>班级管理<br>数据看板")]
    cols=st.columns(4)
    for col,(icon,label,portal,color,desc) in zip(cols,portals):
        with col:
            st.markdown(f"""
<div style="background:linear-gradient(135deg,{color},{color}CC);color:white;
  border-radius:16px;padding:26px;text-align:center;margin-bottom:8px;">
  <div style="font-size:2.8rem;">{icon}</div>
  <div style="font-size:1.25rem;font-weight:900;margin:10px 0;">{label}端</div>
  <div style="font-size:.9rem;opacity:.88;line-height:1.8;">{desc}</div>
</div>""", unsafe_allow_html=True)
            if st.button(f"进入{label}端 →",key=f"ent_{portal}",use_container_width=True,type="primary"):
                st.session_state.portal=portal; st.rerun()

# ══════════════════════════════════════════════════════
# 学生端侧边栏
# ══════════════════════════════════════════════════════
def _stu_sb():
    with st.sidebar:
        st.markdown("""<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:2rem;">🦉</div>
  <div style="font-weight:900;font-size:1rem;letter-spacing:2px;">OMNI-LEARN OS</div>
  <div style="font-size:.7rem;opacity:.7;">全阶英语学习系统</div>
</div>""", unsafe_allow_html=True)
        st.divider()
        with st.expander("⚙️ 路径配置",expanded=False):
            dd=st.text_input("用户数据目录",value=st.session_state.data_dir,key="s_dd")
            ld=st.text_input("内容库目录",value=st.session_state.library_dir,key="s_ld")
            if st.button("✅ 确认路径",key="s_confirm",use_container_width=True):
                st.session_state.data_dir=dd.strip().strip("\"'")
                st.session_state.library_dir=ld.strip().strip("\"'")
                st.session_state.daily_cards=None; st.rerun()
            for k,s in [("s_dd","data_dir"),("s_ld","library_dir")]:
                v=st.session_state.get(k,"")
                if v is not None: st.session_state[s]=v.strip().strip("\"'")

        if not _UP_OK: st.error(f"user_profile.py 加载失败: {_UP_ERR}"); return None,None

        pm=_pm(st.session_state.data_dir); users=pm.list_users()
        st.divider(); st.markdown("**👤 学习者**")
        options=(users if users else [])+["➕ 新建学习者"]
        sel=st.selectbox("选择",options,label_visibility="collapsed",key="user_select")

        if sel=="➕ 新建学习者": _new_user(pm); return pm,None

        if st.session_state.current_user!=sel:
            st.session_state.current_user=sel; st.session_state.daily_cards=None

        profile=pm.load_user(sel)
        if not profile: return pm,None
        ov=profile["omni_levels"].get("overall",0)
        if ov>0:
            cefr,cn=level_to_cefr(ov); sg=get_stage(ov)
            st.caption(f"L{ov} · {cefr}（{cn}）\n{sg['icon']} {sg['name']}")
        else: st.caption("⚠️ 尚未完成入学测试")

        st.divider(); st.markdown("**导航**")
        for icon,label,mode in [("🏠","今日主页","home"),("📚","教材学习","curriculum"),
                                  ("🧭","自由探索","explorer"),("📊","我的档案","profile")]:
            active=st.session_state.mode==mode
            if st.button(f"{icon} {label}",key=f"nav_{mode}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.mode=mode; st.rerun()
        st.divider()
        if ov==0:
            if st.button("🎯 开始入学测试",use_container_width=True,type="primary",key="sb_start"):
                st.session_state.mode="placement"; st.session_state.placement_phase="q"
                st.session_state.q_step=0; st.rerun()
        else:
            if st.button("🔄 重新入学测试",use_container_width=True,key="sb_retest2"):
                st.session_state.mode="placement"; st.session_state.placement_phase="q"
                st.session_state.q_step=0; _irt_reset(); st.rerun()
        if st.button("🔙 切换身份",use_container_width=True,key="s_back"):
            st.session_state.portal="login"; st.rerun()
        return pm,profile

def _new_user(pm):
    st.markdown("**✨ 创建新学习者**")
    with st.form("new_user_form"):
        nick=st.text_input("昵称",placeholder="如：小明")
        age=st.text_input("年龄参考（选填）",placeholder="如：8岁")
        goal=st.selectbox("学习目标",["兴趣爱好","小学英语提升","初中备考","高考备考","出国留学","剑桥考试","国际学校","职业发展","其他"])
        tier=st.selectbox("套餐",["pro","basic"],format_func=lambda x:"Pro（全库）" if x=="pro" else "Basic（基础）")
        if st.form_submit_button("创建",type="primary",use_container_width=True):
            if nick:
                pm.create_user(nick,age,goal,tier); st.session_state.current_user=nick
                st.session_state.mode="placement"; st.session_state.placement_phase="q"
                st.session_state.q_step=0; st.rerun()
            else: st.warning("请输入昵称")

# ══════════════════════════════════════════════════════
# 今日主页
# ══════════════════════════════════════════════════════
def _home(pm,matcher,profile):
    nick=profile.get("nickname","同学"); ov=profile["omni_levels"].get("overall",0)
    streak=profile.get("achievements",{}).get("streak_days",0)
    hour=datetime.now().hour; greet="早上好" if hour<12 else ("下午好" if hour<18 else "晚上好")
    st.markdown(f"## {greet}，{nick}！👋")
    if ov==0:
        st.warning("还没有完成入学测试，先完成测试再开始学习吧。")
        if st.button("🎯 立即开始入学测试",type="primary"):
            st.session_state.mode="placement"; st.session_state.placement_phase="q"
            st.session_state.q_step=0; st.rerun()
        return
    cefr,cn=level_to_cefr(ov); sg=get_stage(ov)
    st.markdown(f"""<div class="stage-bar">
  <span style="font-size:1.4rem;">{sg['icon']}</span>
  <strong> L{ov} · {cefr}（{cn}）</strong> &nbsp;|&nbsp; {sg['name']}
  &nbsp;|&nbsp; 🔥 连续 {streak} 天</div>""", unsafe_allow_html=True)

    # ✅ 只展示 IRT 实测维度（非零才显示）
    tested=[(sk,lv) for sk in ["listening","reading","vocabulary","grammar"]
            if (lv:=profile["omni_levels"].get(sk,0))>0]
    if not tested: tested=[("listening",ov),("reading",ov)]
    st.markdown(f"### 能力快览（{len(tested)} 项已测）")
    cols=st.columns(len(tested))
    for i,(sk,lv) in enumerate(tested):
        c,n=level_to_cefr(lv)
        with cols[i]: st.metric(f"{SKILL_ICONS[sk]} {SKILL_CN[sk]}",f"L{lv}",c)

    st.divider(); st.markdown("### 📬 今日推荐")
    today=datetime.now().strftime("%Y-%m-%d")
    if st.session_state.daily_date!=today or not st.session_state.daily_cards:
        if matcher:
            with st.spinner("正在生成今日推荐..."):
                rec=matcher.get_daily_recommendation(profile,n_items=6)
                st.session_state.daily_cards=rec.get("cards",[]); st.session_state.daily_date=today
        else: st.session_state.daily_cards=[]

    cards=st.session_state.daily_cards
    if not cards: st.info("内容库尚未加载，请确认内容库目录路径。")
    else:
        cols=st.columns(3)
        for i,card in enumerate(cards[:6]):
            with cols[i%3]:
                sk=card.get("card_type",""); icon=SKILL_ICONS.get(sk,"📄")
                lv=card.get("level",0); c,_=level_to_cefr(lv)
                title=card.get("title","") or "未知内容"; desc=card.get("description","")
                st.markdown(f"""
<div class="omni-card">
  <div style="font-size:.85rem;color:#7C3AED;font-weight:600;margin-bottom:5px;">
    {icon} {SKILL_CN.get(sk,sk).upper()} &nbsp;<span class="level-chip">L{lv}</span>
  </div>
  <div style="font-weight:700;font-size:1rem;margin-bottom:5px;">{title}</div>
  <div style="font-size:.9rem;color:#6B7280;">{desc}</div>
</div>""", unsafe_allow_html=True)

    st.divider(); c1,c2=st.columns(2)
    with c1:
        if st.button("📚 进入教材学习",use_container_width=True,type="primary"):
            st.session_state.mode="curriculum"; st.rerun()
    with c2:
        if st.button("🧭 自由探索",use_container_width=True):
            st.session_state.mode="explorer"; st.rerun()

# ══════════════════════════════════════════════════════
# 教材模式（正确调用 ContentMatcher）
# ══════════════════════════════════════════════════════
def _curriculum(pm,matcher,profile):
    st.markdown("## 📚 教材学习")
    lib=st.session_state.library_dir or st.session_state.data_dir
    tb_path=os.path.join(lib,"textbook_library.json")
    if not os.path.exists(tb_path):
        st.warning(f"教材库文件未找到：`{tb_path}`\n\n当前内容库目录：`{lib}`"); return
    with open(tb_path,encoding="utf-8") as f: tbl=json.load(f)
    textbooks=tbl.get("textbooks",[])
    if not textbooks: st.info("教材库为空。"); return

    sel_name=st.selectbox("选择教材",[t.get("textbook_name","未命名") for t in textbooks],key="sel_tb")
    sel_tb=next((t for t in textbooks if t.get("textbook_name")==sel_name),None)
    if not sel_tb: return
    c1,c2,c3=st.columns(3); lr=sel_tb.get("level_range",{})
    c1.metric("总单元数",len(sel_tb.get("units",[])))
    c2.metric("OMNI等级范围",f"L{lr.get('min',0)}-L{lr.get('max',0)}")
    c3.metric("出版社",sel_tb.get("publisher","-"))
    st.divider()

    units=sel_tb.get("units",[])
    if not units: st.info("该教材暂无单元信息。"); return
    sel_un=st.selectbox("选择单元",[u.get("unit_name",f"Unit {i+1}") for i,u in enumerate(units)],key="sel_unit")
    sel_u=next((u for u in units if u.get("unit_name")==sel_un),None)
    if not sel_u: return

    ul=sel_u.get("omni_level",0)
    if ul:
        c,cn_str=level_to_cefr(ul)
        st.markdown(f"""<div class="stage-bar" style="background:linear-gradient(90deg,#059669,#0891B2);">
  📖 {sel_un} &nbsp;|&nbsp; L{ul} · {c}（{cn_str}）</div>""", unsafe_allow_html=True)

    topics=sel_u.get("topics",[]); grammar=sel_u.get("grammar_points",[]); vocab=sel_u.get("vocabulary",[])
    ic1,ic2,ic3=st.columns(3)
    with ic1: st.markdown("**📌 话题**"); st.write("、".join(topics) if topics else "-")
    with ic2: st.markdown("**📐 语法**"); st.write("、".join(grammar) if grammar else "-")
    with ic3: st.markdown("**📝 核心词汇**"); st.write("、".join(vocab[:8]) if vocab else "-")
    st.divider()

    if not matcher: st.warning("内容匹配器未加载，请确认 content_matcher.py 存在。"); return
    st.markdown("### 🎯 本单元配套资源")
    tabs=st.tabs(["🎧 听力","📖 阅读","🗣️ 口语","✍️ 写作","📝 词汇"])
    for idx,(sk,sk_cn) in enumerate([("listening","听力"),("reading","阅读"),("speaking","口语"),
                                      ("writing","写作"),("vocabulary","词汇")]):
        with tabs[idx]:
            with st.spinner(f"匹配{sk_cn}资源..."):
                # ✅ 正确调用签名: match_for_curriculum(unit_data, user_data)
                raw=matcher.match_for_curriculum(sel_u,profile)
            results=(raw.get("suggested_sequence",[]) if isinstance(raw,dict) and "suggested_sequence" in raw
                     else raw if isinstance(raw,list) else [])
            if not results: st.info(f"暂无匹配的{sk_cn}资源，建议扩充内容库。"); continue
            for item in results:
                title=item.get("title","") or item.get("textbook_name","未知")
                lv=item.get("omni_level",item.get("level",0)); c,_=level_to_cefr(lv) if lv else ("-","-")
                desc=item.get("summary_cn","") or item.get("description","")
                score=item.get("_match_score",0); src=item.get("_lib_source","")
                si={"picturebook":"📗","media":"🎬","movie":"🎥","ebook":"📘","textbook":"📕"}.get(src,"📄")
                st.markdown(f"""
<div class="omni-card" style="border-left-color:#059669;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-weight:700;font-size:1rem;">{si} {title[:50]}</span>
    <span class="level-chip">{c} · L{lv}</span>
  </div>
  <div style="font-size:.9rem;color:#6B7280;margin-top:5px;">{desc[:80]}</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 探索模式（正确调用 ContentMatcher.match_for_explorer）
# ══════════════════════════════════════════════════════
def _explorer(pm,matcher,profile):
    st.markdown("## 🧭 自由探索")
    ov=profile["omni_levels"].get("overall",0)
    if ov==0: st.warning("请先完成入学测试。"); return

    sg=get_stage(ov); scaffold=get_scaffold_hint(ov); cefr,cn=level_to_cefr(ov)
    st.markdown(f"""<div class="stage-bar">
  {sg['icon']} <strong>{sg['name']}</strong> &nbsp;|&nbsp;
  L{ov} · {cefr}（{cn}）&nbsp;|&nbsp; 引导力度：{scaffold}</div>""", unsafe_allow_html=True)

    st.markdown("#### 🗺️ 探索策略")
    sc=st.columns(4)
    for i,(key,(icon,name,desc)) in enumerate(STRATEGIES.items()):
        with sc[i]:
            active=st.session_state.exp_strategy==key
            if st.button(f"{icon} {name}",key=f"strat_{key}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.exp_strategy=key; st.session_state.exp_results=[]; st.rerun()
            st.caption(desc)

    st.divider()
    sc2,bc=st.columns([5,1])
    with sc2:
        query=st.text_input("搜索",value=st.session_state.exp_search,
                             placeholder="输入话题、词汇、人物...",label_visibility="collapsed",key="exp_inp")
    with bc:
        searched=st.button("搜索",type="primary",use_container_width=True,key="do_search")
    if searched and query:
        st.session_state.exp_search=query; st.session_state.exp_entry="search"
        st.session_state.exp_results=[]

    st.divider()
    n_e=4 if ov<=15 else (6 if ov<=35 else 8)
    e_cols=st.columns(n_e)
    for i,(emoji,label,key,skills) in enumerate(EXPLORER_ENTRIES[:n_e]):
        with e_cols[i]:
            active=st.session_state.exp_entry==key
            if st.button(f"{emoji}\n{label}",key=f"entry_{key}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.exp_entry=key; st.session_state.exp_results=[]; st.rerun()

    if (st.session_state.exp_entry or st.session_state.exp_search) and not st.session_state.exp_results:
        if matcher:
            with st.spinner("正在为你探索内容..."):
                entry=st.session_state.exp_entry or "topic"
                entry_skills=next((sks for _,_,k,sks in EXPLORER_ENTRIES if k==entry),["reading","listening"])
                # ✅ 正确调用签名: match_for_explorer(user_data, skills, mode)
                raw=matcher.match_for_explorer(user_data=profile,skills=entry_skills,
                                               mode=st.session_state.exp_strategy)
                if isinstance(raw,dict) and "by_skill" in raw:
                    results=[]
                    for sk,its in raw["by_skill"].items():
                        for it in its: it["_match_skill"]=sk; results.append(it)
                elif isinstance(raw,list): results=raw
                else: results=[]
                st.session_state.exp_results=results

    results=st.session_state.exp_results
    if results:
        st.divider(); st.markdown(f"### 📦 找到 {len(results)} 个匹配内容")
        skill_groups={}
        for r in results: skill_groups.setdefault(r.get("_match_skill","reading"),[]).append(r)
        rtabs=st.tabs([f"{SKILL_ICONS.get(sk,'📄')} {SKILL_CN.get(sk,sk)}" for sk in skill_groups])
        for tab,(sk,items) in zip(rtabs,skill_groups.items()):
            with tab:
                ic=st.columns(2)
                for j,item in enumerate(items):
                    with ic[j%2]:
                        title=item.get("title","") or "未知"; lv=item.get("omni_level",0)
                        c,_=level_to_cefr(lv) if lv else ("-","-")
                        src=item.get("_lib_source",""); desc=item.get("summary_cn","") or item.get("description","")
                        si={"picturebook":"📗","media":"🎬","movie":"🎥","ebook":"📘","textbook":"📕"}.get(src,"📄")
                        st.markdown(f"""
<div class="omni-card">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-weight:700;font-size:1rem;">{si} {title[:45]}</span>
    <span class="level-chip">L{lv}</span>
  </div>
  <div style="font-size:.9rem;color:#6B7280;margin-top:5px;">{desc[:80]}</div>
  <div style="font-size:.85rem;color:#9CA3AF;margin-top:5px;">{c}</div>
</div>""", unsafe_allow_html=True)
    elif st.session_state.exp_entry or st.session_state.exp_search:
        st.info("暂无匹配内容，内容库建设中...")

# ══════════════════════════════════════════════════════
# 我的档案
# ══════════════════════════════════════════════════════
def _profile_page(pm,matcher,profile):
    st.markdown("## 📊 我的学习档案")
    nick=profile.get("nickname",""); ov=profile["omni_levels"].get("overall",0)
    if ov==0: st.warning("请先完成入学测试。"); return
    cefr,cn=level_to_cefr(ov); sg=get_stage(ov)
    streak=profile.get("achievements",{}).get("streak_days",0)
    hist=profile.get("learning_history",{})
    st.markdown(f"""<div class="stage-bar">
  {sg['icon']} <strong>{nick}</strong> &nbsp;|&nbsp;
  综合 L{ov} · {cefr}（{cn}）&nbsp;|&nbsp; 🔥 连续 {streak} 天</div>""", unsafe_allow_html=True)

    # 只展示有值的技能
    all_skills=[("listening","听力","🎧"),("reading","阅读","📖"),
                ("vocabulary","词汇","📝"),("grammar","语法","📐"),
                ("speaking","口语","🗣️"),("writing","写作","✍️")]
    has_val=[(sk,profile["omni_levels"].get(sk,0)) for sk,_,_ in all_skills
             if profile["omni_levels"].get(sk,0)>0]
    if has_val:
        st.markdown("### 技能等级")
        cols=st.columns(len(has_val))
        for i,(sk,lv) in enumerate(has_val):
            c,_=level_to_cefr(lv)
            with cols[i]:
                icon=SKILL_ICONS.get(sk,"📄"); cn_s=SKILL_CN.get(sk,sk)
                st.metric(f"{icon}\n{cn_s}",f"L{lv}",c)

    st.divider()
    col1,col2=st.columns(2)
    with col1:
        st.markdown("**💪 需要强化**"); weak=hist.get("weak_points",[])
        [st.markdown(f"- {w}") for w in weak] if weak else st.caption("暂无数据")
    with col2:
        st.markdown("**⭐ 你的强项**"); strong=hist.get("strong_points",[])
        [st.markdown(f"- {s}") for s in strong] if strong else st.caption("暂无数据")

    interests=profile.get("interests",[])
    if interests:
        st.divider(); st.markdown("**❤️ 兴趣标签**")
        st.markdown(" ".join([f'<span class="skill-badge">{t}</span>' for t in interests]),
                    unsafe_allow_html=True)

    if matcher:
        st.divider(); st.markdown("### 📚 内容库概况")
        stats=matcher.get_library_stats()
        if stats:
            sc=st.columns(len(stats)); icons={"教材":"📕","绘本":"📗","影音":"🎬","电影":"🎥"}
            for i,(name,count) in enumerate(stats.items()):
                with sc[i]: st.metric(f"{icons.get(name,'📄')} {name}",count,"条目")

# ══════════════════════════════════════════════════════
# 教师端
# ══════════════════════════════════════════════════════
def _teacher():
    pm=_pm(st.session_state.data_dir); lib=st.session_state.library_dir or st.session_state.data_dir
    matcher=_mat(lib) if _CM_OK else None; cm=_cm(st.session_state.data_dir)
    with st.sidebar:
        st.markdown("""<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:2rem;">👩‍🏫</div>
  <div style="font-weight:900;font-size:1rem;">OMNI 教师端</div>
  <div style="font-size:.7rem;opacity:.7;">班级管理 · 学情分析 · 任务发布</div>
</div>""", unsafe_allow_html=True)
        st.divider()
        with st.expander("⚙️ 路径配置",expanded=False):
            dd=st.text_input("用户数据目录",value=st.session_state.data_dir,key="t_dd")
            ld=st.text_input("内容库目录",value=st.session_state.library_dir,key="t_ld")
            if st.button("✅ 确认路径",key="t_path",use_container_width=True):
                st.session_state.data_dir=dd.strip().strip("\"'")
                st.session_state.library_dir=ld.strip().strip("\"'"); st.rerun()
        st.divider(); st.markdown("**导航**")
        for icon,label,page in [("🏠","概览","home"),("🏫","班级管理","classes"),
                                  ("📊","学情分析","analytics"),("📋","任务发布","tasks"),
                                  ("📤","导出报告","export")]:
            active=st.session_state.t_page==page
            if st.button(f"{icon} {label}",key=f"t_{page}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.t_page=page; st.rerun()
        st.divider()
        if st.button("🔙 切换身份",key="t_back",use_container_width=True):
            st.session_state.portal="login"; st.rerun()

    if not pm: st.error("请先配置路径。"); return
    page=st.session_state.t_page
    if page=="home":        _t_home(pm,cm)
    elif page=="classes":   _t_classes(pm,cm)
    elif page=="analytics": _t_analytics(pm,cm)
    elif page=="tasks":     _t_tasks(pm,cm,matcher)
    elif page=="export":    _t_export(pm,cm)

def _t_home(pm,cm):
    st.markdown("## 👩‍🏫 教师端概览")
    classes=cm.all(); profiles=_allp(pm); all_s=set()
    [all_s.update(c.get("students",[])) for c in classes]
    today=datetime.now().strftime("%Y-%m-%d")
    active_c=sum(1 for n in all_s if profiles.get(n,{}).get("achievements",{}).get("last_study_date","")==today)
    tested_c=sum(1 for n in all_s if profiles.get(n,{}).get("diagnostic_done",False))
    pct=int(tested_c/max(len(all_s),1)*100)
    c1,c2,c3,c4=st.columns(4)
    for col,num,label in [(c1,len(classes),"班级数量"),(c2,len(all_s),"学员总数"),
                           (c3,active_c,"今日活跃"),(c4,f"{pct}%","已完成测试")]:
        with col: st.markdown(f'<div class="stat-card"><div class="stat-num">{num}</div>'
                               f'<div class="stat-label">{label}</div></div>',unsafe_allow_html=True)
    st.divider()
    if not classes: st.info("还没有班级，点击左侧「班级管理」创建。"); return
    st.markdown("### 班级快览")
    for cls in classes:
        students=cls.get("students",[]); lvs=[profiles[s]["omni_levels"].get("overall",0) for s in students if s in profiles]
        avg_lv=int(sum(lvs)/len(lvs)) if lvs else 0; cefr,_=level_to_cefr(avg_lv) if avg_lv else ("--","--")
        c1,c2,c3,c4,c5=st.columns([3,2,2,2,1])
        c1.markdown(f"**🏫 {cls['name']}** · {cls.get('grade','')}"); c2.markdown(f"👥 {len(students)}名学员")
        c3.markdown(f"📊 均 L{avg_lv} · {cefr}"); c4.markdown(f"📋 {len(cls.get('tasks',[]))}个任务")
        with c5:
            if st.button("管理",key=f"th_{cls['class_id']}",use_container_width=True):
                st.session_state.t_class=cls["class_id"]; st.session_state.t_page="classes"; st.rerun()
        st.divider()

def _t_classes(pm,cm):
    st.markdown("## 🏫 班级管理")
    tab1,tab2=st.tabs(["📋 班级列表","➕ 创建班级"])
    with tab1:
        classes=cm.all(); profiles=_allp(pm)
        if not classes: st.info("还没有班级，切换到「创建班级」标签创建。")
        for cls in classes:
            is_sel=(st.session_state.t_class==cls["class_id"])
            border="2px solid #7C3AED" if is_sel else "1px solid #E5E7EB"
            st.markdown(f"""<div style="background:white;border-radius:10px;padding:14px;border:{border};margin-bottom:4px;">
  <b>🏫 {cls['name']}</b>　{cls.get('grade','')}　
  <span style="color:#6B7280;font-size:.9rem;">教师：{cls.get('teacher','')} · 创建：{cls.get('created_at','')}</span>
</div>""",unsafe_allow_html=True)
            bc1,bc2,bc3,bc4=st.columns(4)
            with bc1:
                if st.button("📊 详情",key=f"td_{cls['class_id']}",use_container_width=True):
                    st.session_state.t_class=cls["class_id"]; st.rerun()
            with bc2:
                if st.button("📋 发布任务",key=f"tt_{cls['class_id']}",use_container_width=True):
                    st.session_state.t_class=cls["class_id"]; st.session_state.t_page="tasks"; st.rerun()
            with bc3:
                if st.button("📤 导出",key=f"te_{cls['class_id']}",use_container_width=True):
                    st.session_state.t_class=cls["class_id"]; st.session_state.t_page="export"; st.rerun()
            with bc4:
                if st.button("🗑️ 删除",key=f"tdel_{cls['class_id']}",use_container_width=True):
                    cm.delete(cls["class_id"])
                    if st.session_state.t_class==cls["class_id"]: st.session_state.t_class=None
                    st.rerun()
            if st.session_state.t_class==cls["class_id"]: _class_detail(cls,profiles,pm,cm)
            st.divider()
    with tab2:
        with st.form("create_class_form"):
            f1,f2=st.columns(2)
            with f1:
                name=st.text_input("班级名称 *",placeholder="如：三年级A班")
                grade=st.selectbox("年级",["幼儿园","小学一年级","小学二年级","小学三年级",
                    "小学四年级","小学五年级","小学六年级","初一","初二","初三",
                    "高一","高二","高三","大学","成人","混合年龄"])
            with f2:
                teacher=st.text_input("授课教师姓名 *",placeholder="如：张老师")
                goal=st.text_input("学习目标",placeholder="如：新课标英语A2水平")
            if st.form_submit_button("✅ 创建班级",type="primary",use_container_width=True):
                if name and teacher:
                    cls=cm.create(name,grade,teacher,goal); st.success(f"✅ 班级「{name}」创建成功！")
                    st.session_state.t_class=cls["class_id"]; st.rerun()
                else: st.warning("请填写班级名称和教师姓名")

def _class_detail(cls,profiles,pm,cm):
    students=cls.get("students",[]); cid=cls["class_id"]
    cl,cr=st.columns([3,2])
    with cl:
        st.markdown(f"**👥 学员名单（{len(students)}人）**")
        not_in=[u for u in pm.list_users() if u not in students]
        if not_in:
            with st.expander("➕ 添加学员"):
                to_add=st.multiselect("选择要添加的学习者",not_in,key=f"add_{cid}")
                if st.button("确认添加",key=f"cfa_{cid}"):
                    [cm.add_student(cid,s) for s in to_add]; st.success(f"已添加 {len(to_add)} 名"); st.rerun()
        today=datetime.now().strftime("%Y-%m-%d")
        for s in students:
            p=profiles.get(s,{}); ov=p.get("omni_levels",{}).get("overall",0)
            streak=p.get("achievements",{}).get("streak_days",0); tested=p.get("diagnostic_done",False)
            active="🟢" if p.get("achievements",{}).get("last_study_date","")==today else "⚪"
            sa,sb,sc_=st.columns([3,3,1])
            with sa: st.markdown(f"{active} **{s}** {'✅' if tested else '⚠️未测'}")
            with sb: st.markdown(f"L{ov} · 连续{streak}天")
            with sc_:
                if st.button("移除",key=f"rm_{cid}_{s}",use_container_width=True):
                    cm.rm_student(cid,s); st.rerun()
    with cr:
        st.markdown("**📊 等级分布**")
        buckets={"Pre-A1(L1-15)":0,"A1(L16-25)":0,"A2(L26-35)":0,"B1(L36-55)":0,"B2+(L56+)":0,"未测试":0}
        for s in students:
            lv=profiles.get(s,{}).get("omni_levels",{}).get("overall",0)
            if lv==0: buckets["未测试"]+=1
            elif lv<=15: buckets["Pre-A1(L1-15)"]+=1
            elif lv<=25: buckets["A1(L16-25)"]+=1
            elif lv<=35: buckets["A2(L26-35)"]+=1
            elif lv<=55: buckets["B1(L36-55)"]+=1
            else: buckets["B2+(L56+)"]+=1
        total=max(len(students),1)
        for bucket,count in buckets.items():
            if count:
                pct=count/total*100; st.markdown(f"`{bucket}` **{count}人** ({pct:.0f}%)")
                st.markdown(_skbar(int(pct)),unsafe_allow_html=True)
        st.markdown("**📚 当前教材**"); st.info(f"当前：{cls.get('textbook','未设置') or '未设置'}")
        new_tb=st.text_input("设置教材名称",placeholder="如：人教版G3上册",key=f"tb_{cid}")
        if st.button("保存",key=f"save_tb_{cid}"):
            cm.update(cid,textbook=new_tb); st.success("✅ 已保存"); st.rerun()

def _t_analytics(pm,cm):
    st.markdown("## 📊 学情分析")
    classes=cm.all(); profiles=_allp(pm)
    if not classes: st.info("请先创建班级并添加学员。"); return
    class_map={c["class_id"]:c["name"] for c in classes}
    sel_id=st.selectbox("选择班级",list(class_map.keys()),format_func=lambda x:class_map[x])
    cls=cm.get(sel_id)
    if not cls: return
    students=cls.get("students",[])
    if not students: st.info("该班级暂无学员。"); return
    st.markdown(f"### 🏫 {cls['name']} · {len(students)}名学员")
    st.markdown("**📈 全班技能平均等级**"); cols=st.columns(4)
    for i,skill in enumerate(["listening","reading","vocabulary","grammar"]):
        lvs=[profiles[s]["omni_levels"].get(skill,0) for s in students if s in profiles and profiles[s]["omni_levels"].get(skill,0)>0]
        avg=int(sum(lvs)/len(lvs)) if lvs else 0; cefr,_=level_to_cefr(avg) if avg else ("--","--")
        with cols[i]: st.metric(f"{SKILL_ICONS.get(skill,'')} {SKILL_CN.get(skill,skill)}",f"L{avg}" if avg else "--",cefr)
    st.divider(); st.markdown("**👥 学员明细（按综合等级排序）**")
    rows=[]
    for s in students:
        p=profiles.get(s,{}); lv=p.get("omni_levels",{}); ach=p.get("achievements",{})
        rows.append({"姓名":s,"综合":lv.get("overall",0),"听":lv.get("listening",0),
                     "读":lv.get("reading",0),"词汇":lv.get("vocabulary",0),
                     "连续":ach.get("streak_days",0),"测试":"✅" if p.get("diagnostic_done") else "⚠️"})
    rows.sort(key=lambda x:-x["综合"])
    hc=st.columns([2,1,1,1,1,1]); [c.markdown(f"**{h}**") for c,h in zip(hc,["姓名","综合","听力","阅读","词汇","连续"])]
    st.divider()
    for row in rows:
        rc=st.columns([2,1,1,1,1,1])
        vals=[row["姓名"],f"L{row['综合']}" if row["综合"] else "--",
              f"L{row['听']}" if row["听"] else "--",f"L{row['读']}" if row["读"] else "--",
              f"L{row['词汇']}" if row["词汇"] else "--",f"{row['连续']}天"]
        [c.markdown(str(v)) for c,v in zip(rc,vals)]

def _t_tasks(pm,cm,matcher):
    st.markdown("## 📋 任务发布")
    classes=cm.all()
    if not classes: st.info("请先创建班级。"); return
    class_map={c["class_id"]:c["name"] for c in classes}
    sel_id=st.selectbox("选择班级",list(class_map.keys()),format_func=lambda x:class_map[x],key="task_cls")
    cls=cm.get(sel_id)
    if not cls: return
    st.divider(); tab1,tab2=st.tabs(["➕ 发布新任务","📋 已有任务"])
    with tab1:
        st.markdown(f"**为「{cls['name']}」发布任务**")
        task_type=st.selectbox("任务类型",["📖 阅读任务","🎧 听力任务","✍️ 写作任务",
            "🗣️ 口语任务","📝 词汇任务","🔤 语法任务","📚 完成单元","🎯 自由探索"])
        task_title=st.text_input("任务标题",placeholder="如：阅读 Unit 3 课文")
        task_desc=st.text_area("任务说明",placeholder="具体要求和注意事项...",height=100)
        fc1,fc2=st.columns(2)
        with fc1: due=st.selectbox("截止时间",["今天","明天","3天内","本周内","本月内"])
        with fc2: tskill=st.selectbox("目标技能",["综合","听力","阅读","口语","写作","词汇","语法"])
        if st.button("✅ 发布任务",type="primary",use_container_width=True,key="pub_task"):
            if task_title:
                cm.assign_task(sel_id,{"type":task_type,"title":task_title,"desc":task_desc,
                                        "due":due,"skill":tskill,"class":cls["name"]})
                st.success(f"✅ 任务「{task_title}」已发布给 {len(cls.get('students',[]))} 名学员！"); st.rerun()
            else: st.warning("请输入任务标题")
    with tab2:
        tasks=cls.get("tasks",[])
        if not tasks: st.info("还没有发布任务。")
        else:
            for task in reversed(tasks[-20:]):
                st.markdown(f"""<div class="task-card">
  <b>{task.get('type','')} {task.get('title','')}</b>
  <span style="color:#6B7280;font-size:.85rem;margin-left:8px;">
    截止：{task.get('due','')} · 技能：{task.get('skill','')} · 发布：{task.get('assigned_at','')[:10]}
  </span><br><span style="font-size:.9rem;">{task.get('desc','')[:80]}</span>
</div>""",unsafe_allow_html=True)

def _t_export(pm,cm):
    st.markdown("## 📤 导出学习报告")
    classes=cm.all()
    if not classes: st.info("请先创建班级。"); return
    class_map={c["class_id"]:c["name"] for c in classes}
    sel_id=st.selectbox("选择班级",list(class_map.keys()),format_func=lambda x:class_map[x],key="exp_cls")
    cls=cm.get(sel_id)
    if not cls: return
    profiles=_allp(pm); students=cls.get("students",[])
    if st.button("📥 生成报告",type="primary",use_container_width=True):
        lines=[f"# OMNI-LEARN OS 学习报告  {cls['name']}",
               f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
               f"授课教师：{cls.get('teacher','')}","",
               f"学生总数：{len(students)}人",
               f"已完成测试：{sum(1 for s in students if profiles.get(s,{}).get('diagnostic_done'))}人","",
               "| 姓名 | 综合 | 听力 | 阅读 | 词汇 | 连续学习 |",
               "|------|------|------|------|------|---------|"]
        for s in students:
            p=profiles.get(s,{}); lv=p.get("omni_levels",{}); ach=p.get("achievements",{})
            lines.append(f"| {s} | L{lv.get('overall',0)} | L{lv.get('listening',0)} | "
                         f"L{lv.get('reading',0)} | L{lv.get('vocabulary',0)} | {ach.get('streak_days',0)}天 |")
        report="\n".join(lines); st.text_area("报告预览",report,height=360)
        st.download_button("⬇️ 下载报告",report.encode("utf-8"),
            f"OMNI报告_{cls['name']}_{datetime.now().strftime('%Y%m%d')}.md","text/markdown",use_container_width=True)

# ══════════════════════════════════════════════════════
# 家长端
# ══════════════════════════════════════════════════════
def _parent():
    pm=_pm(st.session_state.data_dir); lib=st.session_state.library_dir or st.session_state.data_dir
    matcher=_mat(lib) if _CM_OK else None; cm=_cm(st.session_state.data_dir)
    with st.sidebar:
        st.markdown("""<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:2rem;">👨‍👩‍👧</div>
  <div style="font-weight:900;font-size:1rem;">OMNI 家长端</div>
  <div style="font-size:.7rem;opacity:.7;">孩子学习 · 实时追踪 · 任务管理</div>
</div>""",unsafe_allow_html=True)
        st.divider()
        with st.expander("⚙️ 路径配置",expanded=False):
            dd=st.text_input("用户数据目录",value=st.session_state.data_dir,key="p_dd")
            ld=st.text_input("内容库目录",value=st.session_state.library_dir,key="p_ld")
            if st.button("✅ 确认路径",key="p_path",use_container_width=True):
                st.session_state.data_dir=dd.strip().strip("\"'"); st.session_state.library_dir=ld.strip().strip("\"'"); st.rerun()
        st.divider()
        pname=st.text_input("📛 你的姓名",value=st.session_state.parent_name,placeholder="如：张妈妈",key="p_name")
        st.session_state.parent_name=pname
        st.divider(); st.markdown("**导航**")
        for icon,label,page in [("🏠","概览","home"),("📊","学习报告","report"),("📋","今日任务","tasks")]:
            active=st.session_state.p_page==page
            if st.button(f"{icon} {label}",key=f"p_{page}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.p_page=page; st.rerun()
        st.divider()
        if st.button("🔙 切换身份",key="p_back",use_container_width=True):
            st.session_state.portal="login"; st.rerun()

    if not pm: st.error("请先配置路径。"); return
    page=st.session_state.p_page
    if page=="home":    _p_home(pm,cm)
    elif page=="report": _p_report(pm,cm)
    elif page=="tasks":  _p_tasks(pm,cm,matcher)

def _p_home(pm,cm):
    st.markdown("## 👨‍👩‍👧 家长端概览")
    pname=st.session_state.get("parent_name","")
    if not pname: st.info("请在左侧输入你的姓名。"); return
    children=cm.children(pname)
    with st.expander("➕ 绑定孩子的账号"):
        not_linked=[u for u in pm.list_users() if u not in children]
        if not_linked:
            to_link=st.multiselect("选择要绑定的学习者账号",not_linked,key="link_children")
            if st.button("确认绑定",key="confirm_link"):
                [cm.link_parent(pname,c) for c in to_link]; st.success(f"已绑定 {len(to_link)} 个账号"); st.rerun()
        else: st.info("所有学习者已绑定")
    if not children: st.info("还没有绑定孩子的账号，请先绑定。"); return
    profiles=_allp(pm); today=datetime.now().strftime("%Y-%m-%d")
    for child in children:
        p=profiles.get(child,{})
        if not p: st.warning(f"⚠️ 找不到「{child}」的档案"); continue
        levels=p.get("omni_levels",{}); overall=levels.get("overall",0)
        cefr,cn=level_to_cefr(overall) if overall else ("--","未测试")
        active=p.get("achievements",{}).get("last_study_date","")==today
        streak=p.get("achievements",{}).get("streak_days",0)
        st.markdown(f"""
<div style="background:white;border-radius:14px;padding:18px;
border:2px solid {'#10B981' if active else '#E5E7EB'};margin-bottom:14px;">
  <div style="display:flex;justify-content:space-between;">
    <span style="font-size:1.15rem;font-weight:900;">{'🟢' if active else '⚪'} {child}
      <span style="color:#6B7280;font-size:.9rem;font-weight:400;margin-left:8px;">{'今日已学习' if active else '今日未学习'}</span>
    </span>
    <span style="font-size:1.2rem;font-weight:900;color:#0F4C81;">L{overall}
      <span style="color:#6B7280;font-size:.9rem;font-weight:400;"> · {cefr} · {cn}</span>
    </span>
  </div>
  <div style="margin-top:10px;font-size:1rem;">🔥 连续 <b>{streak}天</b></div>
</div>""",unsafe_allow_html=True)
        tested_sk=[(sk,lv) for sk in ["listening","reading","vocabulary","grammar"]
                   if (lv:=levels.get(sk,0))>0]
        if tested_sk:
            scols=st.columns(len(tested_sk))
            for i,(sk,lv) in enumerate(tested_sk):
                c,_=level_to_cefr(lv)
                with scols[i]:
                    st.markdown(f"{SKILL_ICONS.get(sk,'')} **{SKILL_CN.get(sk,sk)}** L{lv} · {c}")
                    st.markdown(_skbar(lv),unsafe_allow_html=True)

def _p_report(pm,cm):
    st.markdown("## 📊 学习报告")
    pname=st.session_state.get("parent_name","")
    if not pname: st.info("请先在左侧输入你的姓名。"); return
    children=cm.children(pname)
    if not children: st.info("还没有绑定孩子账号。"); return
    profiles=_allp(pm); child=st.selectbox("选择孩子",children)
    p=profiles.get(child,{})
    if not p: st.warning("找不到档案"); return
    levels=p.get("omni_levels",{}); hist=p.get("learning_history",{}); ach=p.get("achievements",{})
    overall=levels.get("overall",0); cefr,cn=level_to_cefr(overall) if overall else ("--","--")
    st.markdown(f"### 📈 {child} 的学习报告")
    c1,c2,c3=st.columns(3)
    c1.metric("综合等级",f"L{overall}",f"{cefr} · {cn}")
    c2.metric("连续学习",f"{ach.get('streak_days',0)}天")
    c3.metric("总学习时长",f"{int(hist.get('total_minutes',0))}分钟")
    st.divider(); st.markdown("**技能等级（IRT 已测项目）**")
    for sk in ["listening","reading","vocabulary","grammar"]:
        lv=levels.get(sk,0)
        if lv>0:
            cefr_s,_=level_to_cefr(lv)
            c1,c2=st.columns([2,8])
            with c1: st.markdown(f"{SKILL_ICONS.get(sk,'')} **{SKILL_CN.get(sk,sk)}** L{lv} · {cefr_s}")
            with c2: st.markdown(_skbar(lv),unsafe_allow_html=True)
    st.divider()
    weak=hist.get("weak_points",[]); strong=hist.get("strong_points",[])
    col1,col2=st.columns(2)
    with col1:
        st.markdown("**📍 需要加强**")
        [st.markdown(f"⚠️ {w}") for w in weak] if weak else st.success("暂无薄弱点")
    with col2:
        st.markdown("**⭐ 表现优秀**")
        [st.markdown(f"🌟 {s}") for s in strong] if strong else st.info("继续加油！")

def _p_tasks(pm,cm,matcher):
    st.markdown("## 📋 今日任务")
    pname=st.session_state.get("parent_name","")
    if not pname: st.info("请先在左侧输入你的姓名。"); return
    children=cm.children(pname)
    if not children: st.info("请先绑定孩子账号。"); return
    profiles=_allp(pm); child=st.selectbox("选择孩子",children,key="p_task_child")
    p=profiles.get(child,{})
    if not p: st.warning("找不到档案"); return
    tab1,tab2=st.tabs(["🤖 AI推荐今日任务","✏️ 手动布置任务"])
    with tab1:
        ov=p.get("omni_levels",{}).get("overall",20); cefr,cn=level_to_cefr(ov) if ov else ("--","--")
        st.info(f"{child} 当前综合等级：L{ov} · {cefr} · {cn}")
        if matcher and st.button("🔍 生成今日推荐",type="primary",use_container_width=True):
            with st.spinner("正在匹配最适合的内容..."):
                daily=matcher.get_daily_recommendation(p,n_items=4)
            for card in daily.get("cards",[]):
                sk=card.get("card_type","reading"); lv=card.get("level",0)
                cefr_s,_=level_to_cefr(lv) if lv else ("--","--")
                st.markdown(f"""<div class="task-card">
  <b>{SKILL_ICONS.get(sk,'📌')} {SKILL_CN.get(sk,sk)}</b>　
  <span style="color:#0369A1;">L{lv} · {cefr_s}</span><br>
  <span style="font-weight:700;font-size:1rem;">{card.get('title','')[:40]}</span>
</div>""",unsafe_allow_html=True)
    with tab2:
        task_type=st.selectbox("任务类型",["📖 阅读","🎧 听力","✍️ 写作","🗣️ 口语","📝 词汇","🎵 唱歌"],key="p_tt")
        task_title=st.text_input("任务内容",placeholder="如：读5页绘本",key="p_ti")
        task_note=st.text_area("备注",placeholder="特别提醒...",height=80,key="p_tn")
        if st.button("✅ 布置任务",type="primary",use_container_width=True,key="p_pub"):
            if task_title:
                classes=cm.all(); assigned=False
                for cls in classes:
                    if child in cls.get("students",[]):
                        cm.assign_task(cls["class_id"],{"type":task_type,"title":task_title,
                            "desc":task_note,"due":"今天","skill":"综合","from_parent":pname}); assigned=True
                (st.success if assigned else st.warning)(
                    f"✅ 已给 {child} 布置任务：{task_title}" if assigned
                    else "该孩子不在任何班级，任务未关联班级。")
            else: st.warning("请输入任务内容")

# ══════════════════════════════════════════════════════
# 管理员后台
# ══════════════════════════════════════════════════════
def _admin():
    pm=_pm(st.session_state.data_dir); lib=st.session_state.library_dir or st.session_state.data_dir
    matcher=_mat(lib) if _CM_OK else None; cm=_cm(st.session_state.data_dir)
    with st.sidebar:
        st.markdown("""<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:2rem;">🛡️</div>
  <div style="font-weight:900;font-size:1rem;">OMNI 管理员后台</div>
  <div style="font-size:.7rem;opacity:.7;">学员管理 · 班级 · 数据看板</div>
</div>""",unsafe_allow_html=True)
        st.divider()
        with st.expander("⚙️ 路径配置",expanded=False):
            dd=st.text_input("用户数据目录",value=st.session_state.data_dir,key="a_dd")
            ld=st.text_input("内容库目录",value=st.session_state.library_dir,key="a_ld")
            if st.button("✅ 确认路径",key="a_path",use_container_width=True):
                st.session_state.data_dir=dd.strip().strip("\"'"); st.session_state.library_dir=ld.strip().strip("\"'"); st.rerun()
        st.divider(); st.markdown("**导航**")
        for icon,label,page in [("👥","学员管理","students"),("🏫","班级管理","classes"),
                                  ("📚","内容库","content"),("📊","数据看板","stats")]:
            active=st.session_state.a_page==page
            if st.button(f"{icon} {label}",key=f"a_{page}",use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.a_page=page; st.rerun()
        st.divider()
        if st.button("🔙 切换身份",key="a_back",use_container_width=True):
            st.session_state.portal="login"; st.rerun()

    if not pm: st.error("请先配置路径。"); return
    page=st.session_state.a_page
    if page=="students": _a_students(pm)
    elif page=="classes": _a_classes(pm,cm)
    elif page=="content": _a_content(matcher)
    elif page=="stats":   _a_stats(pm)

def _a_students(pm):
    st.markdown("### 👥 学员账户管理")
    with st.expander("➕ 添加新学员",expanded=False):
        with st.form("admin_add"):
            ac1,ac2=st.columns(2)
            with ac1:
                new_nick=st.text_input("昵称 *",placeholder="如：小明")
                new_age=st.text_input("年龄参考",placeholder="如：10岁")
            with ac2:
                new_tier=st.selectbox("套餐类型",list(TIERS.keys()),format_func=lambda x:TIERS[x])
                expire_days=st.number_input("有效天数",min_value=1,max_value=3650,value=365)
            new_goal=st.selectbox("学习目标",["兴趣爱好","小学英语提升","初中备考","高中备考",
                "出国留学","剑桥考试（YLE/KET/PET/FCE）","国际学校（IB/AP/A-Level）","职业发展","其他"])
            if st.form_submit_button("✅ 创建学员",type="primary"):
                if new_nick.strip():
                    prof=pm.create_user(new_nick.strip(),new_age,new_goal,new_tier)
                    expire=(datetime.now()+timedelta(days=int(expire_days))).strftime("%Y-%m-%d")
                    prof["subscription"]["expire_date"]=expire; pm.save_user(prof)
                    st.success(f"✅ 学员「{new_nick}」创建成功！"); st.rerun()
                else: st.warning("请填写昵称")
    st.divider()
    users=pm.list_users()
    if not users: st.info("暂无学员。"); return
    fq=st.text_input("🔍 搜索学员",placeholder="输入昵称...",label_visibility="collapsed",key="admin_filter")
    if fq: users=[u for u in users if fq.lower() in u.lower()]
    st.caption(f"共 {len(users)} 位学员")
    for username in users:
        prof=pm.load_user(username)
        if not prof: continue
        sub=prof.get("subscription",{}); tier=sub.get("tier","basic")
        expire=sub.get("expire_date","—"); ov=prof.get("omni_levels",{}).get("overall",0)
        done=prof.get("diagnostic_done",False)
        label=f"👤 {username}  ·  {TIERS.get(tier,tier)}  ·  {'L'+str(ov) if ov else '未测试'}"
        with st.expander(label,expanded=False):
            mc1,mc2=st.columns(2)
            mc1.metric("综合等级",f"L{ov}" if ov else "未测试")
            mc2.metric("入学测试","✅ 完成" if done else "❌ 未完成")
            with st.form(f"admin_edit_{username}"):
                ec1,ec2=st.columns(2)
                with ec1:
                    new_tier_sel=st.selectbox("套餐类型",list(TIERS.keys()),
                        index=list(TIERS.keys()).index(tier) if tier in TIERS else 0,
                        format_func=lambda x:TIERS[x],key=f"tier_{username}")
                    new_expire=st.text_input("到期日 (YYYY-MM-DD)",value=expire,key=f"exp_{username}")
                with ec2:
                    new_goal=st.text_input("学习目标",value=prof.get("learning_goal",""),key=f"goal_{username}")
                    manual_lv=st.number_input("手动设置综合等级（0=不修改）",min_value=0,max_value=100,value=0,key=f"lv_{username}")
                sc1,sc2=st.columns([4,1])
                with sc1:
                    if st.form_submit_button("💾 保存",type="primary",use_container_width=True):
                        prof["subscription"]["tier"]=new_tier_sel; prof["subscription"]["expire_date"]=new_expire
                        if new_goal: prof["learning_goal"]=new_goal
                        if manual_lv>0: prof["omni_levels"]["overall"]=manual_lv; prof["diagnostic_done"]=True
                        pm.save_user(prof); st.success(f"「{username}」已更新。"); st.rerun()
                with sc2:
                    if st.form_submit_button("🗑️ 删除",use_container_width=True):
                        path=pm._path(username)
                        if path.exists(): path.unlink()
                        st.rerun()

def _a_classes(pm,cm):
    st.markdown("### 🏫 班级管理")
    classes=cm.all(); all_users=pm.list_users()
    with st.expander("➕ 新建班级",expanded=False):
        with st.form("new_cls"):
            cc1,cc2=st.columns(2)
            with cc1: cn=st.text_input("班级名称 *"); cg=st.text_input("年级")
            with cc2: ct=st.text_input("教师名称"); cd=st.text_input("备注")
            if st.form_submit_button("创建",type="primary"):
                if cn.strip():
                    cm.create(cn,cg,ct or "管理员",cd); st.success(f"班级「{cn}」已创建！"); st.rerun()
                else: st.warning("请填写班级名称")
    st.divider()
    if not classes: st.info("暂无班级，请先创建。"); return
    for cls in classes:
        students=cls.get("students",[]); cid=cls["class_id"]
        with st.expander(f"🏫 {cls['name']}  ·  {len(students)}名学员",expanded=False):
            if students: st.markdown("**当前学员：** "+"、".join(students))
            else: st.caption("（暂无学员）")
            with st.form(f"cls_edit_{cid}"):
                available=[u for u in all_users if u not in students]
                ec1,ec2=st.columns(2)
                with ec1: add_sel=st.selectbox("添加学员",["（不添加）"]+available,key=f"cadd_{cid}")
                with ec2: rm_sel=st.selectbox("移除学员",["（不移除）"]+students,key=f"crm_{cid}")
                bc1,bc2,bc3=st.columns(3)
                with bc1:
                    if st.form_submit_button("➕ 添加"):
                        if add_sel!="（不添加）": cm.add_student(cid,add_sel); st.rerun()
                with bc2:
                    if st.form_submit_button("➖ 移除"):
                        if rm_sel!="（不移除）" and rm_sel in students: cm.rm_student(cid,rm_sel); st.rerun()
                with bc3:
                    if st.form_submit_button("🗑️ 删除班级"):
                        cm.delete(cid); st.rerun()

def _a_content(matcher):
    st.markdown("### 📚 内容库概况")
    if not matcher: st.warning("内容匹配器未加载，请检查路径配置。"); return
    stats=matcher.get_library_stats()
    if not stats: st.info("内容库为空，请先构建各库 JSON 文件。"); return
    icons={"教材":"📕","绘本":"📗","影音":"🎬","电影":"🎥"}
    cols=st.columns(len(stats)); total=0
    for i,(name,count) in enumerate(stats.items()):
        with cols[i]: st.metric(f"{icons.get(name,'📄')} {name}",count,"条目"); total+=count
    st.success(f"内容库总计：**{total}** 条目  （路径：`{st.session_state.library_dir}`）")

def _a_stats(pm):
    st.markdown("### 📊 全局数据看板")
    users=pm.list_users()
    if not users: st.info("暂无学员数据。"); return
    total=len(users); tested=0; tier_dist={}; lv_dist={}; streaks=[]
    for u in users:
        p=pm.load_user(u)
        if not p: continue
        if p.get("diagnostic_done"): tested+=1
        tier=p.get("subscription",{}).get("tier","basic"); tier_dist[tier]=tier_dist.get(tier,0)+1
        lv=p.get("omni_levels",{}).get("overall",0)
        bucket=("未测试" if lv==0 else "L1-10" if lv<=10 else "L11-20" if lv<=20
                else "L21-30" if lv<=30 else "L31-50" if lv<=50 else "L51+")
        lv_dist[bucket]=lv_dist.get(bucket,0)+1
        streaks.append(p.get("achievements",{}).get("streak_days",0))
    c1,c2,c3,c4=st.columns(4)
    c1.metric("总学员数",total); c2.metric("已完成入学测试",tested)
    c3.metric("测试完成率",f"{tested/total:.0%}" if total else "0%")
    c4.metric("最长连续天数",max(streaks) if streaks else 0,"天")
    st.divider(); ca,cb=st.columns(2)
    with ca:
        st.markdown("**套餐分布**")
        for t,cnt in sorted(tier_dist.items()):
            pct=cnt/total*100 if total else 0; st.markdown(f"- {TIERS.get(t,t)}：**{cnt}** 人（{pct:.0f}%）")
    with cb:
        st.markdown("**能力等级分布**")
        for bucket in ["未测试","L1-10","L11-20","L21-30","L31-50","L51+"]:
            cnt=lv_dist.get(bucket,0)
            if cnt:
                pct=cnt/total*100 if total else 0
                st.markdown(f"- {bucket}：{'█'*int(pct/5)} **{cnt}** 人")

# ══════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════
def main():
    portal=st.session_state.portal

    if portal=="login":
        with st.sidebar:
            st.markdown("""<div style="text-align:center;padding:16px 0 8px;">
  <div style="font-size:2.2rem;">🦉</div>
  <div style="font-weight:900;font-size:1.1rem;letter-spacing:2px;">OMNI-LEARN OS</div>
  <div style="font-size:.7rem;opacity:.7;">全阶英语学习系统</div>
</div>""",unsafe_allow_html=True)
            st.divider()
            with st.expander("⚙️ 路径配置",expanded=True):
                dd=st.text_input("用户数据目录",value=st.session_state.data_dir,
                    key="login_dd")
                ld=st.text_input("内容库目录",value=st.session_state.library_dir,
                    key="login_ld")
                if st.button("✅ 确认路径",use_container_width=True,key="login_path"):
                    st.session_state.data_dir=dd.strip().strip("\"'")
                    st.session_state.library_dir=ld.strip().strip("\"'"); st.rerun()
                for k,s in [("login_dd","data_dir"),("login_ld","library_dir")]:
                    v=st.session_state.get(k,"")
                    if v is not None: st.session_state[s]=v.strip().strip("\"'")
        _login(); return

    if portal=="student":
        if not _UP_OK: st.error(f"user_profile.py 加载失败：{_UP_ERR}"); return
        pm,profile=_stu_sb()
        if not pm: return
        if not profile:
            st.markdown("""<div style="text-align:center;padding:60px 20px;">
  <div style="font-size:3rem;">👤</div><h2>请在左侧选择或创建学习者</h2>
</div>""",unsafe_allow_html=True); return
        lib=st.session_state.library_dir or st.session_state.data_dir
        matcher=_mat(lib) if _CM_OK else None
        mode=st.session_state.mode
        if   mode=="home":         _home(pm,matcher,profile)
        elif mode=="curriculum":   _curriculum(pm,matcher,profile)
        elif mode=="explorer":     _explorer(pm,matcher,profile)
        elif mode=="profile":      _profile_page(pm,matcher,profile)
        elif mode=="placement":    _render_placement(pm,profile)
        else:                      _home(pm,matcher,profile)

    elif portal=="teacher": _teacher()
    elif portal=="parent":  _parent()
    elif portal=="admin":   _admin()

if __name__=="__main__":
    main()
