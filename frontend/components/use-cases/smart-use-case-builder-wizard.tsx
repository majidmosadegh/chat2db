"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ArrowLeft, ArrowRight, Loader2, Database, Users, MessageSquare, BarChart3, Check, Briefcase, Microscope, User, Bot, TrendingUp, Scale, Calendar, ClipboardList, Target, Search, AlertCircle, X } from "lucide-react"
import axios from "axios"
import { useApiError } from "@/lib/use-api-error"
import { toast } from "@/lib/use-toast"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"

interface SchemaSnapshot {
  id: number
  name: string
  description: string
  created_at: string
}

interface WizardData {
  snapshot_id: number
  business_context: string
  primary_audience: string[]
  typical_questions: string[]
  sample_questions: string[]
  output_preference: string
  number_of_use_cases: number
  language: string
}

interface GeneratedUseCase {
  name?: string
  usecase_name?: string
  description: string
  typical_questions?: string[] | null
  example_queries?: string[] | null
  output_type?: string
  main_tables?: string[] | null
  risk_notes?: string
  // New fields from enhanced format
  title?: string
  business_goal?: string
  actor?: string
  scope?: string
  sql_intent?: string
  expected_output?: string
  expected_sql_patterns?: string[]
  required_relations?: string[]
  edge_cases?: string[]
  sample_examples?: any[]
  query_feasibility_score?: number
  reasoning?: string
}

const AUDIENCE_OPTIONS = [
  { id: "manager", label: "Manager", icon: Briefcase },
  { id: "analyst", label: "Analyst", icon: BarChart3 },
  { id: "expert", label: "Expert", icon: Microscope },
  { id: "general_user", label: "General User", icon: User },
]

interface SmartUseCaseBuilderWizardProps {
  onComplete?: () => void
}

const QUESTION_TYPE_OPTIONS = [
  { id: "numeric_stats", label: "Numeric / Statistical", icon: TrendingUp },
  { id: "comparative", label: "Comparative", icon: Scale },
  { id: "temporal_trends", label: "Time Trends", icon: Calendar },
  { id: "record_lists", label: "Record Lists", icon: ClipboardList },
  { id: "kpis", label: "KPIs & Metrics", icon: Target },
  { id: "anomaly_detection", label: "Anomaly Detection", icon: Search }
]

const OUTPUT_PREFERENCE_OPTIONS = [
  { id: "short_number", label: "Short Number", description: "Example: Total sales = $120,000" },
  { id: "summary_table", label: "Summary Table", description: "Table with key columns" },
  { id: "text_report", label: "Text Report", description: "Descriptive and complete response" },
  { id: "combined", label: "Combined", description: "Table + text analysis" }
]

const STEPS = [
  { id: 1, title: "Select Snapshot", icon: Database },
  { id: 2, title: "Business Context", icon: MessageSquare },
  { id: 3, title: "Primary Audience", icon: Users },
  { id: 4, title: "Question Types", icon: MessageSquare },
  { id: 5, title: "Language", icon: MessageSquare },
  { id: 6, title: "Sample Questions", icon: MessageSquare },
  { id: 7, title: "Output Settings", icon: BarChart3 },
  { id: 8, title: "Review Use Cases", icon: Check }
]

export function SmartUseCaseBuilderWizard({ onComplete }: SmartUseCaseBuilderWizardProps) {
  const [currentStep, setCurrentStep] = useState(1)
  const [snapshots, setSnapshots] = useState<SchemaSnapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const { withErrorHandling, clearError, error: apiError, isError } = useApiError()
  const [wizardData, setWizardData] = useState<WizardData>({
    snapshot_id: 0,
    business_context: "",
    primary_audience: [],
    typical_questions: [],
    sample_questions: [],
    output_preference: "summary_table", // Default value
    number_of_use_cases: 5, // Will be overridden by AI
    language: "english"
  })
  const [generatedUseCases, setGeneratedUseCases] = useState<GeneratedUseCase[]>([])
  const [generationLogId, setGenerationLogId] = useState<number | null>(null)
  const [systemPromptExamples, setSystemPromptExamples] = useState<string>("")
  const [selectedLanguage, setSelectedLanguage] = useState<string>("en")
  
  // Job-based generation state
  const [showGenerationModal, setShowGenerationModal] = useState(false)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [jobProgress, setJobProgress] = useState(0)
  const [jobStatus, setJobStatus] = useState<'waiting' | 'processing' | 'done' | 'failed' | 'canceled'>('waiting')
  const [jobError, setJobError] = useState<string | null>(null)
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null)
  // Per-table processing state
  const [currentTable, setCurrentTable] = useState<string | null>(null)
  const [totalTables, setTotalTables] = useState<number>(0)
  const [processedTables, setProcessedTables] = useState<number>(0)
  const [processingMessage, setProcessingMessage] = useState<string | null>(null)

  useEffect(() => {
    fetchSnapshots()
  }, [])

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsConnection) {
        wsConnection.close()
        setWsConnection(null)
      }
    }
  }, [wsConnection])

  const fetchSnapshots = async () => {
    const result = await withErrorHandling(async () => {
      const response = await axios.get('/api/schema/snapshots')
      return response.data
    })

    if (result) {
      setSnapshots(result)
    }
  }

  const updateWizardData = (updates: Partial<WizardData>) => {
    setWizardData(prev => ({ ...prev, ...updates }))
  }

  const handleNext = () => {
    if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleGenerate = async () => {
    // Clear any previous errors
    clearError()

    // Filter out empty sample questions
    const cleanWizardData = {
      ...wizardData,
      sample_questions: wizardData.sample_questions.filter(q => q.trim() !== '')
    }

    try {
      // Create job using new endpoint
      const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const response = await axios.post(`${API_BASE_URL}/api/use-case-job/generate`, {
        snapshot_id: cleanWizardData.snapshot_id,
        business_context: cleanWizardData.business_context,
        primary_audience: cleanWizardData.primary_audience,
        typical_questions: cleanWizardData.typical_questions,
        output_preference: cleanWizardData.output_preference,
        number_of_use_cases: cleanWizardData.number_of_use_cases,
        language: cleanWizardData.language,
        sample_questions: cleanWizardData.sample_questions,
        scope: "snapshot"
      })

      if (response.data?.job_id) {
        const jobId = response.data.job_id
        setCurrentJobId(jobId)
        setJobProgress(0)
        setJobStatus('waiting')
        setJobError(null)
        setShowGenerationModal(true)
        
        // Connect WebSocket
        connectWebSocket(jobId)
      } else {
        throw new Error("No job ID received")
      }
    } catch (error: any) {
      toast({
        title: "Generation Failed",
        description: error.response?.data?.detail || "Unable to start use case generation. Please try again.",
        variant: "destructive",
        duration: 6000
      })
    }
  }

  const connectWebSocket = (jobId: string) => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
    const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://')
    const ws = new WebSocket(`${wsUrl}/api/use-case-job/ws/use-case-job-status/${jobId}`)

    ws.onopen = () => {
      console.log('WebSocket connected for job', jobId)
      setWsConnection(ws)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.type === 'job_status_update') {
          setJobStatus(data.status)
          setJobProgress(data.progress || 0)
          
          // Update per-table processing info
          if (data.current_table !== undefined) {
            setCurrentTable(data.current_table)
          }
          if (data.total_tables !== undefined) {
            setTotalTables(data.total_tables)
          }
          if (data.processed_tables !== undefined) {
            setProcessedTables(data.processed_tables)
          }
          if (data.message) {
            setProcessingMessage(data.message)
          }
          
          if (data.error) {
            setJobError(data.error)
          }
          
          // If job is done, get the results
          if (data.status === 'done' && data.use_cases) {
            // Normalize use cases data to ensure consistent structure
            // Support both new format (title, business_goal) and old format (usecase_name, description)
            const normalizedUseCases = data.use_cases.map((uc: any) => ({
              name: uc.title || uc.usecase_name || uc.name || 'Unnamed Use Case',
              description: uc.business_goal || uc.description || '',
              typical_questions: Array.isArray(uc.typical_questions) ? uc.typical_questions : [],
              example_queries: Array.isArray(uc.example_queries) ? uc.example_queries : [],
              output_type: uc.output_type || 'aggregation',
              main_tables: Array.isArray(uc.main_tables) ? uc.main_tables : [],
              risk_notes: uc.risk_notes || '',
              // Include new format fields for reference
              title: uc.title,
              business_goal: uc.business_goal,
              actor: uc.actor,
              scope: uc.scope,
              sql_intent: uc.sql_intent,
              expected_output: uc.expected_output
            }))
            setGeneratedUseCases(normalizedUseCases)
            setGenerationLogId(data.generation_log_id)
            
            // Generate system prompt examples
            const examples = data.use_cases.slice(0, 3).map((uc: any, i: number) => {
              const name = uc.title || uc.usecase_name || uc.name || 'Unnamed'
              const desc = uc.business_goal || uc.description || ''
              return `Example ${i+1}: ${name}\nDescription: ${desc}\n`
            }).join('\n')
            setSystemPromptExamples(examples)
            
            // Close WebSocket after a short delay
            setTimeout(() => {
              ws.close()
              setWsConnection(null)
              setShowGenerationModal(false)
              handleNext() // Move to review step
            }, 1500)
          }
          
          // If job failed
          if (data.status === 'failed') {
            setJobError(data.error || 'Generation failed')
            setCurrentTable(null)
            setProcessingMessage(null)
            setTimeout(() => {
              ws.close()
              setWsConnection(null)
            }, 3000)
          }
          
          // Reset per-table state when done
          if (data.status === 'done') {
            setCurrentTable(null)
            setProcessingMessage(null)
          }
        } else if (data.type === 'keepalive' || data.type === 'pong') {
          // Keep connection alive
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setJobError('Connection error. Please check your network.')
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      setWsConnection(null)
    }
  }

  const handleCancelGeneration = () => {
    if (currentJobId && wsConnection) {
      // Cancel job
      const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      axios.post(`${API_BASE_URL}/api/use-case-job/jobs/${currentJobId}/cancel`)
        .catch(err => console.error('Failed to cancel job:', err))
      
      wsConnection.close()
      setWsConnection(null)
      setShowGenerationModal(false)
      setCurrentJobId(null)
      setJobProgress(0)
      setJobStatus('waiting')
      setCurrentTable(null)
      setTotalTables(0)
      setProcessedTables(0)
      setProcessingMessage(null)
    }
  }


  const handleSaveSelected = async (selectedUseCases: GeneratedUseCase[]) => {
    if (!generationLogId) {
      toast({
        title: "Save Failed",
        description: "No generation log ID found. Please try generating use cases again.",
        variant: "destructive"
      })
      return
    }

    if (!selectedUseCases || selectedUseCases.length === 0) {
      toast({
        title: "Save Failed",
        description: "No use cases selected to save.",
        variant: "destructive"
      })
      return
    }

    console.log('[FRONTEND] Saving use cases:', {
      generationLogId,
      count: selectedUseCases.length,
      useCases: selectedUseCases.map(uc => ({
        name: uc.name || uc.title || uc.usecase_name,
        description: uc.description || uc.business_goal,
        has_questions: !!uc.typical_questions,
        questions_count: uc.typical_questions?.length || 0,
        has_queries: !!uc.example_queries,
        queries_count: uc.example_queries?.length || 0
      }))
    })

    setIsSaving(true)

    const result = await withErrorHandling(async () => {
      const response = await axios.post(`/api/smart-use-case-builder/save/${generationLogId}`, selectedUseCases)
      console.log('[FRONTEND] Save response:', response.data)
      
      if (response.data?.saved_use_cases && response.data.saved_use_cases.length > 0) {
        toast({
          title: "Success",
          description: `Successfully saved ${response.data.saved_use_cases.length} use case(s)!`,
          variant: "default"
        })
        onComplete?.()
        return true
      } else {
        throw new Error("No use cases were saved")
      }
    })

    setIsSaving(false)

    if (!result && isError) {
      toast({
        title: "Save Failed",
        description: "Unable to save selected use cases. Please check the console for details.",
        variant: "destructive"
      })
    }
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="snapshot">Select Database Snapshot</Label>
              <Select
                value={wizardData.snapshot_id.toString()}
                onValueChange={(value) => updateWizardData({ snapshot_id: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choose a snapshot" />
                </SelectTrigger>
                <SelectContent>
                  {snapshots.map((snapshot) => (
                    <SelectItem key={snapshot.id} value={snapshot.id.toString()}>
                      {snapshot.name}
                      {snapshot.description && ` - ${snapshot.description}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {snapshots.length === 0 && (
                <p className="text-sm text-muted-foreground mt-2">
                  No snapshots found. Please create a database connection and run schema introspection first.
                </p>
              )}
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-4">
            <div>
              <Label htmlFor="business_context">
                What is the business context of this database?
              </Label>
              <Textarea
                id="business_context"
                placeholder="Example: Management reporting, market analysis, daily operations, monitoring, finance, trading, etc."
                value={wizardData.business_context}
                onChange={(e) => updateWizardData({ business_context: e.target.value })}
                rows={4}
                className="mt-2"
              />
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-4">
            <div>
              <Label>Who will primarily use these use cases?</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Select multiple options
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {AUDIENCE_OPTIONS.map((option) => (
                  <div key={option.id} className="flex items-center space-x-2 space-x-reverse p-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800">
                    <Checkbox
                      id={option.id}
                      checked={wizardData.primary_audience.includes(option.id)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          updateWizardData({
                            primary_audience: [...wizardData.primary_audience, option.id]
                          })
                        } else {
                          updateWizardData({
                            primary_audience: wizardData.primary_audience.filter(a => a !== option.id)
                          })
                        }
                      }}
                    />
                    <Label htmlFor={option.id} className="flex items-center gap-2 cursor-pointer flex-1">
                      <option.icon className="h-4 w-4" />
                      <span className="text-sm">{option.label}</span>
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case 4:
        return (
          <div className="space-y-4">
            <div>
              <Label>What types of questions do users typically ask about this data?</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Select multiple options
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {QUESTION_TYPE_OPTIONS.map((option) => (
                  <div key={option.id} className="flex items-center space-x-2 space-x-reverse p-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800">
                    <Checkbox
                      id={option.id}
                      checked={wizardData.typical_questions.includes(option.id)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          updateWizardData({
                            typical_questions: [...wizardData.typical_questions, option.id]
                          })
                        } else {
                          updateWizardData({
                            typical_questions: wizardData.typical_questions.filter(q => q !== option.id)
                          })
                        }
                      }}
                    />
                    <Label htmlFor={option.id} className="flex items-center gap-2 cursor-pointer flex-1">
                      <option.icon className="h-4 w-4" />
                      <span className="text-sm">{option.label}</span>
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )

      case 5:
        return (
          <div className="space-y-4">
            <div>
              <Label>What language should the use cases be generated in?</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Select the language for use case names, descriptions, and example questions
              </p>
              <RadioGroup
                value={wizardData.language}
                onValueChange={(value) => {
                  setSelectedLanguage(value)
                  updateWizardData({ language: value })
                }}
                className="mt-3 space-y-3"
              >
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="english" id="english" defaultChecked />
                  <Label htmlFor="english" className="flex-1 cursor-pointer">
                    <div className="font-medium">English</div>
                    <div className="text-sm text-muted-foreground">Generate use cases in English</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="persian" id="persian" />
                  <Label htmlFor="persian" className="flex-1 cursor-pointer">
                    <div className="font-medium">فارسی (Persian)</div>
                    <div className="text-sm text-muted-foreground">تولید use caseها به زبان فارسی</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="arabic" id="arabic" />
                  <Label htmlFor="arabic" className="flex-1 cursor-pointer">
                    <div className="font-medium">العربية (Arabic)</div>
                    <div className="text-sm text-muted-foreground">تولید use caseها به زبان عربی</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="turkish" id="turkish" />
                  <Label htmlFor="turkish" className="flex-1 cursor-pointer">
                    <div className="font-medium">Türkçe (Turkish)</div>
                    <div className="text-sm text-muted-foreground">Generate use cases in Turkish</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="german" id="german" />
                  <Label htmlFor="german" className="flex-1 cursor-pointer">
                    <div className="font-medium">Deutsch (German)</div>
                    <div className="text-sm text-muted-foreground">Generate use cases in German</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="french" id="french" />
                  <Label htmlFor="french" className="flex-1 cursor-pointer">
                    <div className="font-medium">Français (French)</div>
                    <div className="text-sm text-muted-foreground">Generate use cases in French</div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                  <RadioGroupItem value="spanish" id="spanish" />
                  <Label htmlFor="spanish" className="flex-1 cursor-pointer">
                    <div className="font-medium">Español (Spanish)</div>
                    <div className="text-sm text-muted-foreground">Generate use cases in Spanish</div>
                  </Label>
                </div>
              </RadioGroup>
            </div>
          </div>
        )

      case 6:
        return (
          <div className="space-y-4">
            <div>
              <Label>Sample questions to convert to SQL (Optional)</Label>
              <p className="text-sm text-muted-foreground mb-4">
                Add up to 5 specific questions that users might ask, which should be converted to SQL queries
              </p>
              <div className="space-y-3">
                {wizardData.sample_questions.map((question, index) => (
                  <div key={index} className="flex flex-col sm:flex-row gap-2">
                    <Input
                      value={question}
                      onChange={(e) => {
                        const newQuestions = [...wizardData.sample_questions]
                        newQuestions[index] = e.target.value
                        updateWizardData({ sample_questions: newQuestions })
                      }}
                      placeholder={`Sample question ${index + 1}`}
                      className="flex-1"
                    />
                    {wizardData.sample_questions.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const newQuestions = wizardData.sample_questions.filter((_, i) => i !== index)
                          updateWizardData({ sample_questions: newQuestions })
                        }}
                        className="w-full sm:w-auto"
                      >
                        <span className="hidden sm:inline">Remove</span>
                        <span className="sm:hidden">×</span>
                      </Button>
                    )}
                  </div>
                ))}
                {wizardData.sample_questions.length < 5 && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      updateWizardData({
                        sample_questions: [...wizardData.sample_questions, ""]
                      })
                    }}
                    className="w-full"
                  >
                    Add Sample Question ({wizardData.sample_questions.length}/5)
                  </Button>
                )}
                {wizardData.sample_questions.length >= 5 && (
                  <p className="text-sm text-muted-foreground text-center">
                    Maximum 5 sample questions allowed
                  </p>
                )}
              </div>
            </div>
          </div>
        )

      case 7:
        return (
          <div className="space-y-6">
            <div>
              <Label>What should the ideal output look like?</Label>
              <RadioGroup
                value={wizardData.output_preference}
                onValueChange={(value) => {
                  updateWizardData({ output_preference: value })
                }}
                className="mt-3 space-y-3"
              >
                {OUTPUT_PREFERENCE_OPTIONS.map((option) => (
                  <div key={option.id} className="flex items-center space-x-2 space-x-reverse p-3 rounded-md border hover:bg-gray-50 dark:hover:bg-gray-800">
                    <RadioGroupItem value={option.id} id={option.id} />
                    <Label htmlFor={option.id} className="flex-1 cursor-pointer">
                      <div className="font-medium">{option.label}</div>
                      <div className="text-sm text-muted-foreground">{option.description}</div>
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            {/* AI will determine the optimal number of use cases based on your schema */}

            <div className="bg-gray-50 p-4 rounded">
              <h4 className="font-medium mb-2">Current Wizard Data:</h4>
              <p className="text-sm text-muted-foreground mb-2">
                AI will determine the optimal number of use cases based on your schema tables (maximum 10).
              </p>
              <pre className="text-xs text-gray-600">
                {JSON.stringify({
                  snapshot_id: wizardData.snapshot_id,
                  business_context: wizardData.business_context?.substring(0, 50) + '...',
                  primary_audience: wizardData.primary_audience,
                  typical_questions: wizardData.typical_questions,
                  language: wizardData.language,
                  sample_questions: wizardData.sample_questions,
                  output_preference: wizardData.output_preference
                }, null, 2)}
              </pre>
            </div>
          </div>
        )

      case 8:
        return (
          <div className="space-y-4">
            {loading ? (
              <div className="text-center py-8">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                <p>Generating use cases with AI...</p>
              </div>
            ) : generatedUseCases.length > 0 ? (
              <GeneratedUseCasesReview
                useCases={generatedUseCases}
                systemPromptExamples={systemPromptExamples}
                onSave={handleSaveSelected}
                onBack={() => setCurrentStep(7)}
                isSaving={isSaving}
              />
            ) : (
              <div className="text-center py-8">
                <div className="text-red-500 mb-4">
                  <p className="text-lg font-semibold">No Use Cases Generated</p>
                  <p className="text-sm">The AI service returned empty results. Please try again.</p>
                </div>
                <Button onClick={() => setCurrentStep(7)} variant="outline">
                  Go Back
                </Button>
              </div>
            )}
          </div>
        )

      case 9:
        return (
          <div className="space-y-4">
            {generatedUseCases.length > 0 ? (
              <GeneratedUseCasesReview
                useCases={generatedUseCases}
                systemPromptExamples={systemPromptExamples}
                onSave={handleSaveSelected}
                onBack={() => setCurrentStep(8)}
                isSaving={isSaving}
              />
            ) : (
              <div className="text-center py-8">
                <div className="text-red-500 mb-4">
                  <p className="text-lg font-semibold">No Use Cases Generated</p>
                  <p className="text-sm">The AI service returned empty results. Please try again.</p>
                </div>
                <Button onClick={() => setCurrentStep(8)} variant="outline">
                  Go Back
                </Button>
              </div>
            )}
          </div>
        )

      default:
        return null
    }
  }

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return wizardData.snapshot_id > 0
      case 2:
        return wizardData.business_context.trim().length > 0
      case 3:
        return wizardData.primary_audience.length > 0
      case 4:
        return wizardData.typical_questions.length > 0
      case 5:
        return wizardData.language && wizardData.language.length > 0
      case 6:
        return true // Sample questions are optional
      case 7:
        const canProceedStep7 = wizardData.output_preference
        return canProceedStep7
      case 8:
        return true
      default:
        return false
    }
  }

  const progress = (currentStep / STEPS.length) * 100

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
      <Card>
        <CardHeader className="pb-4 sm:pb-6">
          <CardTitle className="flex items-center gap-2 text-lg sm:text-xl">
            <Database className="h-5 w-5" />
            Smart Use Case Builder
          </CardTitle>
          <CardDescription className="text-sm sm:text-base">
            This wizard will help you generate practical use cases with just a few simple questions.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-4 sm:px-6">
          {/* Progress Bar */}
          <div className="mb-6 sm:mb-8">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium">
                Step {currentStep} of {STEPS.length}
              </span>
              <span className="text-sm text-muted-foreground">
                {Math.round(progress)}% completed
              </span>
            </div>
            <Progress value={progress} className="h-2" />

            {/* Step Indicators */}
            <div className="flex justify-between mt-4 overflow-x-auto pb-2">
              {STEPS.map((step) => {
                const Icon = step.icon
                const isCompleted = currentStep > step.id
                const isCurrent = currentStep === step.id

                return (
                  <div key={step.id} className="flex flex-col items-center min-w-0 flex-1 px-1">
                    <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center mb-1 ${
                      isCompleted
                        ? 'bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-400'
                        : isCurrent
                        ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400'
                        : 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500'
                    }`}>
                      {isCompleted ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </div>
                    <span className={`text-xs text-center px-1 leading-tight ${
                      isCurrent ? 'font-medium' : 'text-muted-foreground'
                    }`}>
                      <span className="hidden sm:inline">{step.title}</span>
                      <span className="sm:hidden">{step.id}</span>
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Step Content */}
          <div className="min-h-[300px] sm:min-h-[400px]">
            {renderStepContent()}
          </div>

          {/* Navigation */}
          <div className="flex flex-col-reverse sm:flex-row justify-between gap-3 sm:gap-4 mt-6 sm:mt-8 pt-4 border-t">
            <Button
              variant="outline"
              onClick={currentStep === 1 ? onComplete : handlePrevious}
              disabled={loading}
              className="w-full sm:w-auto order-2 sm:order-1"
            >
              <ArrowRight className="h-4 w-4 mr-2 rotate-180" />
              {currentStep === 1 ? 'Cancel' : 'Previous'}
            </Button>

            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 order-1 sm:order-2">
              {currentStep < STEPS.length - 1 && (
                <Button onClick={handleNext} disabled={!canProceed() || loading} className="w-full sm:w-auto">
                  Next
                  <ArrowLeft className="h-4 w-4 ml-2" />
                </Button>
              )}

              {currentStep === 7 && (
                <>
                  <Button onClick={() => {
                    handleGenerate()
                  }} disabled={!canProceed() || loading} className="w-full sm:w-auto">
                    {loading ? (
                      <>
                        Generating...
                        <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                      </>
                    ) : (
                      <>
                        <span className="hidden sm:inline">Generate with AI</span>
                        <span className="sm:hidden">Generate</span>
                        <ArrowLeft className="h-4 w-4 ml-2" />
                      </>
                    )}
                  </Button>

                  {/* Error state and retry */}
                  {isError && !loading && (
                    <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex items-center gap-2 text-red-800 mb-2">
                        <AlertCircle className="h-4 w-4" />
                        <span className="font-medium">Generation Failed</span>
                      </div>
                      <p className="text-sm text-red-700 mb-3">
                        {apiError?.userMessage || 'An error occurred while generating use cases.'}
                      </p>
                      <Button
                        onClick={() => {
                          clearError()
                          handleGenerate()
                        }}
                        variant="outline"
                        size="sm"
                        className="text-red-700 border-red-300 hover:bg-red-100"
                      >
                        Try Again
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Generation Progress Modal */}
      <Dialog open={showGenerationModal} onOpenChange={(open) => {
        if (!open && jobStatus !== 'processing') {
          setShowGenerationModal(false)
        }
      }}>
        <DialogContent className="sm:max-w-md" onInteractOutside={(e) => {
          if (jobStatus === 'processing') {
            e.preventDefault()
          }
        }}>
          <DialogHeader>
            <DialogTitle>Generating Use Cases</DialogTitle>
            <DialogDescription>
              Please wait while we generate your use cases. This may take a few minutes.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Progress</span>
                <span className="font-medium">{Math.round(jobProgress)}%</span>
              </div>
              <Progress value={jobProgress} className="h-2" />
            </div>

            {/* Per-Table Processing Info */}
            {jobStatus === 'processing' && totalTables > 0 && (
              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-md border border-blue-200 dark:border-blue-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                    Processing Tables
                  </span>
                  <span className="text-sm text-blue-700 dark:text-blue-300">
                    {processedTables} / {totalTables}
                  </span>
                </div>
                {currentTable && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sm text-blue-800 dark:text-blue-200">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      <span className="font-medium">Current: {currentTable}</span>
                    </div>
                    {processingMessage && (
                      <p className="text-xs text-blue-600 dark:text-blue-400 ml-5">
                        {processingMessage}
                      </p>
                    )}
                  </div>
                )}
                {!currentTable && processedTables > 0 && (
                  <p className="text-xs text-blue-600 dark:text-blue-400">
                    Validating use cases...
                  </p>
                )}
              </div>
            )}

            {/* Status Messages */}
            <div className="space-y-2 text-sm">
              {jobStatus === 'waiting' && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Initializing job...</span>
                </div>
              )}
              {jobStatus === 'processing' && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="font-medium">Processing...</span>
                  </div>
                  {!totalTables && (
                    <>
                      {jobProgress < 20 && <p className="text-muted-foreground text-xs ml-6">Loading schema...</p>}
                      {jobProgress >= 20 && jobProgress < 40 && <p className="text-muted-foreground text-xs ml-6">Processing data dictionary...</p>}
                      {jobProgress >= 40 && jobProgress < 50 && <p className="text-muted-foreground text-xs ml-6">Preparing table processing...</p>}
                    </>
                  )}
                  {totalTables > 0 && (
                    <p className="text-muted-foreground text-xs ml-6">
                      Processing {totalTables} table{totalTables > 1 ? 's' : ''} sequentially with real data...
                    </p>
                  )}
                  {jobProgress >= 95 && <p className="text-muted-foreground text-xs ml-6">Finalizing results...</p>}
                </div>
              )}
              {jobStatus === 'done' && (
                <div className="flex items-center gap-2 text-green-600">
                  <Check className="h-4 w-4" />
                  <span className="font-medium">Generation completed successfully!</span>
                </div>
              )}
              {jobStatus === 'failed' && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    <span className="font-medium">Generation failed</span>
                  </div>
                  {jobError && (
                    <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{jobError}</p>
                  )}
                </div>
              )}
            </div>

            {/* Cancel Button (only when processing) */}
            {jobStatus === 'processing' && (
              <Button
                variant="outline"
                onClick={handleCancelGeneration}
                className="w-full"
              >
                Cancel Generation
              </Button>
            )}

            {/* Close Button (when done or failed) */}
            {(jobStatus === 'done' || jobStatus === 'failed') && (
              <Button
                onClick={() => {
                  setShowGenerationModal(false)
                  if (jobStatus === 'failed') {
                    setCurrentJobId(null)
                    setJobProgress(0)
                    setJobStatus('waiting')
                    setCurrentTable(null)
                    setTotalTables(0)
                    setProcessedTables(0)
                    setProcessingMessage(null)
                  }
                }}
                className="w-full"
              >
                {jobStatus === 'done' ? 'View Results' : 'Close'}
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// Generated Use Cases Review Component
interface GeneratedUseCasesReviewProps {
  useCases: GeneratedUseCase[]
  systemPromptExamples: string
  onSave: (selectedUseCases: GeneratedUseCase[]) => void
  onBack: () => void
  isSaving?: boolean
}

function GeneratedUseCasesReview({ useCases, systemPromptExamples, onSave, onBack, isSaving = false }: GeneratedUseCasesReviewProps) {
  const [selectedUseCases, setSelectedUseCases] = useState<Set<number>>(new Set(useCases.map((_, i) => i)))
  const [editingUseCase, setEditingUseCase] = useState<number | null>(null)
  const [editedData, setEditedData] = useState<Partial<GeneratedUseCase>>({})

  const toggleSelection = (index: number) => {
    const newSelection = new Set(selectedUseCases)
    if (newSelection.has(index)) {
      newSelection.delete(index)
    } else {
      newSelection.add(index)
    }
    setSelectedUseCases(newSelection)
  }

  const startEditing = (index: number) => {
    setEditingUseCase(index)
    setEditedData(useCases[index])
  }

  const saveEdit = () => {
    if (editingUseCase !== null) {
      // In a real app, you'd update the useCases array
      // For now, we'll just close the edit mode
      setEditingUseCase(null)
      setEditedData({})
    }
  }

  const handleSave = () => {
    const selected = Array.from(selectedUseCases).map(index => {
      const useCase = useCases[index]
      if (editingUseCase === index) {
        // Merge edited data with original, ensuring name and description are set correctly
        return { 
          ...useCase, 
          ...editedData,
          name: editedData.name || useCase.name || useCase.title || useCase.usecase_name || 'Unnamed Use Case',
          description: editedData.description || useCase.description || useCase.business_goal || '',
          typical_questions: editedData.typical_questions || useCase.typical_questions || [],
          example_queries: editedData.example_queries || useCase.example_queries || []
        }
      }
      // Ensure name and description are set for non-edited use cases
      return {
        ...useCase,
        name: useCase.name || useCase.title || useCase.usecase_name || 'Unnamed Use Case',
        description: useCase.description || useCase.business_goal || '',
        typical_questions: useCase.typical_questions || [],
        example_queries: useCase.example_queries || [],
        main_tables: useCase.main_tables || []
      }
    })
    onSave(selected)
  }

  const getOutputTypeBadge = (outputType: string) => {
    const colors = {
      aggregation: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
      list: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
      trend: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
      comparison: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
      report: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300"
    }
    return colors[outputType as keyof typeof colors] || colors.report
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-lg font-semibold mb-2">Generated Use Cases</h3>
        <p className="text-muted-foreground">
          {useCases.length} use cases generated. Review and customize before saving.
        </p>
      </div>

      <Tabs defaultValue="use-cases" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="use-cases">Use Cases ({selectedUseCases.size} selected)</TabsTrigger>
          <TabsTrigger value="prompt-examples">System Prompt Examples</TabsTrigger>
        </TabsList>

        <TabsContent value="use-cases" className="space-y-4">
          {useCases.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-red-500">No use cases received from API</p>
              <p className="text-sm text-gray-500 mt-2">Check console for API response details</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {useCases.map((useCase, index) => (
          <Card key={index} className={`transition-all ${
            selectedUseCases.has(index) ? 'ring-2 ring-blue-500' : ''
          }`}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="text-base flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedUseCases.has(index)}
                      onChange={() => toggleSelection(index)}
                      className="rounded"
                    />
                    {editingUseCase === index ? (
                      <Input
                        value={editedData.name || useCase.name || useCase.title || ''}
                        onChange={(e) => setEditedData(prev => ({ ...prev, name: e.target.value }))}
                        className="text-base"
                      />
                    ) : (
                      useCase.name || useCase.title || useCase.usecase_name || 'Unnamed Use Case'
                    )}
                  </CardTitle>
                  {useCase.output_type && (
                    <Badge className={`mt-1 ${getOutputTypeBadge(useCase.output_type)}`}>
                      {useCase.output_type}
                    </Badge>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => editingUseCase === index ? saveEdit() : startEditing(index)}
                >
                  {editingUseCase === index ? 'Save' : 'Edit'}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-sm text-muted-foreground mb-3">
                {editingUseCase === index ? (
                  <Textarea
                    value={editedData.description || useCase.description || useCase.business_goal || ''}
                    onChange={(e) => setEditedData(prev => ({ ...prev, description: e.target.value }))}
                    rows={2}
                  />
                ) : (
                  useCase.description || useCase.business_goal || ''
                )}
              </p>

              <div className="space-y-2">
                <div className="text-sm font-medium">Sample questions:</div>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {((editingUseCase === index ? editedData.typical_questions || useCase.typical_questions : useCase.typical_questions) || []).map((question, qIndex) => (
                    <li key={qIndex} className="flex items-start gap-2">
                      <span className="text-blue-500 mt-1">•</span>
                      {question}
                    </li>
                  ))}
                  {(!useCase.typical_questions || useCase.typical_questions.length === 0) && (
                    <li className="text-muted-foreground italic">No questions provided</li>
                  )}
                </ul>
              </div>

              {((editingUseCase === index ? editedData.example_queries || useCase.example_queries : useCase.example_queries) || []).length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium">Example SQL queries:</div>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    {((editingUseCase === index ? editedData.example_queries || useCase.example_queries : useCase.example_queries) || []).map((query, qIndex) => (
                      <li key={qIndex} className="flex items-start gap-2">
                        <span className="text-green-500 mt-1">→</span>
                        <code className="bg-gray-100 px-2 py-1 rounded text-xs font-mono break-all" style={{wordBreak: 'break-all', whiteSpace: 'pre-wrap'}}>
                          {typeof query === 'string' ? query : JSON.stringify(query, null, 2)}
                        </code>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {useCase.main_tables && useCase.main_tables.length > 0 && (
                <div className="mt-3">
                  <div className="text-sm font-medium mb-1">Main tables:</div>
                  <div className="flex flex-wrap gap-1">
                    {useCase.main_tables.map((table, tIndex) => (
                      <Badge key={tIndex} variant="outline" className="text-xs">
                        {table}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {useCase.risk_notes && useCase.risk_notes !== "None" && (
                <div className="mt-3 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded text-sm text-yellow-800 dark:text-yellow-200">
                  ⚠️ {useCase.risk_notes}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="prompt-examples" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Prompt Examples</CardTitle>
              <CardDescription>
                How these use cases will appear in optimized system prompts for Text-to-SQL
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
                <pre className="text-sm whitespace-pre-wrap font-mono">
                  {systemPromptExamples}
                </pre>
              </div>
              <p className="text-sm text-muted-foreground mt-4">
                These examples help AI models understand what types of questions users ask and how to respond appropriately in Text-to-SQL scenarios.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          <ArrowRight className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={handleSave} disabled={selectedUseCases.size === 0 || isSaving}>
          {isSaving ? (
            <>
              Saving...
              <Loader2 className="h-4 w-4 ml-2 animate-spin" />
            </>
          ) : (
            <>
              Save {selectedUseCases.size} selected use case{selectedUseCases.size !== 1 ? 's' : ''}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}