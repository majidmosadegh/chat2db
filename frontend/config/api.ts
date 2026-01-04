// API configuration
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export const apiUrls = {
  chat: `${API_BASE_URL}/api/chat/execute`,
  chatBots: `${API_BASE_URL}/api/chat/bots`,
  chatBot: (id: number) => `${API_BASE_URL}/api/chat/bots/${id}`,
  chatBotSessions: (botId: number) => `${API_BASE_URL}/api/chat/bots/${botId}/sessions`,
  chatSessions: `${API_BASE_URL}/api/chat/sessions`,
  chatSession: (id: string) => `${API_BASE_URL}/api/chat/sessions/${id}`,
  feedback: `${API_BASE_URL}/api/chat-orchestrator/feedback`,
  models: `${API_BASE_URL}/api/models`,
  schemaSnapshots: `${API_BASE_URL}/api/schema/snapshots`,
}


