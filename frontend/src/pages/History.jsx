import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { GitPullRequest, Clock, Trash2, ExternalLink, Loader2, Filter, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { getReviewHistory, deleteReview } from '../services/api'

const riskLevelColors = {
  high: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  medium: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
  low: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
}

const statusLabels = {
  pending: { text: '等待中', color: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300' },
  analyzing: { text: '分析中', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' },
  completed: { text: '已完成', color: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' },
  failed: { text: '失败', color: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' },
}

export default function History() {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)
  const [riskFilter, setRiskFilter] = useState(null)

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const data = await getReviewHistory(50)
      setReviews(data)
    } catch (error) {
      toast.error('加载历史记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定要删除这条记录吗？')) return

    setDeleting(id)
    try {
      await deleteReview(id)
      setReviews(reviews.filter((r) => r.id !== id))
      toast.success('删除成功')
    } catch (error) {
      toast.error('删除失败')
    } finally {
      setDeleting(null)
    }
  }

  // 筛选后的数据
  const filteredReviews = useMemo(() => {
    return reviews.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false
      if (riskFilter && r.risk_level !== riskFilter) return false
      return true
    })
  }, [reviews, statusFilter, riskFilter])

  // 统计
  const statusCounts = useMemo(() => {
    const counts = {}
    reviews.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1 })
    return counts
  }, [reviews])

  const riskCounts = useMemo(() => {
    const counts = {}
    reviews.forEach((r) => {
      if (r.risk_level) counts[r.risk_level] = (counts[r.risk_level] || 0) + 1
    })
    return counts
  }, [reviews])

  const hasActiveFilter = statusFilter || riskFilter

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">分析历史</h1>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {hasActiveFilter ? `${filteredReviews.length}/${reviews.length}` : reviews.length} 条记录
        </span>
      </div>

      {/* 筛选器 */}
      {reviews.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
          <div className="flex items-center flex-wrap gap-3">
            <span className="flex items-center text-sm text-gray-500 dark:text-gray-400">
              <Filter className="w-4 h-4 mr-1" />
              筛选：
            </span>

            {/* 状态筛选 */}
            {Object.entries(statusLabels).map(([key, { text, color }]) => {
              const count = statusCounts[key] || 0
              if (count === 0) return null
              return (
                <button
                  key={key}
                  onClick={() => setStatusFilter(statusFilter === key ? null : key)}
                  className={`px-3 py-1 text-xs font-medium rounded-full transition-all ${
                    statusFilter === key
                      ? 'ring-2 ring-offset-1 ring-primary-400 ' + color
                      : color + ' opacity-70 hover:opacity-100'
                  }`}
                >
                  {text} ({count})
                </button>
              )
            })}

            <span className="w-px h-5 bg-gray-200 dark:bg-gray-600" />

            {/* 风险等级筛选 */}
            {['high', 'medium', 'low'].map((key) => {
              const count = riskCounts[key] || 0
              if (count === 0) return null
              const labels = { high: '高风险', medium: '中风险', low: '低风险' }
              return (
                <button
                  key={key}
                  onClick={() => setRiskFilter(riskFilter === key ? null : key)}
                  className={`px-3 py-1 text-xs font-medium rounded-full transition-all ${
                    riskFilter === key
                      ? 'ring-2 ring-offset-1 ring-primary-400 ' + riskLevelColors[key]
                      : riskLevelColors[key] + ' opacity-70 hover:opacity-100'
                  }`}
                >
                  {labels[key]} ({count})
                </button>
              )
            })}

            {hasActiveFilter && (
              <button
                onClick={() => { setStatusFilter(null); setRiskFilter(null) }}
                className="flex items-center text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 ml-2"
              >
                <X className="w-3 h-3 mr-1" />
                清除
              </button>
            )}
          </div>
        </div>
      )}

      {filteredReviews.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
          <GitPullRequest className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            {hasActiveFilter ? '没有符合筛选条件的记录' : '暂无分析记录'}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            {hasActiveFilter ? '尝试调整筛选条件' : '开始分析你的第一个 PR 吧'}
          </p>
          {!hasActiveFilter && (
            <Link
              to="/"
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              去分析
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReviews.map((review) => (
            <div
              key={review.id}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        statusLabels[review.status]?.color || 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {statusLabels[review.status]?.text || review.status}
                    </span>
                    {review.risk_level && (
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          riskLevelColors[review.risk_level] || ''
                        }`}
                      >
                        {review.risk_level === 'high' ? '高风险' : review.risk_level === 'medium' ? '中风险' : '低风险'}
                      </span>
                    )}
                  </div>

                  <Link
                    to={`/review/${review.id}`}
                    className="text-lg font-medium text-gray-900 dark:text-white hover:text-primary-600 transition-colors"
                  >
                    {review.pr_title || '未命名 PR'}
                  </Link>

                  <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500 dark:text-gray-400">
                    {review.pr_author && <span>作者: {review.pr_author}</span>}
                    <span className="flex items-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {new Date(review.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>

                  {review.summary && (
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 line-clamp-2">{review.summary}</p>
                  )}
                </div>

                <div className="flex items-center space-x-2 ml-4">
                  <a
                    href={review.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                    title="在 GitHub 查看"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                  <button
                    onClick={() => handleDelete(review.id)}
                    disabled={deleting === review.id}
                    className="p-2 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                    title="删除"
                  >
                    {deleting === review.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
