"use client"

import { useState, useEffect } from "react"
import { useToast } from "@/lib/use-toast"
import {
  ChatMessage,
  ChatInput,
  ChatHeader,
  ChatMessages,
  TypingIndicator,
  ChatSettings,
  ChatSessionList,
  ChatSession,
  ChatBotList,
  ChatBot
} from "@/components/chat"
import { apiUrls } from "@/config/api"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ChatResponse {
  success: boolean
  user_question: string
  generated_sql: string
  rows: any[]
  row_count: number
  snapshot_id: number
  model_used: string
  execution_status: string
  error_message?: string
  context_hash: string
  sql_validation_status: string
  execution_time_ms: number
  conversation_id?: string
  conversational_response?: string
}

type ViewMode = 'bot-list' | 'bot-sessions' | 'settings' | 'chat'

export default function ChatPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('bot-list')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [currentBot, setCurrentBot] = useState<ChatBot | null>(null)
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null)
  const { toast } = useToast()

  // Load bot sessions
  const loadBotSessions = async (bot: ChatBot) => {
    try {
      setIsLoading(true)
      const response = await fetch(apiUrls.chatBotSessions(bot.id))
      if (!response.ok) {
        throw new Error("Failed to load bot sessions")
      }

      const data = await response.json()
      setCurrentBot(bot)
      setViewMode('bot-sessions')
      
      // Return data for potential use
      return data
    } catch (error) {
      setIsLoading(false)
      toast({
        title: "Error",
        description: "Failed to load bot sessions",
        variant: "destructive",
      })
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  // Create new session for bot and start chat
  const startNewSession = async (bot: ChatBot) => {
    try {
      setIsLoading(true)
      const response = await fetch(apiUrls.chatBotSessions(bot.id), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to create session: ${errorText}`)
      }

      const data = await response.json()
      setCurrentBot(bot)
      setConversationId(data.conversation_id)
      setCurrentSession(data.session)
      setMessages([])
      setViewMode('chat')
      
      // Small delay to ensure state is updated
      setTimeout(() => {
        setIsLoading(false)
      }, 100)
    } catch (error) {
      setIsLoading(false)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create session",
        variant: "destructive",
      })
    }
  }

  // Load session messages
  const loadSessionMessages = async (session: ChatSession) => {
    try {
      setIsLoading(true)
      const response = await fetch(apiUrls.chatSession(session.conversation_id))
      if (!response.ok) {
        throw new Error("Failed to load session")
      }

      const data = await response.json()
      
      setCurrentSession(session)
      setConversationId(session.conversation_id)

      // Convert API messages to ChatMessage format
      const loadedMessages: ChatMessage[] = data.messages.map((msg: any) => ({
        id: `msg_${msg.id}`,
        type: msg.role === 'user' ? 'user' : 'assistant',
        content: msg.content,
        timestamp: new Date(msg.created_at),
        metadata: {
          sql_query: msg.generated_sql || '',
          execution_status: msg.execution_status,
          row_count: msg.row_count,
          execution_time_ms: msg.execution_time_ms,
          ...(msg.metadata || {})
        }
      }))

      setMessages(loadedMessages)
      setViewMode('chat')
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load chat session",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const sendMessage = async (message: string) => {
    if (!message.trim() || isLoading || !currentBot || !conversationId) return

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: message,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      // Use bot's settings for the request
      const languageCode = currentBot.language === 'persian' ? 'fa' : currentBot.language === 'english' ? 'en' : 'en'
      
      const response = await fetch(apiUrls.chat, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          snapshot_id: currentBot.snapshot_id,
          selected_model_id: currentBot.model_id,
          language: languageCode,
          user_question: message,
          conversation_id: conversationId
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data: ChatResponse = await response.json()
      setConversationId(data.conversation_id || conversationId)

      let content = ""
      if (data.success) {
        if (data.conversational_response && data.execution_status === 'completed') {
          content = data.conversational_response
        } else if (data.generated_sql) {
          content = `**Generated SQL:**\n\`\`\`sql\n${data.generated_sql}\n\`\`\`\n\n`
          if (data.rows && data.rows.length > 0) {
            content += `**Query executed successfully** (${data.row_count} rows returned)`
          } else if (data.execution_status === 'success') {
            content += `**Query executed successfully** (${data.row_count} rows affected)`
          }
        } else {
          content = `Query completed successfully (${data.execution_time_ms}ms)`
        }
      } else {
        content = `❌ **Error:** ${data.error_message || 'Unknown error occurred'}`
      }

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        type: 'assistant',
        content: content,
        timestamp: new Date(),
        metadata: {
          success: data.success,
          sql_query: data.generated_sql || '',
          execution_status: data.execution_status,
          row_count: data.row_count,
          sql_validation_status: data.sql_validation_status,
          execution_time_ms: data.execution_time_ms,
          intent_type: data.conversational_response ? 'conversational' : 'sql_query',
          conversational_response: data.conversational_response,
          results: data.rows && Array.isArray(data.rows) ? data.rows : [],
          debug_generated_sql: data.generated_sql,
          debug_sql_length: data.generated_sql?.length || 0
        }
      }

      setMessages(prev => [...prev, assistantMessage])

    } catch (error) {
      let errorTitle = "Connection Error"
      let errorDescription = "Unable to send your message. Please check your connection and try again."
      let userFriendlyMessage = "I couldn't process your request right now. Please check your connection and try again."

      if (error instanceof Error) {
        if (error.message.includes('fetch')) {
          errorTitle = "Network Error"
          errorDescription = "Connection failed. Please check your internet connection."
          userFriendlyMessage = "Network connection issue. Please check your internet and try again."
        } else if (error.message.includes('timeout')) {
          errorTitle = "Request Timeout"
          errorDescription = "The request took too long to process."
          userFriendlyMessage = "The request timed out. Please try a simpler question or try again later."
        } else if (error.message.includes('500')) {
          errorTitle = "Server Error"
          errorDescription = "Our servers are experiencing issues."
          userFriendlyMessage = "Our servers are busy right now. Please try again in a moment."
        }
      }

      toast({
        title: errorTitle,
        description: errorDescription,
        variant: "destructive",
      })

      const errorMessage: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        type: 'assistant',
        content: userFriendlyMessage,
        timestamp: new Date(),
        metadata: { error: error instanceof Error ? error.message : 'Unknown error' }
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleBotSettingsComplete = async (settings: {
    databaseId: number
    modelId: string
    language: string
  }) => {
    try {
      setIsLoading(true)
      
      // Get database and model names for auto-naming
      const [dbResponse, modelResponse] = await Promise.all([
        fetch(apiUrls.schemaSnapshots),
        fetch(apiUrls.models)
      ])
      
      let dbName = "Database"
      let modelName = "Model"
      
      if (dbResponse.ok) {
        const dbs = await dbResponse.json()
        const db = dbs.find((d: any) => d.id === settings.databaseId)
        if (db) dbName = db.name
      }
      
      if (modelResponse.ok) {
        const models = await modelResponse.json()
        const model = models.find((m: any) => m.id.toString() === settings.modelId)
        if (model) modelName = model.name || model.model_name
      }
      
      // Auto-generate bot name from database and model
      const autoName = `${dbName} - ${modelName}`
      
      // Create bot with settings
      const response = await fetch(apiUrls.chatBots, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: autoName,
          snapshot_id: settings.databaseId,
          model_id: parseInt(settings.modelId),
          language: settings.language === 'english' ? 'en' : settings.language === 'persian' ? 'fa' : 'en'
        }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to create bot: ${errorText}`)
      }

      const bot = await response.json()
      
      // Automatically create a session and start chatting
      await startNewSession(bot)
      
      toast({
        title: "Chat Bot Created",
        description: "Your chat bot has been created and ready to chat.",
      })
    } catch (error) {
      setIsLoading(false)
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create chat bot",
        variant: "destructive",
      })
    }
  }

  const handleSelectBot = async (bot: ChatBot) => {
    // Start a new session directly and go to chat
    await startNewSession(bot)
  }

  const handleSelectSession = (session: ChatSession) => {
    loadSessionMessages(session)
  }

  const handleNewBot = () => {
    setViewMode('settings')
  }

  const handleBackToBots = () => {
    setViewMode('bot-list')
    setCurrentBot(null)
    setCurrentSession(null)
    setMessages([])
    setConversationId(null)
  }

  const handleBackToSessions = () => {
    if (currentBot) {
      loadBotSessions(currentBot)
    } else {
      setViewMode('bot-list')
    }
  }

  const submitFeedback = async (messageId: string, rating: number) => {
    try {
      const response = await fetch(apiUrls.feedback, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: conversationId,
          message_id: messageId,
          rating: rating,
          feedback_type: 'general'
        }),
      })

      if (!response.ok) {
        throw new Error(`Feedback submission failed: ${response.status}`)
      }

      toast({
        title: "Thank you!",
        description: "Your feedback helps us improve.",
      })
    } catch (error) {
      toast({
        title: "Feedback not sent",
        description: "We couldn't save your feedback, but you can continue chatting.",
        variant: "destructive",
      })
    }
  }

  // Render based on view mode
  if (viewMode === 'bot-list') {
    return (
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto w-full h-full">
          <ChatBotList
            onSelectBot={handleSelectBot}
            onNewBot={handleNewBot}
          />
        </div>
      </div>
    )
  }

  if (viewMode === 'settings') {
    return (
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0 w-full h-full">
          <ChatHeader sessionId={null} chatMode={undefined} />
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="p-3 sm:p-4">
              <Button variant="ghost" onClick={handleBackToBots} className="mb-4 gap-2 text-sm">
                <ArrowLeft className="h-4 w-4" />
                <span className="hidden sm:inline">Back to Chat Bots</span>
                <span className="sm:hidden">Back</span>
              </Button>
            </div>
            <ChatSettings
              onSettingsComplete={handleBotSettingsComplete}
              isLoading={isLoading}
            />
          </div>
        </div>
      </div>
    )
  }

  if (viewMode === 'bot-sessions' && currentBot) {
    return (
      <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0 w-full h-full">
          <ChatHeader 
            sessionId={null} 
            chatMode={currentBot.name}
          />
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="p-3 sm:p-4">
              <Button variant="ghost" onClick={handleBackToBots} className="mb-4 gap-2 text-sm">
                <ArrowLeft className="h-4 w-4" />
                <span className="hidden sm:inline">Back to Chat Bots</span>
                <span className="sm:hidden">Back</span>
              </Button>
              <div className="mb-4">
                <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
                  {currentBot.name}
                </h2>
                {currentBot.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {currentBot.description}
                  </p>
                )}
              </div>
            </div>
            <ChatSessionList
              onSelectSession={handleSelectSession}
              onNewChat={() => startNewSession(currentBot)}
              botId={currentBot.id}
            />
          </div>
        </div>
      </div>
    )
  }

  // Chat view
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0 min-h-0 w-full h-full">
        <ChatHeader
          sessionId={conversationId}
          chatMode={currentBot 
            ? `${currentBot.name}${currentBot.snapshot_name ? ` - ${currentBot.snapshot_name}` : ''}`
            : undefined}
        />

        {/* Back button - integrated in header area */}
        <div className="flex-shrink-0 px-3 sm:px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <div className="w-full max-w-6xl mx-auto">
            <Button variant="ghost" size="sm" onClick={handleBackToBots} className="gap-2 text-sm">
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Back to Chat Bots</span>
              <span className="sm:hidden">Back</span>
            </Button>
          </div>
        </div>

        {/* Chat Interface */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <ChatMessages 
            messages={messages} 
            onFeedback={submitFeedback}
            onSuggestionClick={(suggestion) => {
              if (!isLoading && currentBot && conversationId) {
                sendMessage(suggestion)
              }
            }}
            language={currentBot?.language}
          />

          {isLoading && (
            <div className="flex-shrink-0 px-3 sm:px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <div className="w-full max-w-6xl mx-auto">
                <TypingIndicator />
              </div>
            </div>
          )}
        </div>

        <ChatInput
          onSendMessage={sendMessage}
          isLoading={isLoading || !currentBot || !conversationId}
          placeholder={currentBot?.language === 'fa' || currentBot?.language === 'persian' 
            ? "هر سوالی درباره داده‌های خود دارید بپرسید..."
            : "Ask me anything about your data..."}
          language={currentBot?.language}
        />
      </div>
    </div>
  )
}
