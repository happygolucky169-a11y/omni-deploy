import streamlit as st
from auth import show_login, is_logged_in, get_role, get_current_user, logout

# 未登录先拦截
if not is_logged_in():
    show_login()
    st.stop()

# 已登录显示登出按钮
user = get_current_user()
role = get_role()

with st.sidebar:
    st.markdown(f"**{user['name']}**")
    if st.button("退出登录"):
        logout()

# 角色路由
if role == "admin":
    exec(open('omni_dashboard.py').read())
elif role == "teacher":
    exec(open('teacher_panel.py').read())
elif role == "parent":
    exec(open('parent_panel.py').read())
elif role == "student":
    exec(open('omni_dashboard.py').read())
else:
    st.error("未知角色")
    st.stop()