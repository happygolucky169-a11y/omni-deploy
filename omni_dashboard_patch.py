"""
OMNI Dashboard 集成补丁
========================
将以下代码块按说明插入 omni_dashboard.py

步骤 1：在文件顶部 import 区域末尾加入：
─────────────────────────────────────────
"""

PATCH_IMPORTS = '''
# ── 新增：问卷 + IRT 引擎 ──────────────────
try:
    from omni_questionnaire import render_questionnaire
    from omni_irt_engine import (
        render_item_bank_overview,
        render_adaptive_test,
        load_item_banks,
        get_bank_stats,
    )
    IRT_AVAILABLE = True
except ImportError as e:
    IRT_AVAILABLE = False
    _irt_import_err = str(e)
'''

"""
步骤 2：在 render_sidebar() 函数的导航按钮区域，加入两个新按钮：
─────────────────────────────────────────
"""

PATCH_SIDEBAR_BUTTONS = '''
    # ── 新增按钮 ──
    if st.sidebar.button("🌟 入学问卷", use_container_width=True,
                         type="primary" if st.session_state.get("page") == "questionnaire" else "secondary"):
        st.session_state.page = "questionnaire"
        st.rerun()

    if st.sidebar.button("🧪 自适应测试", use_container_width=True,
                         type="primary" if st.session_state.get("page") == "adaptive_test" else "secondary"):
        st.session_state.page = "adaptive_test"
        st.rerun()

    if st.sidebar.button("📚 题库管理", use_container_width=True,
                         type="primary" if st.session_state.get("page") == "item_bank" else "secondary"):
        st.session_state.page = "item_bank"
        st.rerun()
'''

"""
步骤 3：在 main() 函数的页面路由区域，加入新页面处理：
（通常在 if page == "今日主页" ... elif page == "教材学习" ... 这段代码中追加）
─────────────────────────────────────────
"""

PATCH_MAIN_ROUTES = '''
    elif page == "questionnaire":
        _render_questionnaire_page(library_dir)

    elif page == "adaptive_test":
        _render_adaptive_test_page(library_dir)

    elif page == "item_bank":
        _render_item_bank_page(library_dir)
'''

"""
步骤 4：在文件末尾（main() 函数之前）加入以下三个页面函数：
─────────────────────────────────────────
"""

PATCH_PAGE_FUNCTIONS = '''
# ════════════════════════════════════════
# 新增页面：入学问卷
# ════════════════════════════════════════
def _render_questionnaire_page(library_dir: str):
    if not IRT_AVAILABLE:
        st.error(f"⚠️ 模块加载失败：{_irt_import_err}")
        st.info("请确认 omni_questionnaire.py 和 omni_irt_engine.py 在同一目录下。")
        return

    # 检查是否已完成问卷
    if st.session_state.get("q_completed"):
        result = st.session_state.get("questionnaire_result", {})
        prior = result.get("prior_estimate", {})
        st.success(f"✅ 问卷已完成！推荐起始级别：**L{prior.get('midpoint', '?')}**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 开始自适应测试", type="primary", use_container_width=True):
                st.session_state.page = "adaptive_test"
                st.session_state.q_completed = False
                st.rerun()
        with col2:
            if st.button("重新填写问卷", use_container_width=True):
                st.session_state.q_completed = False
                st.session_state.q_step = 0
                st.session_state.q_data = {}
                st.rerun()

        with st.expander("查看问卷结果"):
            st.json(result)
        return

    render_questionnaire()


# ════════════════════════════════════════
# 新增页面：自适应测试
# ════════════════════════════════════════
def _render_adaptive_test_page(library_dir: str):
    if not IRT_AVAILABLE:
        st.error(f"⚠️ 模块加载失败：{_irt_import_err}")
        return

    st.markdown("## 🧪 自适应入学测试")

    # 优先使用问卷先验
    prior = None
    if st.session_state.get("questionnaire_result"):
        prior = st.session_state.questionnaire_result.get("prior_estimate")
        conf = prior.get("confidence", "?")
        midpoint = prior.get("midpoint", "?")
        st.info(f"📋 根据问卷数据，起始级别设为 **L{midpoint}**（置信度：{conf}）")
    else:
        st.info("💡 未检测到问卷数据，将使用默认起点 L10。建议先完成入学问卷。")
        if st.button("去填写入学问卷"):
            st.session_state.page = "questionnaire"
            st.rerun()

    st.divider()

    # 锚定题（中等置信度）
    if prior and prior.get("confidence") == "medium":
        st.caption("📌 先进行 2 道快速锚定题，确认起点")

    render_adaptive_test(library_dir, prior)


# ════════════════════════════════════════
# 新增页面：题库管理
# ════════════════════════════════════════
def _render_item_bank_page(library_dir: str):
    if not IRT_AVAILABLE:
        st.error(f"⚠️ 模块加载失败：{_irt_import_err}")
        return

    st.markdown("## 📚 题库管理")
    render_item_bank_overview(library_dir)
'''

# ─── 输出完整说明 ───────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("OMNI Dashboard 集成补丁说明")
    print("=" * 60)
    print()
    print("需要修改 omni_dashboard.py，共 4 处插入点：")
    print()
    print("1. 顶部 import 区域末尾 → 加入 PATCH_IMPORTS")
    print("2. render_sidebar() 导航按钮区 → 加入 PATCH_SIDEBAR_BUTTONS")
    print("3. main() 页面路由区 → 加入 PATCH_MAIN_ROUTES")
    print("4. main() 函数之前 → 加入 PATCH_PAGE_FUNCTIONS")
    print()
    print("详情见 omni_dashboard_patch.py")
