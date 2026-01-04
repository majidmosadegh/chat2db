"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Plus, Lightbulb, Wand2, List, Edit, Trash2, Sparkles, TrendingUp } from "lucide-react"
import { SmartUseCaseBuilderWizard } from "@/components/use-cases/smart-use-case-builder-wizard"
import { UseCasesList } from "@/components/use-cases/use-cases-list"
import { PageLoader } from "@/components/ui/loading"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { useToast } from "@/lib/use-toast"
import axios from "axios"

interface UseCase {
  id: number
  name: string
  business_goal: string
  example_questions: string[]
  example_queries?: string[]
  output_style: string
  created_at: string
  is_ai_generated: boolean
  generation_log_id?: number
  generation_version?: number
  business_context?: string
  primary_audience?: string[]
  typical_questions_wizard?: string[]
  output_preference?: string
  dictionary_version?: number
  relationships_version?: number
}

interface SchemaSnapshot {
  id: number
  name: string
  description: string
  created_at: string
}

export default function UseCasesPage() {
  const { toast } = useToast()
  const [useCases, setUseCases] = useState<UseCase[]>([])
  const [snapshots, setSnapshots] = useState<SchemaSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [showWizard, setShowWizard] = useState(false)
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState("list")
  const [autoMatureLoading, setAutoMatureLoading] = useState(false)
  const [showAutoMatureDialog, setShowAutoMatureDialog] = useState(false)

  useEffect(() => {
    // Check if URL has #builder hash and switch to smart builder tab
    if (typeof window !== 'undefined' && window.location.hash === '#builder') {
      setActiveTab("builder")
    }
  }, [])

  useEffect(() => {
    fetchSnapshots()
    fetchUseCases()
  }, [])

  useEffect(() => {
    fetchUseCases()
  }, [selectedSnapshotId])

  const fetchSnapshots = async () => {
    try {
      const response = await axios.get('/api/schema/snapshots')
      setSnapshots(response.data)
    } catch (error) {
    }
  }

  const fetchUseCases = async () => {
    try {
      const params = selectedSnapshotId ? { snapshot_id: selectedSnapshotId } : {}
      const response = await axios.get('/api/use-cases', { params })
      setUseCases(response.data)
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const handleWizardComplete = () => {
    setShowWizard(false)
    fetchUseCases() // Refresh the list
  }

  const handleAutoMature = () => {
    if (!selectedSnapshotId) {
      toast({
        title: "No Snapshot Selected",
        description: "Please select a snapshot first",
        variant: "destructive",
      })
      return
    }
    setShowAutoMatureDialog(true)
  }

  const handleAutoMatureConfirm = async () => {
    if (!selectedSnapshotId) return

    setAutoMatureLoading(true)
    try {
      const response = await axios.post("/api/use-cases/auto-mature", {
        snapshot_id: selectedSnapshotId,
        language: "persian"
      })
      
      toast({
        title: "Success",
        description: `Auto-maturation complete! Optimized ${response.data.total_optimized} use case(s).`,
      })
      fetchUseCases()
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || error.message || "Failed to auto-mature use cases",
        variant: "destructive",
      })
    } finally {
      setAutoMatureLoading(false)
      setShowAutoMatureDialog(false)
    }
  }

  if (loading) {
    return <PageLoader message="Loading use cases..." />
  }

  if (showWizard) {
    return (
      <div className="container mx-auto p-6">
        <SmartUseCaseBuilderWizard onComplete={handleWizardComplete} />
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Use Cases</h1>
          <p className="text-muted-foreground">
            Define and manage use cases to improve chat-with-database accuracy
          </p>
        </div>
        <div className="flex gap-2">
          {selectedSnapshotId && (
            <Button 
              onClick={handleAutoMature} 
              variant="outline" 
              className="gap-2"
              disabled={autoMatureLoading}
            >
              {autoMatureLoading ? (
                <>
                  <Sparkles className="h-4 w-4 animate-spin" />
                  Optimizing...
                </>
              ) : (
                <>
                  <TrendingUp className="h-4 w-4" />
                  Auto-Mature All
                </>
              )}
            </Button>
          )}
          <Button onClick={() => setShowWizard(true)} className="gap-2">
            <Wand2 className="h-4 w-4" />
            Smart Use Case Builder
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="list">Use Cases List</TabsTrigger>
          <TabsTrigger value="builder">Smart Builder</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <UseCasesList
            useCases={useCases}
            snapshots={snapshots}
            loading={loading}
            selectedSnapshotId={selectedSnapshotId}
            onSnapshotChange={setSelectedSnapshotId}
            onRefresh={fetchUseCases}
          />
        </TabsContent>

        <TabsContent value="builder">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="h-5 w-5" />
                Smart Use Case Builder
              </CardTitle>
              <CardDescription>
                This tool uses AI and your database analysis to generate practical use cases.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <Lightbulb className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-semibold mb-2">Ready to get started?</h3>
                <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                  With just a few simple questions, our smart tool will generate practical use cases based on your database.
                </p>
                <Button onClick={() => setShowWizard(true)} size="lg" className="gap-2">
                  <Plus className="h-4 w-4" />
                  Get Started
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <ConfirmationDialog
        open={showAutoMatureDialog}
        onOpenChange={setShowAutoMatureDialog}
        title="Auto-Mature Use Cases"
        description="This will optimize all outdated use cases in this snapshot. This action may take a few moments. Continue?"
        onConfirm={handleAutoMatureConfirm}
        confirmText="Continue"
        cancelText="Cancel"
      />
    </div>
  )
}