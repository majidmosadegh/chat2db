"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Send } from "lucide-react"

interface ChatInputProps {
  onSendMessage: (message: string) => void
  isLoading: boolean
  placeholder?: string
  language?: string
}

export function ChatInput({
  onSendMessage,
  isLoading,
  placeholder = "Ask me anything about your data...",
  language
}: ChatInputProps) {
  const isRTL = language === 'fa' || language === 'persian'
  const defaultPlaceholder = isRTL 
    ? "هر سوالی درباره داده‌های خود دارید بپرسید..."
    : "Ask me anything about your data..."
  const [message, setMessage] = useState("")

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSendMessage(message.trim())
      setMessage("")
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 p-3 sm:p-4 flex-shrink-0">
      <div className="w-full max-w-6xl mx-auto">
        <div className={`flex gap-2 sm:gap-3 ${isRTL ? 'flex-row-reverse' : ''}`} role="form" aria-label="Send message">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={placeholder || defaultPlaceholder}
            className="flex-1 text-sm sm:text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all min-h-[44px]"
            disabled={isLoading}
            aria-label={isRTL ? "پیام خود را تایپ کنید" : "Type your message"}
            aria-describedby="send-instructions"
            dir={isRTL ? 'rtl' : 'ltr'}
          />
          <Button
            onClick={handleSend}
            disabled={!message.trim() || isLoading}
            className="px-4 sm:px-6 flex-shrink-0 min-h-[44px]"
            size="sm"
            aria-label={isLoading ? "Sending message..." : "Send message"}
          >
            <Send className="h-4 w-4 sm:h-5 sm:w-5" aria-hidden="true" />
          </Button>
        </div>
        <p id="send-instructions" className="text-xs text-gray-500 dark:text-gray-400 mt-2 hidden sm:block" dir={isRTL ? 'rtl' : 'ltr'}>
          {isRTL 
            ? 'Enter برای ارسال • Shift + Enter برای خط جدید'
            : 'Press Enter to send • Shift + Enter for new line'}
        </p>
      </div>
    </div>
  )
}