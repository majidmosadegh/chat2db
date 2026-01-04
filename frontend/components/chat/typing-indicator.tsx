"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Bot } from "lucide-react"

export function TypingIndicator() {
  return (
    <div className="flex gap-2 sm:gap-3 justify-start">
      <div className="w-6 h-6 sm:w-8 sm:h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
        <Bot className="h-3 w-3 sm:h-4 sm:w-4 text-white" />
      </div>
      <Card className="max-w-[90%] sm:max-w-[75%] lg:max-w-[80%] shadow-sm">
        <CardContent className="p-3 sm:p-4">
          <div className="flex items-center gap-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
            <span className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">AI is thinking...</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}