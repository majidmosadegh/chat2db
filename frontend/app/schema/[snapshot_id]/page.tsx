"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useToast } from "@/lib/use-toast"
import { PageLoader, TableSkeleton } from "@/components/ui/loading"
import { EmptyTable } from "@/components/ui/empty-state"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  ArrowLeft,
  Search,
  Database,
  Table,
  Columns,
  Key,
  ArrowRight,
  Info,
  Calendar,
  Hash
} from "lucide-react"

interface ColumnInfo {
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
  row_count: number
  columns: ColumnInfo[]
}

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

interface TreeNode {
  id: string
  name: string
  type: 'schema' | 'table' | 'column'
  children?: TreeNode[]
  data?: any
  expanded?: boolean
}

interface SchemaSnapshot {
  id: number
  name: string
  description?: string
  connection_id: number
  created_at: string
}

interface SnapshotData {
  snapshot: SchemaSnapshot
  schema_data: TableInfo[]
  total_tables: number
}

export default function SchemaSnapshotViewPage() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const [snapshotData, setSnapshotData] = useState<SnapshotData | null>(null)
  const [schemaData, setSchemaData] = useState<SchemaInfo[]>([])
  const [tableData, setTableData] = useState<TableInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null)
  const [treeData, setTreeData] = useState<TreeNode[]>([])

  const snapshotId = params.snapshot_id as string

  useEffect(() => {
    fetchSnapshotData()
  }, [snapshotId])

  useEffect(() => {
    if (schemaData.length > 0) {
      buildTreeData()
    }
  }, [schemaData, searchTerm])

  const fetchSnapshotData = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/schema/snapshots/${snapshotId}/data`)

      if (response.ok) {
        const data: SnapshotData = await response.json()
        setSnapshotData(data)

        // Convert table-based data to column-based data for frontend display
        const columnBasedData: SchemaInfo[] = []

        if (data.schema_data) {
          data.schema_data.forEach((table: TableInfo) => {
            table.columns.forEach((column: ColumnInfo) => {
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

        setSchemaData(columnBasedData)
        setTableData(data.schema_data)
      } else {
        const error = await response.json()
        toast({
          title: "Error",
          description: `Failed to load snapshot: ${error.detail}`,
          variant: "destructive",
        })
        router.push("/schema")
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load snapshot data",
        variant: "destructive",
      })
      router.push("/schema")
    } finally {
      setLoading(false)
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
            <ArrowRight className={`h-4 w-4 mr-1 transform transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
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
    return <PageLoader message="Loading snapshot data..." />
  }

  if (!snapshotData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={() => router.push("/schema")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Schema Explorer
          </Button>
        </div>
        <EmptyTable
          icon={Info}
          title="Snapshot not found"
          description="The requested schema snapshot could not be found or has been deleted."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-4 mb-2">
            <Button variant="outline" onClick={() => router.push("/schema")}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Schema Explorer
            </Button>
          </div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Database className="h-8 w-8 text-blue-600" />
            {snapshotData.snapshot.name}
          </h1>
          <div className="flex items-center gap-4 mt-2 text-muted-foreground">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>Created: {new Date(snapshotData.snapshot.created_at).toLocaleDateString()}</span>
            </div>
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4" />
              <span>{snapshotData.total_tables} tables</span>
            </div>
          </div>
          {snapshotData.snapshot.description && (
            <p className="text-muted-foreground mt-2">
              {snapshotData.snapshot.description}
            </p>
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
                      : "No schema data available in this snapshot"
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
                  icon={Database}
                  title={searchTerm ? "No search results" : "No schema data"}
                  description={searchTerm
                    ? "No items match your search criteria. Try different keywords."
                    : "No schema data available in this snapshot."
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
                        <div className="text-sm font-medium text-muted-foreground">Row Count</div>
                        <div>
                          {tableData.find(t =>
                            t.schema_name === selectedNode.data.schema_name &&
                            t.table_name === selectedNode.data.table_name
                          )?.row_count || 0} rows
                        </div>
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
    </div>
  )
}






