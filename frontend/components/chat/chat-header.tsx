"use client"

import { Badge } from "@/components/ui/badge"
import { Bot } from "lucide-react"

export interface ChatHeaderProps {
  sessionId?: string | null
  chatMode?: string
  isOnline?: boolean
}

export function ChatHeader({ sessionId, chatMode, isOnline = true }: ChatHeaderProps) {
  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-3 sm:p-4 flex-shrink-0" role="banner">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          <div className="w-8 h-8 sm:w-10 sm:h-10 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0" aria-hidden="true">
            <Bot className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-base sm:text-lg md:text-xl font-semibold text-gray-900 dark:text-white truncate">
              SQL Assistant
            </h1>
            {chatMode ? (
              <p className="text-xs sm:text-sm text-blue-600 dark:text-blue-400 truncate" aria-label={`Chat bot: ${chatMode}`}>
                {chatMode}
              </p>
            ) : (
              <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 truncate" aria-label={`Chat session status: ${sessionId ? `Session ${sessionId}` : 'New Session'}`}>
                {sessionId ? `Session: ${sessionId.slice(0, 8)}...` : 'New Session'}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <Badge
            variant={isOnline ? "default" : "secondary"}
            className={`text-xs ${isOnline ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" : ""}`}
            aria-label={`Connection status: ${isOnline ? 'Online' : 'Offline'}`}
          >
            <span className="hidden sm:inline">{isOnline ? "● Online" : "● Offline"}</span>
            <span className="sm:hidden">{isOnline ? "●" : "○"}</span>
          </Badge>
          <Badge variant="outline" className="text-xs hidden md:inline-flex" aria-label="This is a beta version">
            Beta
          </Badge>
        </div>
      </div>
    </header>
  )
}