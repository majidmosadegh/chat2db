"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Plus, Edit, Trash2, CheckCircle, TestTube, Database as DatabaseIcon, Loader2 } from "lucide-react"
import { useToast } from "@/lib/use-toast"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { PageLoader } from "@/components/ui/loading"
import { EmptyTable } from "@/components/ui/empty-state"

interface DatabaseConnection {
  id: number
  db_type: string
  host: string
  port: number
  username: string
  database_name: string
  is_active: boolean
}

const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "sqlserver", label: "SQL Server" },
]

const DEFAULT_PORTS = {
  postgresql: 5432,
  mysql: 3306,
  sqlserver: 1433,
}

export default function DatabasePage() {
  const { toast } = useToast()
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingConnection, setEditingConnection] = useState<DatabaseConnection | null>(null)
  const [testingConnection, setTestingConnection] = useState<number | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [connectionToDelete, setConnectionToDelete] = useState<DatabaseConnection | null>(null)
  const [formData, setFormData] = useState({
    db_type: "",
    host: "",
    port: 5432,
    username: "",
    password: "",
    database_name: "",
  })
  const [formErrors, setFormErrors] = useState<{
    db_type?: string
    host?: string
    port?: string
    username?: string
    password?: string
    database_name?: string
  }>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchConnections()
  }, [])

  const fetchConnections = async () => {
    try {
      const response = await fetch("/api/database")
      if (response.ok) {
        const data = await response.json()
        setConnections(data)
      }
    } catch (error) {
    } finally {
      setLoading(false)
    }
  }

  const validateForm = (): typeof formErrors => {
    const errors: typeof formErrors = {}
    
    if (!formData.db_type.trim()) {
      errors.db_type = "Database type is required"
    }
    if (!formData.host.trim()) {
      errors.host = "Host is required"
    }
    if (!formData.port || formData.port < 1 || formData.port > 65535) {
      errors.port = "Port must be between 1 and 65535"
    }
    if (!formData.username.trim()) {
      errors.username = "Username is required"
    }
    if (!editingConnection && !formData.password.trim()) {
      errors.password = "Password is required"
    }
    if (!formData.database_name.trim()) {
      errors.database_name = "Database name is required"
    }
    
    return errors
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const errors = validateForm()
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields",
        variant: "destructive",
      })
      return
    }

    setFormErrors({})
    setSubmitting(true)

    try {
      const url = editingConnection
        ? `/api/database/${editingConnection.id}`
        : "/api/database"
      const method = editingConnection ? "PUT" : "POST"

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      })

      if (response.ok) {
        await fetchConnections()
        setShowForm(false)
        setEditingConnection(null)
        resetForm()
        toast({
          title: "Success",
          description: editingConnection ? "Connection updated successfully" : "Connection created successfully",
        })
      } else {
        const errorData = await response.json()
        toast({
          title: "Error",
          description: errorData.detail || "Failed to save connection",
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save connection",
        variant: "destructive",
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleEdit = (connection: DatabaseConnection) => {
    setEditingConnection(connection)
    setFormData({
      db_type: connection.db_type,
      host: connection.host,
      port: connection.port,
      username: connection.username,
      password: "", // Don't populate password for security
      database_name: connection.database_name,
    })
    setShowForm(true)
  }

  const handleDeleteClick = (connection: DatabaseConnection) => {
    setConnectionToDelete(connection)
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!connectionToDelete) return

    try {
      const response = await fetch(`/api/database/${connectionToDelete.id}`, {
        method: "DELETE",
      })

      if (response.ok) {
        await fetchConnections()
        toast({
          title: "Success",
          description: "Database connection deleted successfully",
          variant: "success",
        })
      } else {
        const errorData = await response.json()
        toast({
          title: "Error",
          description: errorData.detail || "Failed to delete database connection",
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete database connection. Please try again.",
        variant: "destructive",
      })
    } finally {
      setShowDeleteDialog(false)
      setConnectionToDelete(null)
    }
  }

  const handleActivate = async (connectionId: number) => {
    try {
      const response = await fetch(`/api/database/${connectionId}/activate`, {
        method: "POST",
      })

      if (response.ok) {
        await fetchConnections()
      }
    } catch (error) {
    }
  }

  const handleTestConnection = async (connectionData: typeof formData) => {
    setTestingConnection(editingConnection?.id || -1)

    try {
      const response = await fetch("/api/database/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(connectionData),
      })

      const result = await response.json()

      if (result.success) {
        toast({
          title: "Connection Successful",
          description: "Database connection test passed!",
          variant: "success",
        })
      } else {
        toast({
          title: "Connection Failed",
          description: result.message || "Database connection test failed",
          variant: "destructive",
        })
      }
    } catch (error) {
      toast({
        title: "Connection Test Failed",
        description: "Failed to test database connection. Please check your settings.",
        variant: "destructive",
      })
    } finally {
      setTestingConnection(null)
    }
  }

  const handleDbTypeChange = (dbType: string) => {
    setFormData({
      ...formData,
      db_type: dbType,
      port: DEFAULT_PORTS[dbType as keyof typeof DEFAULT_PORTS] || 5432,
    })
  }

  const resetForm = () => {
    setFormData({
      db_type: "",
      host: "",
      port: 5432,
      username: "",
      password: "",
      database_name: "",
    })
    setFormErrors({})
  }

  const cancelEdit = () => {
    setShowForm(false)
    setEditingConnection(null)
    resetForm()
    setFormErrors({})
  }

  if (loading) {
    return <PageLoader message="Loading database connections..." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Database Connection</h1>
          <p className="text-muted-foreground">
            Configure read-only database connections for schema introspection
          </p>
        </div>
        <Button onClick={() => setShowForm(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Add Connection
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingConnection ? "Edit Connection" : "Add New Connection"}</CardTitle>
            <CardDescription>
              Configure database connection settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="db_type">Database Type</Label>
                  <Select value={formData.db_type} onValueChange={handleDbTypeChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select database type" />
                    </SelectTrigger>
                    <SelectContent>
                      {DB_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.db_type && (
                  <p className="text-sm text-destructive">{formErrors.db_type}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="host">Host *</Label>
                <Input
                  id="host"
                  value={formData.host}
                  onChange={(e) => {
                    setFormData({ ...formData, host: e.target.value })
                    if (formErrors.host) {
                      setFormErrors(prev => ({ ...prev, host: undefined }))
                    }
                  }}
                  placeholder="localhost"
                  className={formErrors.host ? "border-destructive" : ""}
                />
                {formErrors.host && (
                  <p className="text-sm text-destructive">{formErrors.host}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="port">Port *</Label>
                <Input
                  id="port"
                  type="number"
                  value={formData.port}
                  onChange={(e) => {
                    setFormData({ ...formData, port: parseInt(e.target.value) || 0 })
                    if (formErrors.port) {
                      setFormErrors(prev => ({ ...prev, port: undefined }))
                    }
                  }}
                  className={formErrors.port ? "border-destructive" : ""}
                />
                {formErrors.port && (
                  <p className="text-sm text-destructive">{formErrors.port}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="database_name">Database Name *</Label>
                <Input
                  id="database_name"
                  value={formData.database_name}
                  onChange={(e) => {
                    setFormData({ ...formData, database_name: e.target.value })
                    if (formErrors.database_name) {
                      setFormErrors(prev => ({ ...prev, database_name: undefined }))
                    }
                  }}
                  className={formErrors.database_name ? "border-destructive" : ""}
                />
                {formErrors.database_name && (
                  <p className="text-sm text-destructive">{formErrors.database_name}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="username">Username *</Label>
                <Input
                  id="username"
                  value={formData.username}
                  onChange={(e) => {
                    setFormData({ ...formData, username: e.target.value })
                    if (formErrors.username) {
                      setFormErrors(prev => ({ ...prev, username: undefined }))
                    }
                  }}
                  className={formErrors.username ? "border-destructive" : ""}
                />
                {formErrors.username && (
                  <p className="text-sm text-destructive">{formErrors.username}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password {!editingConnection && "*"}</Label>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => {
                    setFormData({ ...formData, password: e.target.value })
                    if (formErrors.password) {
                      setFormErrors(prev => ({ ...prev, password: undefined }))
                    }
                  }}
                  className={formErrors.password ? "border-destructive" : ""}
                />
                {formErrors.password && (
                  <p className="text-sm text-destructive">{formErrors.password}</p>
                )}
              </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={submitting}>
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editingConnection ? "Updating..." : "Adding..."}
                    </>
                  ) : (
                    editingConnection ? "Update Connection" : "Add Connection"
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleTestConnection(formData)}
                  disabled={testingConnection === (editingConnection?.id || -1)}
                >
                  <TestTube className="mr-2 h-4 w-4" />
                  {testingConnection === (editingConnection?.id || -1) ? "Testing..." : "Test Connection"}
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
          <CardTitle>Database Connections</CardTitle>
          <CardDescription>
            Manage your database connections. Only one connection can be active at a time.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {connections.length === 0 ? (
            <EmptyTable
              icon={DatabaseIcon}
              title="No database connections"
              description="Configure your first database connection to start exploring schemas. Connect to PostgreSQL, MySQL, or SQL Server."
              action={{
                label: "Add Your First Connection",
                onClick: () => setShowForm(true)
              }}
            />
          ) : (
            <div>
              <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Host</TableHead>
                  <TableHead>Database</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                  {connections.map((connection) => (
                    <TableRow key={connection.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <DatabaseIcon className="h-4 w-4 shrink-0" />
                          <span className="break-words">{connection.db_type}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm break-words">
                        {connection.host}:{connection.port}
                      </TableCell>
                      <TableCell className="font-medium break-words">{connection.database_name}</TableCell>
                      <TableCell className="break-words">{connection.username}</TableCell>
                      <TableCell>
                        {connection.is_active ? (
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
                          {!connection.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleActivate(connection.id)}
                              className="text-xs px-2 py-1 h-7"
                            >
                              <span className="hidden sm:inline">Activate</span>
                              <span className="sm:hidden">✓</span>
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(connection)}
                            className="text-xs px-2 py-1 h-7"
                            aria-label={`Edit connection ${connection.database_name || connection.host}`}
                            title={`Edit connection`}
                          >
                            <Edit className="h-3 w-3" aria-hidden="true" />
                          </Button>
                          {!connection.is_active && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteClick(connection)}
                              className="text-xs px-2 py-1 h-7"
                              aria-label={`Delete connection ${connection.database_name || connection.host}`}
                              title={`Delete connection`}
                            >
                              <Trash2 className="h-3 w-3" aria-hidden="true" />
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
        title="Delete Database Connection"
        description="Are you sure you want to delete this database connection? This action cannot be undone."
        onConfirm={handleDeleteConfirm}
        confirmText="Delete Connection"
        cancelText="Cancel"
        variant="destructive"
      />
    </div>
  )
}
