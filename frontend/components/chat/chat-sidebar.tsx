"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { MessageSquare, Plus, Trash2, Clock, PanelLeftClose, PanelLeftOpen } from "lucide-react"
import { apiUrls } from "@/config/api"
import { useToast } from "@/lib/use-toast"
import { ChatSession } from "./chat-session-list"

interface ChatSidebarProps {
  botId: number
  currentSessionId?: string
  onSelectSession: (session: ChatSession) => void
  onNewChat: () => void
  onToggleSidebar: () => void
  isCollapsed: boolean
  language?: string
  onClearAllSessions?: () => void
}

export function ChatSidebar({
  botId,
  currentSessionId,
  onSelectSession,
  onNewChat,
  onToggleSidebar,
  isCollapsed = false,
  language,
  onClearAllSessions
}: ChatSidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const { toast } = useToast()

  const isRTL = language === 'fa' || language === 'persian'

  const loadSessions = async () => {
    try {
      setLoading(true)
      const response = await fetch(apiUrls.chatBotSessions(botId))
      if (response.ok) {
        const data = await response.json()
        setSessions(data)
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load chat sessions",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (botId && !isCollapsed) {
      loadSessions()
    }
  }, [botId, isCollapsed])

  const handleDelete = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Are you sure you want to delete this chat session?")) {
      return
    }

    try {
      setDeletingId(conversationId)
      const response = await fetch(apiUrls.chatSession(conversationId), {
        method: "DELETE",
      })

      if (response.ok) {
        toast({
          title: "Success",
          description: "Chat session deleted successfully",
        })
        await loadSessions()
      } else {
        throw new Error("Failed to delete")
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete chat session",
        variant: "destructive",
      })
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m`
    if (diffHours < 24) return `${diffHours}h`
    if (diffDays < 7) return `${diffDays}d`
    return date.toLocaleDateString("en-US", { month: 'short', day: 'numeric' })
  }

  return (
    <div className={`w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col ${isRTL ? 'border-l border-r-0' : ''}`} dir={isRTL ? 'rtl' : 'ltr'}>
      {/* Header */}
      <div className={`flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 ${isRTL ? 'flex-row-reverse' : ''}`}>
        <h2 className="font-semibold text-gray-900 dark:text-white">Chat Sessions</h2>
        <div className={`flex items-center gap-1 ${isRTL ? 'flex-row-reverse' : ''}`}>
          {onClearAllSessions && (
            <Button
              onClick={onClearAllSessions}
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
              title="Clear all sessions"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleSidebar}
            className="h-8 w-8 p-0"
            title="Collapse sidebar"
          >
            {isRTL ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <Button
          onClick={onNewChat}
          size="sm"
          className="w-full gap-2"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      <Separator />

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 px-4">
              <MessageSquare className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No chat sessions yet
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => (
                <div
                  key={session.conversation_id}
                  className={`group relative p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                    currentSessionId === session.conversation_id
                      ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                      : "hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  }`}
                  onClick={() => onSelectSession(session)}
                >
                  <div className={`flex items-start justify-between mb-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
                    <h3 className={`font-medium text-sm text-gray-900 dark:text-white truncate flex-1 ${isRTL ? 'ml-2 mr-0' : 'mr-2'}`}>
                      {session.title || "Untitled Chat"}
                    </h3>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950 transition-opacity"
                      onClick={(e) => handleDelete(session.conversation_id, e)}
                      disabled={deletingId === session.conversation_id}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>

                  <div className={`flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 ${isRTL ? 'flex-row-reverse' : ''}`}>
                    <div className={`flex items-center gap-1 ${isRTL ? 'flex-row-reverse' : ''}`}>
                      <MessageSquare className="h-3 w-3" />
                      <span>{session.message_count}</span>
                    </div>
                    <div className={`flex items-center gap-1 ${isRTL ? 'flex-row-reverse' : ''}`}>
                      <Clock className="h-3 w-3" />
                      <span>{formatDate(session.last_activity_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
