import { Link, useLocation } from 'react-router-dom'
import { GitPullRequest, History, Home } from 'lucide-react'

export default function Navbar() {
  const location = useLocation()

  const isActive = (path) => {
    return location.pathname === path
      ? 'bg-primary-700 text-white'
      : 'text-primary-100 hover:bg-primary-600'
  }

  return (
    <nav className="bg-primary-600 shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2 text-white font-bold text-xl">
            <GitPullRequest size={24} />
            <span>AI Code Reviewer</span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center space-x-1">
            <Link
              to="/"
              className={`flex items-center space-x-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/')}`}
            >
              <Home size={16} />
              <span>首页</span>
            </Link>
            <Link
              to="/history"
              className={`flex items-center space-x-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/history')}`}
            >
              <History size={16} />
              <span>历史记录</span>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}
