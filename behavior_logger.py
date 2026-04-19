"""
OMNI-LEARN OS — 行为埋点系统
behavior_logger.py

追踪指标：
  ① 模块停留时长     进入/离开每个模块的时间差
  ② 答题响应时间     题目展示 → 提交答案 的时间差
  ③ 答题正确率       每道题对错及得分
  ④ 音频播放完成率   播放开始 → 播放结束 的比例
  ⑤ 模块访问频次     每个模块被打开了多少次

存储格式：
  omni_data/behavior_logs/{username}/{YYYY-MM-DD}.jsonl
  每行一个 JSON 事件，追加写入，零性能开销

用法（在各模块文件顶部引入）：
  from behavior_logger import BLogger
  BLogger.page_enter(username, "words")
  BLogger.question_shown(username, "words", q_id="w_001")
  BLogger.question_answered(username, "words", q_id="w_001", correct=True, score=1.0)
  BLogger.audio_play(username, "listening", audio_id="l_001", duration_sec=12)
  BLogger.audio_end(username, "listening", audio_id="l_001", listened_sec=10)
  BLogger.page_leave(username, "words")
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime
import streamlit as st

# ── 模块中文名映射 ──────────────────────────────────────
MODULE_CN = {
    "words":     "单词",
    "listening": "听力",
    "speaking":  "口语",
    "reading":   "阅读",
    "writing":   "写作",
    "ktv":       "英语KTV",
    "textbook":  "教材",
    "jobs":      "职业英语",
    "placement": "入学测试",
    "explorer":  "探索模式",
}


class BehaviorLogger:
    """
    轻量级行为埋点记录器。
    所有方法为静态方法，无需实例化，直接 BLogger.xxx() 调用。
    """

    @staticmethod
    def _data_dir() -> Path:
        """从 session_state 读取数据目录，若不存在则用当前目录"""
        d = st.session_state.get("data_dir", ".")
        return Path(d) if d else Path(".")

    @staticmethod
    def _log_dir(username: str) -> Path:
        p = BehaviorLogger._data_dir() / "behavior_logs" / username
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _write(username: str, event: dict):
        """追加写入一行 JSON"""
        today = datetime.now().strftime("%Y-%m-%d")
        f = BehaviorLogger._log_dir(username) / f"{today}.jsonl"
        event["ts"] = datetime.now().isoformat()
        event["user"] = username
        try:
            with open(f, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 埋点失败不影响主流程

    # ── ① 页面进入 / 离开 ──────────────────────────────
    @staticmethod
    def page_enter(username: str, module: str):
        """进入模块时调用"""
        key = f"_benter_{module}"
        st.session_state[key] = time.time()
        BehaviorLogger._write(username, {
            "event": "page_enter",
            "module": module,
        })

    @staticmethod
    def page_leave(username: str, module: str):
        """离开模块时调用（切换模式前）"""
        key = f"_benter_{module}"
        enter_t = st.session_state.get(key)
        duration = round(time.time() - enter_t, 1) if enter_t else 0
        BehaviorLogger._write(username, {
            "event": "page_leave",
            "module": module,
            "duration_sec": duration,
        })
        st.session_state.pop(key, None)

    # ── ② 答题计时 ────────────────────────────────────
    @staticmethod
    def question_shown(username: str, module: str, q_id: str = ""):
        """题目展示时调用"""
        st.session_state[f"_qshow_{module}_{q_id}"] = time.time()
        BehaviorLogger._write(username, {
            "event": "question_shown",
            "module": module,
            "q_id": q_id,
        })

    @staticmethod
    def question_answered(username: str, module: str,
                          q_id: str = "", correct: bool = False,
                          score: float = 0.0):
        """答题提交时调用"""
        key = f"_qshow_{module}_{q_id}"
        show_t = st.session_state.get(key)
        response_sec = round(time.time() - show_t, 1) if show_t else 0
        BehaviorLogger._write(username, {
            "event": "question_answered",
            "module": module,
            "q_id": q_id,
            "correct": correct,
            "score": score,
            "response_sec": response_sec,
        })
        st.session_state.pop(key, None)

    # ── ③ 音频播放 ────────────────────────────────────
    @staticmethod
    def audio_play(username: str, module: str,
                   audio_id: str = "", duration_sec: float = 0):
        """音频开始播放时调用"""
        st.session_state[f"_aplay_{module}_{audio_id}"] = time.time()
        BehaviorLogger._write(username, {
            "event": "audio_play",
            "module": module,
            "audio_id": audio_id,
            "total_sec": duration_sec,
        })

    @staticmethod
    def audio_end(username: str, module: str,
                  audio_id: str = "", listened_sec: float = 0,
                  total_sec: float = 0):
        """音频播放结束/跳过时调用"""
        completion = round(listened_sec / total_sec, 2) if total_sec > 0 else 1.0
        BehaviorLogger._write(username, {
            "event": "audio_end",
            "module": module,
            "audio_id": audio_id,
            "listened_sec": listened_sec,
            "total_sec": total_sec,
            "completion_rate": completion,
        })


# 简写别名
BLogger = BehaviorLogger


# ══════════════════════════════════════════════════════
# 数据读取与聚合（供 Admin 后台调用）
# ══════════════════════════════════════════════════════

class BehaviorReader:
    """读取并聚合行为日志，供 Admin 展示"""

    def __init__(self, data_dir: str):
        self.base = Path(data_dir) / "behavior_logs"

    def _iter_events(self, username: str, days: int = 30):
        """遍历最近 N 天的事件"""
        user_dir = self.base / username
        if not user_dir.exists():
            return
        from datetime import timedelta
        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(days)]
        for d in dates:
            f = user_dir / f"{d}.jsonl"
            if not f.exists():
                continue
            with open(f, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except Exception:
                            pass

    def get_user_summary(self, username: str, days: int = 30) -> dict:
        """返回单个用户的行为摘要"""
        module_time   = {}   # module → total seconds
        module_visits = {}   # module → visit count
        module_correct= {}   # module → [correct_count, total_count]
        module_resp   = {}   # module → [response_sec list]
        audio_comps   = []   # completion rates
        daily_active  = set()

        for ev in self._iter_events(username, days):
            mod = ev.get("module", "unknown")
            date = ev.get("ts", "")[:10]
            if date:
                daily_active.add(date)

            if ev["event"] == "page_leave":
                module_time[mod] = module_time.get(mod, 0) + ev.get("duration_sec", 0)
            elif ev["event"] == "page_enter":
                module_visits[mod] = module_visits.get(mod, 0) + 1
            elif ev["event"] == "question_answered":
                c = module_correct.setdefault(mod, [0, 0])
                c[1] += 1
                if ev.get("correct"): c[0] += 1
                r = module_resp.setdefault(mod, [])
                if ev.get("response_sec", 0) > 0:
                    r.append(ev["response_sec"])
            elif ev["event"] == "audio_end":
                cr = ev.get("completion_rate", 1.0)
                audio_comps.append(cr)

        # 整理
        accuracy = {
            m: round(v[0] / v[1] * 100, 1) if v[1] else 0
            for m, v in module_correct.items()
        }
        avg_resp = {
            m: round(sum(v) / len(v), 1) if v else 0
            for m, v in module_resp.items()
        }
        return {
            "module_time_sec":   module_time,
            "module_visits":     module_visits,
            "module_accuracy":   accuracy,
            "avg_response_sec":  avg_resp,
            "audio_completion":  round(sum(audio_comps) / len(audio_comps), 2) if audio_comps else None,
            "active_days":       sorted(daily_active)[-days:],
            "active_day_count":  len(daily_active),
            "total_questions":   sum(v[1] for v in module_correct.values()),
            "total_correct":     sum(v[0] for v in module_correct.values()),
        }

    def get_global_summary(self, usernames: list, days: int = 30) -> dict:
        """所有用户的聚合摘要"""
        module_time_total = {}
        module_visits_total = {}
        accuracy_pool = {}
        audio_comps = []
        active_today = set()
        today = datetime.now().strftime("%Y-%m-%d")

        for u in usernames:
            s = self.get_user_summary(u, days)
            if today in s["active_days"]:
                active_today.add(u)
            for m, t in s["module_time_sec"].items():
                module_time_total[m] = module_time_total.get(m, 0) + t
            for m, v in s["module_visits"].items():
                module_visits_total[m] = module_visits_total.get(m, 0) + v
            for m, a in s["module_accuracy"].items():
                pool = accuracy_pool.setdefault(m, [])
                pool.append(a)
            if s["audio_completion"] is not None:
                audio_comps.append(s["audio_completion"])

        avg_accuracy = {
            m: round(sum(v) / len(v), 1)
            for m, v in accuracy_pool.items() if v
        }
        return {
            "module_time_total":   module_time_total,
            "module_visits_total": module_visits_total,
            "avg_accuracy":        avg_accuracy,
            "avg_audio_completion": round(sum(audio_comps) / len(audio_comps) * 100, 1) if audio_comps else None,
            "active_today_count":  len(active_today),
        }
