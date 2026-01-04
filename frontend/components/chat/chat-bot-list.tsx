"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Bot, Plus, Trash2, Clock, Database, MessageSquare, Languages } from "lucide-react"
import { apiUrls } from "@/config/api"
import { useToast } from "@/lib/use-toast"

export interface ChatBot {
  id: number
  name: string
  description: string | null
  snapshot_id: number
  snapshot_name: string | null
  model_id: number
  model_name: string | null
  language: string
  session_count: number
  total_message_count: number
  last_activity_at: string | null
  created_at: string
}

interface ChatBotListProps {
  onSelectBot: (bot: ChatBot) => void
  onNewBot: () => void
}

export function ChatBotList({ onSelectBot, onNewBot }: ChatBotListProps) {
  const [bots, setBots] = useState<ChatBot[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const { toast } = useToast()

  const loadBots = async () => {
    try {
      setLoading(true)
      const response = await fetch(apiUrls.chatBots)
      if (response.ok) {
        const data = await response.json()
        setBots(data)
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load chat bots",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBots()
  }, [])

  const handleDelete = async (botId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Are you sure you want to delete this chat bot? All sessions and messages will be deleted.")) {
      return
    }

    try {
      setDeletingId(botId)
      const response = await fetch(apiUrls.chatBot(botId), {
        method: "DELETE",
      })

      if (response.ok) {
        toast({
          title: "Success",
          description: "Chat bot deleted successfully",
        })
        await loadBots()
      } else {
        throw new Error("Failed to delete")
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete chat bot",
        variant: "destructive",
      })
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never"
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
            <p className="text-gray-600 dark:text-gray-400">Loading chat bots...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
              Chat Bots
            </h1>
            <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400">
              Select a chat bot or create a new one with your preferred settings
            </p>
          </div>
          <Button
            onClick={onNewBot}
            size="lg"
            className="gap-2 w-full sm:w-auto"
          >
            <Plus className="h-5 w-5" />
            <span className="hidden sm:inline">New Chat Bot</span>
            <span className="sm:hidden">New Bot</span>
          </Button>
        </div>

        {/* Bots Grid */}
        {bots.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <Bot className="h-16 w-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                No chat bots yet
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                Create your first chat bot with your preferred database, model, and language settings
              </p>
              <Button onClick={onNewBot} size="lg" className="gap-2">
                <Plus className="h-5 w-5" />
                Create Chat Bot
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {bots.map((bot) => (
              <Card
                key={bot.id}
                className="cursor-pointer hover:shadow-lg transition-all duration-200 hover:border-blue-500 dark:hover:border-blue-400"
                onClick={() => onSelectBot(bot)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-lg truncate mb-2 flex items-center gap-2">
                        <Bot className="h-5 w-5 text-blue-600" />
                        {bot.name}
                      </CardTitle>
                      {bot.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-2">
                          {bot.description}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2 mb-2">
                        {bot.snapshot_name && (
                          <Badge variant="outline" className="gap-1 text-xs">
                            <Database className="h-3 w-3" />
                            {bot.snapshot_name}
                          </Badge>
                        )}
                        {bot.model_name && (
                          <Badge variant="outline" className="gap-1 text-xs">
                            <Bot className="h-3 w-3" />
                            {bot.model_name}
                          </Badge>
                        )}
                        <Badge variant="outline" className="gap-1 text-xs">
                          <Languages className="h-3 w-3" />
                          {bot.language === "fa" || bot.language === "persian" ? "Persian" : bot.language === "en" ? "English" : bot.language}
                        </Badge>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                      onClick={(e) => handleDelete(bot.id, e)}
                      disabled={deletingId === bot.id}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        <MessageSquare className="h-4 w-4" />
                        <span>{bot.session_count} session{bot.session_count !== 1 ? 's' : ''}</span>
                      </div>
                      <span>{bot.total_message_count} messages</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      <span>{formatDate(bot.last_activity_at)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

