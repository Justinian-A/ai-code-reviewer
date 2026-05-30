"""
GitHub API 服务
"""
import httpx
from typing import Optional
from app.config import get_settings


class GitHubServiceError(Exception):
    """GitHub 服务错误基类"""
    pass


class GitHubRateLimitError(GitHubServiceError):
    """API 频率限制错误"""
    pass


class GitHubPRNotFoundError(GitHubServiceError):
    """PR 不存在错误"""
    pass


class GitHubAuthError(GitHubServiceError):
    """认证错误"""
    pass


class GitHubNetworkError(GitHubServiceError):
    """网络错误"""
    pass


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

    def _handle_response(self, response: httpx.Response, context: str = ""):
        """处理 API 响应错误"""
        if response.status_code == 200:
            return

        error_msg = f"GitHub API 错误 ({context})" if context else "GitHub API 错误"

        if response.status_code == 404:
            raise GitHubPRNotFoundError(f"{error_msg}: 资源不存在，请检查 PR 链接是否正确")
        elif response.status_code == 403:
            # 检查是否是频率限制
            if "rate limit" in response.text.lower():
                reset_time = response.headers.get("X-RateLimit-Reset", "")
                raise GitHubRateLimitError(
                    f"{error_msg}: API 频率限制，请提供 GitHub Token 或稍后重试"
                )
            raise GitHubAuthError(f"{error_msg}: 访问被拒绝，请检查 Token 权限")
        elif response.status_code == 401:
            raise GitHubAuthError(f"{error_msg}: 认证失败，请检查 Token 是否正确")
        else:
            raise GitHubServiceError(f"{error_msg}: HTTP {response.status_code}")

    async def get_pr_info(self, owner: str, repo: str, pr_number: int) -> dict:
        """获取 PR 基本信息"""
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                    headers=self.headers,
                )
                self._handle_response(response, f"获取 PR {owner}/{repo}#{pr_number}")
                return response.json()
        except httpx.TimeoutException:
            raise GitHubNetworkError("网络超时，请检查网络连接后重试")
        except httpx.NetworkError:
            raise GitHubNetworkError("网络连接失败，请检查网络连接")

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list:
        """获取 PR 变更的文件列表"""
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                    headers=self.headers,
                )
                self._handle_response(response, f"获取 PR 文件列表")
                return response.json()
        except httpx.TimeoutException:
            raise GitHubNetworkError("网络超时，请检查网络连接后重试")
        except httpx.NetworkError:
            raise GitHubNetworkError("网络连接失败，请检查网络连接")

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """获取 PR 的 diff 内容"""
        try:
            headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
            async with httpx.AsyncClient(trust_env=False, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}",
                    headers=headers,
                )
                self._handle_response(response, f"获取 PR diff")
                return response.text
        except httpx.TimeoutException:
            raise GitHubNetworkError("网络超时，请检查网络连接后重试")
        except httpx.NetworkError:
            raise GitHubNetworkError("网络连接失败，请检查网络连接")

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        """获取文件完整内容"""
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/contents/{path}",
                    headers=self.headers,
                    params={"ref": ref},
                )
                self._handle_response(response, f"获取文件 {path}")
                data = response.json()
                import base64
                return base64.b64decode(data["content"]).decode("utf-8")
        except httpx.TimeoutException:
            raise GitHubNetworkError("网络超时，请检查网络连接后重试")
        except httpx.NetworkError:
            raise GitHubNetworkError("网络连接失败，请检查网络连接")

    async def get_pr_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list:
        """获取 PR 评论"""
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                    headers=self.headers,
                )
                self._handle_response(response, f"获取 PR 评论")
                return response.json()
        except httpx.TimeoutException:
            raise GitHubNetworkError("网络超时，请检查网络连接后重试")
        except httpx.NetworkError:
            raise GitHubNetworkError("网络连接失败，请检查网络连接")

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
