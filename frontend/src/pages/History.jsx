import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { GitPullRequest, Clock, Trash2, ExternalLink, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getReviewHistory, deleteReview } from '../services/api'

const riskLevelColors = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-green-100 text-green-700',
}

const statusLabels = {
  pending: { text: '等待中', color: 'bg-gray-100 text-gray-700' },
  analyzing: { text: '分析中', color: 'bg-blue-100 text-blue-700' },
  completed: { text: '已完成', color: 'bg-green-100 text-green-700' },
  failed: { text: '失败', color: 'bg-red-100 text-red-700' },
}

export default function History() {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)

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
        <h1 className="text-2xl font-bold text-gray-900">分析历史</h1>
        <span className="text-sm text-gray-500">共 {reviews.length} 条记录</span>
      </div>

      {reviews.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <GitPullRequest className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无分析记录</h3>
          <p className="text-gray-500 mb-4">开始分析你的第一个 PR 吧</p>
          <Link
            to="/"
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            去分析
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <div
              key={review.id}
              className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
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
                        {review.risk_level === 'high'
                          ? '高风险'
                          : review.risk_level === 'medium'
                          ? '中风险'
                          : '低风险'}
                      </span>
                    )}
                  </div>

                  <Link
                    to={`/review/${review.id}`}
                    className="text-lg font-medium text-gray-900 hover:text-primary-600 transition-colors"
                  >
                    {review.pr_title || '未命名 PR'}
                  </Link>

                  <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                    {review.pr_author && <span>作者: {review.pr_author}</span>}
                    <span className="flex items-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {new Date(review.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>

                  {review.summary && (
                    <p className="mt-2 text-sm text-gray-600 line-clamp-2">{review.summary}</p>
                  )}
                </div>

                <div className="flex items-center space-x-2 ml-4">
                  <a
                    href={review.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
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
