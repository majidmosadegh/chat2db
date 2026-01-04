"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { PageLoader, TableSkeleton } from "@/components/ui/loading"
import { EmptyTable } from "@/components/ui/empty-state"
import { Database as DatabaseIcon, FileText } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import {
  RefreshCw,
  Search,
  Database,
  Table,
  Columns,
  Key,
  ArrowRight,
  ChevronRight,
  ChevronDown,
  Loader2,
  Save,
  BookOpen
} from "lucide-react"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useRouter } from "next/navigation"

interface SchemaInfo {
  schema_name: string
  table_name: string
  column_name: string
  column_type: string
  is_primary_key: boolean
  is_foreign_key: boolean
  foreign_key_table?: string
  foreign_key_column?: string
}

interface TableInfo {
  schema_name: string
  table_name: string
  columns: Array<{
    name: string
    type: string
    is_primary_key: boolean
    is_foreign_key: boolean
    foreign_key_table?: string
    foreign_key_column?: string
  }>
}

interface TreeNode {
  id: string
  name: string
  type: 'schema' | 'table' | 'column'
  children?: TreeNode[]
  data?: any
  expanded?: boolean
}

interface DatabaseConnection {
  id: number
  db_type: string
  host: string
  port: number
  username: string
  database_name: string
  is_active: boolean
}

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  connection_id: number
  created_at: string
  table_count: number
}

interface IntrospectionTable {
  schema_name: string
  table_name: string
  row_count: number
  columns: Array<{
    column_name: string
    column_type: string
    is_primary_key: boolean
    is_foreign_key: boolean
    foreign_key_table?: string
    foreign_key_column?: string
  }>
}

interface IntrospectionResult {
  connection_id: number
  database_name: string
  schema_data: IntrospectionTable[]
  total_items: number
}

export default function SchemaExplorerPage() {
  const { toast } = useToast()
  const [schemaData, setSchemaData] = useState<SchemaInfo[]>([])
  const [tableData, setTableData] = useState<TableInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [introspecting, setIntrospecting] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null)
  const [treeData, setTreeData] = useState<TreeNode[]>([])
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null)
  const [dataVersion, setDataVersion] = useState(0)

  // Schema snapshot states
  const [schemaSnapshots, setSchemaSnapshots] = useState<SchemaSnapshot[]>([])
  const [lastIntrospectionResult, setLastIntrospectionResult] = useState<IntrospectionResult | null>(null)
  const [showSnapshotDialog, setShowSnapshotDialog] = useState(false)
  const [snapshotName, setSnapshotName] = useState("")
  const [snapshotDescription, setSnapshotDescription] = useState("")
  const [savingSnapshot, setSavingSnapshot] = useState(false)
  const [activeTab, setActiveTab] = useState("explorer")

  // Confirmation dialog states
  const [showDeleteSnapshotDialog, setShowDeleteSnapshotDialog] = useState(false)
  const [showClearMetadataDialog, setShowClearMetadataDialog] = useState(false)
  const [snapshotToDelete, setSnapshotToDelete] = useState<SchemaSnapshot | null>(null)

  const router = useRouter()

  useEffect(() => {
    fetchConnections()
    fetchSchemaSnapshots()
  }, [])

  useEffect(() => {
    if (activeTab === "snapshots") {
      fetchSchemaSnapshots()
    }
  }, [activeTab])

  // Auto-switch to snapshots tab if snapshots exist (only on initial load)
  useEffect(() => {
    if (schemaSnapshots.length > 0 && activeTab === "explorer") {
      setActiveTab("snapshots")
    }
  }, [schemaSnapshots])

  useEffect(() => {
    if (selectedConnectionId) {
      fetchSchemaData()
    }
  }, [selectedConnectionId, dataVersion])

  useEffect(() => {
    if (schemaData.length > 0) {
      buildTreeData()
    }
  }, [schemaData, searchTerm])

  const fetchConnections = async () => {
    try {
      const response = await fetch("/api/database")
      if (response.ok) {
        const data = await response.json()
        setConnections(data)
        // Set first available connection as selected if none selected
        if (!selectedConnectionId && data.length > 0) {
          setSelectedConnectionId(data[0].id)
        }
      }
    } catch (error) {
    }
  }

  const fetchSchemaSnapshots = async () => {
    try {
      const response = await fetch("/api/schema/snapshots")
      if (response.ok) {
        const snapshots: SchemaSnapshot[] = await response.json()
        setSchemaSnapshots(snapshots)
      }
    } catch (error) {
    }
  }

  const handleSaveSnapshot = async () => {
    if (!snapshotName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a snapshot name.",
        variant: "destructive",
      })
      return
    }

    if (!lastIntrospectionResult) {
      toast({
        title: "Warning",
        description: "No introspection data available. Please run introspection first.",
        variant: "warning",
      })
      return
    }

    try {
      setSavingSnapshot(true)

      // First create the snapshot
      const createResponse = await fetch("/api/schema/snapshots/with-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: snapshotName.trim(),
          description: snapshotDescription.trim() || null,
          connection_id: selectedConnectionId
        })
      })

      if (!createResponse.ok) {
        const error = await createResponse.json()
        throw new Error(error.detail || "Failed to create snapshot")
      }

      const snapshotResult = await createResponse.json()
      const snapshotId = snapshotResult.snapshot.id

      // Then save the schema data to the snapshot
      const saveDataResponse = await fetch(`/api/schema/snapshots/${snapshotId}/save-data`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastIntrospectionResult)
      })

      if (!saveDataResponse.ok) {
        throw new Error("Failed to save schema data to snapshot")
      }

      // Refresh snapshots and close dialog
      await fetchSchemaSnapshots()
      setShowSnapshotDialog(false)
      setSnapshotName("")
      setSnapshotDescription("")

      // Switch to snapshots tab
      setActiveTab("snapshots")

    } catch (error) {
      toast({
        title: "Error",
        description: `Failed to save snapshot: ${error instanceof Error ? error.message : 'Unknown error'}`,
        variant: "destructive",
      })
    } finally {
      setSavingSnapshot(false)
    }
  }

// Removed handleActivateSnapshot - no longer needed

  const handleDeleteSnapshotClick = (snapshot: SchemaSnapshot) => {
    setSnapshotToDelete(snapshot)
    setShowDeleteSnapshotDialog(true)
  }

  const handleDeleteSnapshotConfirm = async () => {
    if (!snapshotToDelete) return

    try {
      const response = await fetch(`/api/schema/snapshots/${snapshotToDelete.id}`, {
        method: "DELETE"
      })

      if (response.ok) {
        await fetchSchemaSnapshots()
        setShowDeleteSnapshotDialog(false)
        setSnapshotToDelete(null)
        toast({
          title: "Success",
          description: "Snapshot deleted successfully",
          variant: "success",
        })
      } else {
        const error = await response.json()
        toast({
          title: "Error",
          description: `Failed to delete snapshot: ${error.detail}`,
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete snapshot",
        variant: "destructive",
      })
    }
  }

  const fetchSchemaData = async () => {
    try {
      setLoading(true)
      const [schemaResponse, tableResponse] = await Promise.all([
        fetch("/api/schema"),
        fetch("/api/schema/tables")
      ])

      if (schemaResponse.ok) {
        const schemaResult = await schemaResponse.json()
        setSchemaData(schemaResult)
      } else {
        }

      if (tableResponse.ok) {
        const tableResult = await tableResponse.json()
        setTableData(tableResult)
      } else {
        }
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const handleIntrospect = async () => {
    if (!selectedConnectionId) {
      toast({
        title: "Warning",
        description: "Please select a database connection first.",
        variant: "warning",
      })
      return
    }

    try {
      setIntrospecting(true)
      const response = await fetch(`/api/schema/introspect/${selectedConnectionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      if (response.ok) {
        try {
          const introspectionResult = await response.json()
          // Store the introspection result for snapshot creation
          setLastIntrospectionResult(introspectionResult)

          // Convert table-based data to column-based data for frontend display
          const columnBasedData: SchemaInfo[] = []
          const tableBasedData: TableInfo[] = []

          if (introspectionResult.schema_data) {
            introspectionResult.schema_data.forEach((table: any) => {
              // Create table info
              const tableInfo: TableInfo = {
                schema_name: table.schema_name,
                table_name: table.table_name,
                columns: table.columns.map((col: any) => ({
                  name: col.column_name,
                  type: col.column_type,
                  is_primary_key: col.is_primary_key,
                  is_foreign_key: col.is_foreign_key,
                  foreign_key_table: col.foreign_key_table,
                  foreign_key_column: col.foreign_key_column
                }))
              }
              tableBasedData.push(tableInfo)

              // Convert to column-based for schema display
              table.columns.forEach((column: any) => {
                columnBasedData.push({
                  schema_name: table.schema_name,
                  table_name: table.table_name,
                  column_name: column.column_name,
                  column_type: column.column_type,
                  is_primary_key: column.is_primary_key,
                  is_foreign_key: column.is_foreign_key,
                  foreign_key_table: column.foreign_key_table,
                  foreign_key_column: column.foreign_key_column
                })
              })
            })
          }

          // Update state with converted data
          setSchemaData(columnBasedData)
          setTableData(tableBasedData)
          setTreeData([])
          setSelectedNode(null)

          } catch (parseError) {
          toast({
            title: "Introspection Failed",
            description: `Error processing response: ${parseError instanceof Error ? parseError.message : 'Unknown error'}`,
            variant: "destructive",
          })
        }
      } else {
        const errorData = await response.json()
        toast({
          title: "Introspection Failed",
          description: errorData.detail || 'Unknown error occurred during schema introspection',
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Introspection Failed",
        description: "Failed to introspect schema. Please check your database connection.",
        variant: "destructive",
      })
    } finally {
      setIntrospecting(false)
    }
  }

  const handleClearSchema = () => {
    setShowClearMetadataDialog(true)
  }

  const handleClearSchemaConfirm = async () => {
    try {
      const response = await fetch("/api/schema", {
        method: "DELETE",
      })

      if (response.ok) {
        setSchemaData([])
        setTableData([])
        setTreeData([])
        setSelectedNode(null)
        toast({
          title: "Success",
          description: "Schema metadata cleared successfully",
        })
      } else {
        const errorData = await response.json()
        toast({
          title: "Error",
          description: errorData.detail || "Failed to clear schema metadata",
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to clear schema metadata",
        variant: "destructive",
      })
    } finally {
      setShowClearMetadataDialog(false)
    }
  }

  const buildTreeData = () => {
    const schemas: { [key: string]: { [key: string]: { [key: string]: any } } } = {}

    // Group columns by schema and table using schemaData
    schemaData.forEach(item => {
      if (!schemas[item.schema_name]) {
        schemas[item.schema_name] = {}
      }
      if (!schemas[item.schema_name][item.table_name]) {
        schemas[item.schema_name][item.table_name] = {}
      }
      schemas[item.schema_name][item.table_name][item.column_name] = item
    })

    const tree: TreeNode[] = []

    Object.keys(schemas).forEach(schemaName => {
      if (searchTerm && !schemaName.toLowerCase().includes(searchTerm.toLowerCase())) {
        return
      }

      const schemaNode: TreeNode = {
        id: `schema-${schemaName}`,
        name: schemaName,
        type: 'schema',
        expanded: true,
        children: []
      }

      Object.keys(schemas[schemaName]).forEach(tableName => {
        if (searchTerm && !tableName.toLowerCase().includes(searchTerm.toLowerCase())) {
          return
        }

        const tableColumns = Object.values(schemas[schemaName][tableName])
        const tableNode: TreeNode = {
          id: `table-${schemaName}-${tableName}`,
          name: tableName,
          type: 'table',
          data: {
            schema_name: schemaName,
            table_name: tableName,
            columns: tableColumns
          },
          children: []
        }

        tableColumns.forEach((column: any) => {
          if (searchTerm && !column.column_name.toLowerCase().includes(searchTerm.toLowerCase())) {
            return
          }

          tableNode.children!.push({
            id: `column-${schemaName}-${tableName}-${column.column_name}`,
            name: column.column_name,
            type: 'column',
            data: {
              ...column,
              name: column.column_name,
              type: column.column_type,
              schema_name: schemaName,
              table_name: tableName
            }
          })
        })

        schemaNode.children!.push(tableNode)
      })

      if (schemaNode.children!.length > 0) {
        tree.push(schemaNode)
      }
    })

    setTreeData(tree)
  }

  const toggleNodeExpansion = (node: TreeNode) => {
    const updateNode = (nodes: TreeNode[]): TreeNode[] => {
      return nodes.map(n => {
        if (n.id === node.id) {
          return { ...n, expanded: !n.expanded }
        }
        if (n.children) {
          return { ...n, children: updateNode(n.children) }
        }
        return n
      })
    }

    setTreeData(updateNode(treeData))
  }

  const renderTreeNode = (node: TreeNode, level = 0) => {
    const hasChildren = node.children && node.children.length > 0
    const isExpanded = node.expanded
    const isSelected = selectedNode?.id === node.id

    return (
      <div key={node.id}>
        <div
          className={`flex items-center py-1 px-2 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer rounded ${
            isSelected ? 'bg-blue-100 dark:bg-blue-900' : ''
          }`}
          style={{ paddingLeft: `${level * 20 + 8}px` }}
          onClick={() => {
            setSelectedNode(node)
            if (hasChildren) {
              toggleNodeExpansion(node)
            }
          }}
        >
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="h-4 w-4 mr-1" />
            ) : (
              <ChevronRight className="h-4 w-4 mr-1" />
            )
          ) : (
            <div className="w-5" />
          )}

          {node.type === 'schema' && <Database className="h-4 w-4 mr-2 text-blue-600" />}
          {node.type === 'table' && <Table className="h-4 w-4 mr-2 text-green-600" />}
          {node.type === 'column' && <Columns className="h-4 w-4 mr-2 text-purple-600" />}

          <span className="text-sm">{node.name}</span>

          {node.type === 'column' && node.data && (
            <div className="ml-auto flex items-center gap-1">
              {node.data.is_primary_key && (
                <Badge variant="default" className="text-xs">
                  <Key className="h-3 w-3 mr-1" />
                  PK
                </Badge>
              )}
              {node.data.is_foreign_key && (
                <Badge variant="secondary" className="text-xs">
                  <ArrowRight className="h-3 w-3 mr-1" />
                  FK
                </Badge>
              )}
              <span className="text-xs text-muted-foreground ml-2">
                {node.data.type}
              </span>
            </div>
          )}
        </div>

        {hasChildren && isExpanded && (
          <div>
            {node.children!.map(child => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return <PageLoader message="Loading schema data..." />
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Schema Management</h1>
        <p className="text-muted-foreground">
          Explore database schemas and manage schema snapshots
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="explorer">Schema Explorer</TabsTrigger>
          <TabsTrigger value="snapshots">Schema Snapshots</TabsTrigger>
        </TabsList>

        <TabsContent value="explorer" className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">Schema Explorer</h2>
              <p className="text-muted-foreground">
                Browse and explore your database schema structure
              </p>
            </div>
        <div className="flex gap-2 items-center">
          <div className="flex items-center gap-2">
            <Label htmlFor="connection-select">Database:</Label>
            <Select
              value={selectedConnectionId?.toString() || ""}
              onValueChange={(value) => setSelectedConnectionId(parseInt(value))}
            >
              <SelectTrigger className="w-64">
                <SelectValue placeholder="Select a database connection" />
              </SelectTrigger>
              <SelectContent>
                {connections.map((conn) => (
                  <SelectItem key={conn.id} value={conn.id.toString()}>
                    <div className="flex items-center gap-2">
                      <Database className="h-4 w-4" />
                      {conn.db_type} - {conn.host}:{conn.port}/{conn.database_name}
                      {conn.is_active && (
                        <Badge variant="default" className="text-xs">Active</Badge>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>


          <Button
            onClick={handleIntrospect}
            disabled={introspecting || !selectedConnectionId}
            className="flex items-center gap-2"
          >
            {introspecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {introspecting ? "Introspecting..." : "Introspect Schema"}
          </Button>

          {lastIntrospectionResult && (
            <Button
              onClick={() => setShowSnapshotDialog(true)}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save Schema Snapshot
            </Button>
          )}

          {schemaData.length > 0 && (
            <Button
              variant="outline"
              onClick={handleClearSchema}
              className="flex items-center gap-2"
            >
              Clear Schema
            </Button>
          )}
        </div>
      </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Schema Tree Panel */}
            <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Schema Structure</CardTitle>
                  <CardDescription>
                    {schemaData.length > 0
                      ? `${schemaData.length} columns across ${tableData.length} tables`
                      : "No schema data available. Run introspection to load schema."
                    }
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search schemas, tables, columns..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-9 w-64"
                    />
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {treeData.length === 0 ? (
                <EmptyTable
                  icon={DatabaseIcon}
                  title={searchTerm ? "No search results" : "No schema data"}
                  description={searchTerm
                    ? "No items match your search criteria. Try different keywords."
                    : "No schema data available. Select a database connection and click 'Introspect Schema' to load your database structure."
                  }
                />
              ) : (
                <div className="max-h-96 overflow-y-auto">
                  {treeData.map(node => renderTreeNode(node))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Details Panel */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
              <CardDescription>
                {selectedNode ? `Details for ${selectedNode.name}` : "Select an item to view details"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedNode ? (
                <div className="space-y-4">
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">Type</div>
                    <div className="capitalize">{selectedNode.type}</div>
                  </div>

                  {selectedNode.type === 'column' && selectedNode.data && (
                    <>
                      <Separator />
                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Data Type</div>
                        <div className="font-mono text-sm">{selectedNode.data.type}</div>
                      </div>

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Constraints</div>
                        <div className="flex gap-2 mt-1">
                          {selectedNode.data.is_primary_key && (
                            <Badge variant="default">
                              <Key className="h-3 w-3 mr-1" />
                              Primary Key
                            </Badge>
                          )}
                          {selectedNode.data.is_foreign_key && (
                            <Badge variant="secondary">
                              <ArrowRight className="h-3 w-3 mr-1" />
                              Foreign Key
                            </Badge>
                          )}
                        </div>
                      </div>

                      {selectedNode.data.is_foreign_key && (
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">References</div>
                          <div className="font-mono text-sm">
                            {selectedNode.data.foreign_key_table}.{selectedNode.data.foreign_key_column}
                          </div>
                        </div>
                      )}

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Location</div>
                        <div className="font-mono text-sm">
                          {selectedNode.data.schema_name}.{selectedNode.data.table_name}.{selectedNode.data.name}
                        </div>
                      </div>
                    </>
                  )}

                  {selectedNode.type === 'table' && selectedNode.data && (
                    <>
                      <Separator />
                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Schema</div>
                        <div>{selectedNode.data.schema_name}</div>
                      </div>

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Columns</div>
                        <div>{selectedNode.data.columns?.length || 0} columns</div>
                      </div>

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Primary Keys</div>
                        <div>
                          {selectedNode.data.columns?.filter((c: any) => c.is_primary_key).length || 0} columns
                        </div>
                      </div>

                      <div>
                        <div className="text-sm font-medium text-muted-foreground">Foreign Keys</div>
                        <div>
                          {selectedNode.data.columns?.filter((c: any) => c.is_foreign_key).length || 0} columns
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  Select a schema element from the tree to view its details.
                </div>
              )}
            </CardContent>
          </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="snapshots" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Schema Snapshots</CardTitle>
                  <CardDescription>
                    Manage your saved schema snapshots
                  </CardDescription>
                </div>
                <Button
                  onClick={() => setActiveTab("explorer")}
                  variant="outline"
                >
                  Create New Snapshot
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {schemaSnapshots.length === 0 ? (
                <EmptyTable
                  icon={FileText}
                  title="No schema snapshots"
                  description="Create your first snapshot by connecting to a database, exploring the schema, and saving it for future use."
                  action={{
                    label: "Create First Snapshot",
                    onClick: () => setActiveTab("explorer")
                  }}
                />
              ) : (
                <div className="space-y-4">
                  {schemaSnapshots.map((snapshot) => (
                    <Card key={snapshot.id}>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <BookOpen className="h-8 w-8 text-blue-600" />
                            <div>
                              <h3 className="font-semibold">{snapshot.name}</h3>
                              {snapshot.description && (
                                <p className="text-sm text-muted-foreground">{snapshot.description}</p>
                              )}
                              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                                <span>{snapshot.table_count} tables</span>
                                <span>Created: {new Date(snapshot.created_at).toLocaleDateString()}</span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                router.push(`/schema/${snapshot.id}`)
                              }}
                            >
                              View
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteSnapshotClick(snapshot)}
                            >
                              Delete
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Schema Snapshot Save Dialog */}
      <Dialog open={showSnapshotDialog} onOpenChange={setShowSnapshotDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Save Schema Snapshot</DialogTitle>
            <DialogDescription>
              Create a snapshot of the introspected schema data. This will allow you to work with the data dictionary and create prompts.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="snapshot-name" className="text-right">
                Name *
              </Label>
              <Input
                id="snapshot-name"
                value={snapshotName}
                onChange={(e) => setSnapshotName(e.target.value)}
                placeholder="e.g., Production Schema v1.0"
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="snapshot-description" className="text-right">
                Description
              </Label>
              <Textarea
                id="snapshot-description"
                value={snapshotDescription}
                onChange={(e) => setSnapshotDescription(e.target.value)}
                placeholder="Optional description of this schema snapshot"
                className="col-span-3"
                rows={3}
              />
            </div>
            <div className="text-sm text-muted-foreground col-span-4">
              <p><strong>Note:</strong> This snapshot will be saved and you'll be redirected to the Snapshots tab.</p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowSnapshotDialog(false)}
              disabled={savingSnapshot}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveSnapshot}
              disabled={savingSnapshot || !snapshotName.trim()}
            >
              {savingSnapshot ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Snapshot
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmationDialog
        open={showDeleteSnapshotDialog}
        onOpenChange={(open) => {
          setShowDeleteSnapshotDialog(open)
          if (!open) {
            setSnapshotToDelete(null)
          }
        }}
        title="Delete Snapshot"
        description={`Are you sure you want to delete "${snapshotToDelete?.name || 'this snapshot'}"? This action cannot be undone.`}
        onConfirm={handleDeleteSnapshotConfirm}
        confirmText="Delete"
        variant="destructive"
      />

      <ConfirmationDialog
        open={showClearMetadataDialog}
        onOpenChange={setShowClearMetadataDialog}
        title="Clear Schema Metadata"
        description="Are you sure you want to clear all schema metadata? This action cannot be undone."
        onConfirm={handleClearSchemaConfirm}
        confirmText="Clear"
        cancelText="Cancel"
        variant="destructive"
      />
    </div>
  )
}