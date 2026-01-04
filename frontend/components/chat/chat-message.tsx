"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Bot,
  User,
  Database,
  AlertCircle,
  CheckCircle,
  Clock,
  ThumbsUp,
  ThumbsDown
} from "lucide-react"
// import ReactMarkdown from 'react-markdown'
// import remarkGfm from 'remark-gfm'

export interface ChatMessage {
  id: string
  type: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  metadata?: {
    intent_type?: string
    execution_time?: number
    sql_query?: string
    row_count?: number
    error?: string
    results?: any
    success?: boolean
    sql_generated?: string
    sql_validated?: boolean
    sql_executed?: boolean
    execution_status?: string
    sql_validation_status?: string
    execution_time_ms?: number
    conversational_response?: string
    // Debug fields
    debug_generated_sql?: string
    debug_sql_length?: number
  }
}

interface ChatMessageProps {
  message: ChatMessage
  onFeedback?: (messageId: string, rating: number) => void
  language?: string
}

export function ChatMessage({ message, onFeedback, language }: ChatMessageProps) {
  // RTL only for Persian language AND conversational content (not SQL queries/tables)
  const isPersianLanguage = language === 'fa' || language === 'persian'
  const isConversational = message.metadata?.intent_type === 'conversational' ||
                          message.metadata?.conversational_response ||
                          (!message.metadata?.results && !message.metadata?.sql_query)
  const isRTL = isPersianLanguage && isConversational
  const isUserMessage = message.type === 'user'
  const messageDirection = isRTL ? 'rtl' : 'ltr'
  const decodePersianText = (text: string) => {
    try {
      // Try to decode Persian text that might be encoded
      let decoded = text.replace(/�/g, '') // Remove replacement characters

      // Common Persian word mappings based on the encoded patterns
      const mappings = {
        'O�O�OU? O3U?U_ O�U?O�O�OO3U?O� O�U?O3O1U? U?O1OO_U? U? O�U?OU?O1 U?O1O_U?U? O"U?U?O� Uc': 'زغال سنگ آنتراسیت توسعه معادن و صنایع معدنی بلور ک',
        'O\'O�UcO� O�U?O3O1U? U?O1OO_U? U?O�U?OU?O1 U?O1O_U?U? O"U?U?O�UcU?U?O�': 'شرکت توسعه معادن وصنایع معدنی بلورکویر',
        'O�O�OU? O3U?U_ O�U?O�O�OO3U?O�': 'زغال سنگ آنتراسیت توسعه معادن و صنایع معدنی بلور ک',
        'O\'O�UcO� O�U?O3O1U? U?O1OO_U? U? O�U?OU?O1 U?O1O_U?U? O"U?U?O� UcU?U?O�': 'شرکت توسعه معادن و صنایع معدنی بلور کویر',
        'O"OU?Uc OrOU?O�U?U?OU?U?': 'بانک خاورمیانه',
        'O�U?': 'تن',
        'O�U?OU?': 'ریال',
        'U?U?O_U?': 'نقدی',
        'O�U?U? O"OO�OO�': 'طول بازار',
        'O3OU?O� OOU?U? U?OU? OU?O�U?U?': 'سایر حامل های انرژی',
        'O_OOrU?U?': 'داخلی'
      }

      for (const [encoded, decoded_text] of Object.entries(mappings)) {
        decoded = decoded.replace(new RegExp(encoded.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), decoded_text)
      }

      return decoded
    } catch {
      return text
    }
  }

  const formatMessageContent = (content: string) => {
    // Decode Persian text first
    const decodedContent = decodePersianText(content)

    // Check if content contains markdown (tables, code blocks, etc.)
    const hasMarkdown = /\*\*.*\*\*|\`\`\`|\|.*\|/.test(decodedContent)

    if (hasMarkdown) {
      // Simple markdown rendering without ReactMarkdown

      // Split by lines and process each line
      const lines = decodedContent.split('\n')
      const elements: React.JSX.Element[] = []
      let inCodeBlock = false
      let codeBlockContent = ''
      let codeBlockLanguage = ''

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]

        // Handle code blocks
        if (line.startsWith('```')) {
          if (inCodeBlock) {
            // End of code block
            elements.push(
              <pre key={`code-${i}`} className="bg-gray-800 text-green-400 p-4 rounded-lg overflow-x-auto my-4">
                <code className={codeBlockLanguage ? `language-${codeBlockLanguage}` : ''}>
                  {codeBlockContent.trim()}
                </code>
              </pre>
            )
            inCodeBlock = false
            codeBlockContent = ''
            codeBlockLanguage = ''
          } else {
            // Start of code block
            inCodeBlock = true
            codeBlockLanguage = line.substring(3).trim()
          }
          continue
        }

        if (inCodeBlock) {
          codeBlockContent += line + '\n'
          continue
        }

        // Handle table rows
        if (line.includes('|') && line.trim().startsWith('|')) {
          const cells = line.split('|').slice(1, -1).map(cell => cell.trim())
          if (cells.length > 0) {
            // Check if this is a separator row
            const isSeparator = cells.every(cell => /^-+$/.test(cell))
            if (isSeparator) {
              // This is handled by CSS, skip
              continue
            }

            elements.push(
              <div key={`table-row-${i}`} className="flex border-b border-gray-200 dark:border-gray-700">
                {cells.map((cell, cellIndex) => (
                  <div key={cellIndex} className="flex-1 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 border-r border-gray-200 dark:border-gray-700 last:border-r-0">
                    {cell}
                  </div>
                ))}
              </div>
            )
            continue
          }
        }

        // Handle bold text
        if (line.includes('**')) {
          const parts = line.split(/(\*\*.*?\*\*)/g)
          const processedParts = parts.map((part, partIndex) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={partIndex} className="font-bold">{part.slice(2, -2)}</strong>
            }
            return part
          })

          elements.push(
            <p key={`line-${i}`} className="mb-2 last:mb-0">
              {processedParts}
            </p>
          )
          continue
        }

        // Regular text
        if (line.trim()) {
          elements.push(
            <p key={`line-${i}`} className="mb-2 last:mb-0">
              {line}
            </p>
          )
        } else {
          // Empty line
          elements.push(<br key={`line-${i}`} />)
        }
      }

      return <div className="space-y-2">{elements}</div>
    } else {
      // Use simple text formatting for plain content
      return decodedContent.split('\n\n').map((paragraph, index) => {
        const lines = paragraph.split('\n')
        return (
          <div key={index} className={index > 0 ? 'mt-4' : ''}>
            {lines.map((line, lineIndex) => {
              // Check if line starts with bullet point
              if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
                return (
                  <div key={lineIndex} className="ml-4">
                    {line}
                  </div>
                )
              }
              // Check if line starts with number (suggestion format)
              if (/^\d+\.\s/.test(line.trim())) {
                return (
                  <div key={lineIndex} className="ml-4">
                    {line}
                  </div>
                )
              }
              return lineIndex > 0 ? <br key={lineIndex} /> : line
            })}
          </div>
        )
      })
    }
  }

  const getIntentIcon = (intentType: string) => {
    switch (intentType) {
      case 'sql_question':
        return <Database className="h-4 w-4" />
      case 'explain_result':
        return <AlertCircle className="h-4 w-4" />
      case 'meta_question':
        return <CheckCircle className="h-4 w-4" />
      case 'help_error':
        return <AlertCircle className="h-4 w-4" />
      default:
        return <Bot className="h-4 w-4" />
    }
  }

  const getIntentColor = (intentType: string) => {
    switch (intentType) {
      case 'sql_question':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'explain_result':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'meta_question':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      case 'help_error':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  return (
    <div className={`flex gap-2 sm:gap-3 group ${
      message.type === 'user' ? 'justify-end' : 'justify-start'
    }`}>
      {message.type === 'assistant' && (
        <div className="w-6 h-6 sm:w-8 sm:h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
          <Bot className="h-3 w-3 sm:h-4 sm:w-4 text-white" />
        </div>
      )}

      <div className={`max-w-[85%] sm:max-w-[75%] lg:max-w-[70%] ${message.type === 'user' ? 'order-1' : 'order-2'}`}>
        <Card className={`shadow-sm hover:shadow-md transition-all ${
          message.type === 'user'
            ? 'bg-blue-600 text-white border-blue-700'
            : message.type === 'system'
            ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
            : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
        }`} dir={messageDirection}>
          <CardContent className="p-3 sm:p-4" dir={messageDirection}>
            {/* Message Metadata - Only show for assistant messages */}
            {message.metadata && message.type === 'assistant' && (
              <div className={`flex items-center gap-1 sm:gap-2 mb-2 flex-wrap ${isRTL ? 'flex-row-reverse' : ''}`}>
                {message.metadata.intent_type && (
                  <Badge className={`text-xs ${getIntentColor(message.metadata.intent_type)}`}>
                    {getIntentIcon(message.metadata.intent_type)}
                    <span className={`ml-1 capitalize hidden sm:inline ${isRTL ? 'mr-1 ml-0' : ''}`}>
                      {message.metadata.intent_type.replace('_', ' ')}
                    </span>
                  </Badge>
                )}
                {message.metadata.execution_time && (
                  <Badge variant="outline" className="text-xs">
                    <Clock className={`h-3 w-3 ${isRTL ? 'ml-1 mr-0' : 'mr-1'}`} />
                    <span className="hidden sm:inline">{message.metadata.execution_time}ms</span>
                    <span className="sm:hidden">{message.metadata.execution_time}</span>
                  </Badge>
                )}
                {message.metadata.row_count !== undefined && (
                  <Badge variant="outline" className="text-xs">
                    <Database className={`h-3 w-3 ${isRTL ? 'ml-1 mr-0' : 'mr-1'}`} />
                    <span className="hidden sm:inline">{message.metadata.row_count} rows</span>
                    <span className="sm:hidden">{message.metadata.row_count}</span>
                  </Badge>
                )}
              </div>
            )}

            {/* Message Content */}
            <div className={`prose prose-sm max-w-none dark:prose-invert break-words overflow-wrap-anywhere ${isRTL ? 'rtl' : 'ltr'}`}>
              <div className="overflow-x-auto w-full">
                <div className={`min-w-0 ${isRTL ? 'text-right' : 'text-left'}`}>
                  {formatMessageContent(message.content)}
                </div>
              </div>
            </div>

            {/* Execution Results Display */}
            {message.metadata?.results && Array.isArray(message.metadata.results) && message.metadata.results.length > 0 && (
              <div className="mt-3 sm:mt-4">
                <div className={`bg-gray-50 dark:bg-gray-900 rounded p-3 sm:p-4 ${isRTL ? 'rtl' : 'ltr'}`}>
                  <h4 className={`text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 ${isRTL ? 'text-right' : 'text-left'}`}>
                    Query Results ({message.metadata.results.length} rows)
                  </h4>
                  <div className="overflow-x-auto max-h-96 border border-gray-200 dark:border-gray-700 rounded -mx-2 sm:mx-0">
                    <div className={`min-w-full inline-block ${isRTL ? 'rtl' : 'ltr'}`}>
                      <table className={`min-w-full text-xs ${isRTL ? 'rtl' : 'ltr'}`}>
                        <thead className="sticky top-0 bg-gray-100 dark:bg-gray-800 z-10">
                          <tr className="border-b border-gray-300 dark:border-gray-600">
                            {Object.keys(message.metadata.results[0]).map((col: string, index: number) => (
                              <th key={index} className={`${isRTL ? 'text-right' : 'text-left'} px-2 sm:px-3 py-2 font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap`}>
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {message.metadata.results.map((row: any, rowIndex: number) => (
                            <tr key={rowIndex} className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800">
                              {Object.keys(row).map((col: string, colIndex: number) => (
                                <td key={colIndex} className={`${isRTL ? 'text-right' : 'text-left'} px-2 sm:px-3 py-2 text-gray-800 dark:text-gray-200 whitespace-nowrap max-w-[200px] sm:max-w-none truncate sm:truncate-none`}>
                                  {String(row[col] ?? '')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* SQL Query Display - Only show if not already in content */}
            {message.metadata?.sql_query && message.metadata.sql_query.trim() &&
             !message.content.includes('Generated SQL') && (
              <div className="mt-3">
                <div className={`bg-gray-50 dark:bg-gray-900 rounded p-3 ${isRTL ? 'rtl' : 'ltr'}`}>
                  <div className={`text-xs sm:text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 ${isRTL ? 'text-right' : 'text-left'}`}>
                    SQL Query:
                  </div>
                  <div className="overflow-x-auto -mx-1 sm:mx-0">
                    <pre className={`text-xs bg-gray-800 text-green-400 p-2 sm:p-3 rounded whitespace-pre-wrap break-words overflow-x-auto ${isRTL ? 'text-right' : 'text-left'}`}>
                      <code>{message.metadata.sql_query}</code>
                    </pre>
                  </div>
                </div>
              </div>
            )}

            {/* Error Display */}
            {message.metadata?.error && (
              <div className={`mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded ${isRTL ? 'rtl' : 'ltr'}`}>
                <div className={`flex items-center gap-2 text-red-800 dark:text-red-200 ${isRTL ? 'flex-row-reverse' : ''}`}>
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span className="text-xs sm:text-sm font-medium">Error</span>
                </div>
                <p className={`text-xs sm:text-sm text-red-700 dark:text-red-300 mt-1 break-words ${isRTL ? 'text-right' : 'text-left'}`}>
                  {message.metadata.error}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Feedback Buttons for Assistant Messages */}
        {message.type === 'assistant' && message.metadata && !message.metadata.error && onFeedback && (
          <div className={`flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity ${isRTL ? 'flex-row-reverse' : ''}`} role="group" aria-label="Rate this response">
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2"
              onClick={() => onFeedback(message.id, 5)}
              aria-label="Good response"
              title="Good response"
            >
              <ThumbsUp className="h-3 w-3" aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2"
              onClick={() => onFeedback(message.id, 1)}
              aria-label="Poor response"
              title="Poor response"
            >
              <ThumbsDown className="h-3 w-3" aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>

      {message.type === 'user' && (
        <div className="w-6 h-6 sm:w-8 sm:h-8 bg-gray-600 rounded-full flex items-center justify-center flex-shrink-0 order-2">
          <User className="h-3 w-3 sm:h-4 sm:w-4 text-white" />
        </div>
      )}
    </div>
  )
}