"""
AI 分析服务 - 使用 MiMo 模型
"""
import json
from openai import AsyncOpenAI
from app.config import get_settings


class AIService:
    """AI 代码分析服务"""

    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=self.settings.MIMO_API_KEY,
            base_url=self.settings.MIMO_BASE_URL,
        )
        self.model = self.settings.MIMO_MODEL

    async def analyze_pr(
        self,
        pr_info: dict,
        diff_content: str,
        files_changed: list,
    ) -> dict:
        """
        分析 PR 代码变更

        Args:
            pr_info: PR 基本信息
            diff_content: diff 内容
            files_changed: 变更文件列表

        Returns:
            dict: 分析结果
        """
        prompt = self._build_analysis_prompt(pr_info, diff_content, files_changed)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        result_text = response.choices[0].message.content
        # Fix surrogate pairs from MiMo model
        if result_text:
            result_text = self._fix_surrogates(result_text)
        return self._parse_analysis_result(result_text)

    def _fix_surrogates(self, text: str) -> str:
        """修复 Unicode 代理对问题"""
        # Method 1: Try surrogatepass
        try:
            fixed = text.encode('utf-16', 'surrogatepass').decode('utf-16')
            if not any(0xD800 <= ord(c) <= 0xDFFF for c in fixed):
                return fixed
        except Exception:
            pass

        # Method 2: Replace surrogates with replacement character
        result = []
        for char in text:
            cp = ord(char)
            if 0xD800 <= cp <= 0xDFFF:
                # Replace surrogate with replacement character
                result.append('�')
            else:
                result.append(char)
        return ''.join(result)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的代码评审专家，精通 Python、JavaScript、TypeScript 等主流编程语言。

你的任务是分析 GitHub Pull Request 的代码变更，提供专业、准确、有建设性的评审意见。

## 评审原则
1. 关注代码质量、安全性、性能和可维护性
2. 区分严重问题（必须修复）和建议改进（可以优化）
3. 提供具体的改进建议，包含代码示例
4. 尊重代码作者的意图，用建设性的语气
5. 对于不确定的问题，标注置信度（0.0-1.0）

## 输出要求
必须使用中文输出，返回标准 JSON 格式，包含以下字段：

```json
{
    "summary": "用2-3句话简述这个 PR 做了什么改动，为什么要做这个改动",
    "risk_level": "high/medium/low",
    "key_changes": ["变更点1", "变更点2"],
    "issues": [
        {
            "file": "文件路径",
            "line": 行号,
            "severity": "high/medium/low",
            "category": "bug/security/performance/style/other",
            "description": "问题描述（中文）",
            "suggestion": "改进建议（中文，可包含代码示例）",
            "confidence": 0.9
        }
    ],
    "positive_points": ["值得肯定的地方1", "值得肯定的地方2"],
    "overall_comment": "总体评价和建议（中文）"
}
```

注意：
- 所有文本字段必须使用中文
- issues 数组按严重程度排序（high 优先）
- 如果没有发现问题，issues 返回空数组
- confidence 表示你对这个问题的置信度"""

    def _build_analysis_prompt(
        self, pr_info: dict, diff_content: str, files_changed: list
    ) -> str:
        """构建分析提示词"""
        files_summary = "\n".join(
            [
                f"- {f['filename']}: +{f['additions']}/-{f['deletions']}"
                for f in files_changed[:20]  # 限制文件数量
            ]
        )

        # 截断过长的 diff
        max_diff_length = 15000
        if len(diff_content) > max_diff_length:
            diff_content = diff_content[:max_diff_length] + "\n\n[... diff 已截断 ...]"

        return f"""请分析以下 Pull Request：

## PR 信息
- 标题: {pr_info.get('title', 'N/A')}
- 描述: {pr_info.get('body', 'N/A')[:500]}
- 作者: {pr_info.get('user', {}).get('login', 'N/A')}
- 分支: {pr_info.get('head', {}).get('ref', 'N/A')} -> {pr_info.get('base', {}).get('ref', 'N/A')}

## 变更文件 ({len(files_changed)} 个)
{files_summary}

## 代码变更 (Diff)
```diff
{diff_content}
```

请提供详细的分析报告。"""

    def _parse_analysis_result(self, result_text: str) -> dict:
        """解析 AI 返回的分析结果"""
        try:
            # 尝试直接解析 JSON
            return json.loads(result_text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            try:
                start = result_text.index("{")
                end = result_text.rindex("}") + 1
                json_str = result_text[start:end]
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                # 解析失败，返回默认结构
                return {
                    "summary": result_text[:500],
                    "risk_level": "medium",
                    "key_changes": [],
                    "issues": [],
                    "positive_points": [],
                    "overall_comment": result_text,
                }
