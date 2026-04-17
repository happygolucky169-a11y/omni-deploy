"""
OMNI-LEARN OS — IRT 自适应测试引擎 + 题库管理
omni_irt_engine.py
"""

import streamlit as st
import json
import os
import math
import random
from pathlib import Path

# ─────────────────────────────────────────────
# 题库加载
# ─────────────────────────────────────────────

BANK_FILES = [
    "omni_irt_itembank_L1_L5_v2.json",
    "omni_irt_itembank_L1_L5_v2__1_.json",  # 备用名
    "omni_irt_itembank_L6_L10.json",
    "omni_irt_itembank_L11_L15.json",
    "omni_irt_itembank_L16_L20.json",
    "omni_irt_itembank_L21_L25.json",
]

CEFR_MAP = {
    range(1, 6):  "Pre-A1 基础",
    range(6, 11): "Pre-A1 巩固",
    range(11, 16): "A1 Entry",
    range(16, 21): "A1 Consolidation",
    range(21, 26): "A2 Entry",
}

def get_cefr(level: int) -> str:
    for r, label in CEFR_MAP.items():
        if level in r:
            return label
    return "未知"


def load_item_banks(library_dir: str) -> dict:
    """
    从 library_dir 加载所有可用题库。
    返回 {"items": [...], "meta": [...], "by_level": {level: [items]}}
    """
    all_items = []
    metas = []

    for fname in BANK_FILES:
        fpath = os.path.join(library_dir, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", [])
            all_items.extend(items)
            metas.append({
                "file": fname,
                "range": data["_meta"].get("level_range", "?"),
                "cefr": data["_meta"].get("cefr", "?"),
                "total": data["_meta"].get("total_items", len(items)),
                "version": data["_meta"].get("version", "1.0"),
                "dimension_weights": data["_meta"].get("dimension_weights", {}),
                "adaptive_strategy": data["_meta"].get("adaptive_strategy", {}),
            })
        except Exception as e:
            pass  # 静默跳过损坏的文件

    # 去重（同一 item_id 只保留第一个）
    seen = set()
    deduped = []
    for item in all_items:
        iid = item.get("item_id", "")
        if iid not in seen:
            seen.add(iid)
            deduped.append(item)

    by_level = {}
    for item in deduped:
        lvl = item.get("level", 0)
        by_level.setdefault(lvl, []).append(item)

    return {"items": deduped, "meta": metas, "by_level": by_level}


def get_bank_stats(bank: dict) -> dict:
    """统计题库数据"""
    items = bank["items"]
    if not items:
        return {}

    from collections import Counter
    levels = [i["level"] for i in items]
    dims = Counter(i["dimension"] for i in items)
    roles = Counter(i["role"] for i in items)
    types = Counter(i["item_type"] for i in items)
    b_vals = [i["irt"]["b"] for i in items if "irt" in i]

    return {
        "total": len(items),
        "levels": sorted(set(levels)),
        "level_count": Counter(levels),
        "dimensions": dict(dims),
        "roles": dict(roles),
        "item_types": dict(types),
        "b_range": (round(min(b_vals), 2), round(max(b_vals), 2)) if b_vals else (0, 0),
        "b_mean": round(sum(b_vals) / len(b_vals), 2) if b_vals else 0,
        "banks_loaded": len(bank["meta"]),
    }


# ─────────────────────────────────────────────
# IRT 核心（2PL + Bayesian theta 更新）
# ─────────────────────────────────────────────

def irt_prob(theta: float, b: float, a: float = 1.0, c: float = 0.25) -> float:
    """3PL IRT 作答正确概率"""
    return c + (1 - c) / (1 + math.exp(-a * (theta - b)))


def update_theta(theta: float, responses: list[dict]) -> tuple[float, float]:
    """
    用已有响应更新 theta（简化最大后验估计）。
    responses: [{"b": float, "a": float, "c": float, "correct": bool}]
    返回 (new_theta, se)
    """
    if not responses:
        return theta, 2.0

    # Newton-Raphson 迭代
    for _ in range(20):
        L1 = 0.0  # 一阶导数
        L2 = 0.0  # 二阶导数（负Fisher信息）

        for r in responses:
            b, a, c = r["b"], r.get("a", 1.0), r.get("c", 0.25)
            p = irt_prob(theta, b, a, c)
            q = 1 - p
            u = 1 if r["correct"] else 0

            # 链式求导
            dp_dtheta = a * (p - c) * q / (1 - c) if (1 - c) > 0 else 0
            if p > 1e-9 and q > 1e-9:
                L1 += (u - p) * dp_dtheta / (p * q)
                L2 -= (dp_dtheta ** 2) / (p * q)

        # 加上先验（均值0，方差1的正态先验）
        L1 -= theta
        L2 -= 1.0

        if abs(L2) < 1e-9:
            break
        delta = -L1 / L2
        theta += delta
        if abs(delta) < 0.001:
            break

    # 标准误
    fisher = max(0.01, -L2)
    se = 1.0 / math.sqrt(fisher)
    return round(theta, 3), round(se, 3)


def theta_to_level(theta: float) -> int:
    """将 theta 值映射到 OMNI 级别（L1-L25）"""
    # 校准：theta=-3 → L1, theta=3 → L25
    level = round((theta + 3) * (25 / 6))
    return max(1, min(25, level))


def level_to_theta(level: int) -> float:
    """将 OMNI 级别映射回 theta"""
    return round((level / (25 / 6)) - 3, 2)


# ─────────────────────────────────────────────
# 自适应测试引擎
# ─────────────────────────────────────────────

class AdaptiveTestEngine:
    """
    简化版 CAT 引擎，基于 2-wrong-1-confirm 策略。
    """

    DIMENSION_WEIGHTS = {
        "vocabulary": 0.35,
        "listening": 0.30,
        "reading": 0.25,
        "grammar": 0.10,
    }

    def __init__(self, bank: dict, prior_estimate: dict = None):
        self.bank = bank
        self.items = bank["items"]
        self.by_level = bank["by_level"]

        # 初始化各维度状态
        prior_level = prior_estimate.get("midpoint", 10) if prior_estimate else 10
        prior_theta = level_to_theta(prior_level)

        self.dim_state = {}
        for dim in ["vocabulary", "listening", "reading", "grammar"]:
            self.dim_state[dim] = {
                "theta": prior_theta,
                "se": 2.0,
                "responses": [],
                "current_level": prior_level,
                "consecutive_wrong": 0,
                "consecutive_right": 0,
                "terminated": False,
                "final_level": None,
                "awaiting_confirm": False,
            }

        self.used_items = set()
        self.current_dim = "vocabulary"
        self.total_answered = 0

    def get_next_item(self) -> dict | None:
        """选择下一道题"""
        # 找到第一个未终止的维度
        dim_order = ["vocabulary", "listening", "reading", "grammar"]
        for dim in dim_order:
            state = self.dim_state[dim]
            if not state["terminated"]:
                self.current_dim = dim
                break
        else:
            return None  # 全部维度已终止

        state = self.dim_state[self.current_dim]
        target_level = state["current_level"]

        # 确认题模式
        if state["awaiting_confirm"]:
            confirm_level = max(1, target_level - 2)
            item = self._pick_item(self.current_dim, confirm_level, "confirm")
            if item:
                return item

        # 主测题
        item = self._pick_item(self.current_dim, target_level, "primary")
        if item:
            return item

        # 找不到精确级别的题，向上找
        for offset in [1, -1, 2, -2, 3]:
            alt_level = target_level + offset
            if 1 <= alt_level <= 25:
                item = self._pick_item(self.current_dim, alt_level, "primary")
                if item:
                    return item

        return None

    def _pick_item(self, dimension: str, level: int, role: str) -> dict | None:
        candidates = [
            i for i in self.by_level.get(level, [])
            if i["dimension"] == dimension
            and i["role"] == role
            and i.get("item_id") not in self.used_items
        ]
        if candidates:
            item = random.choice(candidates)
            self.used_items.add(item["item_id"])
            return item
        return None

    def record_response(self, item: dict, correct: bool):
        """记录作答，更新状态"""
        dim = item["dimension"]
        state = self.dim_state[dim]
        irt = item.get("irt", {})

        # 记录到响应列表
        state["responses"].append({
            "b": irt.get("b", 0),
            "a": irt.get("a", 1.0),
            "c": irt.get("c", 0.25),
            "correct": correct,
        })

        # 更新 theta
        state["theta"], state["se"] = update_theta(state["theta"], state["responses"])
        self.total_answered += 1

        # 更新连续对错计数
        if state["awaiting_confirm"]:
            # 确认题逻辑
            confirm_level = max(1, state["current_level"] - 2)
            if correct:
                state["final_level"] = confirm_level
            else:
                state["final_level"] = max(1, confirm_level - 1)
            state["terminated"] = True
            state["awaiting_confirm"] = False
            return

        if correct:
            state["consecutive_wrong"] = 0
            state["consecutive_right"] += 1
            # 连续答对2题→向上升级
            if state["consecutive_right"] >= 2:
                state["consecutive_right"] = 0
                new_level = min(25, state["current_level"] + 1)
                if new_level == 25:
                    # 到达上限，终止
                    state["final_level"] = 25
                    state["terminated"] = True
                else:
                    state["current_level"] = new_level
        else:
            state["consecutive_right"] = 0
            state["consecutive_wrong"] += 1
            # 连续答错2题→触发确认题
            if state["consecutive_wrong"] >= 2:
                state["consecutive_wrong"] = 0
                state["awaiting_confirm"] = True

        # SE 足够小→终止
        if state["se"] < 0.4 and len(state["responses"]) >= 5:
            state["final_level"] = theta_to_level(state["theta"])
            state["terminated"] = True

        # 题量上限→终止
        if len(state["responses"]) >= 8:
            state["final_level"] = theta_to_level(state["theta"])
            state["terminated"] = True

    def is_complete(self) -> bool:
        return all(s["terminated"] for s in self.dim_state.values())

    def get_result(self) -> dict:
        """计算最终综合等级"""
        weights = self.DIMENSION_WEIGHTS
        weighted_sum = 0.0
        total_weight = 0.0

        dim_results = {}
        for dim, state in self.dim_state.items():
            level = state.get("final_level") or theta_to_level(state["theta"])
            dim_results[dim] = {
                "level": level,
                "theta": round(state["theta"], 2),
                "se": round(state["se"], 2),
                "items_answered": len(state["responses"]),
                "cefr": get_cefr(level),
            }
            w = weights.get(dim, 0.25)
            weighted_sum += level * w
            total_weight += w

        composite = round(weighted_sum / total_weight) if total_weight > 0 else 10

        # 短板保护：综合等级不超过（最低维度 + 2）
        min_level = min(r["level"] for r in dim_results.values())
        composite = min(composite, min_level + 2)

        return {
            "composite_level": composite,
            "composite_cefr": get_cefr(composite),
            "dimensions": dim_results,
            "total_items": self.total_answered,
        }


# ─────────────────────────────────────────────
# Dashboard 页面：题库管理
# ─────────────────────────────────────────────

def render_item_bank_overview(library_dir: str):
    """题库概况页面"""
    bank = load_item_banks(library_dir)
    stats = get_bank_stats(bank)

    if not stats:
        st.warning("⚠️ 未找到任何题库文件。请确认 JSON 文件在内容库目录中。")
        st.markdown("**需要的文件名：**")
        for f in BANK_FILES:
            exists = os.path.exists(os.path.join(library_dir, f))
            icon = "✅" if exists else "❌"
            st.markdown(f"- {icon} `{f}`")
        return

    # 总览指标
    st.markdown("### 📊 题库总览")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总题目数", stats["total"])
    with col2:
        st.metric("覆盖级别", f"L{min(stats['levels'])}–L{max(stats['levels'])}")
    with col3:
        st.metric("已加载题库", f"{stats['banks_loaded']} 个")
    with col4:
        st.metric("难度范围(b值)", f"{stats['b_range'][0]} ~ {stats['b_range'][1]}")

    # 加载的题库列表
    st.markdown("### 📁 已加载题库")
    for meta in bank["meta"]:
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{meta['range']}** · {meta['cefr']}")
            with col2:
                st.markdown(f"共 **{meta['total']}** 题")
            with col3:
                st.markdown(f"v{meta['version']}")

    st.divider()

    # 各级别分布
    st.markdown("### 📈 各级别题目分布")
    level_data = {}
    for lvl in sorted(stats["levels"]):
        count = stats["level_count"].get(lvl, 0)
        cefr = get_cefr(lvl)
        level_data[f"L{lvl}"] = count

    if level_data:
        st.bar_chart(level_data)

    # 维度分布
    st.markdown("### 🎯 维度分布")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**各维度题量**")
        for dim, cnt in stats["dimensions"].items():
            dim_labels = {"vocabulary": "📖 词汇", "listening": "🎧 听力", "reading": "📝 阅读", "grammar": "✏️ 语法"}
            label = dim_labels.get(dim, dim)
            st.progress(cnt / stats["total"], text=f"{label}: {cnt} 题")
    with col2:
        st.markdown("**题目角色**")
        primary = stats["roles"].get("primary", 0)
        confirm = stats["roles"].get("confirm", 0)
        total = primary + confirm
        if total > 0:
            st.progress(primary / total, text=f"主测题: {primary}")
            st.progress(confirm / total, text=f"确认题: {confirm}")

    st.divider()

    # 题目浏览器
    st.markdown("### 🔍 题目浏览")
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_level = st.selectbox("级别", ["全部"] + [f"L{l}" for l in sorted(stats["levels"])])
    with col2:
        sel_dim = st.selectbox("维度", ["全部", "vocabulary", "listening", "reading", "grammar"])
    with col3:
        sel_role = st.selectbox("角色", ["全部", "primary", "confirm"])

    # 过滤
    filtered = bank["items"]
    if sel_level != "全部":
        lvl_num = int(sel_level[1:])
        filtered = [i for i in filtered if i["level"] == lvl_num]
    if sel_dim != "全部":
        filtered = [i for i in filtered if i["dimension"] == sel_dim]
    if sel_role != "全部":
        filtered = [i for i in filtered if i["role"] == sel_role]

    st.markdown(f"筛选结果：**{len(filtered)}** 道题")

    for item in filtered[:20]:  # 最多显示20条
        with st.expander(f"**{item['item_id']}** · L{item['level']} · {item['dimension']} · {item['role']}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                if "instruction_zh" in item:
                    st.markdown(f"**中文指令：** {item['instruction_zh']}")
                if "instruction_en" in item:
                    st.markdown(f"**英文指令：** {item['instruction_en']}")
                if "audio_content" in item:
                    st.markdown(f"**音频内容：** *{item['audio_content']}*")
                if "stimulus_text" in item:
                    st.markdown(f"**阅读材料：** {item['stimulus_text']}")
                if "stimulus_sentence" in item:
                    st.markdown(f"**刺激句：** {item['stimulus_sentence']}")

                # 选项
                options = item.get("options", [])
                correct = item.get("correct", "")
                for opt in options:
                    icon = "✅" if opt["id"] == correct else "○"
                    content = opt.get("content", opt.get("text_en", ""))
                    st.markdown(f"  {icon} **{opt['id']}**  {content}")

            with col2:
                irt = item.get("irt", {})
                st.markdown(f"**b = {irt.get('b', '?')}**")
                st.markdown(f"a = {irt.get('a', '?')}")
                st.markdown(f"c = {irt.get('c', '?')}")
                st.markdown(f"*{item.get('skill_focus', '')}*")

    if len(filtered) > 20:
        st.info(f"只显示前 20 条，共 {len(filtered)} 条。")


# ─────────────────────────────────────────────
# Dashboard 页面：自适应测试（演示模式）
# ─────────────────────────────────────────────

def render_adaptive_test(library_dir: str, prior_estimate: dict = None):
    """
    自适应测试页面。
    prior_estimate: 来自问卷的先验估计，格式见 omni_questionnaire.py
    """
    bank = load_item_banks(library_dir)

    if not bank["items"]:
        st.error("❌ 未找到题库文件，无法启动测试。")
        return

    # 初始化引擎
    if "irt_engine" not in st.session_state:
        if prior_estimate is None:
            prior_estimate = {"midpoint": 10, "range_low": 7, "range_high": 13}
        st.session_state.irt_engine = AdaptiveTestEngine(bank, prior_estimate)
        st.session_state.irt_current_item = None
        st.session_state.irt_feedback = None
        st.session_state.irt_prior = prior_estimate

    engine: AdaptiveTestEngine = st.session_state.irt_engine
    prior = st.session_state.irt_prior

    if engine.is_complete():
        _render_test_result(engine)
        return

    # 显示进度
    active_dims = [d for d, s in engine.dim_state.items() if not s["terminated"]]
    done_dims = [d for d, s in engine.dim_state.items() if s["terminated"]]
    st.progress(len(done_dims) / 4, text=f"已完成 {len(done_dims)}/4 个维度")

    # 显示当前维度状态
    dim_labels = {"vocabulary": "📖 词汇", "listening": "🎧 听力", "reading": "📝 阅读", "grammar": "✏️ 语法"}
    cols = st.columns(4)
    for i, (dim, state) in enumerate(engine.dim_state.items()):
        with cols[i]:
            if state["terminated"]:
                st.success(f"{dim_labels[dim]}\nL{state.get('final_level', '?')}")
            elif dim == engine.current_dim:
                st.info(f"**{dim_labels[dim]}**\n进行中")
            else:
                st.markdown(f"{dim_labels[dim]}\n等待中")

    st.divider()

    # 获取当前题目
    if st.session_state.irt_current_item is None:
        item = engine.get_next_item()
        if item is None:
            result = engine.get_result()
            st.session_state.irt_result = result
            st.rerun()
        st.session_state.irt_current_item = item
        st.session_state.irt_feedback = None

    item = st.session_state.irt_current_item
    if item is None:
        st.error("找不到合适的题目")
        return

    # 题目信息
    st.markdown(f"**题目 #{engine.total_answered + 1}** · `{item['item_id']}` · L{item['level']} · {dim_labels.get(item['dimension'], item['dimension'])}")

    is_confirm = item.get("role") == "confirm"
    if is_confirm:
        st.caption("（确认题）")

    # 指令显示（双语或纯中文）
    if item.get("role") == "primary":
        instr = item.get("instruction_zh", "") + ("  \n*" + item.get("instruction_en", "") + "*" if item.get("instruction_en") else "")
    else:
        instr = item.get("instruction_zh", "")

    st.markdown(f"> {instr}")

    # 音频/文本内容
    if item.get("audio_content"):
        st.info(f"🔊 *{item['audio_content']}*")
    if item.get("stimulus_text"):
        st.markdown(f"**阅读材料：**\n\n> {item['stimulus_text']}")
    if item.get("stimulus_sentence"):
        st.markdown(f"> **{item['stimulus_sentence']}**")
    if item.get("picture_shown"):
        st.caption(f"🖼 图片：{item['picture_shown']}")

    # 选项
    options = item.get("options", [])
    correct_id = item.get("correct", "")

    if st.session_state.irt_feedback is None:
        option_labels = []
        for opt in options:
            content = opt.get("content", opt.get("text_en", opt.get("text_zh", "")))
            option_labels.append(f"{opt['id']}. {content}")

        chosen = st.radio("请选择：", option_labels, key=f"q_{engine.total_answered}")

        if st.button("确认答案 →", type="primary"):
            chosen_id = chosen.split(".")[0].strip()
            correct = (chosen_id == correct_id)
            st.session_state.irt_feedback = {"correct": correct, "chosen": chosen_id, "correct_id": correct_id}
            engine.record_response(item, correct)
            st.rerun()
    else:
        # 显示反馈
        fb = st.session_state.irt_feedback
        if fb["correct"]:
            st.success("✅ 答对了！")
        else:
            correct_opt = next((o for o in options if o["id"] == fb["correct_id"]), None)
            correct_content = correct_opt.get("content", fb["correct_id"]) if correct_opt else fb["correct_id"]
            st.error(f"❌ 答错了。正确答案是 **{fb['correct_id']}. {correct_content}**")

        if item.get("skill_focus"):
            st.caption(f"考查点：{item['skill_focus']}")

        if st.button("下一题 →", type="primary"):
            st.session_state.irt_current_item = None
            st.session_state.irt_feedback = None
            if engine.is_complete():
                result = engine.get_result()
                st.session_state.irt_result = result
            st.rerun()


def _render_test_result(engine: AdaptiveTestEngine):
    """渲染测试结果"""
    result = engine.get_result()
    st.balloons()

    st.markdown("## 🎓 测试完成！")
    st.markdown(f"### 综合等级：**L{result['composite_level']}** · {result['composite_cefr']}")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("综合 OMNI 级别", f"L{result['composite_level']}")
    with col2:
        st.metric("总作答题数", result["total_items"])

    st.divider()
    st.markdown("#### 各维度详情")

    dim_labels = {"vocabulary": "📖 词汇", "listening": "🎧 听力", "reading": "📝 阅读", "grammar": "✏️ 语法"}
    cols = st.columns(4)
    for i, (dim, dr) in enumerate(result["dimensions"].items()):
        with cols[i]:
            st.metric(
                dim_labels.get(dim, dim),
                f"L{dr['level']}",
                help=f"θ={dr['theta']}, SE={dr['se']}, 答题数={dr['items_answered']}"
            )
            st.caption(dr["cefr"])

    st.divider()

    # 建议
    level = result["composite_level"]
    if level <= 5:
        advice = "建议从**字母认知**和**基础词汇**开始，配合大量听力输入。"
    elif level <= 10:
        advice = "建议以**Phonics解码**和**简单句型**为核心，多听多读。"
    elif level <= 15:
        advice = "可以开始接触**简短语篇**和**基础语法**，同时扩大词汇量。"
    elif level <= 20:
        advice = "进入**A1巩固**阶段，重点攻克**过去时**和**第三人称单数**。"
    else:
        advice = "已达到**A2入门**水平，建议挑战更复杂的**语篇理解**和**词义推断**。"

    st.info(f"💡 学习建议：{advice}")

    with st.expander("📄 完整结果 JSON"):
        st.json(result)

    if st.button("🔄 重新测试", use_container_width=True):
        del st.session_state.irt_engine
        del st.session_state.irt_current_item
        del st.session_state.irt_feedback
        if "irt_result" in st.session_state:
            del st.session_state.irt_result
        st.rerun()


# ─────────────────────────────────────────────
# 独立运行入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(page_title="OMNI 题库管理", page_icon="📚", layout="wide")
    library_dir = st.sidebar.text_input("题库目录", value=".")
    tab1, tab2 = st.tabs(["📊 题库概况", "🎯 自适应测试演示"])
    with tab1:
        render_item_bank_overview(library_dir)
    with tab2:
        render_adaptive_test(library_dir)
