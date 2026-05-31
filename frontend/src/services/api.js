import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    }
    return Promise.reject(error)
  }
)

// ========== 评审相关 API ==========

/**
 * 创建 PR 分析任务
 */
export async function createReview(prUrl, githubToken = '') {
  return api.post('/reviews/analyze', {
    pr_url: prUrl,
    github_token: githubToken || undefined,
  })
}

/**
 * 获取评审详情
 */
export async function getReviewDetail(reviewId) {
  return api.get(`/reviews/${reviewId}`)
}

/**
 * 获取评审历史
 */
export async function getReviewHistory(limit = 20, offset = 0) {
  return api.get('/reviews/history', { params: { limit, offset } })
}

/**
 * 删除评审记录
 */
export async function deleteReview(reviewId) {
  return api.delete(`/reviews/${reviewId}`)
}

// ========== GitHub 相关 API ==========

/**
 * 解析 PR URL
 */
export async function parsePrUrl(prUrl) {
  return api.post('/github/parse-url', { pr_url: prUrl })
}

/**
 * 获取 PR 信息
 */
export async function getPrInfo(prUrl, githubToken = '') {
  return api.post('/github/pr-info', {
    pr_url: prUrl,
    github_token: githubToken || undefined,
  })
}

// ========== 认证相关 API ==========

/**
 * 用户注册
 */
export async function register(userData) {
  return api.post('/auth/register', userData)
}

/**
 * 用户登录
 */
export async function login(username, password) {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)

  return api.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export default api
