
import streamlit as st
import os
import pandas as pd

st.set_page_config(page_title="四大英语评测与教材体系", page_icon="🎓", layout="wide")

# --- UI 样式 ---
st.markdown("""
<style>
    .system-title { font-size: 2.5rem; font-weight: 900; background: linear-gradient(90deg, #8b5cf6, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .card-box { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; height: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.3s ease; }
    .card-box:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(59, 130, 246, 0.15); border-color: #3b82f6; }
    .tag { display: inline-block; padding: 4px 10px; border-radius: 15px; font-size: 0.8rem; font-weight: bold; margin-bottom: 10px; margin-right: 5px; }
    .tag-cn { background: #fee2e2; color: #b91c1c; }
    .tag-cefr { background: #dbeafe; color: #1d4ed8; }
    .tag-us { background: #fef08a; color: #a16207; }
    .tag-intl { background: #dcfce7; color: #15803d; }
    .func-link { color: #64748b; font-size: 0.9rem; margin-top: 15px; border-top: 1px dashed #cbd5e1; padding-top: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='system-title'>🎓 四大权威英语评测与教材体系</div>", unsafe_allow_html=True)
st.write("统一调度您的单词、听力、口语、阅读与写作引擎，全面适配全球四大英语教育路线。")
st.divider()

# --- 核心架构：四大标签页 ---
tabs = st.tabs([
    "🇨🇳 1. 中国新课标英语体系", 
    "🇪🇺 2. CEFR体系 (YLE/MSE/雅思)", 
    "🇺🇸 3. 北美考试体系 (CCSS)", 
    "🌍 4. 国际学校体系 (IB/AP/A-Level)"
])

# ==========================================
# 1. 中国新课标英语体系
# ==========================================
with tabs[0]:
    st.markdown("### 🇨🇳 义务教育与普通高中英语课程标准")
    st.info("🎯 核心诉求：词汇大纲达标、语法长难句解析、应试得高分。")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='card-box'><span class='tag tag-cn'>中考英语 (Zhongkao)</span><h3>初中新课标 1600词</h3><p>聚焦人教版/外研版教材核心语料，完形填空与阅读理解真题库。</p><div class='func-link'>🔗 联动建议：使用 `1_单词卡片.py` (SM-2算法) 快速清空大纲词汇。</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card-box'><span class='tag tag-cn'>高考英语 (Gaokao)</span><h3>高中新课标 3500词</h3><p>全国一卷/二卷长难句语法树拆解，高考七选五与应用文写作。</p><div class='func-link'>🔗 联动建议：使用 `4_英语阅读分级.py` 进行长文本速读训练。</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='card-box'><span class='tag tag-cn'>大学及进阶 (CET/PGEE)</span><h3>四六级与考研英语</h3><p>考研英语(一/二)历年真题核心词汇与翻译题库。</p><div class='func-link'>🔗 联动建议：使用 `main_app.py` OCR 直接解析考研真题 PDF。</div></div>", unsafe_allow_html=True)

# ==========================================
# 2. CEFR英语体系 (接入了您的 PET 数据)
# ==========================================
with tabs[1]:
    st.markdown("### 🇪🇺 欧洲语言共同参考框架 (CEFR)")
    st.info("🎯 核心诉求：听力语速(WPM)分级、真实交流场景、能力标化定级 (A1 - C2)。")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("<div class='card-box'><span class='tag tag-cefr'>Pre-A1 ~ A2</span><h3>剑桥少儿 (YLE)</h3><p>Starters / Movers / Flyers <br>对应剑桥 Primary 体系与日常场景口语交流。</p><div class='func-link'>🔗 联动：`KTV系统.py` (儿歌启蒙)</div></div>", unsafe_allow_html=True)
    with col_b:
        st.markdown("<div class='card-box' style='border: 2px solid #3b82f6;'><span class='tag tag-cefr'>A2 ~ C2</span><h3>剑桥五级 (MSE)</h3><p>KET / <b>PET</b> / FCE / CAE / CPE <br>系统已侦测到本地 PET 听力数据！</p><div class='func-link'>🔗 联动：`2_听力分级.py` (WPM解析)</div></div>", unsafe_allow_html=True)
        if st.button("🌟 加载本地 PET (Compact) 数据", key="load_pet"):
            st.session_state['show_cefr_data'] = True
    with col_c:
        st.markdown("<div class='card-box'><span class='tag tag-cefr'>B1 ~ C2</span><h3>雅思 (IELTS)</h3><p>剑桥雅思 4-18 全集<br>包含听力填空、口语 P1-P3 题库、学术类/培训类阅读。</p><div class='func-link'>🔗 联动：`3_口语练习.py` (AI考官)</div></div>", unsafe_allow_html=True)
        
    # 动态加载 CSV 数据
    if st.session_state.get('show_cefr_data', False):
        st.markdown("---")
        st.subheader("📡 CEFR - MSE B1 级别底层数据挂载：PET")
        try:
            if os.path.exists("audio_analysis_full_report.csv"):
                df = pd.read_csv("audio_analysis_full_report.csv")
                pet_data = df[df['wpm'] > 0]
                st.dataframe(
                    pet_data[['filename', 'wpm', 'difficulty', 'duration', 'text']],
                    column_config={"filename": "原版听力文件 (MP3)", "wpm": st.column_config.ProgressColumn("实际语速 (WPM)", format="%.1f", max_value=200), "text": "精听原文提取"},
                    use_container_width=True, height=200
                )
                st.button("🎧 启动 Whisper 并发送至『听力分级跟读模块』", type="primary")
            else:
                st.warning("未找到 audio_analysis_full_report.csv 文件")
        except Exception as e:
            st.error(f"加载数据失败: {e}")

# ==========================================
# 3. 北美考试体系 (CCSS)
# ==========================================
with tabs[2]:
    st.markdown("### 🇺🇸 美国共同核心州立标准 (CCSS)")
    st.info("🎯 核心诉求：跨学科原版阅读、Lexile蓝思分级、美式批判性思维 (Critical Thinking)。")
    c_us1, c_us2 = st.columns(2)
    with c_us1:
        st.markdown("""
        <div class='card-box'>
            <span class='tag tag-us'>K-12 Foundation</span>
            <h3>CCSS 原版分级阅读库</h3>
            <p>包含 RAZ (Reading A-Z) aa-Z级别、Wonders 加州教材、以及海量科普文学读物。</p>
            <ul>
                <li>Lexile 蓝思指数自动评估</li>
                <li>非虚构类 (Non-Fiction) 信息提取训练</li>
            </ul>
            <div class='func-link'>🔗 建议挂载：`4_英语阅读分级.py` (长文本解析引擎)</div>
        </div>
        """, unsafe_allow_html=True)
        st.button("进入蓝思分级阅读大厅")
    with c_us2:
        st.markdown("""
        <div class='card-box'>
            <span class='tag tag-us'>Higher Ed</span>
            <h3>托福 & 标化考试 (TOEFL/SAT/SSAT)</h3>
            <p>托福 TPO 模考系统，涵盖天文、地质、历史等美式学术讲座 (Lecture) 听力。</p>
            <ul>
                <li>SAT/ACT 核心学术词汇与逻辑阅读</li>
                <li>托福机考综合口语模考</li>
            </ul>
            <div class='func-link'>🔗 建议挂载：`3_口语练习.py` & `1_单词卡片.py`</div>
        </div>
        """, unsafe_allow_html=True)
        st.button("启动托福 (TOEFL) 模考引擎")

# ==========================================
# 4. 国际学校体系 (IB体系，AP, A-Level)
# ==========================================
with tabs[3]:
    st.markdown("### 🌍 国际学校顶级核心课程 (IB / AP / A-Level)")
    st.info("🎯 核心诉求：用英语学专业知识、高强度学术写作 (Essay)、TOK (认识论)。")
    
    st.markdown("🚨 **特别提醒：此模块强烈依赖于您的 `6_🚀_未来100个职业英语.py` 和 `5_写作训练.py`！**", unsafe_allow_html=True)
    
    c_ib1, c_ib2, c_ib3 = st.columns(3)
    with c_ib1:
        st.markdown("<div class='card-box'><span class='tag tag-intl'>IB (International Baccalaureate)</span><h3>IBDP 全科体系</h3><p>最顶级的全能学术体系。涵盖 EE (拓展论文)、TOK (认识论) 以及跨学科词汇探究。</p><div class='func-link'>🔗 核心引擎：`5_写作训练.py` (用于批改EE)</div></div>", unsafe_allow_html=True)
    with c_ib2:
        st.markdown("<div class='card-box'><span class='tag tag-intl'>AP (Advanced Placement)</span><h3>AP 美国大学先修课</h3><p>聚焦单科深度：AP微积分、AP物理、AP心理学、AP宏观/微观经济学双语语料。</p><div class='func-link'>🔗 核心引擎：`6_未来100个职业英语.py`</div></div>", unsafe_allow_html=True)
    with c_ib3:
        st.markdown("<div class='card-box'><span class='tag tag-intl'>A-Level / IGCSE</span><h3>英联邦高中课程</h3><p>深度对标英联邦学术体系，提供数学、高阶物理、商科等科目的英文真题解析。</p><div class='func-link'>🔗 核心引擎：`main_app.py` (PDF试卷扫描)</div></div>", unsafe_allow_html=True)
        
    st.divider()
    st.markdown("#### 🚀 启动学术引擎")
    st.button("一键打通『国际学校科目』与『未来100大职业库』", use_container_width=True, type="primary")

