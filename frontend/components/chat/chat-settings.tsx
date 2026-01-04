"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Database, Bot, Languages } from "lucide-react"
import { useState, useEffect } from "react"
import { apiUrls } from "@/config/api"

interface ChatSettingsProps {
  onSettingsComplete: (settings: {
    databaseId: number
    modelId: string
    language: string
  }) => void
  isLoading?: boolean
}

interface DatabaseSnapshot {
  id: number
  name: string
  description?: string
}

interface LLMModel {
  id: number
  name: string
  service_name: string
  model_name: string
}

export function ChatSettings({ onSettingsComplete, isLoading }: ChatSettingsProps) {
  const [selectedDatabase, setSelectedDatabase] = useState<number | null>(null)
  const [selectedModel, setSelectedModel] = useState<string>("")
  const [selectedLanguage, setSelectedLanguage] = useState<string>("english")
  const [databases, setDatabases] = useState<DatabaseSnapshot[]>([])
  const [models, setModels] = useState<LLMModel[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadSettings = async () => {
      try {
        // Load databases
        const dbResponse = await fetch(apiUrls.schemaSnapshots)
        if (dbResponse.ok) {
          const dbData = await dbResponse.json()
          setDatabases(dbData)
          // Auto-select first active database
          const activeDb = dbData.find((db: any) => db.is_active)
          if (activeDb) {
            setSelectedDatabase(activeDb.id)
          }
        }

        // Load models
        const modelResponse = await fetch(apiUrls.models)
        if (modelResponse.ok) {
          const modelData = await modelResponse.json()
          setModels(modelData)
          // Auto-select first active model
          const activeModel = modelData.find((model: any) => model.is_active)
          if (activeModel) {
            setSelectedModel(activeModel.id.toString())
          }
        }
      } catch (error) {
      } finally {
        setLoading(false)
      }
    }

    loadSettings()
  }, [])

  const handleContinue = () => {
    if (selectedDatabase && selectedModel && selectedLanguage) {
      onSettingsComplete({
        databaseId: selectedDatabase,
        modelId: selectedModel,
        language: selectedLanguage
      })
    }
  }

  const isFormValid = selectedDatabase && selectedModel && selectedLanguage

  if (loading) {
    return (
      <div className="p-6">
        <div className="max-w-2xl mx-auto">
          <Card>
            <CardContent className="p-8">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600 dark:text-gray-400 font-medium">Loading chat settings...</p>
                <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">Please wait while we prepare your workspace</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="w-full max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Chat Settings
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Configure your chat preferences
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database Selection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="database">Select Database</Label>
              <Select value={selectedDatabase?.toString()} onValueChange={(value) => setSelectedDatabase(parseInt(value))}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a database..." />
                </SelectTrigger>
                <SelectContent>
                  {databases.map((db) => (
                    <SelectItem key={db.id} value={db.id.toString()}>
                      {db.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              AI Model Selection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="model">Select AI Model</Label>
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose an AI model..." />
                </SelectTrigger>
                <SelectContent>
                  {models.map((model) => (
                    <SelectItem key={model.id} value={model.id.toString()}>
                      {model.name} - {model.model_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Languages className="h-5 w-5" />
              Language Selection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="language">Select Language</Label>
              <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose language..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="english">English</SelectItem>
                  <SelectItem value="persian">Persian</SelectItem>
                  <SelectItem value="french">French</SelectItem>
                  <SelectItem value="german">German</SelectItem>
                  <SelectItem value="spanish">Spanish</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>


        <div className="text-center mt-8">
          <Button
            size="lg"
            onClick={handleContinue}
            disabled={!isFormValid || isLoading}
            className="px-8"
          >
            {isLoading ? 'Starting Chat...' : 'Start Chat'}
          </Button>
        </div>
      </div>
    </div>
  )
}