"""
GitHub 相关 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.services.github_service import GitHubService

router = APIRouter()


class PRUrlRequest(BaseModel):
    """PR URL 请求"""
    pr_url: str
    github_token: Optional[str] = None


class PRInfoResponse(BaseModel):
    """PR 信息响应"""
    owner: str
    repo: str
    pr_number: int
    title: str
    description: Optional[str]
    author: str
    state: str
    additions: int
    deletions: int
    changed_files: int


@router.post("/parse-url")
async def parse_pr_url(request: PRUrlRequest):
    """解析 PR URL"""
    try:
        owner, repo, pr_number = GitHubService.parse_pr_url(request.pr_url)
        return {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pr-info")
async def get_pr_info(request: PRUrlRequest):
    """获取 PR 详细信息"""
    try:
        owner, repo, pr_number = GitHubService.parse_pr_url(request.pr_url)
        github = GitHubService(token=request.github_token)
        pr_info = await github.get_pr_info(owner, repo, pr_number)

        return {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "title": pr_info.get("title"),
            "description": pr_info.get("body"),
            "author": pr_info.get("user", {}).get("login"),
            "state": pr_info.get("state"),
            "additions": pr_info.get("additions"),
            "deletions": pr_info.get("deletions"),
            "changed_files": pr_info.get("changed_files"),
            "base_branch": pr_info.get("base", {}).get("ref"),
            "head_branch": pr_info.get("head", {}).get("ref"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 PR 信息失败: {str(e)}")
