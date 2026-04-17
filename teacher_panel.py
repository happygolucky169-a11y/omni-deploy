"""
OMNI-LEARN OS — 老师管理面板
teacher_panel.py

功能：
  · 创建/管理多个班级
  · 添加/移除学生
  · 批量分配学习任务
  · 全班学情分析
  · 导出学习报告

使用：
  streamlit run teacher_panel.py

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
    page_title="OMNI 老师端",
    page_icon="👩\u200d🏫",
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

def render_teacher_home(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 👩‍🏫 老师端概览")

    classes  = cm.list_classes()
    profiles = load_all_profiles(pm)
    all_students = set()
    for cls in classes:
        all_students.update(cls.get("students", []))

    # 统计卡
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-num">{len(classes)}</div>
  <div class="stat-label">班级数量</div>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-num">{len(all_students)}</div>
  <div class="stat-label">学生总数</div>
</div>""", unsafe_allow_html=True)
    with c3:
        active = sum(1 for n in all_students
                     if n in profiles and
                     profiles[n].get("achievements", {}).get(
                         "last_study_date", "") ==
                     datetime.now().strftime("%Y-%m-%d"))
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-num">{active}</div>
  <div class="stat-label">今日活跃</div>
</div>""", unsafe_allow_html=True)
    with c4:
        tested = sum(1 for n in all_students
                     if n in profiles and
                     profiles[n].get("diagnostic", {}).get("completed"))
        pct = int(tested / max(len(all_students), 1) * 100)
        st.markdown(f"""
<div class="stat-card">
  <div class="stat-num">{pct}%</div>
  <div class="stat-label">已完成测试</div>
</div>""", unsafe_allow_html=True)

    st.divider()

    # 班级列表快览
    if not classes:
        st.info("还没有班级，点击左侧「班级管理」创建第一个班级。")
        return

    st.markdown("### 班级快览")
    for cls in classes:
        students = cls.get("students", [])
        n = len(students)
        avg_lv = 0
        if students:
            lvs = [profiles[s]["omni_levels"].get("overall", 0)
                   for s in students if s in profiles]
            avg_lv = int(sum(lvs) / len(lvs)) if lvs else 0

        cefr, cn = level_to_cefr(avg_lv) if avg_lv > 0 else ("--", "未测试")

        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
        with col1:
            st.markdown(f"**🏫 {cls['name']}** · {cls.get('grade','')}")
        with col2:
            st.markdown(f"👥 {n}名学生")
        with col3:
            st.markdown(f"📊 均 L{avg_lv} · {cefr}")
        with col4:
            tasks = cls.get("tasks", [])
            st.markdown(f"📋 {len(tasks)}个任务")
        with col5:
            if st.button("管理", key=f"mgr_{cls['class_id']}",
                         use_container_width=True):
                st.session_state.selected_class = cls["class_id"]
                st.session_state.current_page   = "classes"
                st.rerun()
        st.divider()


def render_teacher_classes(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 🏫 班级管理")

    tab1, tab2 = st.tabs(["📋 班级列表", "➕ 创建班级"])

    with tab1:
        classes  = cm.list_classes()
        profiles = load_all_profiles(pm)

        if not classes:
            st.info("还没有班级，切换到「创建班级」标签创建。")
        else:
            for cls in classes:
                is_selected = (st.session_state.selected_class ==
                               cls["class_id"])
                border = "2px solid #0F4C81" if is_selected else "1px solid #E5E7EB"
                st.markdown(f"""
<div class="class-card" style="border:{border};">
  <b>🏫 {cls['name']}</b>　{cls.get('grade','')}　
  <span style="color:#6B7280;font-size:.85rem;">
    教师：{cls.get('teacher','')} ·
    创建：{cls.get('created_at','')}
  </span>
</div>
""", unsafe_allow_html=True)

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if st.button("📊 查看详情",
                                 key=f"detail_{cls['class_id']}",
                                 use_container_width=True):
                        st.session_state.selected_class = cls["class_id"]
                        st.rerun()
                with c2:
                    if st.button("📋 分配任务",
                                 key=f"task_{cls['class_id']}",
                                 use_container_width=True):
                        st.session_state.selected_class = cls["class_id"]
                        st.session_state.current_page   = "tasks"
                        st.rerun()
                with c3:
                    if st.button("📤 导出报告",
                                 key=f"export_{cls['class_id']}",
                                 use_container_width=True):
                        st.session_state.selected_class = cls["class_id"]
                        st.session_state.current_page   = "export"
                        st.rerun()
                with c4:
                    if st.button("🗑️ 删除",
                                 key=f"del_{cls['class_id']}",
                                 use_container_width=True):
                        cm.delete_class(cls["class_id"])
                        st.success("已删除")
                        st.rerun()

                # 展开班级详情
                if st.session_state.selected_class == cls["class_id"]:
                    _render_class_detail(cls, profiles, pm, cm)

                st.divider()

    with tab2:
        with st.form("create_class_form"):
            st.markdown("**创建新班级**")
            col1, col2 = st.columns(2)
            with col1:
                name    = st.text_input("班级名称", placeholder="如：三年级A班")
                grade   = st.selectbox("年级",
                    ["幼儿园", "小学一年级", "小学二年级", "小学三年级",
                     "小学四年级", "小学五年级", "小学六年级",
                     "初一", "初二", "初三", "高一", "高二", "高三",
                     "大学", "成人", "混合年龄"])
            with col2:
                teacher = st.text_input("授课教师姓名", placeholder="如：张老师")
                goal    = st.text_input("学习目标",
                    placeholder="如：新课标英语A2水平")
            if st.form_submit_button("✅ 创建班级", type="primary",
                                     use_container_width=True):
                if name and teacher:
                    cls = cm.create_class(name, grade, teacher, goal)
                    st.success(f"✅ 班级「{name}」创建成功！")
                    st.session_state.selected_class = cls["class_id"]
                    st.rerun()


def _render_class_detail(cls: dict, profiles: dict,
                          pm: ProfileManager, cm: ClassManager):
    """展示班级详情：学生列表 + 等级分布"""
    students = cls.get("students", [])
    class_id = cls["class_id"]

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown(f"**👥 学生名单（{len(students)}人）**")

        # 添加学生
        all_users  = pm.list_users()
        not_in_cls = [u for u in all_users if u not in students]
        if not_in_cls:
            with st.expander("➕ 添加学生"):
                to_add = st.multiselect(
                    "选择要添加的学习者",
                    not_in_cls,
                    key=f"add_{class_id}"
                )
                if st.button("确认添加", key=f"confirm_add_{class_id}"):
                    for s in to_add:
                        cm.add_student(class_id, s)
                    st.success(f"已添加 {len(to_add)} 名学生")
                    st.rerun()

        # 学生列表
        for student in students:
            profile = profiles.get(student, {})
            overall = profile.get("omni_levels", {}).get("overall", 0)
            streak  = profile.get("achievements", {}).get("streak_days", 0)
            tested  = profile.get("diagnostic", {}).get("completed", False)
            last    = profile.get("achievements", {}).get("last_study_date", "")
            today   = datetime.now().strftime("%Y-%m-%d")
            active  = "🟢" if last == today else "⚪"

            col_a, col_b, col_c = st.columns([3, 3, 1])
            with col_a:
                st.markdown(
                    f"{active} **{student}** "
                    f"{'✅' if tested else '⚠️未测试'}"
                )
            with col_b:
                st.markdown(
                    f"L{overall} · 连续{streak}天",
                    unsafe_allow_html=True
                )
            with col_c:
                if st.button("移除", key=f"rm_{class_id}_{student}",
                             use_container_width=True):
                    cm.remove_student(class_id, student)
                    st.rerun()

    with col_right:
        st.markdown("**📊 等级分布**")
        if not students:
            st.info("暂无学生")
        else:
            # 等级区间统计
            buckets = {"Pre-A1(L1-15)": 0, "A1(L16-25)": 0,
                       "A2(L26-35)": 0,  "B1(L36-55)": 0,
                       "B2+(L56+)": 0,   "未测试": 0}
            for s in students:
                lv = profiles.get(s, {}).get(
                    "omni_levels", {}).get("overall", 0)
                if lv == 0:
                    buckets["未测试"] += 1
                elif lv <= 15:
                    buckets["Pre-A1(L1-15)"] += 1
                elif lv <= 25:
                    buckets["A1(L16-25)"] += 1
                elif lv <= 35:
                    buckets["A2(L26-35)"] += 1
                elif lv <= 55:
                    buckets["B1(L36-55)"] += 1
                else:
                    buckets["B2+(L56+)"] += 1

            total = max(len(students), 1)
            for bucket, count in buckets.items():
                if count == 0:
                    continue
                pct = count / total * 100
                st.markdown(
                    f"`{bucket}` **{count}人** ({pct:.0f}%)"
                )
                st.markdown(render_skill_bar(int(pct)),
                            unsafe_allow_html=True)

        # 设置教材
        st.markdown("**📚 当前教材**")
        current_tb = cls.get("textbook", "未设置")
        st.info(f"当前：{current_tb or '未设置'}")
        new_tb = st.text_input("设置教材名称",
                               placeholder="如：人教版G3上册",
                               key=f"tb_{class_id}")
        if st.button("保存教材设置", key=f"save_tb_{class_id}"):
            cm.update_class(class_id, textbook=new_tb)
            st.success("✅ 已保存")
            st.rerun()


def render_teacher_analytics(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 📊 学情分析")

    classes  = cm.list_classes()
    profiles = load_all_profiles(pm)

    if not classes:
        st.info("请先创建班级并添加学生。")
        return

    # 班级选择
    class_names = {c["class_id"]: c["name"] for c in classes}
    selected_id = st.selectbox(
        "选择班级",
        options=list(class_names.keys()),
        format_func=lambda x: class_names[x],
    )
    cls = cm.get_class(selected_id)
    if not cls:
        return

    students = cls.get("students", [])
    if not students:
        st.info("该班级暂无学生。")
        return

    st.markdown(f"### 🏫 {cls['name']} · {len(students)}名学生")

    # ── 四技能平均等级 ──
    st.markdown("**📈 全班四技能平均等级**")
    skill_avgs = {}
    for skill in ["listening", "reading", "speaking", "writing"]:
        lvs = [profiles[s]["omni_levels"].get(skill, 0)
               for s in students
               if s in profiles and
               profiles[s]["omni_levels"].get(skill, 0) > 0]
        skill_avgs[skill] = int(sum(lvs) / len(lvs)) if lvs else 0

    cols = st.columns(4)
    for i, (skill, avg) in enumerate(skill_avgs.items()):
        cefr, cn = level_to_cefr(avg) if avg > 0 else ("--", "--")
        with cols[i]:
            st.metric(
                f"{SKILL_ICONS.get(skill, '')} {SKILL_CN.get(skill, skill)}",
                f"L{avg}" if avg > 0 else "--",
                f"{cefr}"
            )

    st.divider()

    # ── 学生详细列表 ──
    st.markdown("**👥 学生明细（按综合等级排序）**")

    student_data = []
    for s in students:
        p = profiles.get(s, {})
        lvs = p.get("omni_levels", {})
        ach = p.get("achievements", {})
        hist = p.get("learning_history", {})
        student_data.append({
            "姓名": s,
            "综合": lvs.get("overall", 0),
            "听力": lvs.get("listening", 0),
            "阅读": lvs.get("reading", 0),
            "口语": lvs.get("speaking", 0),
            "写作": lvs.get("writing", 0),
            "连续天数": ach.get("streak_days", 0),
            "累计分钟": int(hist.get("total_minutes", 0)),
            "已测试": "✅" if p.get("diagnostic",{}).get("completed") else "⚠️",
        })

    student_data.sort(key=lambda x: -x["综合"])

    # 表格展示
    header_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1])
    headers = ["姓名", "综合", "听", "读", "说", "写", "连续", "总时长", "测试"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")
    st.divider()

    for row in student_data:
        row_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1])
        values = [
            row["姓名"],
            f"L{row['综合']}" if row["综合"] > 0 else "--",
            f"L{row['听力']}" if row["听力"] > 0 else "--",
            f"L{row['阅读']}" if row["阅读"] > 0 else "--",
            f"L{row['口语']}" if row["口语"] > 0 else "--",
            f"L{row['写作']}" if row["写作"] > 0 else "--",
            f"{row['连续天数']}天",
            f"{row['累计分钟']}分",
            row["已测试"],
        ]
        for col, val in zip(row_cols, values):
            col.markdown(str(val))

    # ── 薄弱点汇总 ──
    st.divider()
    st.markdown("**📍 全班薄弱点汇总**")
    weak_count = {}
    for s in students:
        p = profiles.get(s, {})
        for wp in p.get("learning_history", {}).get("weak_points", []):
            weak_count[wp] = weak_count.get(wp, 0) + 1

    if weak_count:
        sorted_weak = sorted(weak_count.items(), key=lambda x: -x[1])
        for wp, count in sorted_weak[:8]:
            pct = count / len(students) * 100
            col1, col2 = st.columns([3, 7])
            with col1:
                st.markdown(f"⚠️ **{wp}**（{count}人，{pct:.0f}%）")
            with col2:
                st.markdown(render_skill_bar(int(pct)),
                            unsafe_allow_html=True)
    else:
        st.success("暂无集中薄弱点！")


def render_teacher_tasks(pm: ProfileManager, cm: ClassManager,
                          matcher: ContentMatcher):
    st.markdown("## 📋 任务分配")

    classes = cm.list_classes()
    if not classes:
        st.info("请先创建班级。")
        return

    class_names = {c["class_id"]: c["name"] for c in classes}
    selected_id = st.selectbox(
        "选择班级",
        options=list(class_names.keys()),
        format_func=lambda x: class_names[x],
    )
    cls = cm.get_class(selected_id)
    if not cls:
        return

    st.divider()

    tab1, tab2 = st.tabs(["➕ 新建任务", "📋 已有任务"])

    with tab1:
        st.markdown(f"**为「{cls['name']}」分配任务**")

        task_type = st.selectbox(
            "任务类型",
            ["📖 阅读任务", "🎧 听力任务", "✍️ 写作任务",
             "🗣️ 口语任务", "📝 词汇任务", "🔤 语法任务",
             "📚 完成单元", "🎯 自由探索"]
        )
        task_title = st.text_input("任务标题",
                                   placeholder="如：阅读 Unit 3 课文")
        task_desc  = st.text_area("任务说明",
                                  placeholder="具体要求和注意事项...",
                                  height=100)
        col1, col2 = st.columns(2)
        with col1:
            due_days = st.selectbox("截止时间",
                                    ["今天", "明天", "3天内", "本周内", "本月内"])
        with col2:
            target_skill = st.selectbox(
                "目标技能",
                ["综合", "听力", "阅读", "口语", "写作", "词汇", "语法"]
            )

        # 自动推荐内容
        if st.checkbox("🔍 自动推荐相关资源"):
            profiles = load_all_profiles(pm)
            students = cls.get("students", [])
            if students:
                lvs = [profiles[s]["omni_levels"].get("overall", 20)
                       for s in students if s in profiles]
                avg_lv = int(sum(lvs) / len(lvs)) if lvs else 20

                skill_map = {
                    "阅读": "reading", "听力": "listening",
                    "口语": "speaking", "写作": "writing",
                    "词汇": "vocabulary", "语法": "grammar",
                }
                skill_key = skill_map.get(target_skill, "reading")
                items = matcher.match_skill(
                    skill=skill_key,
                    user_level=avg_lv,
                    top_k=3,
                )
                if items:
                    st.markdown(f"**推荐资源（班级均等级 L{avg_lv}）：**")
                    for item in items:
                        lv = item.get("omni_level", avg_lv)
                        title = item.get("title", "")[:40]
                        src = item.get("_lib_source", "")
                        score = item.get("_match_score", 0)
                        st.markdown(
                            f"- L{lv} · {title} · {src} "
                            f"（匹配{score:.0f}分）"
                        )

        if st.button("✅ 发布任务", type="primary", use_container_width=True):
            if task_title:
                task = {
                    "type":    task_type,
                    "title":   task_title,
                    "desc":    task_desc,
                    "due":     due_days,
                    "skill":   target_skill,
                    "class":   cls["name"],
                }
                cm.assign_task(selected_id, task)
                st.success(f"✅ 任务「{task_title}」已发布给{len(cls.get('students',[]))}名学生！")
                st.rerun()

    with tab2:
        tasks = cls.get("tasks", [])
        if not tasks:
            st.info("还没有发布任务。")
        else:
            for task in reversed(tasks[-20:]):
                st.markdown(f"""
<div class="task-card">
  <b>{task.get('type','')} {task.get('title','')}</b>
  <span style="color:#6B7280;font-size:.8rem;margin-left:8px;">
    截止：{task.get('due','')} · 技能：{task.get('skill','')}
    · 发布：{task.get('assigned_at','')[:10]}
  </span><br>
  <span style="color:#374151;font-size:.82rem;">{task.get('desc','')[:80]}</span>
</div>
""", unsafe_allow_html=True)


def render_teacher_export(pm: ProfileManager, cm: ClassManager):
    st.markdown("## 📤 导出学习报告")

    classes = cm.list_classes()
    if not classes:
        st.info("请先创建班级。")
        return

    class_names = {c["class_id"]: c["name"] for c in classes}
    selected_id = st.selectbox(
        "选择班级",
        options=list(class_names.keys()),
        format_func=lambda x: class_names[x],
    )
    cls = cm.get_class(selected_id)
    if not cls:
        return

    profiles = load_all_profiles(pm)
    students  = cls.get("students", [])

    report_type = st.selectbox("报告类型",
        ["📊 班级进度报告", "📈 个人详细报告", "📋 任务完成情况"])

    if st.button("📥 生成报告", type="primary", use_container_width=True):
        report_lines = []
        report_lines.append(f"# OMNI-LEARN OS 学习报告")
        report_lines.append(f"## {cls['name']} · {report_type}")
        report_lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report_lines.append(f"授课教师：{cls.get('teacher', '')}")
        report_lines.append("")

        if "班级进度" in report_type:
            report_lines.append("## 班级概况")
            report_lines.append(f"- 学生总数：{len(students)}人")
            tested = sum(1 for s in students
                         if profiles.get(s, {}).get(
                             "diagnostic", {}).get("completed"))
            report_lines.append(f"- 已完成测试：{tested}人")
            report_lines.append("")
            report_lines.append("## 学生等级汇总")
            report_lines.append("| 姓名 | 综合 | 听力 | 阅读 | 口语 | 写作 | 连续学习 |")
            report_lines.append("|------|------|------|------|------|------|---------|")
            for s in students:
                p  = profiles.get(s, {})
                lv = p.get("omni_levels", {})
                ach = p.get("achievements", {})
                report_lines.append(
                    f"| {s} | L{lv.get('overall',0)} | "
                    f"L{lv.get('listening',0)} | L{lv.get('reading',0)} | "
                    f"L{lv.get('speaking',0)} | L{lv.get('writing',0)} | "
                    f"{ach.get('streak_days',0)}天 |"
                )

        elif "任务完成" in report_type:
            report_lines.append("## 任务列表")
            for task in cls.get("tasks", [])[-20:]:
                report_lines.append(
                    f"- [{task.get('assigned_at','')[:10]}] "
                    f"{task.get('type','')} {task.get('title','')} "
                    f"（截止：{task.get('due','')}）"
                )

        report_text = "\n".join(report_lines)
        st.text_area("报告预览", report_text, height=400)
        st.download_button(
            "⬇️ 下载 Markdown 报告",
            report_text.encode("utf-8"),
            f"OMNI报告_{cls['name']}_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════
# 家长端
# ══════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════
# 老师端侧边栏
# ══════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
<div style="text-align:center;padding:10px 0;">
  <div style="font-size:1.8rem;">👩\u200d🏫</div>
  <div style="font-weight:900;font-size:1rem;color:#0F4C81;">OMNI 老师端</div>
  <div style="font-size:.72rem;color:#6B7280;">班级管理 · 学情分析 · 任务分配</div>
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

        st.divider()
        st.markdown("**导航**")
        nav = [
            ("🏠", "概览",     "home"),
            ("🏫", "班级管理", "classes"),
            ("📊", "学情分析", "analytics"),
            ("📋", "任务分配", "tasks"),
            ("📤", "导出报告", "export"),
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
## 👩‍🏫 OMNI 老师管理面板

请在左侧配置路径后开始使用。

**功能：**
- 🏫 创建和管理班级（最多支持100名学生）
- 📊 查看全班学情分析
- 📋 批量分配学习任务
- 📤 导出学习进度报告
        """)
        return

    page = st.session_state.current_page
    if page == "home":
        render_teacher_home(pm, cm)
    elif page == "classes":
        render_teacher_classes(pm, cm)
    elif page == "analytics":
        render_teacher_analytics(pm, cm)
    elif page == "tasks":
        render_teacher_tasks(pm, cm, matcher)
    elif page == "export":
        render_teacher_export(pm, cm)


if __name__ == "__main__":
    main()
