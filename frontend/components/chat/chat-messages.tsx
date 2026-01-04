"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Bot } from "lucide-react"
import { ChatMessage } from "./chat-message"

interface ChatMessagesProps {
  messages: ChatMessage[]
  onFeedback?: (messageId: string, rating: number) => void
  onSuggestionClick?: (suggestion: string) => void
  language?: string
}

export function ChatMessages({ messages, onFeedback, onSuggestionClick, language }: ChatMessagesProps) {
  const isRTL = language === 'fa' || language === 'persian'
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  if (messages.length === 0) {
    const welcomeText = isRTL 
      ? 'به دستیار SQL خوش آمدید!'
      : 'Welcome to SQL Assistant!'
    const descriptionText = isRTL
      ? 'هر سوالی درباره داده‌های خود دارید به زبان طبیعی بپرسید و من آن را به کوئری SQL تبدیل می‌کنم.'
      : "Ask me anything about your data in natural language and I'll convert it to SQL queries."
    
    return (
      <div className="flex-1 flex items-center justify-center p-4 sm:p-8 min-h-0">
        <div className={`text-center max-w-2xl mx-auto w-full ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
          <div className="relative mb-4 sm:mb-6">
            <Bot className="h-16 w-16 sm:h-20 sm:w-20 text-blue-500 mx-auto mb-3 sm:mb-4" />
            <div className="absolute -top-1 -right-1 sm:-top-2 sm:-right-2 w-5 h-5 sm:w-6 sm:h-6 bg-green-500 rounded-full animate-pulse"></div>
          </div>
          <h3 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mb-2 sm:mb-3" dir={isRTL ? 'rtl' : 'ltr'}>
            {welcomeText}
          </h3>
          <p className="text-sm sm:text-lg text-gray-600 dark:text-gray-400 mb-6 sm:mb-8 px-4" dir={isRTL ? 'rtl' : 'ltr'}>
            {descriptionText}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 max-w-xl mx-auto px-4">
            <Card 
              className={`p-3 sm:p-4 ${isRTL ? 'text-right' : 'text-left'} hover:shadow-md transition-all cursor-pointer border-2 hover:border-blue-300 dark:hover:border-blue-700 active:scale-95`}
              onClick={() => onSuggestionClick?.(isRTL ? "فروش کل ماه گذشته چقدر بود؟" : "What was the total sales last month?")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSuggestionClick?.(isRTL ? "فروش کل ماه گذشته چقدر بود؟" : "What was the total sales last month?")
                }
              }}
              aria-label={isRTL ? "پیشنهاد: فروش کل ماه گذشته چقدر بود؟" : "Suggestion: What was the total sales last month?"}
              dir={isRTL ? 'rtl' : 'ltr'}
            >
              <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 font-medium" dir={isRTL ? 'rtl' : 'ltr'}>
                {isRTL ? '"فروش کل ماه گذشته چقدر بود؟"' : '"What was the total sales last month?"'}
              </p>
            </Card>
            <Card 
              className={`p-3 sm:p-4 ${isRTL ? 'text-right' : 'text-left'} hover:shadow-md transition-all cursor-pointer border-2 hover:border-blue-300 dark:hover:border-blue-700 active:scale-95`}
              onClick={() => onSuggestionClick?.(isRTL ? "۱۰ مشتری برتر بر اساس مبلغ خرید را نشان بده" : "Show me the top 10 customers by purchase amount")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSuggestionClick?.(isRTL ? "۱۰ مشتری برتر بر اساس مبلغ خرید را نشان بده" : "Show me the top 10 customers by purchase amount")
                }
              }}
              aria-label={isRTL ? "پیشنهاد: ۱۰ مشتری برتر بر اساس مبلغ خرید را نشان بده" : "Suggestion: Show me the top 10 customers by purchase amount"}
              dir={isRTL ? 'rtl' : 'ltr'}
            >
              <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 font-medium" dir={isRTL ? 'rtl' : 'ltr'}>
                {isRTL ? '"۱۰ مشتری برتر بر اساس مبلغ خرید را نشان بده"' : '"Show me the top 10 customers by purchase amount"'}
              </p>
            </Card>
            <Card 
              className={`p-3 sm:p-4 ${isRTL ? 'text-right' : 'text-left'} hover:shadow-md transition-all cursor-pointer border-2 hover:border-blue-300 dark:hover:border-blue-700 active:scale-95`}
              onClick={() => onSuggestionClick?.(isRTL ? "لیست تمام جداول موجود" : "List all available tables")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSuggestionClick?.(isRTL ? "لیست تمام جداول موجود" : "List all available tables")
                }
              }}
              aria-label={isRTL ? "پیشنهاد: لیست تمام جداول موجود" : "Suggestion: List all available tables"}
              dir={isRTL ? 'rtl' : 'ltr'}
            >
              <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 font-medium" dir={isRTL ? 'rtl' : 'ltr'}>
                {isRTL ? '"لیست تمام جداول موجود"' : '"List all available tables"'}
              </p>
            </Card>
            <Card 
              className={`p-3 sm:p-4 ${isRTL ? 'text-right' : 'text-left'} hover:shadow-md transition-all cursor-pointer border-2 hover:border-blue-300 dark:hover:border-blue-700 active:scale-95`}
              onClick={() => onSuggestionClick?.(isRTL ? "جدول مشتریان را توضیح بده" : "Describe the customers table")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSuggestionClick?.(isRTL ? "جدول مشتریان را توضیح بده" : "Describe the customers table")
                }
              }}
              aria-label={isRTL ? "پیشنهاد: جدول مشتریان را توضیح بده" : "Suggestion: Describe the customers table"}
              dir={isRTL ? 'rtl' : 'ltr'}
            >
              <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 font-medium" dir={isRTL ? 'rtl' : 'ltr'}>
                {isRTL ? '"جدول مشتریان را توضیح بده"' : '"Describe the customers table"'}
              </p>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto min-h-0 scroll-smooth" role="log" aria-label="Chat messages" aria-live="polite">
      <div className="p-3 sm:p-4">
        <div className="w-full max-w-6xl mx-auto space-y-3 sm:space-y-4 pb-4">
          {messages.map((message, index) => (
            <div
              key={message.id}
              className="animate-in slide-in-from-bottom-2 fade-in-0 duration-300"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <ChatMessage
                message={message}
                onFeedback={onFeedback}
                language={language}
              />
            </div>
          ))}
          <div ref={messagesEndRef} aria-hidden="true" />
        </div>
      </div>
    </div>
  )
}