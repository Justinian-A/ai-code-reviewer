import { useState, useEffect } from 'react'
import { Loader2, GitPullRequest, FileCode, Brain, CheckCircle } from 'lucide-react'

const steps = [
  { icon: GitPullRequest, label: '获取 PR 信息', duration: 5000 },
  { icon: FileCode, label: '读取代码变更', duration: 8000 },
  { icon: Brain, label: 'AI 分析中', duration: 30000 },
  { icon: CheckCircle, label: '生成报告', duration: 3000 },
]

export default function AnalysisProgress({ startTime }) {
  const [currentStep, setCurrentStep] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const elapsed = Date.now() - startTime
    let accumulated = 0

    for (let i = 0; i < steps.length; i++) {
      accumulated += steps[i].duration
      if (elapsed < accumulated) {
        setCurrentStep(i)
        const stepProgress = (elapsed - (accumulated - steps[i].duration)) / steps[i].duration
        setProgress(Math.min(stepProgress * 100, 100))
        break
      }
    }

    if (elapsed >= accumulated) {
      setCurrentStep(steps.length - 1)
      setProgress(100)
    }

    const timer = setInterval(() => {
      const elapsed = Date.now() - startTime
      let accumulated = 0

      for (let i = 0; i < steps.length; i++) {
        accumulated += steps[i].duration
        if (elapsed < accumulated) {
          setCurrentStep(i)
          const stepProgress = (elapsed - (accumulated - steps[i].duration)) / steps[i].duration
          setProgress(Math.min(stepProgress * 100, 100))
          break
        }
      }

      if (elapsed >= accumulated) {
        setCurrentStep(steps.length - 1)
        setProgress(100)
      }
    }, 500)

    return () => clearInterval(timer)
  }, [startTime])

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
      <div className="text-center mb-6">
        <Loader2 className="w-12 h-12 text-primary-600 animate-spin mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">正在分析 PR</h2>
        <p className="text-gray-500">AI 正在分析代码变更，请稍候...</p>
      </div>

      {/* Progress Steps */}
      <div className="max-w-md mx-auto">
        {steps.map((step, index) => {
          const Icon = step.icon
          const isActive = index === currentStep
          const isCompleted = index < currentStep

          return (
            <div key={index} className="flex items-center mb-4 last:mb-0">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center mr-4 transition-colors ${
                  isCompleted
                    ? 'bg-green-100 text-green-600'
                    : isActive
                    ? 'bg-primary-100 text-primary-600'
                    : 'bg-gray-100 text-gray-400'
                }`}
              >
                {isCompleted ? (
                  <CheckCircle className="w-5 h-5" />
                ) : (
                  <Icon className={`w-5 h-5 ${isActive ? 'animate-pulse' : ''}`} />
                )}
              </div>

              <div className="flex-1">
                <p
                  className={`text-sm font-medium ${
                    isActive ? 'text-primary-600' : isCompleted ? 'text-green-600' : 'text-gray-400'
                  }`}
                >
                  {step.label}
                </p>
                {isActive && (
                  <div className="mt-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-center text-sm text-gray-400 mt-6">预计需要 1-2 分钟</p>
    </div>
  )
}
