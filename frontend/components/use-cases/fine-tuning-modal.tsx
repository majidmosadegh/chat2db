"use client"

import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { CheckCircle, Circle, Loader2, XCircle, Wand2 } from "lucide-react"
import { FineTuningContextPreview } from "./fine-tuning-context-preview"
import { FineTuningQuestionGeneration } from "./fine-tuning-question-generation"
import { FineTuningSQLExecution } from "./fine-tuning-sql-execution"
import { FineTuningUseCaseRefinement } from "./fine-tuning-use-case-refinement"
import axios from "axios"

interface UseCase {
  id: number
  name: string
  business_goal: string
  example_questions: string[]
  output_style: string
}

interface FineTuningSession {
  id: number
  use_case_id: number
  status: string
  current_step: string | null
  include_full_dictionary: boolean
  questions_count: number
  generated_questions_count: number
  approved_questions_count: number
  rejected_questions_count: number
  confidence_score: number | null
  created_at: string
}

type StepType = "context_preview" | "question_generation" | "sql_execution" | "use_case_refinement"

interface StepConfig {
  id: StepType
  title: string
  description: string
  icon: React.ReactNode
}

const steps: StepConfig[] = [
  {
    id: "context_preview",
    title: "Context Preview",
    description: "Review tables, relations, and data dictionary",
    icon: <Circle className="h-4 w-4" />
  },
  {
    id: "question_generation",
    title: "Generate Questions",
    description: "AI generates realistic business questions",
    icon: <Circle className="h-4 w-4" />
  },
  {
    id: "sql_execution",
    title: "Test & Execute",
    description: "Generate SQL, execute queries, and provide feedback",
    icon: <Circle className="h-4 w-4" />
  },
  {
    id: "use_case_refinement",
    title: "Refine Use Case",
    description: "AI refines the use case based on results",
    icon: <Circle className="h-4 w-4" />
  }
]

interface FineTuningModalProps {
  isOpen: boolean
  onClose: () => void
  useCase: UseCase
  onComplete?: (refinedUseCase: any) => void
}

export function FineTuningModal({ isOpen, onClose, useCase, onComplete }: FineTuningModalProps) {
  const [currentStep, setCurrentStep] = useState<StepType>("context_preview")
  const [session, setSession] = useState<FineTuningSession | null>(null)
  const [loading, setLoading] = useState(false)
  const [sessionConfig, setSessionConfig] = useState({
    include_full_dictionary: false,
    questions_count: 5,
    language: "english" as "english" | "persian"
  })

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setCurrentStep("context_preview")
      setSession(null)
      setSessionConfig({
        include_full_dictionary: false,
        questions_count: 5,
        language: "english"
      })
    }
  }, [isOpen])

  // Simple session refresh - only when needed
  const refreshSession = async () => {
    if (!session?.id) return
    try {
      const response = await axios.get(`/api/fine-tuning/sessions/${session.id}`)
      const updatedSession = response.data
      setSession(updatedSession)
    } catch (error) {
    }
  }

  const handleStartFineTuning = async () => {
    setLoading(true)
    try {
      const response = await axios.post('/api/fine-tuning/sessions', {
        use_case_id: useCase.id,
        include_full_dictionary: sessionConfig.include_full_dictionary,
        questions_count: sessionConfig.questions_count,
        language: sessionConfig.language
      })

      setSession(response.data)
      setCurrentStep("context_preview")
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const handleNext = () => {
    const currentIndex = steps.findIndex(step => step.id === currentStep)
    if (currentIndex < steps.length - 1) {
      setCurrentStep(steps[currentIndex + 1].id)
    }
  }

  const handlePrevious = () => {
    const currentIndex = steps.findIndex(step => step.id === currentStep)
    if (currentIndex > 0) {
      setCurrentStep(steps[currentIndex - 1].id)
    }
  }

  const getStepStatus = (stepId: StepType) => {
    if (!session) return "pending"

    const stepIndex = steps.findIndex(step => step.id === stepId)
    const currentStepIndex = steps.findIndex(step => step.id === currentStep)

    if (stepIndex < currentStepIndex) return "completed"
    if (stepIndex === currentStepIndex) return "active"
    return "pending"
  }

  const getStepIcon = (stepId: StepType) => {
    const status = getStepStatus(stepId)

    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "active":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      default:
        return <Circle className="h-4 w-4 text-gray-400" />
    }
  }

  const renderCurrentStep = () => {
    if (!session) {
      // Initial setup screen
      return (
        <div className="space-y-4 sm:space-y-6">
          <div className="text-center px-2 sm:px-0">
            <Wand2 className="h-8 w-8 sm:h-12 sm:w-12 mx-auto mb-3 sm:mb-4 text-blue-500" />
            <h2 className="text-xl sm:text-2xl font-bold mb-2">Fine-Tune Use Case</h2>
            <p className="text-muted-foreground text-sm sm:text-base max-w-md mx-auto leading-relaxed">
              Use AI to improve your use case by generating realistic questions,
              testing SQL generation, and refining based on real execution results.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Use Case to Fine-Tune</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <h3 className="font-semibold">{useCase.name}</h3>
                <p className="text-sm text-muted-foreground">{useCase.business_goal}</p>
                <div className="flex flex-wrap gap-1">
                  {useCase.example_questions.slice(0, 3).map((question, index) => (
                    <Badge key={index} variant="secondary" className="text-xs">
                      Question {index + 1}
                    </Badge>
                  ))}
                  {useCase.example_questions.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{useCase.example_questions.length - 3} more
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3 sm:pb-4">
              <CardTitle className="text-base sm:text-lg">Configuration</CardTitle>
              <CardDescription className="text-sm">
                Customize the fine-tuning process
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 sm:space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
                <div className="flex-1 min-w-0">
                  <label className="text-sm font-medium block mb-1">Include Full Data Dictionary</label>
                  <p className="text-xs text-muted-foreground">
                    Include all table and column descriptions in AI context
                  </p>
                </div>
                <div className="flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={sessionConfig.include_full_dictionary}
                    onChange={(e) => setSessionConfig(prev => ({
                      ...prev,
                      include_full_dictionary: e.target.checked
                    }))}
                    className="rounded w-4 h-4"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium block">
                  Number of Questions: <span className="text-blue-600">{sessionConfig.questions_count}</span>
                </label>
                <input
                  type="range"
                  min="3"
                  max="10"
                  value={sessionConfig.questions_count}
                  onChange={(e) => setSessionConfig(prev => ({
                    ...prev,
                    questions_count: parseInt(e.target.value)
                  }))}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>3</span>
                  <span>10</span>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium block">Question Language</label>
                <select
                  value={sessionConfig.language}
                  onChange={(e) => setSessionConfig(prev => ({
                    ...prev,
                    language: e.target.value as "english" | "persian"
                  }))}
                  className="w-full p-2 sm:p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                >
                  <option value="english">English</option>
                  <option value="persian">Persian (فارسی)</option>
                </select>
                <p className="text-xs text-muted-foreground">
                  Choose the language for generated questions and analysis
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3 pt-4 border-t">
            <Button
              variant="outline"
              onClick={onClose}
              className="w-full sm:w-auto order-2 sm:order-1"
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleStartFineTuning}
              disabled={loading}
              className="w-full sm:w-auto order-1 sm:order-2"
            >
              {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              <span className="hidden sm:inline">Start Fine-Tuning</span>
              <span className="sm:hidden">Start</span>
            </Button>
          </div>
        </div>
      )
    }

    // Render appropriate step component
    switch (currentStep) {
      case "context_preview":
        return <FineTuningContextPreview sessionId={session.id} onNext={handleNext} />
      case "question_generation":
        return <FineTuningQuestionGeneration sessionId={session.id} onNext={handleNext} />
      case "sql_execution":
        return <FineTuningSQLExecution sessionId={session.id} onNext={handleNext} />
      case "use_case_refinement":
        return (
          <FineTuningUseCaseRefinement
            sessionId={session.id}
            onComplete={(refinedUseCase) => {
              onComplete?.(refinedUseCase)
              onClose()
            }}
          />
        )
      default:
        return <div>Unknown step</div>
    }
  }

  const getProgressPercentage = () => {
    if (!session) return 0
    const currentIndex = steps.findIndex(step => step.id === currentStep)
    return ((currentIndex + 1) / steps.length) * 100
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="w-[95vw] sm:w-[90vw] md:max-w-4xl max-h-[95vh] sm:max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="pb-2 sm:pb-4">
          <DialogTitle className="flex items-center gap-2 text-lg sm:text-xl">
            <Wand2 className="h-4 w-4 sm:h-5 sm:w-5" />
            Use Case Fine-Tuning
          </DialogTitle>
        </DialogHeader>

        {session && (
          <>
            {/* Progress indicator */}
            <div className="space-y-3 sm:space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Progress</span>
                <span className="text-muted-foreground">{Math.round(getProgressPercentage())}%</span>
              </div>
              <Progress value={getProgressPercentage()} className="h-2" />

              {/* Step indicators - responsive layout */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0">
                {steps.map((step, index) => (
                  <div key={step.id} className="flex items-center flex-1 sm:flex-none">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 flex-1">
                      {getStepIcon(step.id)}
                      <span className={`text-xs sm:text-sm ${
                        getStepStatus(step.id) === "active" ? "text-blue-600 font-medium" :
                        getStepStatus(step.id) === "completed" ? "text-green-600" :
                        "text-gray-400"
                      }`}>
                        <span className="hidden sm:inline">{step.title}</span>
                        <span className="sm:hidden">{step.title.split(' ')[0]}</span>
                      </span>
                    </div>
                    {index < steps.length - 1 && (
                      <Separator className="hidden sm:flex w-6 sm:w-8 mx-1 sm:mx-2" orientation="horizontal" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator className="my-3 sm:my-4" />
          </>
        )}

        {/* Step content */}
        <div className="flex-1 overflow-y-auto min-h-0 px-1 sm:px-0">
          <div className="pr-1 sm:pr-0">
            {renderCurrentStep()}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
