import json
import hashlib
import streamlit as st
from pathlib import Path

# ─────────────────────────────────────────
# 用户数据加载
# ─────────────────────────────────────────

USERS_FILE = Path(__file__).parent / "users.json"

def load_users():
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def hash_password(password: str) -> str:
    """密码哈希（生产环境建议换成 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()

# ─────────────────────────────────────────
# 核心验证逻辑（角色由服务器决定，用户无法干预）
# ─────────────────────────────────────────

def verify_user(username: str, password: str):
    """
    验证账号密码，返回用户信息。
    角色完全由 users.json 决定，前端没有任何角色选择入口。
    """
    users = load_users()
    user = users.get(username.strip())

    if not user:
        return None, "账号不存在"

    # 生产环境：改为 hash_password(password) == user["password"]
    if password != user["password"]:
        return None, "密码错误"

    return {
        "username": username,
        "role": user["role"],       # 角色来自数据库，用户无法伪造
        "name": user.get("name", username),
        "class_ids": user.get("class_ids", []),
        "student_id": user.get("student_id", None),
    }, None

# ─────────────────────────────────────────
# Session 管理
# ─────────────────────────────────────────

def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)

def get_current_user() -> dict:
    return st.session_state.get("user", {})

def get_role() -> str:
    return get_current_user().get("role", "")

def logout():
    st.session_state.logged_in = False
    st.session_state.user = {}
    st.rerun()

# ─────────────────────────────────────────
# 登录 UI
# ─────────────────────────────────────────

def show_login_page():
    st.markdown("""
        <style>
        .login-box {
            max-width: 400px;
            margin: 80px auto;
            padding: 40px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        }
        .login-title {
            font-size: 28px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 8px;
            color: #1a1a2e;
        }
        .login-sub {
            text-align: center;
            color: #888;
            margin-bottom: 32px;
            font-size: 14px;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-title">🌟 OMNI-LEARN OS</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">全息伴生学习系统</div>', unsafe_allow_html=True)

        username = st.text_input("账号", placeholder="请输入账号")
        password = st.text_input("密码", type="password", placeholder="请输入密码")

        if st.button("登 录", use_container_width=True, type="primary"):
            if not username or not password:
                st.error("请输入账号和密码")
                return

            user, error = verify_user(username, password)
            if error:
                st.error(f"❌ {error}")
            else:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.success(f"欢迎回来，{user['name']}！")
                st.rerun()

# ─────────────────────────────────────────
# 权限守卫装饰器（用于保护各个页面）
# ─────────────────────────────────────────

def require_role(*allowed_roles):
    """
    用法：
        require_role("admin", "teacher")
    在页面顶部调用，角色不符直接拦截。
    """
    if not is_logged_in():
        st.error("请先登录")
        st.stop()

    if get_role() not in allowed_roles:
        st.error("⛔ 你没有权限访问此页面")
        st.stop()
