"""
GitHub API 服务
"""
import httpx
from typing import Optional
from app.config import get_settings


class GitHubService:
    """GitHub API 交互服务"""

    def __init__(self, token: Optional[str] = None):
        self.settings = get_settings()
        self.base_url = self.settings.GITHUB_API_BASE
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def get_pr_info(self, owner: str, repo: str, pr_number: int) -> dict:
        """获取 PR 基本信息"""
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self.headers,
            )
            if response.status_code == 403:
                raise Exception("GitHub API 频率限制，请提供 GitHub Token 或稍后重试")
            response.raise_for_status()
            return response.json()

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list:
        """获取 PR 变更的文件列表"""
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """获取 PR 的 diff 内容"""
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            response.raise_for_status()
            return response.text

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        """获取文件完整内容"""
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/contents/{path}",
                headers=self.headers,
                params={"ref": ref},
            )
            response.raise_for_status()
            data = response.json()
            import base64

            return base64.b64decode(data["content"]).decode("utf-8")

    async def get_pr_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list:
        """获取 PR 评论"""
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def parse_pr_url(url: str) -> tuple:
        """
        解析 PR URL

        Args:
            url: GitHub PR URL

        Returns:
            tuple: (owner, repo, pr_number)
        """
        # 支持格式: https://github.com/owner/repo/pull/123
        parts = url.strip("/").split("/")
        if "github.com" in url and "pull" in parts:
            pull_index = parts.index("pull")
            owner = parts[pull_index - 2]
            repo = parts[pull_index - 1]
            pr_number = int(parts[pull_index + 1])
            return owner, repo, pr_number
        raise ValueError(f"无法解析 PR URL: {url}")
