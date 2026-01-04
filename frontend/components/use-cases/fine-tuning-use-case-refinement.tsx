"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Loader2, CheckCircle, FileText, Sparkles, ArrowRight } from "lucide-react"
import axios from "axios"

interface UseCaseRefinementData {
  original_use_case: string
  refined_use_case: string
  summary_of_changes: string
  new_version_id: number
}

interface FineTuningUseCaseRefinementProps {
  sessionId: number
  onComplete: (refinedUseCase: UseCaseRefinementData) => void
}

export function FineTuningUseCaseRefinement({ sessionId, onComplete }: FineTuningUseCaseRefinementProps) {
  const [data, setData] = useState<UseCaseRefinementData | null>(null)
  const [loading, setLoading] = useState(false)
  const [refining, setRefining] = useState(false)

  useEffect(() => {
    // Auto-start refinement when component mounts
    handleRefineUseCase()
  }, [sessionId])

  // Auto-complete when refinement is done
  useEffect(() => {
    if (data) {
      setTimeout(() => {
        handleSaveVersion()
      }, 2000) // Show results for 2 seconds
    }
  }, [data])

  const handleRefineUseCase = async () => {
    setRefining(true)
    try {
      const response = await axios.post(`/api/fine-tuning/sessions/${sessionId}/refine-use-case`)
      setData(response.data)
    } catch (error) {
    } finally {
      setRefining(false)
    }
  }

  const handleSaveVersion = () => {
    if (data) {
      onComplete(data)
    }
  }

  if (refining) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center space-y-4">
          <div className="relative">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
            <Sparkles className="h-6 w-6 absolute top-3 left-3 text-blue-500 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-semibold mb-2">Refining Use Case</h3>
            <p className="text-muted-foreground">
              AI is analyzing execution results and refining your use case...
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500">Failed to refine use case</p>
        <Button onClick={handleRefineUseCase} className="mt-4">
          Try Again
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-2">Use Case Refinement Complete</h2>
        <p className="text-muted-foreground">
          AI has analyzed the execution results and refined your use case
        </p>
      </div>

      {/* Summary of Changes */}
      <Card className="border-green-200 bg-green-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-800">
            <CheckCircle className="h-5 w-5" />
            Refinement Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-green-700">{data.summary_of_changes}</p>
        </CardContent>
      </Card>

      {/* Before/After Comparison */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Original Use Case */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Original Use Case
            </CardTitle>
            <CardDescription>
              Your original use case text
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <Badge variant="outline" className="mb-2 border-red-300 text-red-700">
                Before
              </Badge>
              <p className="text-sm text-red-900">{data.original_use_case}</p>
            </div>
          </CardContent>
        </Card>

        {/* Refined Use Case */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              Refined Use Case
            </CardTitle>
            <CardDescription>
              AI-improved version based on execution results
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <Badge variant="outline" className="mb-2 border-green-300 text-green-700">
                After
              </Badge>
              <p className="text-sm text-green-900">{data.refined_use_case}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Changes */}
      <Card>
        <CardHeader>
          <CardTitle>Detailed Comparison</CardTitle>
          <CardDescription>
            Side-by-side comparison of the changes made
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="font-semibold text-red-700">Removed/Changed</h4>
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <p className="text-sm text-red-800">
                    Parts of the original use case that were identified as problematic
                    or could be improved based on SQL execution patterns.
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold text-green-700">Added/Improved</h4>
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-sm text-green-800">
                    New clarifications, table/column specifications, and improvements
                    to prevent previously failed SQL patterns.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Version Info */}
      <Card>
        <CardHeader>
          <CardTitle>Version Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm font-medium">New Version ID:</span>
              <Badge variant="outline">{data.new_version_id}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-sm font-medium">Created:</span>
              <span className="text-sm text-muted-foreground">
                {new Date().toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm font-medium">Method:</span>
              <Badge>AI Fine-tuned</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Button variant="outline">
          Cancel
        </Button>
        <Button onClick={handleSaveVersion} className="gap-2">
          <CheckCircle className="h-4 w-4" />
          Save New Version
        </Button>
      </div>
    </div>
  )
}
