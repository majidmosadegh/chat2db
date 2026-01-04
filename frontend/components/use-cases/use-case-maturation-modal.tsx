"use client"

import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Sparkles, TrendingUp, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"
import axios from "axios"

interface UseCase {
  id: number
  name: string
  dictionary_version?: number
  relationships_version?: number
}

interface MaturityAnalysis {
  use_case_id: number
  current_dict_version: number | null
  current_rel_version: number | null
  latest_dict_version: number
  latest_rel_version: number
  is_dict_outdated: boolean
  is_rel_outdated: boolean
  maturity_score: number
  recommendations: string[]
}

interface OptimizedUseCase {
  use_case_id: number
  optimized_name: string
  optimized_description: string
  optimized_questions: string[]
  optimized_queries: string[]
  improvements: string[]
  maturity_score_before: number
  maturity_score_after: number
  new_version_id?: number | null
}

interface UseCaseMaturationModalProps {
  isOpen: boolean
  onClose: () => void
  useCase: UseCase | null
  onOptimized: () => void
}

export function UseCaseMaturationModal({
  isOpen,
  onClose,
  useCase,
  onOptimized
}: UseCaseMaturationModalProps) {
  const [step, setStep] = useState<"analyze" | "optimize" | "result">("analyze")
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<MaturityAnalysis | null>(null)
  const [optimized, setOptimized] = useState<OptimizedUseCase | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && useCase) {
      setStep("analyze")
      setAnalysis(null)
      setOptimized(null)
      setError(null)
      handleAnalyze()
    }
  }, [isOpen, useCase])

  const handleAnalyze = async () => {
    if (!useCase) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.get(`/api/use-cases/${useCase.id}/analyze-maturity`)
      setAnalysis(response.data)
      setStep("optimize")
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to analyze maturity")
    } finally {
      setLoading(false)
    }
  }

  const handleOptimize = async (createVersion: boolean = true) => {
    if (!useCase) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`/api/use-cases/${useCase.id}/optimize`, {
        language: "persian",
        create_version: createVersion,
        update_original: false
      })
      setOptimized(response.data)
      setStep("result")
      onOptimized()
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to optimize use case")
    } finally {
      setLoading(false)
    }
  }

  const getMaturityColor = (score: number) => {
    if (score >= 0.8) return "text-green-600"
    if (score >= 0.6) return "text-yellow-600"
    return "text-red-600"
  }

  const getMaturityBadge = (score: number): "default" | "secondary" | "destructive" | "outline" => {
    if (score >= 0.8) return "default"
    if (score >= 0.6) return "secondary"
    return "destructive"
  }

  if (!useCase) return null

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Use Case Maturation
          </DialogTitle>
          <DialogDescription>
            Analyze and optimize use case maturity using latest dictionary and relationships
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800">Error</p>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          </div>
        )}

        {step === "analyze" && (
          <div className="space-y-4">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-center space-y-4">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-500" />
                  <p className="text-sm text-muted-foreground">Analyzing use case maturity...</p>
                </div>
              </div>
            ) : analysis ? (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Maturity Score</span>
                    <Badge variant={getMaturityBadge(analysis.maturity_score)}>
                      {(analysis.maturity_score * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <Progress value={analysis.maturity_score * 100} className="mt-2" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Dictionary Version</p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">
                        Current: {analysis.current_dict_version ?? "N/A"}
                      </span>
                      {analysis.is_dict_outdated && (
                        <Badge variant="secondary" className="text-xs">
                          Outdated
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Latest: {analysis.latest_dict_version}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-medium">Relationships Version</p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">
                        Current: {analysis.current_rel_version ?? "N/A"}
                      </span>
                      {analysis.is_rel_outdated && (
                        <Badge variant="secondary" className="text-xs">
                          Outdated
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Latest: {analysis.latest_rel_version}
                    </p>
                  </div>
                </div>

                {analysis.recommendations.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Recommendations</p>
                    <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                      {analysis.recommendations.map((rec, idx) => (
                        <li key={idx}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button onClick={() => handleOptimize(true)} className="flex-1">
                    <TrendingUp className="h-4 w-4 mr-2" />
                    Optimize & Create Version
                  </Button>
                  <Button onClick={() => handleOptimize(false)} variant="outline" className="flex-1">
                    Optimize (Preview Only)
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">Click to analyze</p>
                <Button onClick={handleAnalyze} className="mt-4">
                  Analyze Maturity
                </Button>
              </div>
            )}
          </div>
        )}

        {step === "optimize" && loading && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-500" />
              <p className="text-sm text-muted-foreground">Optimizing use case with AI...</p>
              <p className="text-xs text-muted-foreground">
                This may take a few moments
              </p>
            </div>
          </div>
        )}

        {step === "result" && optimized && (
          <div className="space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="font-medium text-green-800">Optimization Complete!</span>
              </div>
              <div className="flex items-center gap-4 mt-3">
                <div>
                  <p className="text-xs text-muted-foreground">Before</p>
                  <p className={`text-lg font-semibold ${getMaturityColor(optimized.maturity_score_before)}`}>
                    {(optimized.maturity_score_before * 100).toFixed(0)}%
                  </p>
                </div>
                <TrendingUp className="h-5 w-5 text-green-600" />
                <div>
                  <p className="text-xs text-muted-foreground">After</p>
                  <p className={`text-lg font-semibold ${getMaturityColor(optimized.maturity_score_after)}`}>
                    {(optimized.maturity_score_after * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
            </div>

            {optimized.improvements.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Improvements Made</p>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                  {optimized.improvements.map((imp, idx) => (
                    <li key={idx}>{imp}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">Optimized Name</p>
                <p className="text-sm text-muted-foreground">{optimized.optimized_name}</p>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Optimized Description</p>
                <p className="text-sm text-muted-foreground">{optimized.optimized_description}</p>
              </div>

              <div>
                <p className="text-sm font-medium mb-2">Questions ({optimized.optimized_questions.length})</p>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                  {optimized.optimized_questions.slice(0, 3).map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                  {optimized.optimized_questions.length > 3 && (
                    <li className="text-xs">... and {optimized.optimized_questions.length - 3} more</li>
                  )}
                </ul>
              </div>
            </div>

            {optimized.new_version_id && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-sm text-blue-800">
                  ✓ New version created (ID: {optimized.new_version_id})
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <Button onClick={onClose} className="flex-1">
                Close
              </Button>
              <Button onClick={() => {
                setStep("analyze")
                handleAnalyze()
              }} variant="outline">
                Analyze Again
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

