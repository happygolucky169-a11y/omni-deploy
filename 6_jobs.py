
import streamlit as st
import os

st.set_page_config(page_title="未来100大职业英语库", page_icon="💼", layout="wide")

# 自定义极客风 UI
st.markdown("""
<style>
    .big-title { font-size: 2.8rem; font-weight: 900; background: linear-gradient(90deg, #10b981, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .folder-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.3s; margin-bottom: 15px;}
    .folder-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(59,130,246,0.15); border-color: #3b82f6; cursor: pointer; }
    .folder-icon { font-size: 2.5rem; margin-bottom: 10px; }
    .folder-name { font-weight: 700; color: #1e293b; font-size: 1.1rem; }
    .bracket-folder { border-left: 5px solid #8b5cf6; } /* 带有 [] 的主分类特殊样式 */
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='big-title'>💼 未来 100 大抗 AI 职业双语语料库</div>", unsafe_allow_html=True)
st.write("直连本地物理机房。探索跨学科、前沿科技与人文社科的专业英语壁垒。")
st.divider()

# --- 1. 动态扫描本地真实文件夹 ---
# 这里的路径对应您的截图结构，假设代码和“未来100个职业英语”文件夹在同级或者您需要根据实际情况微调
BASE_DIR = os.path.join(os.path.dirname(__file__), "未来100个职业英语", "职业英语库")

# 容错处理：如果当前路径不对，可以手动指定绝对路径
# BASE_DIR = r"C:\Users\您的用户名\Desktop\omni-admin\未来100个职业英语\职业英语库"

if not os.path.exists(BASE_DIR):
    st.warning(f"⚠️ 未找到路径: {BASE_DIR}")
    st.info("💡 请确保您的 Python 脚本运行目录正确，或者在代码中修改 BASE_DIR 为您的绝对路径。")
    st.stop()

# 获取所有文件夹
all_folders = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]

# 智能分类：将带中括号 [xxx] 的识别为主分类，其他的为具体专业
main_categories = [f for f in all_folders if f.startswith("[") and f.endswith("]")]
specific_majors = [f for f in all_folders if not (f.startswith("[") and f.endswith("]"))]

# --- 2. 界面展示区：宏观分类 ---
st.subheader("📁 宏观产业集群 (大类)")
cat_cols = st.columns(4)
for i, cat in enumerate(main_categories):
    with cat_cols[i % 4]:
        # 去掉括号展示
        clean_name = cat.strip("[]")
        st.markdown(f"""
        <div class="folder-card bracket-folder">
            <div class="folder-icon">🏢</div>
            <div class="folder-name">{clean_name}</div>
            <div style="font-size:0.8rem; color:#64748b; margin-top:5px;">产业集群语料</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# --- 3. 界面展示区：100个具体细分专业 ---
st.subheader("🎯 核心不可替代专业 (细分领域)")

# 添加一个搜索框方便在一堆文件夹中查找
search_query = st.text_input("🔍 检索您的目标专业 (例如: 脑科学, 金融, 芯片)...")

# 过滤搜索结果
filtered_majors = [m for m in specific_majors if search_query.lower() in m.lower()]

# 用 5 列网格密集展示所有专业文件夹
cols = st.columns(5)
for i, major in enumerate(filtered_majors):
    with cols[i % 5]:
        if st.button(f"📂 {major}", use_container_width=True, key=f"btn_{major}"):
            st.session_state['selected_folder'] = major

# --- 4. 动态展开选中文件夹的内容 ---
if 'selected_folder' in st.session_state:
    selected = st.session_state['selected_folder']
    target_path = os.path.join(BASE_DIR, selected)
    
    st.markdown("---")
    st.markdown(f"## 📡 正在解析本地库: **{selected}**")
    
    # 扫描该专业文件夹下的真实文件 (视频, 音频, PDF)
    try:
        files_in_major = os.listdir(target_path)
        
        if not files_in_major:
            st.info(f"📁 文件夹 **{selected}** 目前为空。请将原版教材、外刊 PDF 或无字幕视频放入此文件夹。")
        else:
            st.success(f"已侦测到 {len(files_in_major)} 个学习资源文件！")
            
            # 分类统计文件
            pdfs = [f for f in files_in_major if f.endswith('.pdf')]
            media = [f for f in files_in_major if f.endswith(('.mp4', '.mp3', '.wav'))]
            docs = [f for f in files_in_major if f.endswith(('.txt', '.docx', '.csv'))]
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("学术文献 (PDF)", len(pdfs))
                for p in pdfs[:3]: st.caption(f"📄 {p}")
                if pdfs: st.button("启动大模型深度泛读", key=f"read_{selected}")
                
            with c2:
                st.metric("前沿视听 (Media)", len(media))
                for m in media[:3]: st.caption(f"🎬 {m}")
                if media: st.button("启动 Whisper AI 断句解析", key=f"listen_{selected}")
                
            with c3:
                st.metric("行业语料与词汇", len(docs))
                for d in docs[:3]: st.caption(f"📝 {d}")
                if docs: st.button("一键导入 SM-2 记忆算法", key=f"word_{selected}")

    except Exception as e:
        st.error(f"读取文件夹失败: {e}")
