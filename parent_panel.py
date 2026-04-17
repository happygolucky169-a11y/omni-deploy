"""
OMNI-LEARN OS — 家长管理面板
parent_panel.py

功能：
  · 绑定孩子的学习账号
  · 查看孩子的学习进度和等级
  · 查看四技能详细报告
  · AI推荐今日学习内容
  · 手动给孩子布置任务
  · 导出孩子的学习报告

使用：
  streamlit run parent_panel.py

依赖（同目录）：
  user_profile.py, content_matcher.py
"""

"""
OMNI-LEARN OS — 管理面板
admin_panel.py

支持两种角色：
  👩‍🏫 老师端：管理多个班级，批量分配任务，查看全班进度
  👨‍👩‍👧  家长端：管理自己的孩子，查看学习报告，设置今日任务

支持 100 名学生同时使用。

使用：
  streamlit run admin_panel.py

依赖：
  pip install streamlit plotly
  同目录需要：user_profile.py, content_matcher.py
"""

import streamlit as st
import json
import os
import sys
import time
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from user_profile import ProfileManager, SKILL_CN, SKILL_ICONS, level_to_cefr, SKILLS
from content_matcher import ContentMatcher

# ══════════════════════════════════════════════════════
# 页面配置
# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="OMNI 家长端",
    page_icon="👨\u200d👩\u200d👧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans SC', sans-serif; }

:root {
  --teacher: #0F4C81;
  --parent:  #059669;
  --accent:  #F59E0B;
  --danger:  #DC2626;
}

.role-card {
  border-radius:14px; padding:20px; cursor:pointer;
  transition:transform .15s, box-shadow .15s;
  border:2px solid transparent; text-align:center;
}
.role-card:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.12); }
.role-teacher { background:linear-gradient(135deg,#0F4C81,#1565C0); color:white; }
.role-parent  { background:linear-gradient(135deg,#059669,#10B981); color:white; }

.stat-card {
  background:white; border-radius:12px; padding:16px;
  border:1px solid #E5E7EB; text-align:center;
  box-shadow:0 1px 4px rgba(0,0,0,.05);
}
.stat-num  { font-size:2rem; font-weight:900; color:#0F4C81; }
.stat-label{ font-size:.8rem; color:#6B7280; margin-top:4px; }

.student-row {
  background:white; border-radius:10px; padding:12px 16px;
  margin-bottom:6px; border:1px solid #E5E7EB;
  display:flex; align-items:center; gap:12px;
}
.class-card {
  background:white; border-radius:12px; padding:16px;
  border:1px solid #E5E7EB; cursor:pointer;
  transition:all .15s; margin-bottom:8px;
}
.class-card:hover { border-color:#0F4C81; box-shadow:0 4px 12px rgba(15,76,129,.1); }

.task-card {
  background:#F0F9FF; border-radius:10px; padding:12px 14px;
  margin-bottom:6px; border-left:3px solid #0284C7;
}
.badge {
  display:inline-block; padding:2px 8px; border-radius:8px;
  font-size:.72rem; font-weight:700; margin-right:4px;
}
.badge-A1   { background:#D1FAE5; color:#065F46; }
.badge-A2   { background:#DBEAFE; color:#1E40AF; }
.badge-B1   { background:#EDE9FE; color:#5B21B6; }
.badge-B2   { background:#FEF3C7; color:#92400E; }
.badge-C1   { background:#FCE7F3; color:#9D174D; }
.badge-preA1{ background:#F3F4F6; color:#374151; }
footer { visibility:hidden; }
#MainMenu { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# Session State
# ══════════════════════════════════════════════════════

defaults = {
    "current_page":    "home",
    "selected_class":  None,
    "selected_student":None,
    "data_dir":        "",
    "library_dir":     "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════
# 班级数据管理
# ══════════════════════════════════════════════════════

class ClassManager:
    """管理班级数据（classes.json）"""

    def __init__(self, data_dir: str):
        self.data_dir   = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.class_file = self.data_dir / "classes.json"
        self._data      = self._load()

    def _load(self) -> dict:
        if self.class_file.exists():
            try:
                with open(self.class_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"classes": {}, "parent_links": {}}

    def _save(self):
        with open(self.class_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ── 班级 CRUD ──

    def list_classes(self) -> list[dict]:
        return list(self._data["classes"].values())

    def get_class(self, class_id: str) -> Optional[dict]:
        return self._data["classes"].get(class_id)

    def create_class(self, name: str, grade: str,
                     teacher: str, goal: str = "") -> dict:
        class_id = f"cls_{int(time.time())}"
        cls = {
            "class_id":   class_id,
            "name":       name,
            "grade":      grade,
            "teacher":    teacher,
            "goal":       goal,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "students":   [],        # nickname 列表
            "tasks":      [],        # 已分配任务列表
            "textbook":   "",        # 当前教材
            "current_unit": 0,
        }
        self._data["classes"][class_id] = cls
        self._save()
        return cls

    def update_class(self, class_id: str, **kwargs):
        if class_id in self._data["classes"]:
            self._data["classes"][class_id].update(kwargs)
            self._save()

    def delete_class(self, class_id: str):
        self._data["classes"].pop(class_id, None)
        self._save()

    # ── 学生管理 ──

    def add_student(self, class_id: str, nickname: str) -> bool:
        cls = self._data["classes"].get(class_id)
        if cls and nickname not in cls["students"]:
            cls["students"].append(nickname)
            self._save()
            return True
        return False

    def remove_student(self, class_id: str, nickname: str):
        cls = self._data["classes"].get(class_id)
        if cls and nickname in cls["students"]:
            cls["students"].remove(nickname)
            self._save()

    # ── 任务分配 ──

    def assign_task(self, class_id: str, task: dict):
        cls = self._data["classes"].get(class_id)
        if cls:
            task["assigned_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            task["task_id"]     = f"task_{int(time.time())}"
            cls["tasks"].append(task)
            cls["tasks"] = cls["tasks"][-50:]  # 只保留最近50条
            self._save()

    # ── 家长端：绑定孩子 ──

    def link_parent(self, parent_name: str, child_nickname: str):
        links = self._data.setdefault("parent_links", {})
        children = links.setdefault(parent_name, [])
        if child_nickname not in children:
            children.append(child_nickname)
            self._save()

    def get_children(self, parent_name: str) -> list[str]:
        return self._data.get("parent_links", {}).get(parent_name, [])


# ══════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════

def get_level_badge(lv: int) -> str:
    if lv == 0:
        return '<span class="badge badge-preA1">未测试</span>'
    cefr, _ = level_to_cefr(lv)
    cls_map = {"Pre-A1": "preA1", "A1": "A1", "A2": "A2",
               "B1": "B1", "B2": "B2", "C1": "C1"}
    cls = cls_map.get(cefr, "preA1")
    return f'<span class="badge badge-{cls}">L{lv}·{cefr}</span>'


def load_all_profiles(pm: ProfileManager) -> dict:
    """加载所有用户画像，返回 {nickname: profile}"""
    profiles = {}
    for name in pm.list_users():
        p = pm.load_user(name)
        if p:
            profiles[name] = p
    return profiles


def render_skill_bar(lv: int, max_lv: int = 90) -> str:
    pct = min(100, lv / max_lv * 100)
    color = ("#84cc16" if lv <= 15 else "#10b981" if lv <= 25
             else "#3b82f6" if lv <= 35 else "#8b5cf6"
             if lv <= 55 else "#f59e0b")
    return f"""
<div style="height:6px;background:#E5E7EB;border-radius:3px;overflow:hidden;">
  <div style="width:{pct:.0f}%;height:100%;background:{color};border-radius:3px;"></div>
</div>"""


@st.cache_resource
def get_pm(data_dir: str) -> ProfileManager:
    return ProfileManager(data_dir=data_dir)


@st.cache_resource
def get_matcher(lib_dir: str) -> ContentMatcher:
    return ContentMatcher(library_dir=lib_dir)


@st.cache_resource
def get_cm(data_dir: str) -> ClassManager:
    return ClassManager(data_dir=data_dir)


# ══════════════════════════════════════════════════════
# 侧边栏
# ══════════════════════════════════════════════════════

def render_role_select():
    st.markdown("## 👋 欢迎使用 OMNI 管理面板")
    st.markdown("请选择你的身份：")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
<div class="role-card role-teacher">
  <div style="font-size:3rem;">👩‍🏫</div>
  <div style="font-size:1.3rem;font-weight:900;margin:8px 0;">老师端</div>
  <div style="font-size:.85rem;opacity:.9;">
    管理多个班级<br>
    批量分配任务<br>
    查看全班学情<br>
    导出进度报告
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("进入老师端 →", key="enter_teacher",
                     use_container_width=True, type="primary"):
            st.session_state.role = "teacher"
            st.rerun()

    with col2:
        st.markdown("""
<div class="role-card role-parent">
  <div style="font-size:3rem;">👨‍👩‍👧</div>
  <div style="font-size:1.3rem;font-weight:900;margin:8px 0;">家长端</div>
  <div style="font-size:.85rem;opacity:.9;">
    管理我的孩子<br>
    查看学习进度<br>
    分配今日任务<br>
    接收学习报告
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("进入家长端 →", key="enter_parent",
                     use_container_width=True, type="primary"):
            st.session_state.role = "parent"
            st.rerun()


# ══════════════════════════════════════════════════════
# 老师端
# ══════════════════════════════════════════════════════

def render_parent_home(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 👨‍👩‍👧 家长端概览")

    # 家长身份输入
    if "parent_name" not in st.session_state:
        st.session_state.parent_name = ""

    parent_name = st.text_input(
        "你的姓名（用于关联孩子）",
        value=st.session_state.parent_name,
        placeholder="如：张妈妈",
    )
    if parent_name != st.session_state.parent_name:
        st.session_state.parent_name = parent_name
        st.rerun()

    if not parent_name:
        st.info("请输入你的姓名")
        return

    children = cm.get_children(parent_name)

    # 绑定孩子
    with st.expander("➕ 绑定孩子的账号"):
        all_users = pm.list_users()
        not_linked = [u for u in all_users if u not in children]
        if not_linked:
            to_link = st.multiselect(
                "选择要绑定的学习者账号",
                not_linked,
                key="link_children"
            )
            if st.button("确认绑定", key="confirm_link"):
                for child in to_link:
                    cm.link_parent(parent_name, child)
                st.success(f"已绑定 {len(to_link)} 个账号")
                st.rerun()
        else:
            st.info("所有学习者已绑定")

    if not children:
        st.info("还没有绑定孩子的账号，请先绑定。")
        return

    # 孩子概览卡
    st.markdown(f"### 我的孩子（{len(children)}人）")
    profiles = load_all_profiles(pm)

    for child in children:
        profile = profiles.get(child, {})
        if not profile:
            st.warning(f"⚠️ 找不到「{child}」的档案")
            continue

        levels = profile.get("omni_levels", {})
        ach    = profile.get("achievements", {})
        hist   = profile.get("learning_history", {})
        overall = levels.get("overall", 0)
        cefr, cn = level_to_cefr(overall) if overall > 0 else ("--", "未测试")
        today  = datetime.now().strftime("%Y-%m-%d")
        active = ach.get("last_study_date", "") == today
        streak = ach.get("streak_days", 0)

        with st.container():
            st.markdown(f"""
<div style="background:white;border-radius:14px;padding:16px;
border:2px solid {'#10B981' if active else '#E5E7EB'};
margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <span style="font-size:1.1rem;font-weight:900;">
        {'🟢' if active else '⚪'} {child}
      </span>
      <span style="color:#6B7280;font-size:.85rem;margin-left:8px;">
        {'今日已学习' if active else '今日未学习'}
      </span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:1.2rem;font-weight:900;color:#0F4C81;">
        L{overall}
      </span>
      <span style="color:#6B7280;font-size:.85rem;"> · {cefr} · {cn}</span>
    </div>
  </div>
  <div style="margin-top:10px;display:flex;gap:16px;flex-wrap:wrap;">
    <span>🔥 连续学习 <b>{streak}天</b></span>
    <span>⏱ 累计 <b>{int(hist.get('total_minutes',0))}分钟</b></span>
    <span>📚 完成单元 <b>{len(hist.get('completed_units',[]))}个</b></span>
  </div>
</div>
""", unsafe_allow_html=True)

            # 四技能等级条
            skill_cols = st.columns(4)
            for i, skill in enumerate(["listening","reading","speaking","writing"]):
                lv = levels.get(skill, 0)
                c, _ = level_to_cefr(lv) if lv > 0 else ("--", "")
                with skill_cols[i]:
                    st.markdown(
                        f"{SKILL_ICONS.get(skill,'')} "
                        f"**{SKILL_CN.get(skill,skill)}** L{lv} · {c}"
                    )
                    if lv > 0:
                        st.markdown(
                            render_skill_bar(lv),
                            unsafe_allow_html=True
                        )


def render_parent_report(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 📊 学习报告")

    parent_name = st.session_state.get("parent_name", "")
    if not parent_name:
        st.info("请先在「概览」页输入你的姓名。")
        return

    children = cm.get_children(parent_name)
    if not children:
        st.info("还没有绑定孩子账号。")
        return

    profiles = load_all_profiles(pm)
    child    = st.selectbox("选择孩子", children)
    profile  = profiles.get(child, {})
    if not profile:
        st.warning("找不到档案")
        return

    levels  = profile.get("omni_levels", {})
    hist    = profile.get("learning_history", {})
    ach     = profile.get("achievements", {})
    overall = levels.get("overall", 0)

    st.markdown(f"### 📈 {child} 的学习报告")

    # 综合等级
    c1, c2, c3 = st.columns(3)
    cefr, cn = level_to_cefr(overall) if overall > 0 else ("--", "--")
    c1.metric("综合等级", f"L{overall}", f"{cefr} · {cn}")
    c2.metric("连续学习", f"{ach.get('streak_days',0)}天")
    c3.metric("总学习时长", f"{int(hist.get('total_minutes',0))}分钟")

    st.divider()

    # 四技能明细
    st.markdown("**四项技能等级**")
    for skill in ["listening", "reading", "speaking", "writing"]:
        lv = levels.get(skill, 0)
        cefr_s, cn_s = level_to_cefr(lv) if lv > 0 else ("--", "--")
        col1, col2 = st.columns([2, 8])
        with col1:
            st.markdown(
                f"{SKILL_ICONS.get(skill,'')} "
                f"**{SKILL_CN.get(skill,skill)}** L{lv} · {cefr_s}"
            )
        with col2:
            if lv > 0:
                st.markdown(render_skill_bar(lv), unsafe_allow_html=True)

    # 弱点与优势
    st.divider()
    weak   = hist.get("weak_points", [])
    strong = hist.get("strong_points", [])
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📍 需要加强**")
        for w in weak:
            st.markdown(f"⚠️ {w}")
        if not weak:
            st.success("暂无薄弱点")
    with col2:
        st.markdown("**⭐ 表现优秀**")
        for s in strong:
            st.markdown(f"🌟 {s}")
        if not strong:
            st.info("继续加油！")

    # 已完成单元
    completed = hist.get("completed_units", [])
    if completed:
        st.divider()
        st.markdown(f"**✅ 已完成单元（{len(completed)}个）**")
        for u in completed[-10:]:
            st.markdown(f"✓ {u}")

    # 导出
    st.divider()
    if st.button("📥 导出孩子的学习报告", use_container_width=True):
        lines = [
            f"# {child} 的 OMNI-LEARN OS 学习报告",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 综合等级",
            f"- 综合：L{overall} · {cefr} · {cn}",
            f"- 听力：L{levels.get('listening',0)}",
            f"- 阅读：L{levels.get('reading',0)}",
            f"- 口语：L{levels.get('speaking',0)}",
            f"- 写作：L{levels.get('writing',0)}",
            "",
            f"## 学习统计",
            f"- 连续学习：{ach.get('streak_days',0)}天",
            f"- 总学习时长：{int(hist.get('total_minutes',0))}分钟",
            f"- 完成单元数：{len(completed)}个",
            "",
            "## 薄弱点",
            "\n".join(f"- {w}" for w in weak) or "- 暂无",
            "",
            "## 优势点",
            "\n".join(f"- {s}" for s in strong) or "- 继续加油",
        ]
        st.download_button(
            "⬇️ 下载报告",
            "\n".join(lines).encode("utf-8"),
            f"OMNI报告_{child}_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown",
            use_container_width=True,
        )


def render_parent_tasks(pm: ProfileManager, cm: ClassManager,
                         matcher: ContentMatcher):
    st.markdown("## 📋 今日任务")

    parent_name = st.session_state.get("parent_name", "")
    if not parent_name:
        st.info("请先在「概览」页输入你的姓名。")
        return

    children = cm.get_children(parent_name)
    if not children:
        st.info("请先绑定孩子账号。")
        return

    profiles = load_all_profiles(pm)
    child    = st.selectbox("选择孩子", children)
    profile  = profiles.get(child, {})

    if not profile:
        st.warning("找不到档案")
        return

    tab1, tab2 = st.tabs(["🤖 AI推荐今日任务", "✏️ 手动指定任务"])

    with tab1:
        st.markdown(f"**根据 {child} 的当前水平，AI推荐今日学习内容：**")
        overall = profile.get("omni_levels", {}).get("overall", 20)
        cefr, cn = level_to_cefr(overall) if overall > 0 else ("--", "--")
        st.info(f"当前综合等级：L{overall} · {cefr} · {cn}")

        if st.button("🔍 生成今日推荐", type="primary",
                     use_container_width=True):
            with st.spinner("正在匹配最适合的内容..."):
                daily = matcher.get_daily_recommendation(profile, n_items=4)
            if daily["cards"]:
                for card in daily["cards"]:
                    skill = card.get("card_type", "reading")
                    lv    = card.get("level", 0)
                    icon  = SKILL_ICONS.get(skill, "📌")
                    cn_s  = SKILL_CN.get(skill, skill)
                    cefr_s, _ = level_to_cefr(lv) if lv > 0 else ("--", "--")
                    st.markdown(f"""
<div class="task-card">
  <b>{icon} {cn_s}</b>　
  <span style="color:#0369A1;">L{lv} · {cefr_s}</span><br>
  <span style="font-weight:700;">{card.get('title','')[:40]}</span>　
  <span style="color:#6B7280;font-size:.82rem;">
    {card.get('description','')[:30]}　⏱ {card.get('duration_hint','')}
  </span>
</div>
""", unsafe_allow_html=True)
            else:
                st.warning("暂无推荐，请确认内容库路径配置正确。")

    with tab2:
        st.markdown("**手动给孩子指定今日任务：**")
        task_type = st.selectbox(
            "任务类型",
            ["📖 阅读", "🎧 听力", "✍️ 写作", "🗣️ 口语", "📝 词汇", "🎵 唱歌"],
            key="parent_task_type"
        )
        task_title = st.text_input("任务内容", placeholder="如：读5页绘本",
                                   key="parent_task_title")
        task_note  = st.text_area("备注", placeholder="特别提醒...",
                                  height=80, key="parent_task_note")

        if st.button("✅ 布置任务", type="primary",
                     use_container_width=True):
            if task_title:
                # 找到孩子所在的班级并写入任务
                classes = cm.list_classes()
                assigned = False
                for cls in classes:
                    if child in cls.get("students", []):
                        cm.assign_task(cls["class_id"], {
                            "type":       task_type,
                            "title":      task_title,
                            "desc":       task_note,
                            "due":        "今天",
                            "skill":      "综合",
                            "from_parent": parent_name,
                        })
                        assigned = True
                if assigned:
                    st.success(f"✅ 已给 {child} 布置任务：{task_title}")
                else:
                    st.warning("该孩子不在任何班级，任务已记录但未关联班级。")


# ══════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════
# 家长端侧边栏
# ══════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
<div style="text-align:center;padding:10px 0;">
  <div style="font-size:1.8rem;">👨\u200d👩\u200d👧</div>
  <div style="font-weight:900;font-size:1rem;color:#059669;">OMNI 家长端</div>
  <div style="font-size:.72rem;color:#6B7280;">孩子学习 · 实时追踪 · 任务管理</div>
</div>
""", unsafe_allow_html=True)
        st.divider()

        with st.expander("📁 路径配置",
                         expanded=not st.session_state.data_dir):
            data_dir = st.text_input(
                "用户数据目录",
                value=st.session_state.data_dir,
                placeholder=r"C:\Users\Administrator\Desktop\omni-data",
            )
            lib_dir = st.text_input(
                "内容库目录",
                value=st.session_state.library_dir,
                placeholder=r"C:\Users\Administrator\Desktop",
            )
            if st.button("✅ 确认", use_container_width=True):
                st.session_state.data_dir    = data_dir.strip().strip('"\'\' ')
                st.session_state.library_dir = lib_dir.strip().strip('"\'\' ')
                st.rerun()

        if not st.session_state.data_dir:
            st.warning("请先配置路径")
            return None, None, None

        pm      = get_pm(st.session_state.data_dir)
        cm      = get_cm(st.session_state.data_dir)
        lib     = st.session_state.library_dir or st.session_state.data_dir
        matcher = get_matcher(lib)

        # 家长姓名
        st.divider()
        parent_name = st.text_input(
            "📛 你的姓名",
            value=st.session_state.get("parent_name", ""),
            placeholder="如：张妈妈",
        )
        st.session_state.parent_name = parent_name

        st.divider()
        st.markdown("**导航**")
        nav = [
            ("🏠", "概览",     "home"),
            ("👧", "我的孩子", "children"),
            ("📊", "学习报告", "report"),
            ("📋", "今日任务", "tasks"),
        ]
        for icon, label, page in nav:
            active = st.session_state.current_page == page
            if st.button(f"{icon} {label}", key=f"nav_{page}",
                         use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.current_page = page
                st.rerun()

        return pm, cm, matcher


# ══════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════

def main():
    pm, cm, matcher = render_sidebar()

    if not pm or not cm:
        st.markdown("""
## 👨‍👩‍👧 OMNI 家长管理面板

请在左侧配置路径后开始使用。

**功能：**
- 👧 绑定并管理孩子的学习账号
- 📊 实时查看孩子的英语水平进展
- 📋 AI推荐今日学习内容 / 手动布置任务
- 📤 导出孩子的学习报告
        """)
        return

    page = st.session_state.current_page
    if page in ("home", "children"):
        render_parent_home(pm, cm)
    elif page == "report":
        render_parent_report(pm, cm)
    elif page == "tasks":
        render_parent_tasks(pm, cm, matcher)


if __name__ == "__main__":
    main()
