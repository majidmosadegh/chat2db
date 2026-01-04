"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Plus, Edit, Trash2, CheckCircle, XCircle } from "lucide-react"
import { useToast } from "@/lib/use-toast"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { PageLoader, TableSkeleton } from "@/components/ui/loading"
import { EmptyTable } from "@/components/ui/empty-state"
import { Cpu } from "lucide-react"
import { useApiError } from "@/lib/use-api-error"

interface LLMModel {
  id: number
  name: string
  service_name: string
  base_url: string
  api_key?: string
  model_name: string
  max_tokens: number
  temperature: number
  top_p: number
  is_active: boolean
}

interface ModelInfo {
  id: string
  object: string
  created?: number
  owned_by?: string
}

interface TestConnectionResponse {
  object: string
  data: ModelInfo[]
}

interface ServicePreset {
  name: string
  baseUrl: string
  description: string
}

const SERVICE_PRESETS: ServicePreset[] = [
  {
    name: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    description: "OpenAI GPT models"
  },
  {
    name: "Google AI Studio",
    baseUrl: "https://generativelanguage.googleapis.com",
    description: "Google Gemini models"
  },
  {
    name: "Ollama (Local)",
    baseUrl: "http://localhost:11434",
    description: "Local Ollama instance"
  },
  {
    name: "vLLM",
    baseUrl: "http://localhost:8000",
    description: "Local vLLM server"
  }
]

export default function ModelsPage() {
  const { toast } = useToast()
  const [models, setModels] = useState<LLMModel[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null)
  const [testingConnection, setTestingConnection] = useState(false)
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [connectionTested, setConnectionTested] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [modelToDelete, setModelToDelete] = useState<LLMModel | null>(null)
  const { withErrorHandling, clearError, error: apiError, isError } = useApiError()
  const [formData, setFormData] = useState({
    name: "",
    service_name: "",
    base_url: "",
    api_key: "",
    model_name: "",
    max_tokens: 2048,
    temperature: 0.7,
    top_p: 1.0,
  })

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = async () => {
    const result = await withErrorHandling(async () => {
      const response = await fetch('/api/models')
      if (!response.ok) throw new Error('Failed to fetch models')
      return response.json()
    })

    if (result) {
      setModels(result)
    }
    setLoading(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const result = await withErrorHandling(async () => {
      const url = editingModel ? `/api/models/${editingModel.id}` : '/api/models'
      const method = editingModel ? 'PUT' : 'POST'

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to save model')
      }

      return response.json()
    })

    if (result) {
      await fetchModels()
      setShowForm(false)
      setEditingModel(null)
      resetForm()
      toast({
        title: "Success",
        description: editingModel ? "Model updated successfully" : "Model added successfully",
        variant: "default"
      })
    }
  }

  const handleEdit = (model: LLMModel) => {
    setEditingModel(model)
    setFormData({
      name: model.name,
      service_name: model.service_name,
      base_url: model.base_url,
      api_key: model.api_key || "",
      model_name: model.model_name,
      max_tokens: model.max_tokens,
      temperature: model.temperature,
      top_p: model.top_p,
    })
    setConnectionTested(false)
    setAvailableModels([])
    setShowForm(true)
  }

  const handleDeleteClick = (model: LLMModel) => {
    setModelToDelete(model)
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!modelToDelete) return

    const result = await withErrorHandling(async () => {
      const response = await fetch(`/api/models/${modelToDelete.id}`, {
        method: 'DELETE',
      })

      if (!response.ok) throw new Error('Failed to delete model')
      return true
    })

    if (result) {
      await fetchModels()
      toast({
        title: "Success",
        description: "Model deleted successfully",
        variant: "default"
      })
    }

    setShowDeleteDialog(false)
    setModelToDelete(null)
  }

  const handleActivate = async (modelId: number) => {
    const result = await withErrorHandling(async () => {
      const response = await fetch(`/api/models/${modelId}/activate`, {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to activate model')
      }

      return response.json()
    })

    if (result) {
      await fetchModels()
      toast({
        title: "Success",
        description: result.message || "Model activated successfully",
        variant: "default"
      })
    }
  }

  const testConnection = async () => {
    if (!formData.base_url) {
      toast({
        title: "Missing URL",
        description: "Please enter a base URL first",
        variant: "destructive",
      })
      return
    }

    setTestingConnection(true)
    const result = await withErrorHandling(async () => {
      const response = await fetch('/api/models/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: formData.base_url,
          api_key: formData.api_key || null,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Connection test failed')
      }

      return response.json()
    })

    if (result) {
      const data: TestConnectionResponse = result
      setAvailableModels(data.data)
      setConnectionTested(true)

      // Auto-fill service name based on URL
      if (formData.base_url.includes("openai.com") && !formData.service_name) {
        setFormData(prev => ({ ...prev, service_name: "OpenAI" }))
      } else if (formData.base_url.includes("generativelanguage.googleapis.com") && !formData.service_name) {
        setFormData(prev => ({ ...prev, service_name: "Google AI" }))
      } else if (formData.base_url.includes("aistudio.google.com") && !formData.service_name) {
        setFormData(prev => ({ ...prev, service_name: "Google AI Studio" }))
      }

      toast({
        title: "Connection Successful",
        description: `Found ${data.data.length} available models`,
        variant: "default",
      })
    } else {
      setAvailableModels([])
      setConnectionTested(false)
    }

    setTestingConnection(false)
  }

  const handleModelSelect = (modelId: string) => {
    setFormData({ ...formData, model_name: modelId })
  }

  const resetForm = () => {
    setFormData({
      name: "",
      service_name: "",
      base_url: "",
      api_key: "",
      model_name: "",
      max_tokens: 2048,
      temperature: 0.7,
      top_p: 1.0,
    })
    setConnectionTested(false)
    setAvailableModels([])
  }

  const cancelEdit = () => {
    setShowForm(false)
    setEditingModel(null)
    resetForm()
  }

  if (loading) {
    return <PageLoader message="Loading AI models..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Model Settings</h1>
          <p className="text-muted-foreground">
            Configure LLM models for prompt generation
          </p>
        </div>
        <Button onClick={() => setShowForm(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Model
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingModel ? "Edit Model" : "Add New Model"}</CardTitle>
            <CardDescription>
              Configure the LLM model settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Service Presets */}
              <div className="space-y-2">
                <Label>Quick Setup</Label>
                <div className="grid grid-cols-2 gap-2">
                  {SERVICE_PRESETS.map((preset) => (
                    <Button
                      key={preset.name}
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setFormData(prev => ({
                          ...prev,
                          service_name: preset.name,
                          base_url: preset.baseUrl
                        }))
                      }}
                      className="justify-start h-auto p-3"
                    >
                      <div className="text-left">
                        <div className="font-medium">{preset.name}</div>
                        <div className="text-xs text-muted-foreground">{preset.description}</div>
                      </div>
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="My Google AI Model"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="service_name">Service Name</Label>
                  <Input
                    id="service_name"
                    value={formData.service_name}
                    onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
                    placeholder="Google AI"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="base_url">Base URL</Label>
                  <Input
                    id="base_url"
                    value={formData.base_url}
                    onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                    placeholder="https://generativelanguage.googleapis.com"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="api_key">API Key (Optional)</Label>
                  <Input
                    id="api_key"
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    placeholder="API key from Google AI Studio"
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={testConnection}
                  disabled={testingConnection || !formData.base_url}
                >
                  {testingConnection ? "Testing..." : "Test Connection"}
                </Button>
              </div>

              {connectionTested && availableModels.length > 0 && (
                <div className="space-y-2">
                  <Label>Available Models</Label>
                  <Select onValueChange={handleModelSelect} value={formData.model_name}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.id} {model.owned_by && `(${model.owned_by})`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="model_name">Model Name</Label>
                  <Input
                    id="model_name"
                    value={formData.model_name}
                    onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                    placeholder="gpt-3.5-turbo"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max_tokens">Max Tokens</Label>
                  <Input
                    id="max_tokens"
                    type="number"
                    value={formData.max_tokens}
                    onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="temperature">Temperature</Label>
                  <Input
                    id="temperature"
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={formData.temperature}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="top_p">Top P</Label>
                  <Input
                    id="top_p"
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={formData.top_p}
                    onChange={(e) => setFormData({ ...formData, top_p: parseFloat(e.target.value) })}
                    required
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button type="submit" disabled={!connectionTested}>
                  {editingModel ? "Update Model" : "Add Model"}
                </Button>
                <Button type="button" variant="outline" onClick={cancelEdit}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>LLM Models</CardTitle>
          <CardDescription>
            Manage your configured LLM models. Only one model can be active at a time.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {models.length === 0 ? (
            <EmptyTable
              icon={Cpu}
              title="No AI models configured"
              description="Configure your first AI model to start generating Text-to-SQL prompts. Connect to Ollama or OpenAI to get started."
              action={{
                label: "Add Your First Model",
                onClick: () => setShowForm(true)
              }}
            />
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <Table className="w-full">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[20%] min-w-[120px]">Name</TableHead>
                    <TableHead className="w-[15%] min-w-[100px]">Service</TableHead>
                    <TableHead className="w-[25%] min-w-[150px]">Base URL</TableHead>
                    <TableHead className="w-[20%] min-w-[120px]">Model</TableHead>
                    <TableHead className="w-[10%] min-w-[80px]">Status</TableHead>
                    <TableHead className="w-[10%] min-w-[100px] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((model) => (
                    <TableRow key={model.id}>
                      <TableCell className="font-medium break-words">{model.name}</TableCell>
                      <TableCell className="break-words">{model.service_name}</TableCell>
                      <TableCell className="font-mono text-sm break-words">{model.base_url}</TableCell>
                      <TableCell className="font-mono text-sm break-words">{model.model_name}</TableCell>
                      <TableCell>
                        {model.is_active ? (
                          <Badge variant="default" className="flex items-center gap-1 w-fit">
                            <CheckCircle className="h-3 w-3" />
                            <span className="hidden sm:inline">Active</span>
                            <span className="sm:hidden">✓</span>
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="w-fit">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {!model.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleActivate(model.id)}
                              className="text-xs px-2 py-1 h-7"
                            >
                              <span className="hidden sm:inline">Activate</span>
                              <span className="sm:hidden">✓</span>
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(model)}
                            className="text-xs px-2 py-1 h-7"
                          >
                            <Edit className="h-3 w-3" />
                          </Button>
                          {!model.is_active && (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDeleteClick(model)}
                            className="text-xs px-2 py-1 h-7"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmationDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        title="Delete Model"
        description={`Are you sure you want to delete the model "${modelToDelete?.name}"? This action cannot be undone.`}
        onConfirm={handleDeleteConfirm}
        confirmText="Delete Model"
        cancelText="Cancel"
        variant="destructive"
      />
    </div>
  )
}