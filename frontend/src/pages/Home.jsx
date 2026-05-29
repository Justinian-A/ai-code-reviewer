import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitPullRequest, ArrowRight, Loader2, Github } from 'lucide-react'
import toast from 'react-hot-toast'
import { createReview } from '../services/api'

export default function Home() {
  const [prUrl, setPrUrl] = useState('')
  const [githubToken, setGithubToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!prUrl.trim()) {
      toast.error('请输入 PR 链接')
      return
    }

    // 验证 URL 格式
    if (!prUrl.includes('github.com') || !prUrl.includes('/pull/')) {
      toast.error('请输入有效的 GitHub PR 链接')
      return
    }

    setIsLoading(true)

    try {
      const result = await createReview(prUrl, githubToken)
      toast.success('分析任务已创建，正在处理...')
      navigate(`/review/${result.id}`)
    } catch (error) {
      toast.error(error.response?.data?.detail || '创建分析任务失败')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-full mb-4">
          <GitPullRequest className="w-8 h-8 text-primary-600" />
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          AI 代码评审助手
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          输入 GitHub Pull Request 链接，AI 自动分析代码变更，识别潜在问题，提供专业的评审建议
        </p>
      </div>

      {/* Input Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Github className="inline w-4 h-4 mr-1" />
              GitHub PR 链接
            </label>
            <input
              type="text"
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/123"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              disabled={isLoading}
            />
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              GitHub Token（推荐）
            </label>
            <input
              type="password"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-500">
              未认证的 API 每小时仅 60 次请求，提供 Token 可避免频率限制
            </p>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                正在分析...
              </>
            ) : (
              <>
                开始分析
                <ArrowRight className="w-5 h-5 ml-2" />
              </>
            )}
          </button>
        </form>
      </div>

      {/* Features Section */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mb-3">
            <span className="text-xl">📋</span>
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">变更总结</h3>
          <p className="text-sm text-gray-600">
            自动分析 PR 的变更内容，生成结构化的变更摘要，快速了解 PR 目的
          </p>
        </div>

        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center mb-3">
            <span className="text-xl">⚠️</span>
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">风险识别</h3>
          <p className="text-sm text-gray-600">
            识别潜在的 Bug、安全漏洞、性能问题，按风险等级分类展示
          </p>
        </div>

        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mb-3">
            <span className="text-xl">💡</span>
          </div>
          <h3 className="font-semibold text-gray-900 mb-2">改进建议</h3>
          <p className="text-sm text-gray-600">
            针对具体代码行给出优化建议，帮助提升代码质量和可维护性
          </p>
        </div>
      </div>
    </div>
  )
}
