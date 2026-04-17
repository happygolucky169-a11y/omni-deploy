import streamlit as st

USERS = {
    "admin": {"password": "omni_admin_2026", "role": "admin", "name": "Hope"},
    "teacher01": {"password": "teacher_2026", "role": "teacher", "name": "张老师"},
    "parent001": {"password": "parent_2026", "role": "parent", "name": "家长"},
}

def verify(username, password):
    user = USERS.get(username.strip())
    if not user:
        return None, "账号不存在"
    if password != user["password"]:
        return None, "密码错误"
    return user, None

def is_logged_in():
    return st.session_state.get("logged_in", False)

def get_current_user():
    return st.session_state.get("user", {})

def get_role():
    return get_current_user().get("role", "")

def logout():
    st.session_state.logged_in = False
    st.session_state.user = {}
    st.rerun()

def show_login():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("## 🌟 OMNI-LEARN OS")
        st.markdown("##### 全阶英语学习系统")
        st.divider()
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        if st.button("登 录", type="primary", use_container_width=True):
            if not username or not password:
                st.error("请输入账号和密码")
            else:
                user, err = verify(username, password)
                if err:
                    st.error(f"❌ {err}")
                else:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
