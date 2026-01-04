"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MessageSquare, Plus, Trash2, Clock, Database, Bot, Languages } from "lucide-react"
import { apiUrls } from "@/config/api"
import { useToast } from "@/lib/use-toast"

export interface ChatSession {
  id: number
  bot_id: number
  conversation_id: string
  title: string | null
  message_count: number
  last_activity_at: string
  created_at: string
}

interface ChatSessionListProps {
  onSelectSession: (session: ChatSession) => void
  onNewChat: () => void
  botId?: number
}

export function ChatSessionList({ onSelectSession, onNewChat, botId }: ChatSessionListProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingAll, setDeletingAll] = useState(false)
  const { toast } = useToast()

  const loadSessions = async () => {
    try {
      setLoading(true)
      const url = botId ? apiUrls.chatBotSessions(botId) : apiUrls.chatSessions
      const response = await fetch(url)
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
    loadSessions()
  }, [botId])

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

  const handleDeleteAll = async () => {
    if (!confirm("Are you sure you want to delete ALL chat sessions? This action cannot be undone!")) {
      return
    }

    try {
      setDeletingAll(true)
      const url = botId
        ? `${apiUrls.deleteAllSessions}?confirm=true&bot_id=${botId}`
        : `${apiUrls.deleteAllSessions}?confirm=true`

      const response = await fetch(url, {
        method: "DELETE",
      })

      if (response.ok) {
        const data = await response.json()
        toast({
          title: "Success",
          description: `Deleted ${data.deleted_sessions} chat sessions successfully`,
        })
        await loadSessions()
      } else {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || "Failed to delete all sessions")
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to delete all chat sessions",
        variant: "destructive",
      })
    } finally {
      setDeletingAll(false)
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
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
    return date.toLocaleDateString("en-US")
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading chat sessions...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header - only show if botId is not provided (standalone list) */}
        {!botId && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
                My Chats
              </h1>
              <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400">
                Select a previous chat or start a new conversation
              </p>
            </div>
            <Button
              onClick={onNewChat}
              size="lg"
              className="gap-2 w-full sm:w-auto"
            >
              <Plus className="h-5 w-5" />
              New Chat
            </Button>
          </div>
        )}

        {/* Sessions Grid */}
        {sessions.length === 0 ? (
          <Card>
            <CardContent className="p-8 sm:p-12 text-center">
              <MessageSquare className="h-12 w-12 sm:h-16 sm:w-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-2">
                No chat sessions yet
              </h3>
              <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 mb-6">
                Start a new chat session to begin your conversation
              </p>
              <Button onClick={onNewChat} size="lg" className="gap-2">
                <Plus className="h-5 w-5" />
                <span className="hidden sm:inline">New Chat Session</span>
                <span className="sm:hidden">New Chat</span>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Show action buttons at top when there are sessions */}
            <div className="mb-4 flex flex-col sm:flex-row justify-end gap-2">
              <Button
                onClick={handleDeleteAll}
                variant="destructive"
                size="lg"
                className="gap-2 w-full sm:w-auto"
                disabled={deletingAll}
              >
                <Trash2 className="h-5 w-5" />
                <span className="hidden sm:inline">
                  {deletingAll ? "Deleting..." : "Delete All Sessions"}
                </span>
                <span className="sm:hidden">
                  {deletingAll ? "Deleting..." : "Delete All"}
                </span>
              </Button>
              <Button onClick={onNewChat} size="lg" className="gap-2 w-full sm:w-auto">
                <Plus className="h-5 w-5" />
                <span className="hidden sm:inline">New Chat Session</span>
                <span className="sm:hidden">New Chat</span>
              </Button>
            </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sessions.map((session) => (
              <Card
                key={session.conversation_id}
                className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:border-blue-500 dark:hover:border-blue-400"
                onClick={() => onSelectSession(session)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-lg truncate mb-2">
                        {session.title || "Untitled Chat"}
                      </CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                      onClick={(e) => handleDelete(session.conversation_id, e)}
                      disabled={deletingId === session.conversation_id}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
                    <div className="flex items-center gap-1">
                      <MessageSquare className="h-4 w-4" />
                      <span>{session.message_count} message{session.message_count !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      <span>{formatDate(session.last_activity_at)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
          </>
        )}
      </div>
    </div>
  )
}

