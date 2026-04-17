"""
OMNI-LEARN OS — 用户画像系统（完整合并版）
user_profile.py

包含：
  ① 完整诊断测试25题 + 动态等级更新
  ② 订阅权限系统 basic/pro/family + check_access()
  ③ get_stage() / get_scaffold_hint() 发展阶段
  ④ ExplorationTracker 探索行为完整记录器

运行：
  streamlit run omni_dashboard.py（被 dashboard 调用）
  python user_profile.py（CLI 测试）
"""

import json
import os
import re
import sys
import time
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st

# ══════════════════════════════════════════════════════
# 常量
# ══════════════════════════════════════════════════════
SKILLS = ["listening", "speaking", "reading", "writing", "vocabulary", "grammar"]

SKILL_CN = {
    "listening": "听力", "speaking": "口语", "reading": "阅读",
    "writing": "写作", "vocabulary": "词汇", "grammar": "语法",
    "overall": "综合",
}
SKILL_ICONS = {
    "listening": "🎧", "speaking": "🗣️", "reading": "📖",
    "writing": "✍️", "vocabulary": "📝", "grammar": "📐",
    "overall": "🌟",
}

# 订阅套餐
SUBSCRIPTION_TIERS = {
    "basic": {
        "name": "Basic（基础）",
        "explorer_mode": True,
        "curriculum_mode": False,
        "full_library": False,
        "max_textbooks": 0,
    },
    "pro": {
        "name": "Pro（全库）",
        "explorer_mode": True,
        "curriculum_mode": True,
        "full_library": True,
        "max_textbooks": 999,
    },
    "family": {
        "name": "Family（家庭）",
        "explorer_mode": True,
        "curriculum_mode": True,
        "full_library": True,
        "max_textbooks": 999,
    },
}

# OMNI 等级 → CEFR
def level_to_cefr(level: int) -> tuple[str, str]:
    if level <= 0:   return ("Pre-A1", "启蒙前")
    if level <= 5:   return ("Pre-A1", "启蒙期")
    if level <= 15:  return ("A1",     "入门级")
    if level <= 25:  return ("A2",     "基础级")
    if level <= 35:  return ("B1",     "进阶级")
    if level <= 50:  return ("B2",     "中高级")
    if level <= 65:  return ("C1",     "高级")
    if level <= 80:  return ("C2",     "精通级")
    return ("C2+", "卓越级")

# 发展阶段
STAGES = [
    {"id": "S1", "name": "感知游戏期", "icon": "🌱", "range": (1,  15),
     "hint": "大量感官输入，游戏化体验，不强调产出"},
    {"id": "S2", "name": "规则建构期", "icon": "🌿", "range": (16, 35),
     "hint": "开始理解规则，鼓励模仿和有引导的输出"},
    {"id": "S3", "name": "批判建构期", "icon": "🌳", "range": (36, 55),
     "hint": "批判性思维，自主分析，多元输出"},
    {"id": "S4", "name": "自主精通期", "icon": "🦅", "range": (56, 100),
     "hint": "自主学习，深度探索，创造性产出"},
]

def get_stage(level: int) -> dict:
    for s in STAGES:
        lo, hi = s["range"]
        if lo <= level <= hi:
            return s
    return STAGES[-1]

def get_scaffold_hint(level: int) -> tuple[str, str]:
    """返回 (提示文字, 标签)"""
    if level <= 15:  return ("需要完整引导和示范", "完整引导")
    if level <= 35:  return ("提供部分支架，鼓励尝试", "部分引导")
    if level <= 55:  return ("最小化支架，激活自主思考", "最小引导")
    return ("完全自主探索", "自主")

# ══════════════════════════════════════════════════════
# ProfileManager
# ══════════════════════════════════════════════════════
class ProfileManager:
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.profiles_dir = self.data_dir / "user_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, nickname: str) -> Path:
        safe = re.sub(r'[\\/:*?"<>|]', '_', nickname)
        return self.profiles_dir / f"{safe}.json"

    def list_users(self) -> list[str]:
        return sorted([
            p.stem for p in self.profiles_dir.glob("*.json")
        ])

    def load_user(self, nickname: str) -> Optional[dict]:
        p = self._path(nickname)
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def save_user(self, profile: dict):
        p = self._path(profile["nickname"])
        with open(p, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def create_user(self, nickname: str, age_ref: str = "",
                    goal: str = "兴趣爱好", tier: str = "pro") -> dict:
        tier_info = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["pro"])
        profile = {
            "nickname":    nickname,
            "age_reference": age_ref,
            "learning_goal": goal,
            "created_at":  datetime.now().isoformat(),
            "subscription": {
                "tier":      tier,
                "tier_name": tier_info["name"],
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "expire_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
            },
            "omni_levels": {
                "listening": 0, "speaking": 0, "reading": 0,
                "writing": 0, "vocabulary": 0, "grammar": 0,
                "overall": 0,
            },
            "interests": [],
            "learning_history": {
                "completed_units":   [],
                "explored_topics":   [],
                "weak_points":       [],
                "strong_points":     [],
                "recent_content_ids": [],
            },
            "achievements": {
                "streak_days":     0,
                "last_study_date": "",
                "total_sessions":  0,
            },
            "diagnostic_done": False,
        }
        self.save_user(profile)
        return profile

    def check_access(self, profile: dict, feature: str) -> bool:
        tier = profile.get("subscription", {}).get("tier", "basic")
        tier_info = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["basic"])
        return bool(tier_info.get(feature, False))

    def get_subscription_info(self, profile: dict) -> dict:
        sub = profile.get("subscription", {})
        tier = sub.get("tier", "basic")
        tier_info = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["basic"])
        expire = sub.get("expire_date", "")
        try:
            days_left = (datetime.strptime(expire, "%Y-%m-%d") - datetime.now()).days
        except Exception:
            days_left = 0
        return {
            "tier":      tier,
            "tier_name": tier_info["name"],
            "days_left": max(0, days_left),
        }

    def set_levels_manually(self, profile: dict, levels: dict):
        for sk, lv in levels.items():
            if sk in profile["omni_levels"]:
                profile["omni_levels"][sk] = lv
        vals = [profile["omni_levels"][sk] for sk in SKILLS
                if profile["omni_levels"][sk] > 0]
        profile["omni_levels"]["overall"] = int(sum(vals)/len(vals)) if vals else 0
        profile["diagnostic_done"] = True
        self.save_user(profile)

    def update_level_after_session(self, profile: dict, skill: str,
                                   score_ratio: float):
        """学习后动态更新等级（score_ratio: 0-1）"""
        cur = profile["omni_levels"].get(skill, 0)
        if cur == 0:
            return
        if score_ratio >= 0.85:
            delta = 1
        elif score_ratio >= 0.65:
            delta = 0
        else:
            delta = -1

        max_lv = 100 if skill == "reading" else 90
        new_lv = max(1, min(max_lv, cur + delta))
        profile["omni_levels"][skill] = new_lv

        vals = [profile["omni_levels"][sk] for sk in SKILLS
                if profile["omni_levels"][sk] > 0]
        profile["omni_levels"]["overall"] = int(sum(vals)/len(vals)) if vals else 0

        self._update_weak_strong(profile, skill, score_ratio)
        self._update_streak(profile)
        self.save_user(profile)

    def _update_weak_strong(self, profile: dict, skill: str, score: float):
        hist  = profile.setdefault("learning_history", {})
        sn    = SKILL_CN.get(skill, skill)
        weak  = hist.setdefault("weak_points", [])
        strong = hist.setdefault("strong_points", [])
        if score < 0.65 and sn not in weak:
            weak.append(sn)
            if sn in strong: strong.remove(sn)
        elif score >= 0.85 and sn not in strong:
            strong.append(sn)
            if sn in weak: weak.remove(sn)
        hist["weak_points"]   = weak[-5:]
        hist["strong_points"] = strong[-5:]

    def _update_streak(self, profile: dict):
        ach   = profile.setdefault("achievements", {})
        today = datetime.now().strftime("%Y-%m-%d")
        last  = ach.get("last_study_date", "")
        yest  = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
        if last == today:
            pass
        elif last == yest:
            ach["streak_days"] = ach.get("streak_days", 0) + 1
        else:
            ach["streak_days"] = 1
        ach["last_study_date"] = today

    # ── 诊断测试 UI ──
    DIAG_QUESTIONS = [
        # (skill, level, question_cn, options, answer_idx)
        ("vocabulary", 8,  "Which word means 'happy'?",
         ["sad","glad","angry","tired"], 1),
        ("vocabulary", 10, "What color is the sky?",
         ["red","green","blue","black"], 2),
        ("grammar",    12, "She ___ a student.",
         ["am","is","are","be"], 1),
        ("reading",    14, "The dog is big. The cat is small. Which is bigger?",
         ["cat","dog","both","neither"], 1),
        ("vocabulary", 16, "Which word means 'to look at'?",
         ["listen","see","smell","touch"], 1),
        ("grammar",    18, "They ___ playing football now.",
         ["is","am","are","be"], 2),
        ("reading",    20, "Tom goes to school every day. He likes math. What does Tom like?",
         ["sports","music","math","art"], 2),
        ("vocabulary", 22, "What does 'ancient' mean?",
         ["new","very old","beautiful","dangerous"], 1),
        ("grammar",    24, "I ___ to the park yesterday.",
         ["go","goes","went","going"], 2),
        ("reading",    26, "The more you read, the more you know. What does this mean?",
         ["Reading is boring","Reading helps you learn","Books are expensive","Libraries are big"], 1),
        ("vocabulary", 28, "What is a 'habitat'?",
         ["A type of food","A place where animals live","A kind of weather","A school subject"], 1),
        ("grammar",    30, "By the time she arrived, the movie ___.",
         ["starts","has started","had started","will start"], 2),
        ("reading",    32, "Renewable energy sources, such as solar and wind power, are becoming increasingly important. What are renewable energy sources?",
         ["Coal and oil","Solar and wind power","Nuclear energy","Natural gas"], 1),
        ("vocabulary", 34, "What does 'eloquent' mean?",
         ["Silent","Well-spoken","Angry","Confused"], 1),
        ("grammar",    36, "___ he studied hard, he failed the exam.",
         ["Although","Because","So","If"], 0),
        ("reading",    38, "The protagonist of the novel undergoes significant character development. What does 'protagonist' mean?",
         ["The villain","The main character","The narrator","The author"], 1),
        ("vocabulary", 40, "What does 'ambiguous' mean?",
         ["Very clear","Having two or more possible meanings","Completely wrong","Extremely important"], 1),
        ("grammar",    42, "The report ___ by the committee before the deadline.",
         ["must submit","must be submitted","must have submitted","must be submitting"], 1),
        ("reading",    44, "Economic inequality refers to the unequal distribution of income and opportunity. What is economic inequality about?",
         ["Equal pay for all","Unequal distribution of wealth","Government policies","Business strategies"], 1),
        ("vocabulary", 46, "What does 'ephemeral' mean?",
         ["Permanent","Long-lasting","Short-lived","Ancient"], 2),
        ("grammar",    48, "Not only ___ the exam, but she also won a scholarship.",
         ["she passed","did she pass","she did pass","passed she"], 1),
        ("reading",    50, "Cognitive dissonance occurs when a person holds contradictory beliefs simultaneously. What is cognitive dissonance?",
         ["Holding contradictory beliefs","Strong memory","Clear thinking","Emotional intelligence"], 0),
        ("vocabulary", 52, "What does 'paradigm' mean?",
         ["A typical example or pattern","A type of grammar","An old book","A scientific experiment"], 0),
        ("grammar",    54, "___ the circumstances, the decision was justified.",
         ["Given","Giving","Give","To give"], 0),
        ("reading",    55, "The hegemony of certain nations in global politics has been a subject of intense debate. What does 'hegemony' mean?",
         ["Leadership or dominance","Economic policy","Military strength","Cultural exchange"], 0),
    ]

    def run_diagnostic_ui(self, nickname: str):
        """在 Streamlit 中渲染诊断测试"""
        profile = self.load_user(nickname)
        if not profile:
            st.error("用户不存在")
            return

        if "diag_step" not in st.session_state:
            st.session_state.diag_step    = 0
            st.session_state.diag_answers = []
            st.session_state.diag_done    = False

        total = len(self.DIAG_QUESTIONS)
        step  = st.session_state.diag_step

        if st.session_state.diag_done:
            self._show_diag_result(profile, st.session_state.diag_answers)
            return

        if step >= total:
            st.session_state.diag_done = True
            st.rerun()
            return

        # 进度条
        st.progress(step / total, text=f"第 {step+1} / {total} 题")

        sk, lv, q, opts, ans = self.DIAG_QUESTIONS[step]
        c, cn = level_to_cefr(lv)
        st.markdown(f"""
<div style="background:#F5F3FF;border-radius:10px;padding:16px;margin-bottom:12px;">
  <div style="font-size:.75rem;color:#7C3AED;margin-bottom:8px;">
    {SKILL_ICONS.get(sk,'📄')} {SKILL_CN.get(sk,sk)} · L{lv} ({c})
  </div>
  <div style="font-size:1.05rem;font-weight:600;">{q}</div>
</div>""", unsafe_allow_html=True)

        for i, opt in enumerate(opts):
            if st.button(f"{'ABCD'[i]}. {opt}", key=f"diag_{step}_{i}",
                         use_container_width=True):
                correct = (i == ans)
                st.session_state.diag_answers.append({
                    "skill": sk, "level": lv,
                    "correct": correct,
                })
                st.session_state.diag_step += 1
                st.rerun()

    def _show_diag_result(self, profile: dict, answers: list):
        """计算并保存诊断结果"""
        skill_scores = {sk: {"correct":0,"total":0,"levels":[]} for sk in SKILLS}
        for a in answers:
            sk = a["skill"]
            skill_scores[sk]["total"]  += 1
            skill_scores[sk]["correct"] += int(a["correct"])
            skill_scores[sk]["levels"].append(a["level"])

        new_levels = {}
        for sk in SKILLS:
            d = skill_scores[sk]
            if d["total"] == 0:
                new_levels[sk] = 20
                continue
            ratio = d["correct"] / d["total"]
            avg_lv = sum(d["levels"]) / len(d["levels"]) if d["levels"] else 20
            if ratio >= 0.8:
                new_levels[sk] = min(int(avg_lv * 1.1) + 2, 90)
            elif ratio >= 0.6:
                new_levels[sk] = int(avg_lv)
            else:
                new_levels[sk] = max(8, int(avg_lv * 0.85))

        self.set_levels_manually(profile, new_levels)

        overall = profile["omni_levels"]["overall"]
        cefr, cn = level_to_cefr(overall)
        stage = get_stage(overall)

        st.balloons()
        st.success(f"测试完成！综合等级：L{overall} · {cefr}（{cn}）")
        st.markdown(f"**{stage['icon']} {stage['name']}** — {stage['hint']}")

        cols = st.columns(3)
        for i, sk in enumerate(SKILLS):
            lv = profile["omni_levels"][sk]
            c, _ = level_to_cefr(lv)
            with cols[i % 3]:
                st.metric(f"{SKILL_ICONS[sk]} {SKILL_CN[sk]}", f"L{lv}", c)

        if st.button("🏠 进入主页", type="primary", use_container_width=True):
            st.session_state.diag_step    = 0
            st.session_state.diag_answers = []
            st.session_state.diag_done    = False
            st.session_state.mode         = "home"
            st.rerun()

# ══════════════════════════════════════════════════════
# ExplorationTracker
# ══════════════════════════════════════════════════════
class ExplorationTracker:
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.exp_dir  = self.data_dir / "exploration_profiles"
        self.exp_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, nickname: str) -> Path:
        safe = re.sub(r'[\\/:*?"<>|]', '_', nickname)
        return self.exp_dir / f"{safe}_exploration.json"

    def _load(self, nickname: str) -> dict:
        p = self._path(nickname)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return self._empty(nickname)

    def _save(self, nickname: str, data: dict):
        with open(self._path(nickname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _empty(self, nickname: str) -> dict:
        return {
            "nickname":          nickname,
            "total_sessions":    0,
            "total_minutes":     0,
            "sessions":          [],
            "search_history":    [],
            "entry_preference":  {e: 0 for e in
                ["story","video","music","game","topic","career","science","write"]},
            "strategy_preference": {s: 0 for s in
                ["balanced","interest","weakness","strength"]},
            "topic_heatmap":     {},
            "lib_preference":    {},
            "skill_exploration": {sk: 0 for sk in SKILLS},
            "reflections":       [],
        }

    def start_session(self, nickname: str, omni_level: int,
                      stage_id: str, stage_name: str,
                      search_query: str = "", entry: str = "",
                      strategy: str = "balanced") -> str:
        sid = f"exp_{int(time.time()*1000)}"
        data = self._load(nickname)
        data["sessions"].append({
            "session_id":    sid,
            "date":          datetime.now().strftime("%Y-%m-%d"),
            "start_time":    datetime.now().isoformat(),
            "end_time":      None,
            "omni_level":    omni_level,
            "stage_id":      stage_id,
            "stage_name":    stage_name,
            "search_query":  search_query,
            "entry":         entry,
            "strategy":      strategy,
            "contents":      [],
            "reflection":    "",
            "duration_min":  0,
        })
        data["total_sessions"] = data.get("total_sessions", 0) + 1
        if entry and entry in data["entry_preference"]:
            data["entry_preference"][entry] += 1
        if strategy in data["strategy_preference"]:
            data["strategy_preference"][strategy] += 1
        self._save(nickname, data)
        return sid

    def end_session(self, nickname: str, session_id: str, duration_min: int = 0):
        data = self._load(nickname)
        for s in data["sessions"]:
            if s["session_id"] == session_id:
                s["end_time"]    = datetime.now().isoformat()
                s["duration_min"] = duration_min
                break
        data["total_minutes"] = data.get("total_minutes", 0) + duration_min
        data["sessions"] = data["sessions"][-200:]
        self._save(nickname, data)

    def record_content_view(self, nickname: str, item: dict, action: str = "view"):
        """记录内容查看行为（简化版，不需要 session_id）"""
        data = self._load(nickname)
        lib  = item.get("_lib_source", "")
        tags = item.get("knowledge_tree", {}).get("level_2_tags", [])
        for tag in tags:
            data["topic_heatmap"][tag] = data["topic_heatmap"].get(tag, 0) + 1
        if lib:
            data["lib_preference"][lib] = data["lib_preference"].get(lib, 0) + 1
        self._save(nickname, data)

    def record_search(self, nickname: str, query: str):
        data = self._load(nickname)
        hist = data.setdefault("search_history", [])
        if query and (not hist or hist[0] != query):
            hist.insert(0, query)
        data["search_history"] = hist[:50]
        self._save(nickname, data)

    def exp_reflection(self, nickname: str, text: str):
        data = self._load(nickname)
        data.setdefault("reflections", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "text": text,
        })
        data["reflections"] = data["reflections"][:20]
        self._save(nickname, data)

    def get_search_history(self, nickname: str, n: int = 6) -> list:
        return self._load(nickname).get("search_history", [])[:n]

    def get_stats_summary(self, nickname: str) -> dict:
        data = self._load(nickname)
        ep   = data.get("entry_preference", {})
        sp   = data.get("strategy_preference", {})
        return {
            "total_sessions":  data.get("total_sessions", 0),
            "total_minutes":   data.get("total_minutes", 0),
            "search_count":    len(data.get("search_history", [])),
            "topics_explored": len(data.get("topic_heatmap", {})),
            "fav_entry":       max(ep.items(), key=lambda x: x[1], default=("story",0))[0],
            "fav_strategy":    max(sp.items(), key=lambda x: x[1], default=("balanced",0))[0],
        }


# ══════════════════════════════════════════════════════
# CLI 测试
# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./test_data"
    print(f"测试 user_profile.py | 数据目录: {data_dir}")
    pm = ProfileManager(data_dir=data_dir)
    p  = pm.create_user("测试小明", "8岁", "小学英语", tier="pro")
    print(f"✅ 创建用户: {p['nickname']} · {p['subscription']['tier_name']}")
    pm.set_levels_manually(p, {"listening":22,"reading":25,"speaking":18,
                                "writing":15,"vocabulary":24,"grammar":20})
    ov = p["omni_levels"]["overall"]
    sg = get_stage(ov)
    print(f"✅ 综合等级 L{ov} · {sg['icon']} {sg['name']}")
    tracker = ExplorationTracker(data_dir=data_dir)
    tracker.record_search("测试小明", "恐龙英语")
    print(f"✅ 搜索历史: {tracker.get_search_history('测试小明')}")
    print("全部通过 ✅")
