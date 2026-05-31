import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitPullRequest, ArrowRight, Loader2, Github, Sparkles, Shield, Zap, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { createReview } from '../services/api'

const examplePRs = [
  { url: 'https://github.com/pallets/flask/pull/5660', name: 'Flask - Session 重构' },
  { url: 'https://github.com/facebook/react/pull/28700', name: 'React - 新特性' },
  { url: 'https://github.com/fastapi/fastapi/pull/11000', name: 'FastAPI - Bug 修复' },
]

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

  const handleExampleClick = (url) => {
    setPrUrl(url)
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-12 pt-8">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-primary-500 to-purple-600 rounded-2xl mb-6 shadow-lg shadow-primary-500/30">
          <GitPullRequest className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          AI <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-purple-600">代码评审</span>助手
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto leading-relaxed">
          输入 GitHub Pull Request 链接，AI 自动分析代码变更
          <br />
          识别潜在问题，提供专业的评审建议
        </p>
      </div>

      {/* Input Form */}
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8 mb-8 relative overflow-hidden">
        {/* 装饰背景 */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-primary-50 to-purple-50 rounded-full -translate-y-32 translate-x-32 opacity-50"></div>

        <form onSubmit={handleSubmit} className="relative z-10">
          <div className="mb-5">
            <label className="flex items-center text-sm font-semibold text-gray-700 mb-2">
              <Github className="w-4 h-4 mr-2" />
              GitHub PR 链接
            </label>
            <input
              type="text"
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/123"
              className="w-full px-4 py-3.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-gray-50 hover:bg-white"
              disabled={isLoading}
            />
          </div>

          <div className="mb-6">
            <label className="flex items-center text-sm font-semibold text-gray-700 mb-2">
              <Shield className="w-4 h-4 mr-2" />
              GitHub Token
              <span className="ml-2 text-xs font-normal text-gray-400">(推荐)</span>
            </label>
            <input
              type="password"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx"
              className="w-full px-4 py-3.5 border border-gray-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-gray-50 hover:bg-white"
              disabled={isLoading}
            />
            <p className="mt-2 text-sm text-gray-500 flex items-center">
              <Zap className="w-3.5 h-3.5 mr-1 text-yellow-500" />
              提供 Token 可避免 API 频率限制，获得更好的分析体验
            </p>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center px-6 py-4 bg-gradient-to-r from-primary-600 to-purple-600 text-white font-semibold rounded-xl hover:from-primary-700 hover:to-purple-700 focus:ring-4 focus:ring-primary-200 transition-all shadow-lg shadow-primary-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                正在分析...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 mr-2" />
                开始分析
                <ArrowRight className="w-5 h-5 ml-2" />
              </>
            )}
          </button>
        </form>

        {/* 示例链接 */}
        <div className="relative z-10 mt-6 pt-6 border-t border-gray-100">
          <p className="text-sm text-gray-500 mb-3">试试这些示例：</p>
          <div className="flex flex-wrap gap-2">
            {examplePRs.map((pr, index) => (
              <button
                key={index}
                onClick={() => handleExampleClick(pr.url)}
                className="inline-flex items-center px-3 py-1.5 text-sm bg-gray-50 hover:bg-primary-50 text-gray-600 hover:text-primary-600 rounded-lg transition-colors border border-gray-200 hover:border-primary-200"
              >
                <ChevronRight className="w-3.5 h-3.5 mr-1" />
                {pr.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="grid md:grid-cols-3 gap-6 mb-12">
        <div className="group bg-white p-6 rounded-2xl border border-gray-100 hover:shadow-lg hover:border-primary-100 transition-all">
          <div className="w-12 h-12 bg-blue-50 group-hover:bg-blue-100 rounded-xl flex items-center justify-center mb-4 transition-colors">
            <span className="text-2xl">📋</span>
          </div>
          <h3 className="font-bold text-gray-900 mb-2 text-lg">变更总结</h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            自动分析 PR 的变更内容，生成结构化的变更摘要，快速了解 PR 目的
          </p>
        </div>

        <div className="group bg-white p-6 rounded-2xl border border-gray-100 hover:shadow-lg hover:border-yellow-100 transition-all">
          <div className="w-12 h-12 bg-yellow-50 group-hover:bg-yellow-100 rounded-xl flex items-center justify-center mb-4 transition-colors">
            <span className="text-2xl">⚠️</span>
          </div>
          <h3 className="font-bold text-gray-900 mb-2 text-lg">风险识别</h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            识别潜在的 Bug、安全漏洞、性能问题，按风险等级分类展示
          </p>
        </div>

        <div className="group bg-white p-6 rounded-2xl border border-gray-100 hover:shadow-lg hover:border-green-100 transition-all">
          <div className="w-12 h-12 bg-green-50 group-hover:bg-green-100 rounded-xl flex items-center justify-center mb-4 transition-colors">
            <span className="text-2xl">💡</span>
          </div>
          <h3 className="font-bold text-gray-900 mb-2 text-lg">改进建议</h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            针对具体代码行给出优化建议，帮助提升代码质量和可维护性
          </p>
        </div>
      </div>

      {/* Stats Section */}
      <div className="bg-gradient-to-r from-primary-600 to-purple-600 rounded-2xl p-8 text-white mb-12">
        <div className="grid md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold mb-1">⚡ 1 分钟</div>
            <div className="text-primary-100">平均分析时间</div>
          </div>
          <div>
            <div className="text-3xl font-bold mb-1">🎯 多维度</div>
            <div className="text-primary-100">代码质量分析</div>
          </div>
          <div>
            <div className="text-3xl font-bold mb-1">🔒 安全</div>
            <div className="text-primary-100">代码不上传存储</div>
          </div>
        </div>
      </div>
    </div>
  )
}
