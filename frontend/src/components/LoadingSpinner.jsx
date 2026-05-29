import { Loader2 } from 'lucide-react'

export default function LoadingSpinner({ text = '加载中...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Loader2 className="w-8 h-8 text-primary-600 animate-spin mb-4" />
      <p className="text-gray-500 text-sm">{text}</p>
    </div>
  )
}
