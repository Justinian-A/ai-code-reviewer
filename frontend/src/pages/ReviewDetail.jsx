import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  ExternalLink,
  GitPullRequest,
  User,
  Clock,
  AlertTriangle,
  CheckCircle,
  Loader2,
  FileCode,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { getReviewDetail } from '../services/api'
import AnalysisProgress from '../components/AnalysisProgress'

const severityColors = {
  high: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: '🔴' },
  medium: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', icon: '🟡' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: '🔵' },
}

const categoryLabels = {
  bug: { label: 'Bug', color: 'bg-red-100 text-red-700' },
  security: { label: '安全', color: 'bg-purple-100 text-purple-700' },
  performance: { label: '性能', color: 'bg-orange-100 text-orange-700' },
  style: { label: '规范', color: 'bg-blue-100 text-blue-700' },
  other: { label: '其他', color: 'bg-gray-100 text-gray-700' },
}

export default function ReviewDetail() {
  const { id } = useParams()
  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedIssues, setExpandedIssues] = useState(new Set())
  const [polling, setPolling] = useState(false)
  const [startTime] = useState(Date.now())

  useEffect(() => {
    loadReview()
  }, [id])

  // 轮询分析状态
  useEffect(() => {
    if (!review || review.status === 'completed' || review.status === 'failed') {
      setPolling(false)
      return
    }

    setPolling(true)
    const interval = setInterval(async () => {
      try {
        const data = await getReviewDetail(id)
        setReview(data)
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval)
          setPolling(false)
          if (data.status === 'completed') {
            toast.success('分析完成！')
          }
        }
      } catch (error) {
        console.error('轮询失败:', error)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [review?.status, id])

  const loadReview = async () => {
    try {
      const data = await getReviewDetail(id)
      setReview(data)
    } catch (error) {
      toast.error('加载评审详情失败')
    } finally {
      setLoading(false)
    }
  }

  const toggleIssue = (issueId) => {
    const newExpanded = new Set(expandedIssues)
    if (newExpanded.has(issueId)) {
      newExpanded.delete(issueId)
    } else {
      newExpanded.add(issueId)
    }
    setExpandedIssues(newExpanded)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!review) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">未找到评审记录</p>
        <Link to="/" className="text-primary-600 hover:underline mt-2 inline-block">
          返回首页
        </Link>
      </div>
    )
  }

  const analysis = review.analysis_result || {}
  const issues = review.issues || []

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <Link
          to="/"
          className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回
        </Link>
        <a
          href={review.pr_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center text-primary-600 hover:text-primary-700 transition-colors"
        >
          在 GitHub 查看
          <ExternalLink className="w-4 h-4 ml-1" />
        </a>
      </div>

      {/* 分析中状态 */}
      {(review.status === 'analyzing' || review.status === 'pending') && (
        <AnalysisProgress startTime={startTime} />
      )}

      {/* 失败状态 */}
      {review.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-6">
          <div className="flex items-start">
            <AlertTriangle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-900">分析失败</h3>
              <p className="text-sm text-red-700 mt-1">
                {review.summary || '分析过程中出现错误，请检查 PR 链接是否正确，或稍后重试。'}
              </p>
              <div className="mt-3 flex space-x-3">
                <Link
                  to="/"
                  className="text-sm text-red-600 hover:text-red-800 underline"
                >
                  返回首页重试
                </Link>
                <a
                  href={review.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-red-600 hover:text-red-800 underline"
                >
                  在 GitHub 查看
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PR 基本信息 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {review.pr_title || `PR #${review.pr_number}`}
            </h1>
            <div className="flex items-center space-x-4 text-sm text-gray-500">
              <span className="flex items-center">
                <GitPullRequest className="w-4 h-4 mr-1" />
                {review.repo_owner}/{review.repo_name}#{review.pr_number}
              </span>
              {review.pr_author && (
                <span className="flex items-center">
                  <User className="w-4 h-4 mr-1" />
                  {review.pr_author}
                </span>
              )}
              <span className="flex items-center">
                <Clock className="w-4 h-4 mr-1" />
                {new Date(review.created_at).toLocaleString('zh-CN')}
              </span>
            </div>
          </div>

          {review.risk_level && (
            <span
              className={`px-3 py-1 text-sm font-medium rounded-full ${
                review.risk_level === 'high'
                  ? 'bg-red-100 text-red-700'
                  : review.risk_level === 'medium'
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-green-100 text-green-700'
              }`}
            >
              {review.risk_level === 'high'
                ? '⚠️ 高风险'
                : review.risk_level === 'medium'
                ? '⚡ 中风险'
                : '✅ 低风险'}
            </span>
          )}
        </div>
      </div>

      {/* 统计卡片 */}
      {analysis.summary && (
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-2xl font-bold text-primary-600">{issues.length}</div>
            <div className="text-sm text-gray-500">发现问题</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-2xl font-bold text-yellow-600">
              {issues.filter(i => i.severity === 'high').length}
            </div>
            <div className="text-sm text-gray-500">高风险</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {analysis.positive_points?.length || 0}
            </div>
            <div className="text-sm text-gray-500">优点</div>
          </div>
        </div>
      )}

      {/* 变更总结 */}
      {analysis.summary && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
            <FileCode className="w-5 h-5 mr-2 text-primary-600" />
            变更总结
          </h2>
          <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{analysis.summary}</p>

          {analysis.key_changes && analysis.key_changes.length > 0 && (
            <div className="mt-5 pt-5 border-t border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">主要变更：</h3>
              <div className="space-y-2">
                {analysis.key_changes.map((change, index) => (
                  <div key={index} className="flex items-start">
                    <span className="w-6 h-6 bg-primary-50 text-primary-600 rounded-full flex items-center justify-center text-xs font-medium mr-3 flex-shrink-0">
                      {index + 1}
                    </span>
                    <span className="text-gray-600 text-sm">{change}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 问题列表 */}
      {issues.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
            <AlertTriangle className="w-5 h-5 mr-2 text-yellow-600" />
            发现的问题
            <span className="ml-2 px-2.5 py-0.5 bg-yellow-50 text-yellow-700 text-sm font-medium rounded-full">
              {issues.length}
            </span>
          </h2>

          <div className="space-y-3">
            {issues.map((issue, index) => {
              const severity = severityColors[issue.severity] || severityColors.low
              const category = categoryLabels[issue.category] || categoryLabels.other
              const isExpanded = expandedIssues.has(issue.id)

              return (
                <div
                  key={issue.id}
                  className={`${severity.bg} border ${severity.border} rounded-xl overflow-hidden transition-all`}
                >
                  <button
                    onClick={() => toggleIssue(issue.id)}
                    className="w-full px-5 py-4 flex items-start justify-between text-left hover:opacity-90 transition-opacity"
                  >
                    <div className="flex items-start space-x-3">
                      <span className="text-lg mt-0.5">{severity.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center flex-wrap gap-2 mb-2">
                          <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${category.color}`}>
                            {category.label}
                          </span>
                          <span className={`px-2.5 py-0.5 text-xs font-medium rounded-full ${
                            issue.severity === 'high' ? 'bg-red-200 text-red-800' :
                            issue.severity === 'medium' ? 'bg-yellow-200 text-yellow-800' :
                            'bg-blue-200 text-blue-800'
                          }`}>
                            {issue.severity === 'high' ? '高' : issue.severity === 'medium' ? '中' : '低'}
                          </span>
                          {issue.file_path && (
                            <span className="text-xs text-gray-500 font-mono bg-white px-2 py-0.5 rounded">
                              {issue.file_path}
                              {issue.line_number && `:${issue.line_number}`}
                            </span>
                          )}
                        </div>
                        <p className={`font-medium ${severity.text}`}>{issue.description}</p>
                      </div>
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" />
                    )}
                  </button>

                  {isExpanded && issue.suggestion && (
                    <div className="px-5 pb-4 pt-1 ml-11">
                      <div className="bg-white rounded-xl p-4 border border-gray-200">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center">
                          💡 改进建议
                        </h4>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed">
                          {issue.suggestion}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 正面评价 */}
      {analysis.positive_points && analysis.positive_points.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-bold text-green-900 mb-4 flex items-center">
            <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
            值得肯定
          </h2>
          <div className="space-y-3">
            {analysis.positive_points.map((point, index) => (
              <div key={index} className="flex items-start">
                <span className="w-6 h-6 bg-green-200 text-green-700 rounded-full flex items-center justify-center text-xs mr-3 flex-shrink-0">
                  ✓
                </span>
                <span className="text-green-800 text-sm">{point}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 总体评价 */}
      {analysis.overall_comment && (
        <div className="bg-gradient-to-br from-primary-50 to-purple-50 border border-primary-100 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
            📝 总体评价
          </h2>
          <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{analysis.overall_comment}</p>
        </div>
      )}
    </div>
  )
}
