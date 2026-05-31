/**
 * 代码块组件 - 支持语法高亮
 */
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// 语言映射
const languageMap = {
  py: 'python',
  js: 'javascript',
  jsx: 'jsx',
  ts: 'typescript',
  tsx: 'tsx',
  rb: 'ruby',
  yml: 'yaml',
  yaml: 'yaml',
  sh: 'bash',
  md: 'markdown',
}

function detectLanguage(code, hint) {
  if (hint) {
    return languageMap[hint.toLowerCase()] || hint.toLowerCase()
  }
  // 简单的语言检测
  if (code.includes('def ') || code.includes('import ') || code.includes('print(')) return 'python'
  if (code.includes('function ') || code.includes('const ') || code.includes('=>')) return 'javascript'
  if (code.includes('class ') && code.includes('public ')) return 'java'
  if (code.includes('#include')) return 'cpp'
  return 'text'
}

export default function CodeBlock({ code, language, className = '' }) {
  const lang = detectLanguage(code, language)

  return (
    <div className={`rounded-lg overflow-hidden ${className}`}>
      <SyntaxHighlighter
        language={lang}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: '1rem',
          fontSize: '0.875rem',
          lineHeight: '1.5',
          borderRadius: '0.5rem',
        }}
        showLineNumbers
        lineNumberStyle={{
          minWidth: '2.5em',
          paddingRight: '1em',
          opacity: 0.5,
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

/**
 * Diff 代码块 - 统一 diff 样式
 */
export function DiffBlock({ diff, className = '' }) {
  if (!diff) return null

  const lines = diff.split('\n')
  // 只取前 200 行，避免过长
  const truncated = lines.length > 200
  const displayLines = truncated ? lines.slice(0, 200) : lines

  return (
    <div className={`rounded-lg overflow-hidden ${className}`}>
      <div className="bg-gray-900 text-gray-100 font-mono text-sm overflow-x-auto">
        <pre className="p-4">
          {displayLines.map((line, i) => {
            let lineClass = ''
            if (line.startsWith('+') && !line.startsWith('+++')) {
              lineClass = 'bg-green-900/30 text-green-300'
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              lineClass = 'bg-red-900/30 text-red-300'
            } else if (line.startsWith('@@')) {
              lineClass = 'text-blue-400'
            } else if (line.startsWith('diff --git') || line.startsWith('index ') || line.startsWith('---') || line.startsWith('+++')) {
              lineClass = 'text-gray-500'
            }
            return (
              <div key={i} className={`${lineClass} px-2 -mx-2`}>
                {line || ' '}
              </div>
            )
          })}
          {truncated && (
            <div className="text-gray-500 mt-2">
              ... 已截断（共 {lines.length} 行）
            </div>
          )}
        </pre>
      </div>
    </div>
  )
}
