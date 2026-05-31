/**
 * Markdown 渲染器 - 解析 AI 建议中的代码块
 */
import { useMemo } from 'react'
import CodeBlock from './CodeBlock'

// 解析 markdown 中的代码块
function parseMarkdown(text) {
  if (!text) return [{ type: 'text', content: '' }]

  const parts = []
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(text)) !== null) {
    // 代码块前的文本
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    // 代码块
    parts.push({
      type: 'code',
      language: match[1] || null,
      content: match[2].trimEnd(),
    })
    lastIndex = match.index + match[0].length
  }

  // 剩余文本
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) })
  }

  return parts.length > 0 ? parts : [{ type: 'text', content: text }]
}

// 解析行内代码
function InlineCode({ text }) {
  const parts = text.split(/(`[^`]+`)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code
              key={i}
              className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded text-sm font-mono"
            >
              {part.slice(1, -1)}
            </code>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

export default function MarkdownRenderer({ content, className = '' }) {
  const parts = useMemo(() => parseMarkdown(content), [content])

  if (!content) return null

  return (
    <div className={className}>
      {parts.map((part, index) => {
        if (part.type === 'code') {
          return (
            <CodeBlock
              key={index}
              code={part.content}
              language={part.language}
              className="my-3"
            />
          )
        }
        // 文本部分，处理换行和行内代码
        const lines = part.content.split('\n')
        return (
          <div key={index}>
            {lines.map((line, lineIndex) => (
              <p key={lineIndex} className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                {line ? <InlineCode text={line} /> : <br />}
              </p>
            ))}
          </div>
        )
      })}
    </div>
  )
}
