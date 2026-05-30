"""
评审相关 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import json

import aiosqlite
from pathlib import Path
from app.database import get_db, DATABASE_PATH
from app.services.github_service import (
    GitHubService,
    GitHubServiceError,
    GitHubRateLimitError,
    GitHubPRNotFoundError,
    GitHubAuthError,
    GitHubNetworkError,
)
from app.services.ai_service import AIService

router = APIRouter()


class ReviewRequest(BaseModel):
    """评审请求"""
    pr_url: str
    github_token: Optional[str] = None


class ReviewResponse(BaseModel):
    """评审响应"""
    id: int
    pr_url: str
    pr_title: Optional[str]
    pr_author: Optional[str]
    summary: Optional[str]
    risk_level: Optional[str]
    status: str
    created_at: str


class ReviewDetailResponse(BaseModel):
    """评审详情响应"""
    id: int
    pr_url: str
    repo_owner: str
    repo_name: str
    pr_number: int
    pr_title: Optional[str]
    pr_author: Optional[str]
    summary: Optional[str]
    risk_level: Optional[str]
    analysis_result: Optional[dict]
    status: str
    created_at: str
    completed_at: Optional[str]


async def analyze_pr_background(review_id: int, pr_url: str, github_token: Optional[str]):
    """后台分析 PR"""
    try:
        # 解析 PR URL
        owner, repo, pr_number = GitHubService.parse_pr_url(pr_url)
        github = GitHubService(token=github_token)
        ai = AIService()

        # 获取 PR 信息
        pr_info = await github.get_pr_info(owner, repo, pr_number)
        files_changed = await github.get_pr_files(owner, repo, pr_number)
        diff_content = await github.get_pr_diff(owner, repo, pr_number)

        # AI 分析
        analysis_result = await ai.analyze_pr(pr_info, diff_content, files_changed)

        # 更新数据库
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """UPDATE reviews
                SET status = 'completed',
                    pr_title = ?,
                    pr_author = ?,
                    summary = ?,
                    risk_level = ?,
                    analysis_result = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    pr_info.get("title"),
                    pr_info.get("user", {}).get("login"),
                    analysis_result.get("summary"),
                    analysis_result.get("risk_level"),
                    json.dumps(analysis_result, ensure_ascii=False),
                    review_id,
                ),
            )

            # 保存问题详情
            for issue in analysis_result.get("issues", []):
                await db.execute(
                    """INSERT INTO issues (review_id, file_path, line_number, severity, category, description, suggestion, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review_id,
                        issue.get("file"),
                        issue.get("line"),
                        issue.get("severity"),
                        issue.get("category"),
                        issue.get("description"),
                        issue.get("suggestion"),
                        issue.get("confidence"),
                    ),
                )

            await db.commit()

    except (GitHubServiceError, Exception) as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"分析失败: {e}")
        print(error_traceback)

        # 根据错误类型提供友好的错误信息
        if isinstance(e, GitHubPRNotFoundError):
            error_msg = f"❌ {str(e)}"
        elif isinstance(e, GitHubRateLimitError):
            error_msg = f"⏰ {str(e)}"
        elif isinstance(e, GitHubAuthError):
            error_msg = f"🔒 {str(e)}"
        elif isinstance(e, GitHubNetworkError):
            error_msg = f"🌐 {str(e)}"
        else:
            error_msg = f"❌ 分析失败: {str(e)}"

        # 更新为失败状态，保存错误信息
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "UPDATE reviews SET status = 'failed', summary = ? WHERE id = ?",
                (error_msg, review_id),
            )
            await db.commit()


@router.post("/analyze", response_model=ReviewResponse)
async def create_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """创建 PR 分析任务"""
    try:
        # 验证 PR URL
        owner, repo, pr_number = GitHubService.parse_pr_url(request.pr_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        # 创建记录
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO reviews (user_id, pr_url, repo_owner, repo_name, pr_number, status)
                VALUES (1, ?, ?, ?, ?, 'analyzing')""",
                (request.pr_url, owner, repo, pr_number),
            )
            await db.commit()
            review_id = cursor.lastrowid

        # 后台执行分析
        background_tasks.add_task(analyze_pr_background, review_id, request.pr_url, request.github_token)

        return ReviewResponse(
            id=review_id,
            pr_url=request.pr_url,
            pr_title=None,
            pr_author=None,
            summary=None,
            risk_level=None,
            status="analyzing",
            created_at="now",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_review_history(limit: int = 20, offset: int = 0):
    """获取评审历史"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, pr_url, pr_title, pr_author, summary, risk_level, status, created_at
            FROM reviews
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()

        return [
            {
                "id": row["id"],
                "pr_url": row["pr_url"],
                "pr_title": row["pr_title"],
                "pr_author": row["pr_author"],
                "summary": row["summary"],
                "risk_level": row["risk_level"],
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


@router.get("/{review_id}")
async def get_review_detail(review_id: int):
    """获取评审详情"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        review = await cursor.fetchone()

        if not review:
            raise HTTPException(status_code=404, detail="评审记录不存在")

        # 获取问题列表
        cursor = await db.execute(
            "SELECT * FROM issues WHERE review_id = ? ORDER BY severity DESC",
            (review_id,),
        )
        issues = await cursor.fetchall()

        analysis_result = None
        if review["analysis_result"]:
            analysis_result = json.loads(review["analysis_result"])

        return {
            "id": review["id"],
            "pr_url": review["pr_url"],
            "repo_owner": review["repo_owner"],
            "repo_name": review["repo_name"],
            "pr_number": review["pr_number"],
            "pr_title": review["pr_title"],
            "pr_author": review["pr_author"],
            "summary": review["summary"],
            "risk_level": review["risk_level"],
            "analysis_result": analysis_result,
            "issues": [
                {
                    "id": issue["id"],
                    "file_path": issue["file_path"],
                    "line_number": issue["line_number"],
                    "severity": issue["severity"],
                    "category": issue["category"],
                    "description": issue["description"],
                    "suggestion": issue["suggestion"],
                    "confidence": issue["confidence"],
                }
                for issue in issues
            ],
            "status": review["status"],
            "created_at": review["created_at"],
            "completed_at": review["completed_at"],
        }


@router.delete("/{review_id}")
async def delete_review(review_id: int):
    """删除评审记录"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id FROM reviews WHERE id = ?", (review_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="评审记录不存在")

        await db.execute("DELETE FROM issues WHERE review_id = ?", (review_id,))
        await db.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        await db.commit()

        return {"message": "删除成功"}
