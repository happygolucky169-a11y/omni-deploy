"""
OMNI-LEARN OS — 智能内容匹配引擎 (高级数据解析版)
content_matcher.py
"""

import os
import json
import random

class ContentMatcher:
    def __init__(self, library_dir):
        self.library_dir = library_dir

    def _load_json_safe(self, filename):
        """安全加载 JSON，找不到文件绝不报错"""
        filepath = os.path.join(self.library_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_daily_recommendation(self, user_data, n_items=4):
        """生成每日推荐，精准提取最新版 JSON 的深层字段"""
        pool = []
        
        # 1. 匹配教材库 (textbook_library.json)
        tb_data = self._load_json_safe("textbook_library.json")
        if tb_data and "textbooks" in tb_data:
            for item in tb_data["textbooks"]:
                pool.append({
                    "card_type": "教材",
                    "level": item.get("omni_level", "?"),
                    "title": item.get("textbook_name", "未知教材"),
                    "description": item.get("summary_cn", "暂无简介")
                })
                
        # 2. 匹配绘本库 (picturebook_library.json 或 reading_library.json)
        pb_data = self._load_json_safe("picturebook_library.json")
        if pb_data and "books" in pb_data:
            for item in pb_data["books"]:
                # 适配新版知识树结构：提取二级标签并去掉前缀（如"动物/宠物"->"宠物"）
                tags = item.get("knowledge_tree", {}).get("level_2_tags", [])
                tag_str = " · ".join([t.split("/")[-1] for t in tags[:2]])
                desc = item.get("summary_cn", "")
                
                # 组合显示：[标签] 简介
                final_desc = f"[{tag_str}] {desc}" if tag_str else desc
                if not final_desc.strip(): final_desc = "暂无简介"
                
                pool.append({
                    "card_type": "绘本",
                    "level": item.get("omni_level", "?"),
                    "title": item.get("title", "未知绘本"),
                    "description": final_desc
                })

        # 3. 匹配音视频库 (media_library.json)
        media_data = self._load_json_safe("media_library.json")
        if media_data and "media" in media_data:
            for item in media_data["media"]:
                # 获取新版的时长格式和简介
                dur = item.get("duration_fmt", "")
                dur_str = f"⏱ {dur} | " if dur and dur != "--:--" else ""
                desc = item.get("summary_cn", "暂无简介")
                
                pool.append({
                    "card_type": "影音",
                    "level": item.get("omni_level", "?"),
                    "title": item.get("title", "未知视频"),
                    "description": f"{dur_str}{desc}"
                })

        # 4. 匹配电影库 (movie_library.json)
        movie_data = self._load_json_safe("movie_library.json")
        if movie_data and "movies" in movie_data:
            for item in movie_data["movies"]:
                dur = item.get("duration_fmt", "")
                dur_str = f"⏱ {dur} | " if dur and dur != "--:--" else ""
                desc = item.get("summary_cn", "暂无简介")
                
                pool.append({
                    "card_type": "电影",
                    "level": item.get("omni_level", "?"),
                    "title": item.get("title", "未知电影"),
                    "description": f"{dur_str}{desc}"
                })

        # 如果所有库都是空的（或者还没建库）
        if not pool:
            return {"cards": []}
            
        # 随机打乱，抽出需要的数量
        random.shuffle(pool)
        return {"cards": pool[:min(n_items, len(pool))]}

    def match_for_curriculum(self, unit_data, user_data):
        """教材同步模式的兜底数据"""
        return {
            "suggested_sequence": [
                {"skill": "vocabulary", "title": "AI 词汇闪卡提取", "level": unit_data.get("omni_level", 10)},
                {"skill": "reading", "title": "匹配的分级阅读拓展", "level": unit_data.get("omni_level", 10)}
            ]
        }
        
    def match_for_explorer(self, user_data, skills, mode):
        """自由探索模式的兜底数据"""
        result = {"by_skill": {}}
        for s in skills:
            result["by_skill"][s] = [
                {"omni_level": 20, "title": f"系统自动匹配的 {s} 资源", "summary_cn": "内容正在构建中..."}
            ]
        return result

    def get_library_stats(self):
        stats = {}
        tb_data = self._load_json_safe("textbook_library.json")
        stats["教材"] = len(tb_data.get("textbooks", [])) if tb_data else 0
        pb_data = self._load_json_safe("picturebook_library.json")
        stats["绘本"] = len(pb_data.get("books", [])) if pb_data else 0
        media_data = self._load_json_safe("media_library.json")
        stats["影音"] = len(media_data.get("media", [])) if media_data else 0
        movie_data = self._load_json_safe("movie_library.json")
        stats["电影"] = len(movie_data.get("movies", [])) if movie_data else 0
        return stats
