"""
OMNI-LEARN OS — Admin 行为数据面板
admin_behavior_panel.py

在 omni_dashboard.py 的 _admin() 函数中新增一个 Tab 调用此模块：

    from admin_behavior_panel import render_behavior_tab
    # 在 _admin() 的 tab 列表里加一项：
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["👤 学员管理","🏫 班级管理","📚 内容库","📊 全局看板","🔍 行为数据"]
    )
    with tab5:
        render_behavior_tab(pm)
"""

import streamlit as st
from datetime import datetime
from pathlib import Path

from user_profile import ProfileManager, SKILL_CN, SKILL_ICONS, level_to_cefr
from behavior_logger import BehaviorReader, MODULE_CN


def _fmt_time(sec: float) -> str:
    if sec >= 3600:
        return f"{sec/3600:.1f} 小时"
    if sec >= 60:
        return f"{sec/60:.0f} 分钟"
    return f"{int(sec)} 秒"


def _bar(pct: float, color: str = "#7C3AED") -> str:
    w = min(100, max(0, pct))
    return (f'<div style="height:8px;background:#E5E7EB;border-radius:4px;overflow:hidden;margin-top:2px;">'
            f'<div style="width:{w:.0f}%;height:100%;background:{color};border-radius:4px;"></div></div>')


def render_behavior_tab(pm: ProfileManager):
    st.markdown("### 🔍 行为数据分析")

    data_dir = st.session_state.get("data_dir", ".")
    reader   = BehaviorReader(data_dir)
    users    = pm.list_users()

    if not users:
        st.info("暂无学员数据。")
        return

    # ── 顶部：天数筛选 ──
    col_days, col_spacer = st.columns([1, 4])
    with col_days:
        days = st.selectbox("统计周期", [7, 14, 30, 90], index=2,
                            format_func=lambda x: f"最近 {x} 天")

    st.divider()

    # ══ 全局摘要 ══════════════════════════════════════
    st.markdown("#### 📊 全平台行为摘要")
    gs = reader.get_global_summary(users, days)

    mv = gs["module_visits_total"]
    mt = gs["module_time_total"]
    aa = gs["avg_accuracy"]
    ac = gs["avg_audio_completion"]
    total_visits = sum(mv.values()) or 1

    # 最受欢迎模块
    top_mod = max(mv, key=mv.get) if mv else "—"
    top_mod_cn = MODULE_CN.get(top_mod, top_mod)

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("今日活跃人数", gs["active_today_count"])
    g2.metric("最受欢迎模块", top_mod_cn)
    g3.metric("音频平均完成率",
              f"{ac:.0f}%" if ac is not None else "暂无数据")
    best_acc_mod = max(aa, key=aa.get) if aa else None
    g4.metric("答题最佳模块",
              f"{MODULE_CN.get(best_acc_mod, best_acc_mod)} {aa[best_acc_mod]:.0f}%" if best_acc_mod else "暂无")

    st.markdown("**各模块访问分布**")
    mod_order = sorted(mv.items(), key=lambda x: x[1], reverse=True)
    for mod, cnt in mod_order:
        pct = cnt / total_visits * 100
        cn  = MODULE_CN.get(mod, mod)
        t   = _fmt_time(mt.get(mod, 0))
        acc = f"  ·  正确率 {aa[mod]:.0f}%" if mod in aa else ""
        c1, c2 = st.columns([3, 7])
        with c1:
            st.markdown(f"**{cn}** · {cnt}次 · {t}{acc}")
        with c2:
            st.markdown(_bar(pct), unsafe_allow_html=True)

    st.divider()

    # ══ 单学员明细 ══════════════════════════════════
    st.markdown("#### 👤 单学员行为明细")

    fq = st.text_input("搜索学员", placeholder="输入昵称...",
                       label_visibility="collapsed", key="beh_filter")
    filtered = [u for u in users if fq.lower() in u.lower()] if fq else users

    for username in filtered:
        prof = pm.load_user(username)
        if not prof:
            continue

        s = reader.get_user_summary(username, days)
        total_t  = sum(s["module_time_sec"].values())
        total_q  = s["total_questions"]
        total_ok = s["total_correct"]
        acc_overall = round(total_ok / total_q * 100, 1) if total_q else 0
        ac_rate = s["audio_completion"]
        active_days = s["active_day_count"]

        # 卡片标题
        ov = prof.get("omni_levels", {}).get("overall", 0)
        label = (f"👤 {username}  ·  L{ov if ov else '未测试'}"
                 f"  ·  活跃{active_days}天"
                 f"  ·  总时长 {_fmt_time(total_t)}"
                 f"  ·  答题正确率 {acc_overall:.0f}%")

        with st.expander(label, expanded=False):

            # ── 4格核心指标 ──
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("活跃天数", f"{active_days} 天")
            r2.metric("总学习时长", _fmt_time(total_t))
            r3.metric("总答题数", total_q)
            r4.metric("整体正确率", f"{acc_overall:.0f}%" if total_q else "暂无")

            # ── 模块停留时长 ──
            mv_u  = s["module_visits"]
            mt_u  = s["module_time_sec"]
            acc_u = s["module_accuracy"]
            resp_u = s["avg_response_sec"]
            total_t_u = total_t or 1

            if mt_u:
                st.markdown("**⏱ 各模块停留时长**")
                for mod, sec in sorted(mt_u.items(), key=lambda x: x[1], reverse=True):
                    cn   = MODULE_CN.get(mod, mod)
                    pct  = sec / total_t_u * 100
                    vis  = mv_u.get(mod, 0)
                    acc  = acc_u.get(mod)
                    resp = resp_u.get(mod)
                    detail = f"{_fmt_time(sec)}  ·  {vis}次访问"
                    if acc is not None:
                        detail += f"  ·  正确率 {acc:.0f}%"
                    if resp:
                        detail += f"  ·  平均答题用时 {resp:.1f}秒"
                    c1, c2 = st.columns([3, 7])
                    with c1:
                        st.markdown(f"**{cn}** · {detail}")
                    with c2:
                        color = ("#06B6D4" if pct > 30 else
                                 "#7C3AED" if pct > 15 else "#94A3B8")
                        st.markdown(_bar(pct, color), unsafe_allow_html=True)

            # ── 答题响应时间 ──
            if resp_u:
                st.markdown("**⚡ 平均答题响应时间**（越短=越熟练）")
                cols = st.columns(len(resp_u))
                for i, (mod, sec) in enumerate(resp_u.items()):
                    cn = MODULE_CN.get(mod, mod)
                    cols[i].metric(cn, f"{sec:.1f} 秒")

            # ── 音频完成率 ──
            if ac_rate is not None:
                color = "🟢" if ac_rate >= 0.8 else "🟡" if ac_rate >= 0.5 else "🔴"
                st.metric(f"{color} 音频平均完成率",
                          f"{ac_rate*100:.0f}%",
                          help="听力/KTV 音频播放完成的平均比例")

            # ── 近期活跃日历 ──
            active_set = set(s["active_days"])
            if active_set:
                st.markdown("**📅 近期活跃记录**")
                from datetime import timedelta
                today = datetime.now().date()
                dots = ""
                for i in range(days - 1, -1, -1):
                    d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                    dots += "🟩" if d in active_set else "⬜"
                    if (i % 7 == 0) and i != 0:
                        dots += " "
                st.markdown(dots)
                st.caption("🟩 有学习  ⬜ 未学习（从左到右 = 最早→今天）")
