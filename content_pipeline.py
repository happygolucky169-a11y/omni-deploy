"""
OMNI-LEARN OS — 内容生产流水线核心引擎
content_pipeline.py

功能：
  1. 支持音频（mp3/wav/m4a）和视频（mp4/mov/avi/mkv）输入
  2. 视频自动用 ffmpeg 提取音轨
  3. Whisper 转录成文字
  4. DeepSeek 分析难度等级（Lexile/CEFR）、词汇统计
  5. 结果可导出 txt / csv
  6. 转录结果自动分配到阅读分级书库
  7. 供 2_listening.py 和 4_reading.py 共享调用

用法：
  from content_pipeline import ContentPipeline
  pipeline = ContentPipeline(client, whisper_model, root_dir)
  result = pipeline.process(file_bytes, filename)
"""

import os
import json
import tempfile
import subprocess
import whisper
from openai import OpenAI

AUDIO_TYPES = [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]
VIDEO_TYPES = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"]

LEVEL_ANALYSIS_PROMPT = """Analyze this English text and return ONLY valid JSON:
{
  "cefr_level": "A1",
  "lexile_range": "200L-400L",
  "wpm_category": "slow/medium/fast/very_fast",
  "avg_sentence_length": 8,
  "vocabulary_size": 150,
  "topic": "family",
  "content_type": "dialogue/narrative/lecture/news/story",
  "key_vocabulary": ["word1", "word2", "word3", "word4", "word5"],
  "summary": "One sentence summary in Chinese",
  "suitable_age": "7-9岁",
  "reading_minutes": 2
}

CEFR rules based on sentence complexity and vocabulary:
- A0: Very simple, 3-5 words/sentence, basic 200 words
- A1: Simple sentences, 5-8 words, basic 500 words  
- A2: Some complex sentences, 8-12 words, 1000 words
- B1: Complex sentences, 12-18 words, 2000 words
- B2+: Academic/professional, 18+ words, 3000+ words

Text to analyze:
"""


class ContentPipeline:
    def __init__(self, deepseek_client: OpenAI, whisper_model, root_dir: str):
        self.client = deepseek_client
        self.whisper = whisper_model
        self.root_dir = root_dir
        self.ffmpeg = self._find_ffmpeg()
        self.save_dir = os.path.join(root_dir, "temp_uploads")
        os.makedirs(self.save_dir, exist_ok=True)
        self.library_file = os.path.join(root_dir, "reading_library.json")

    def _find_ffmpeg(self) -> str:
        candidates = [
            os.path.join(self.root_dir, "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(self.root_dir, "ffmpeg.exe"),
            "ffmpeg"
        ]
        for c in candidates:
            try:
                r = subprocess.run([c, "-version"], capture_output=True, timeout=3)
                if r.returncode == 0:
                    return c
            except:
                continue
        return "ffmpeg"

    def _extract_audio(self, video_path: str) -> str:
        """用 ffmpeg 从视频提取音频"""
        audio_path = video_path.replace(
            os.path.splitext(video_path)[1], "_extracted.mp3")
        cmd = [self.ffmpeg, "-y", "-i", video_path,
               "-vn", "-acodec", "mp3", "-ar", "16000", audio_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 提取音频失败: {result.stderr.decode()[-300:]}")
        return audio_path

    def _transcribe(self, audio_path: str) -> dict:
        """Whisper 转录"""
        result = self.whisper.transcribe(audio_path, language="en")
        text = result["text"].strip()
        segments = result.get("segments", [])
        duration = segments[-1]["end"] if segments else 1.0
        wpm = int(len(text.split()) / duration * 60)
        return {
            "transcript": text,
            "wpm": wpm,
            "duration": int(duration),
            "segments": segments
        }

    def _analyze_level(self, transcript: str) -> dict:
        """DeepSeek 分析难度等级"""
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user",
                           "content": LEVEL_ANALYSIS_PROMPT + transcript[:2000]}],
                max_tokens=400,
                temperature=0.2
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception as e:
            return {
                "cefr_level": "A2", "lexile_range": "500L-800L",
                "topic": "general", "content_type": "dialogue",
                "key_vocabulary": [], "summary": "内容分析失败",
                "suitable_age": "10-12岁", "reading_minutes": 3,
                "error": str(e)
            }

    def _save_to_library(self, filename: str, result: dict):
        """保存到阅读分级书库（供 4_reading.py 使用）"""
        library = {}
        if os.path.exists(self.library_file):
            try:
                with open(self.library_file, "r", encoding="utf-8") as f:
                    library = json.load(f)
            except:
                library = {}

        level = result.get("analysis", {}).get("cefr_level", "A2")
        if level not in library:
            library[level] = []

        # 检查是否已存在
        existing = [x for x in library[level] if x.get("source_file") == filename]
        if not existing:
            library[level].append({
                "source_file": filename,
                "title": os.path.splitext(filename)[0],
                "content_type": result.get("analysis", {}).get("content_type", "audio"),
                "topic": result.get("analysis", {}).get("topic", "general"),
                "summary": result.get("analysis", {}).get("summary", ""),
                "transcript": result.get("transcript", ""),
                "wpm": result.get("wpm", 0),
                "duration": result.get("duration", 0),
                "key_vocabulary": result.get("analysis", {}).get("key_vocabulary", []),
                "suitable_age": result.get("analysis", {}).get("suitable_age", ""),
                "lexile_range": result.get("analysis", {}).get("lexile_range", ""),
            })

        with open(self.library_file, "w", encoding="utf-8") as f:
            json.dump(library, f, ensure_ascii=False, indent=2)

    def process(self, file_bytes: bytes, filename: str,
                save_to_library: bool = True) -> dict:
        """
        主处理函数
        输入：文件字节流 + 文件名
        输出：{transcript, wpm, duration, analysis, file_type, audio_path}
        """
        ext = os.path.splitext(filename)[1].lower()
        file_path = os.path.join(self.save_dir, filename)

        # 保存原始文件
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # 判断是音频还是视频
        is_video = ext in VIDEO_TYPES
        file_type = "video" if is_video else "audio"

        # 视频 → 提取音频
        if is_video:
            audio_path = self._extract_audio(file_path)
        else:
            audio_path = file_path

        # Whisper 转录
        transcription = self._transcribe(audio_path)

        # DeepSeek 分析难度
        analysis = self._analyze_level(transcription["transcript"])

        result = {
            "filename": filename,
            "file_type": file_type,
            "audio_path": audio_path,
            "transcript": transcription["transcript"],
            "wpm": transcription["wpm"],
            "duration": transcription["duration"],
            "analysis": analysis,
        }

        # 保存到阅读书库
        if save_to_library:
            self._save_to_library(filename, result)

        return result

    def export_txt(self, results: list, output_path: str):
        """批量导出转录文本为 txt"""
        with open(output_path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(f"{'='*60}\n")
                f.write(f"文件: {r['filename']}\n")
                f.write(f"类型: {r['file_type']} | 语速: {r['wpm']} WPM | 时长: {r['duration']}秒\n")
                a = r.get("analysis", {})
                f.write(f"等级: {a.get('cefr_level','')} | {a.get('lexile_range','')}\n")
                f.write(f"主题: {a.get('topic','')} | 适合年龄: {a.get('suitable_age','')}\n")
                f.write(f"摘要: {a.get('summary','')}\n")
                f.write(f"核心词汇: {', '.join(a.get('key_vocabulary', []))}\n")
                f.write(f"\n原文:\n{r['transcript']}\n\n")

    def export_csv(self, results: list, output_path: str):
        """批量导出为 CSV"""
        import csv
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "filename", "file_type", "wpm", "duration",
                "cefr_level", "lexile_range", "topic", "suitable_age",
                "summary", "key_vocabulary", "transcript"
            ])
            writer.writeheader()
            for r in results:
                a = r.get("analysis", {})
                writer.writerow({
                    "filename": r["filename"],
                    "file_type": r["file_type"],
                    "wpm": r["wpm"],
                    "duration": r["duration"],
                    "cefr_level": a.get("cefr_level", ""),
                    "lexile_range": a.get("lexile_range", ""),
                    "topic": a.get("topic", ""),
                    "suitable_age": a.get("suitable_age", ""),
                    "summary": a.get("summary", ""),
                    "key_vocabulary": ", ".join(a.get("key_vocabulary", [])),
                    "transcript": r["transcript"][:500]
                })
