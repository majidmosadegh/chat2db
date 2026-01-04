"use client"

import React, { useState, useRef, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Database,
  Key,
  ArrowRight,
  Edit,
  Trash2,
  Check,
  X
} from "lucide-react"

interface TableNode {
  id: string
  schema_name: string
  table_name: string
  row_count: number
  columns: Array<{
    name: string
    type: string
    is_primary_key: boolean
    is_foreign_key: boolean
  }>
  x: number
  y: number
}

interface Relationship {
  id: number
  schema_snapshot_id: number
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship_type: "db_fk" | "ai_suggested" | "user_defined"
  join_type: "inner" | "left" | "right"
  cardinality: "1-1" | "1-n" | "n-1" | "n-n"
  description: string
  confidence_score?: number
  strength_score?: number
  semantic_similarity?: number
  user_accepted: boolean
  agent_approved: boolean
  is_confirmed: boolean
  created_at: string
  updated_at: string
}

interface RelationshipEdge {
  id: string
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship: Relationship
  sourceNode: TableNode
  targetNode: TableNode
  // Edge bundling properties
  _bundleLayer?: number
  _bundlePosition?: number
  _bundleOffset?: number
  _positionOffset?: number
}

interface RelationshipCanvasProps {
  tableNodes: TableNode[]
  relationships: Relationship[]
  onEditRelationship?: (relationship: Relationship) => void
  onDeleteRelationship?: (relationshipId: number) => void
  onAcceptRelationship?: (relationship: Relationship) => void
  onCreateRelationship?: (sourceTable: string, sourceColumn: string, targetTable: string, targetColumn: string) => void
  onOpenCreateRelationshipModal?: (sourceTable: string, sourceColumn: string) => void
  onTableMove?: (tableId: string, newX: number, newY: number) => void
  resetTrigger?: number
  zoomLevel?: number
  isFullscreen?: boolean
  cleanMode?: boolean
  advancedMode?: boolean
  onRelationshipClick?: (relationship: Relationship) => void
  autoFitTrigger?: number
}

const TABLE_WIDTH = 200
const TABLE_HEIGHT = 250
const COLUMN_HEIGHT = 20
const MAX_VISIBLE_COLUMNS_DEFAULT = 10
const MAX_VISIBLE_COLUMNS_EXPANDED = Infinity

export function RelationshipCanvas({
  tableNodes,
  relationships,
  onEditRelationship,
  onDeleteRelationship,
  onAcceptRelationship,
  onCreateRelationship,
  onOpenCreateRelationshipModal,
  onTableMove,
  resetTrigger = 0,
  zoomLevel = 1,
  isFullscreen = false,
  cleanMode = true,
  advancedMode = false,
  onRelationshipClick,
  autoFitTrigger = 0
}: RelationshipCanvasProps) {
  // No auto-expansion - tables start collapsed by default

  const [selectedRelationship, setSelectedRelationship] = useState<Relationship | null>(null)
  const [hoveredColumn, setHoveredColumn] = useState<{
    tableId: string
    columnName: string
  } | null>(null)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
  const [draggingTable, setDraggingTable] = useState<{
    tableId: string
    startX: number
    startY: number
    offsetX: number
    offsetY: number
  } | null>(null)
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState<{x: number, y: number} | null>(null)
  const [viewBoxOffset, setViewBoxOffset] = useState<{x: number, y: number}>({x: 0, y: 0})
  const [isSpacePressed, setIsSpacePressed] = useState(false)
  const [viewportSize, setViewportSize] = useState({ width: 1400, height: 1000 })
  const svgRef = useRef<SVGSVGElement>(null)

  // Helper functions for edge management
  const avoidEdgeConflicts = (detour: {x: number, y: number}, start: {x: number, y: number}, end: {x: number, y: number}, otherEdges: RelationshipEdge[]) => {
    let adjustedDetour = { ...detour }
    let conflictFound = true
    let attempts = 0
    const maxAttempts = 8

    while (conflictFound && attempts < maxAttempts) {
      conflictFound = false

      for (const edge of otherEdges) {
        // Calculate edge midpoint
        const edgeStartX = edge.sourceNode.x + TABLE_WIDTH - 5
        const edgeEndX = edge.targetNode.x + 5
        const edgeMidX = (edgeStartX + edgeEndX) / 2

        const sourceColIndex = edge.sourceNode.columns.findIndex(c => c.name === edge.source_column)
        const targetColIndex = edge.targetNode.columns.findIndex(c => c.name === edge.target_column)
        const sourceScrollOffset = getTableScrollOffset(edge.sourceNode.id)
        const targetScrollOffset = getTableScrollOffset(edge.targetNode.id)

        const sourceMaxVisible = getMaxVisibleColumns(edge.sourceNode.id)
        const targetMaxVisible = getMaxVisibleColumns(edge.targetNode.id)
        const sourceVisible = sourceColIndex >= sourceScrollOffset && sourceColIndex <= sourceScrollOffset + sourceMaxVisible - 1
        const targetVisible = targetColIndex >= targetScrollOffset && targetColIndex <= targetScrollOffset + targetMaxVisible - 1

        // Calculate dynamic height for source and target tables
        const sourceVisibleCount = Math.min(edge.sourceNode.columns.length, sourceMaxVisible)
        const targetVisibleCount = Math.min(edge.targetNode.columns.length, targetMaxVisible)

        const sourceHeaderHeight = 35
        const sourceFooterHeight = edge.sourceNode.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0
        const sourceContentHeight = sourceVisibleCount * COLUMN_HEIGHT + 10
        const sourceDynamicHeight = sourceHeaderHeight + sourceContentHeight + sourceFooterHeight

        const targetHeaderHeight = 35
        const targetFooterHeight = edge.targetNode.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0
        const targetContentHeight = targetVisibleCount * COLUMN_HEIGHT + 10
        const targetDynamicHeight = targetHeaderHeight + targetContentHeight + targetFooterHeight

        let edgeStartY = edge.sourceNode.y + sourceDynamicHeight / 2
        let edgeEndY = edge.targetNode.y + targetDynamicHeight / 2

        if (sourceVisible) {
          const visibleIndex = sourceColIndex - sourceScrollOffset
          edgeStartY = edge.sourceNode.y + 40 + (visibleIndex * COLUMN_HEIGHT) + (COLUMN_HEIGHT / 2)
        }
        if (targetVisible) {
          const visibleIndex = targetColIndex - targetScrollOffset
          edgeEndY = edge.targetNode.y + 40 + (visibleIndex * COLUMN_HEIGHT) + (COLUMN_HEIGHT / 2)
        }

        const edgeMidY = (edgeStartY + edgeEndY) / 2

        // Check distance from detour point to edge path
        const distance = Math.sqrt(
          Math.pow(adjustedDetour.x - edgeMidX, 2) +
          Math.pow(adjustedDetour.y - edgeMidY, 2)
        )

        if (distance < 100) { // Too close to another edge
          // Adjust detour point perpendicular to the line between start and end
          const lineAngle = Math.atan2(end.y - start.y, end.x - start.x)
          const perpendicularAngle = lineAngle + Math.PI / 2

          adjustedDetour.x += Math.cos(perpendicularAngle) * 50
          adjustedDetour.y += Math.sin(perpendicularAngle) * 50
          conflictFound = true
          break
        }
      }

      attempts++
    }

    return adjustedDetour
  }

  const calculateSmartRouting = (start: {x: number, y: number}, end: {x: number, y: number}, currentEdge: RelationshipEdge) => {
    // Get bundle information
    const bundleLayer = (currentEdge as any)._bundleLayer || 0
    const bundlePosition = (currentEdge as any)._bundlePosition || 0

    // Create edges array to check for overlaps (excluding current edge)
    const allEdges = edges.filter(e => e.id !== currentEdge.id)

    // Hierarchical routing based on bundle layer
    const layerOffset = bundleLayer * 80 // Vertical separation between layers
    const positionSpread = bundlePosition * 25 // Horizontal spread within layer

    // If tables are far apart horizontally, use direct layered connection
    if (Math.abs(end.x - start.x) > 400) {
      const midX = (start.x + end.x) / 2 + positionSpread
      const controlOffset = Math.abs(end.y - start.y) * 0.4

      return {
        start,
        end,
        controlPoints: [
          {x: start.x + controlOffset + positionSpread, y: start.y + layerOffset},
          {x: end.x - controlOffset + positionSpread, y: end.y + layerOffset}
        ],
        path: `M ${start.x} ${start.y} C ${start.x + controlOffset + positionSpread} ${start.y + layerOffset} ${end.x - controlOffset + positionSpread} ${end.y + layerOffset} ${end.x} ${end.y}`
      }
    }

    // For closer tables, use hierarchical routing with detour points
    const midY = (start.y + end.y) / 2 + layerOffset
    const baseOffsetY = Math.abs(end.x - start.x) * 0.3

    // Determine direction based on table positions
    const sourceCenterX = currentEdge.sourceNode.x + TABLE_WIDTH / 2
    const targetCenterX = currentEdge.targetNode.x + TABLE_WIDTH / 2

    let detourPoint: {x: number, y: number}

    if (sourceCenterX < targetCenterX) {
      // Source is left of target
      detourPoint = {
        x: Math.min(start.x, end.x) - 120 - bundleLayer * 30,
        y: midY + (start.y < end.y ? baseOffsetY : -baseOffsetY) + positionSpread
      }
    } else {
      // Source is right of target
      detourPoint = {
        x: Math.max(start.x, end.x) + 120 + bundleLayer * 30,
        y: midY + (start.y < end.y ? baseOffsetY : -baseOffsetY) + positionSpread
      }
    }

    // Check for conflicts with other edges and adjust
    const adjustedDetour = avoidEdgeConflicts(detourPoint, start, end, allEdges)

    // Create smooth curved path with hierarchical offset
    const path = `M ${start.x} ${start.y} Q ${(start.x + adjustedDetour.x) / 2} ${(start.y + adjustedDetour.y) / 2 + layerOffset} ${adjustedDetour.x} ${adjustedDetour.y} Q ${(end.x + adjustedDetour.x) / 2 + positionSpread} ${(end.y + adjustedDetour.y) / 2 + layerOffset} ${end.x} ${end.y}`

    return {
      start,
      end,
      controlPoints: [
        {x: (start.x + adjustedDetour.x) / 2, y: (start.y + adjustedDetour.y) / 2 + layerOffset},
        {x: (end.x + adjustedDetour.x) / 2 + positionSpread, y: (end.y + adjustedDetour.y) / 2 + layerOffset}
      ],
      path
    }
  }

  const applyEdgeBundling = (edgesInGroup: RelationshipEdge[]): RelationshipEdge[] => {
    // Advanced edge bundling with hierarchical routing
    const bundledEdges: RelationshipEdge[] = []

    // Sort edges to ensure consistent ordering
    const sortedEdges = edgesInGroup.sort((a, b) => a.relationship.id - b.relationship.id)

    sortedEdges.forEach((edge, index) => {
      // Create multiple routing layers to avoid overlaps
      const layer = Math.floor(index / 3) // 3 edges per layer
      const positionInLayer = index % 3

      // Calculate offset based on layer and position
      const layerOffset = layer * 60 // Vertical separation between layers
      const positionOffset = (positionInLayer - 1) * 20 // Horizontal spread within layer

      // Create a modified edge with hierarchical routing
      const bundledEdge: RelationshipEdge = {
        ...edge,
        id: `${edge.id}-bundled-l${layer}-p${positionInLayer}`,
        _bundleLayer: layer,
        _bundlePosition: positionInLayer,
        _bundleOffset: layerOffset,
        _positionOffset: positionOffset
      }

      bundledEdges.push(bundledEdge)
    })

    return bundledEdges
  }

  // Handle keyboard events for space key - only in fullscreen
  useEffect(() => {
    // فقط در fullscreen فعال است
    if (!isFullscreen) {
      setIsSpacePressed(false)
      setIsPanning(false)
      setPanStart(null)
      return
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault()
        setIsSpacePressed(true)
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        setIsSpacePressed(false)
        setIsPanning(false)
        setPanStart(null)
      }
    }

    const handleMouseDown = (e: MouseEvent) => {
      if (isSpacePressed && svgRef.current && !draggingTable) {
        e.preventDefault()
        setIsPanning(true)
        setPanStart({x: e.clientX, y: e.clientY})
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('keyup', handleKeyUp)
    document.addEventListener('mousedown', handleMouseDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('keyup', handleKeyUp)
      document.removeEventListener('mousedown', handleMouseDown)
    }
  }, [isSpacePressed, draggingTable, isFullscreen])

  // Reset view when resetTrigger changes
  useEffect(() => {
    setViewBoxOffset({x: 0, y: 0})
  }, [resetTrigger])

  // Store base viewport size (without zoom)
  const [baseViewportSize, setBaseViewportSize] = useState({ width: 1400, height: 1000 })
  
  // Update base viewport size when fullscreen changes
  useEffect(() => {
    if (isFullscreen && svgRef.current) {
      const updateBaseSize = () => {
        if (svgRef.current) {
          const rect = svgRef.current.getBoundingClientRect()
          const baseWidth = rect.width || window.innerWidth - 40
          const baseHeight = rect.height || window.innerHeight - 100
          
          // فقط اگر baseViewportSize تغییر کرده باشد، به‌روزرسانی می‌کنیم
          setBaseViewportSize(prev => {
            if (Math.abs(prev.width - baseWidth) > 1 || Math.abs(prev.height - baseHeight) > 1) {
              // viewportSize برای viewBox باید با zoom تطبیق داده شود
              setViewportSize({ 
                width: baseWidth / zoomLevel, 
                height: baseHeight / zoomLevel 
              })
              return { width: baseWidth, height: baseHeight }
            }
            return prev
          })
        }
      }
      
      const timeoutId = setTimeout(updateBaseSize, 100)
      updateBaseSize()
      window.addEventListener('resize', updateBaseSize)
      
      return () => {
        clearTimeout(timeoutId)
        window.removeEventListener('resize', updateBaseSize)
      }
    } else {
      setBaseViewportSize({ width: 1400, height: 1000 })
      setViewportSize({ width: 1400, height: 1000 })
    }
  }, [isFullscreen, zoomLevel])

  // Handle auto-fit trigger from parent component
  useEffect(() => {
    if (autoFitTrigger > 0 && tableNodes.length > 0) {
      const minX = Math.min(...tableNodes.map(n => n.x))
      const minY = Math.min(...tableNodes.map(n => n.y))
      const maxX = Math.max(...tableNodes.map(n => n.x + TABLE_WIDTH))
      // Calculate maxY considering expanded tables
      const maxY = Math.max(...tableNodes.map(n => {
        const isExpanded = expandedTables.has(n.id)
        const visibleColumns = isExpanded ? n.columns.length : Math.min(n.columns.length, MAX_VISIBLE_COLUMNS_DEFAULT)
        const tableHeight = 35 + visibleColumns * COLUMN_HEIGHT + (n.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0)
        return n.y + tableHeight
      }))

      // Center the content in the current viewport
      const contentCenterX = (minX + maxX) / 2
      const contentCenterY = (minY + maxY) / 2
      const viewportCenterX = 700 // 1400/2
      const viewportCenterY = 500 // 1000/2

      const offsetX = viewportCenterX - contentCenterX
      const offsetY = viewportCenterY - contentCenterY

      setViewBoxOffset({ x: offsetX, y: offsetY })
    }
  }, [autoFitTrigger, tableNodes, expandedTables])


  // Auto-fit viewBox when fullscreen changes (only if no manual fit triggered)
  useEffect(() => {
    if (tableNodes.length > 0 && isFullscreen && autoFitTrigger === 0 && svgRef.current) {
      // Only apply fullscreen auto-fit if no manual fit has been triggered
      const minX = Math.min(...tableNodes.map(n => n.x))
      const minY = Math.min(...tableNodes.map(n => n.y))
      const maxX = Math.max(...tableNodes.map(n => n.x + TABLE_WIDTH))
      // Calculate maxY considering expanded tables
      const maxY = Math.max(...tableNodes.map(n => {
        const isExpanded = expandedTables.has(n.id)
        const visibleColumns = isExpanded ? n.columns.length : Math.min(n.columns.length, MAX_VISIBLE_COLUMNS_DEFAULT)
        const tableHeight = 35 + visibleColumns * COLUMN_HEIGHT + (n.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0)
        return n.y + tableHeight
      }))

      // Get actual viewport dimensions (base size before zoom)
      const rect = svgRef.current.getBoundingClientRect()
      const baseWidth = rect.width || baseViewportSize.width
      const baseHeight = rect.height || baseViewportSize.height
      
      // محاسبه viewport برای viewBox (با zoom تطبیق داده شده)
      const viewportWidth = baseWidth / zoomLevel
      const viewportHeight = baseHeight / zoomLevel

      // Center the content in viewport
      const contentCenterX = (minX + maxX) / 2
      const contentCenterY = (minY + maxY) / 2
      const viewportCenterX = viewportWidth / 2
      const viewportCenterY = viewportHeight / 2

      // به‌روزرسانی viewportSize برای viewBox
      // استفاده از functional update برای جلوگیری از dependency issue
      setViewportSize(prev => {
        const newViewportSize = {
          width: viewportWidth,
          height: viewportHeight
        }
        
        // فقط اگر تغییر معنی‌داری داشته باشد (بیش از 1 پیکسل)، به‌روزرسانی می‌کنیم
        const hasSignificantChange = 
          Math.abs(prev.width - newViewportSize.width) > 1 || 
          Math.abs(prev.height - newViewportSize.height) > 1
        
        return hasSignificantChange ? newViewportSize : prev
      })

      setViewBoxOffset({
        x: viewportCenterX - contentCenterX,
        y: viewportCenterY - contentCenterY
      })
    } else if (!isFullscreen) {
      // Reset when exiting fullscreen
      setViewBoxOffset({x: 0, y: 0})
    }
  }, [isFullscreen, tableNodes.length, autoFitTrigger, expandedTables, baseViewportSize, zoomLevel])

  // Tables start collapsed by default - no auto-expansion


  const handleMouseMove = (e: React.MouseEvent) => {
    // Handle panning with space + mouse - only in fullscreen
    if (isPanning && panStart && svgRef.current && isFullscreen) {
      const deltaX = e.clientX - panStart.x
      const deltaY = e.clientY - panStart.y

      // اصلاح جهت: وقتی ماوس به راست می‌رود، محتوا باید به راست برود
      setViewBoxOffset(prev => ({
        x: prev.x + deltaX / zoomLevel,
        y: prev.y + deltaY / zoomLevel
      }))

      setPanStart({x: e.clientX, y: e.clientY})
      return
    }

    if (draggingTable && svgRef.current && onTableMove) {
      const rect = svgRef.current.getBoundingClientRect()
      
      // محاسبه موقعیت ماوس در سیستم مختصات SVG (با در نظر گیری zoom و viewBoxOffset)
      // وقتی zoom out می‌کنیم، باید zoom level را در محاسبات در نظر بگیریم
      let currentX = (e.clientX - rect.left) / zoomLevel
      let currentY = (e.clientY - rect.top) / zoomLevel
      
      // اضافه کردن viewBoxOffset برای بدست آوردن موقعیت واقعی در viewBox
      currentX = currentX + viewBoxOffset.x
      currentY = currentY + viewBoxOffset.y

      // محاسبه موقعیت جدید جدول
      let newX = currentX - draggingTable.offsetX
      let newY = currentY - draggingTable.offsetY

      // محدود کردن حرکت به محدوده منطقی
      // در fullscreen، نباید محدودیت سخت داشته باشیم - جدول‌ها باید آزادانه حرکت کنند
      if (isFullscreen) {
        // در fullscreen، محدودیت‌ها را خیلی زیاد می‌کنیم تا جدول‌ها آزادانه حرکت کنند
        // فقط از مقادیر منفی خیلی زیاد جلوگیری می‌کنیم
        const minBound = -1000 // اجازه حرکت به بالا
        const maxBound = 10000 // حد بالا (خیلی زیاد)
        newX = Math.max(minBound, Math.min(newX, maxBound))
        newY = Math.max(minBound, Math.min(newY, maxBound))
      } else {
        // در حالت عادی، باید zoom را در نظر بگیریم
        const effectiveWidth = 1400 / zoomLevel
        const effectiveHeight = 1000 / zoomLevel
        const maxX = effectiveWidth - TABLE_WIDTH + 50
        const maxY = effectiveHeight - TABLE_HEIGHT + 50
        newX = Math.max(-50, Math.min(newX, maxX))
        newY = Math.max(-50, Math.min(newY, maxY))
      }

      onTableMove(draggingTable.tableId, newX, newY)
    }

  }

  const handleTableMouseDown = (e: React.MouseEvent, tableId: string, tableX: number, tableY: number) => {
    // در fullscreen، اگر space فشرده شده باشد، drag غیرفعال است
    if (!onTableMove || !svgRef.current || (isFullscreen && isSpacePressed)) return

    const rect = svgRef.current.getBoundingClientRect()
    // محاسبه موقعیت ماوس با در نظر گیری zoom level
    let mouseX = (e.clientX - rect.left) / zoomLevel
    let mouseY = (e.clientY - rect.top) / zoomLevel
    
    // اضافه کردن viewBoxOffset برای بدست آوردن موقعیت واقعی
    mouseX = mouseX + viewBoxOffset.x
    mouseY = mouseY + viewBoxOffset.y

    setDraggingTable({
      tableId,
      startX: mouseX,
      startY: mouseY,
      offsetX: mouseX - tableX,
      offsetY: mouseY - tableY
    })

    e.preventDefault()
    e.stopPropagation()
  }

  const handleMouseUp = (e: React.MouseEvent) => {
    if (isPanning) {
      setIsPanning(false)
      setPanStart(null)
      return
    }

    if (draggingTable) {
      setDraggingTable(null)
      return
    }

  }

  // Create edges from relationships with edge bundling
  const rawEdges: RelationshipEdge[] = relationships.map(rel => {
    const sourceNode = tableNodes.find(n => n.id === rel.source_table)
    const targetNode = tableNodes.find(n => n.id === rel.target_table)

    if (!sourceNode || !targetNode) {
      return null
    }

    // Check if columns exist
    const sourceColExists = sourceNode.columns.some(c => c.name === rel.source_column)
    const targetColExists = targetNode.columns.some(c => c.name === rel.target_column)

    if (!sourceColExists || !targetColExists) {
      return null
    }

    return {
      id: `edge-${rel.id}`,
      source_table: rel.source_table,
      source_column: rel.source_column,
      target_table: rel.target_table,
      target_column: rel.target_column,
      relationship: rel,
      sourceNode,
      targetNode
    }
  }).filter(Boolean) as RelationshipEdge[]

  // Apply relationship selection logic based on display mode
  let selectedEdges = rawEdges

  if (cleanMode && !advancedMode) {
    // Clean mode: Keep only highest-ranked relationship per table pair
    const pairGroups: {[key: string]: RelationshipEdge[]} = {}

    rawEdges.forEach(edge => {
      const pairKey = `${edge.source_table}-${edge.target_table}`
      if (!pairGroups[pairKey]) {
        pairGroups[pairKey] = []
      }
      pairGroups[pairKey].push(edge)
    })

    selectedEdges = []
    Object.values(pairGroups).forEach(group => {
      if (group.length === 1) {
        selectedEdges.push(group[0])
      } else {
        // Sort by strength score and pick the highest
        const sorted = group.sort((a, b) =>
          (b.relationship.strength_score || 0) - (a.relationship.strength_score || 0)
        )
        selectedEdges.push(sorted[0])
      }
    })
  }

  // Group edges by source-target table pairs and apply bundling
  const edgeGroups = new Map<string, RelationshipEdge[]>()
  selectedEdges.forEach(edge => {
    const key = `${edge.source_table}-${edge.target_table}`
    if (!edgeGroups.has(key)) {
      edgeGroups.set(key, [])
    }
    edgeGroups.get(key)!.push(edge)
  })

  // Store group information for display
  const groupSizes = new Map<string, number>()
  edgeGroups.forEach((edges, key) => {
    groupSizes.set(key, edges.length)
  })

  // Apply bundling to each group
  const bundledEdges: RelationshipEdge[] = []
  edgeGroups.forEach((edgesInGroup, key) => {
    if (edgesInGroup.length === 1) {
      // Single edge, no bundling needed
      bundledEdges.push(edgesInGroup[0])
    } else if (advancedMode) {
      // Advanced mode: Show all edges but mark secondary ones
      const sorted = edgesInGroup.sort((a, b) =>
        (b.relationship.strength_score || 0) - (a.relationship.strength_score || 0)
      )

      sorted.forEach((edge, index) => {
        const markedEdge = {
          ...edge,
          _isSecondary: index > 0, // Mark non-primary edges
          _rankInGroup: index + 1
        }
        bundledEdges.push(markedEdge)
      })
    } else {
      // Clean mode: Apply bundling to reduce clutter
      const bundled = applyEdgeBundling(edgesInGroup)
      bundledEdges.push(...bundled)
    }
  })

  const edges = bundledEdges
  const getRelationshipColor = (type: string) => {
    switch (type) {
      case "schema_fk": return "#059669" // green - database foreign keys (دیتابیس داشته)
      case "ai_suggested": return "#3b82f6" // blue - AI suggestions (پیشنهاد AI بوده)
      case "manual": return "#f59e0b" // amber - user defined (کاربر اضافه کرده)
      default: return "#6b7280"
    }
  }

  const getRelationshipZIndex = (type: string) => {
    // Higher z-index for more important relationships
    switch (type) {
      case "db_fk": return 3 // Database constraints on top
      case "user_defined": return 2 // User defined relationships
      case "ai_suggested": return 1 // AI suggestions at bottom
      default: return 1
    }
  }

  const getRelationshipStrokeDashArray = (type: string) => {
    switch (type) {
      case "ai_suggested": return "8,4" // Dashed line for AI suggestions
      case "manual": return "none" // Solid line for user relationships
      case "schema_fk": return "none" // Solid line for database relationships
      default: return "none"
    }
  }

  const calculateEdgePoints = (edge: RelationshipEdge) => {
    const { sourceNode, targetNode, source_column, target_column } = edge

    if (!sourceNode || !targetNode) {
      return null
    }

    // Find column positions (no scrolling, direct index)
    const sourceColIndex = sourceNode.columns.findIndex(c => c.name === source_column)
    const targetColIndex = targetNode.columns.findIndex(c => c.name === target_column)

    if (sourceColIndex === -1 || targetColIndex === -1) {
      return null
    }

    // Calculate positions based on table expansion state
    const sourceIsExpanded = expandedTables.has(sourceNode.id)
    const targetIsExpanded = expandedTables.has(targetNode.id)

    let sourceY, targetY

    if (sourceIsExpanded) {
      // Table is expanded - connect to exact column center
      sourceY = sourceNode.y + 40 + (sourceColIndex * COLUMN_HEIGHT) + ((COLUMN_HEIGHT - 2) / 2)
    } else {
      // Table is collapsed - connect to table center
      const sourceDynamicHeight = 35 + Math.min(sourceNode.columns.length, MAX_VISIBLE_COLUMNS_DEFAULT) * COLUMN_HEIGHT + 10
      sourceY = sourceNode.y + sourceDynamicHeight / 2
    }

    if (targetIsExpanded) {
      // Table is expanded - connect to exact column center
      targetY = targetNode.y + 40 + (targetColIndex * COLUMN_HEIGHT) + ((COLUMN_HEIGHT - 2) / 2)
    } else {
      // Table is collapsed - connect to table center
      const targetDynamicHeight = 35 + Math.min(targetNode.columns.length, MAX_VISIBLE_COLUMNS_DEFAULT) * COLUMN_HEIGHT + 10
      targetY = targetNode.y + targetDynamicHeight / 2
    }

    // Adjust X positions based on table positions - connect to table edges with slight offset
    const sourceX = sourceNode.x + TABLE_WIDTH + 2 // Connect just outside right edge of source table
    const targetX = targetNode.x - 2 // Connect just outside left edge of target table

    let routing;

    // If both tables are collapsed, use simple straight line
    if (!sourceIsExpanded && !targetIsExpanded) {
      routing = {
        start: {x: sourceX, y: sourceY},
        end: {x: targetX, y: targetY},
        controlPoints: [],
        path: `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`
      }
    } else {
      // At least one table is expanded - use curved routing
      const midX = (sourceX + targetX) / 2
      const midY = (sourceY + targetY) / 2
      const curveOffset = Math.abs(targetX - sourceX) * 0.3 // Curve amount based on distance

      if (sourceNode.x < targetNode.x) {
        // Source is left of target - curve to the right
        routing = {
          start: {x: sourceX, y: sourceY},
          end: {x: targetX, y: targetY},
          controlPoints: [
            {x: midX + curveOffset, y: sourceY},
            {x: midX + curveOffset, y: targetY}
          ],
          path: `M ${sourceX} ${sourceY} Q ${midX + curveOffset} ${sourceY} ${midX + curveOffset} ${midY} Q ${midX + curveOffset} ${targetY} ${targetX} ${targetY}`
        }
      } else {
        // Source is right of target - curve to the left
        routing = {
          start: {x: sourceX, y: sourceY},
          end: {x: targetX, y: targetY},
          controlPoints: [
            {x: midX - curveOffset, y: sourceY},
            {x: midX - curveOffset, y: targetY}
          ],
          path: `M ${sourceX} ${sourceY} Q ${midX - curveOffset} ${sourceY} ${midX - curveOffset} ${midY} Q ${midX - curveOffset} ${targetY} ${targetX} ${targetY}`
        }
      }
    }

    return {
      sourceX: routing.start.x,
      sourceY: routing.start.y,
      targetX: routing.end.x,
      targetY: routing.end.y,
      controlPoints: routing.controlPoints,
      path: routing.path,
      sourceVisible: true, // Always visible since no scrolling
      targetVisible: true  // Always visible since no scrolling
    }
  }


  const getMaxVisibleColumns = (tableId: string) => {
    return expandedTables.has(tableId) ? MAX_VISIBLE_COLUMNS_EXPANDED : MAX_VISIBLE_COLUMNS_DEFAULT
  }

  const toggleTableExpansion = (tableId: string) => {
    setExpandedTables(prev => {
      const newSet = new Set(prev)
      if (newSet.has(tableId)) {
        newSet.delete(tableId)
      } else {
        newSet.add(tableId)
      }
      return newSet
    })
  }

  const getTableScrollOffset = (tableId: string) => {
    return 0 // No scrolling, always show from start
  }

  const renderTableNode = (node: TableNode) => {
    const scrollOffset = getTableScrollOffset(node.id)
    const maxVisible = getMaxVisibleColumns(node.id)
    const visibleColumns = node.columns.slice(scrollOffset, scrollOffset + maxVisible)
    const hasMoreColumns = node.columns.length > maxVisible
    const canScrollUp = scrollOffset > 0
    const canScrollDown = scrollOffset < node.columns.length - maxVisible
    const isExpanded = expandedTables.has(node.id)
    const isDragging = draggingTable?.tableId === node.id

    // Calculate dynamic height based on visible columns
    const headerHeight = 35
    const footerHeight = node.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0 // Space for column count text
    const contentHeight = visibleColumns.length * COLUMN_HEIGHT + 10 // 10px padding
    const dynamicHeight = headerHeight + contentHeight + footerHeight

    return (
      <g 
        key={node.id}
      >
        {/* Table Card */}
        <rect
          x={node.x}
          y={node.y}
          width={TABLE_WIDTH}
          height={dynamicHeight}
          fill="white"
          stroke={isDragging ? "#3b82f6" : "#e5e7eb"}
          strokeWidth={isDragging ? "3" : "2"}
          rx="8"
          style={{
            filter: isDragging ? "drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3))" : "none"
          }}
        />

        {/* Table Header */}
        <rect
          x={node.x}
          y={node.y}
          width={TABLE_WIDTH}
          height="35"
          fill="#f3f4f6"
          rx="8"
          style={{ cursor: (isFullscreen && isSpacePressed) ? 'grab' : 'move' }}
          onMouseDown={(e) => {
            if (!onTableMove || (isFullscreen && isSpacePressed)) return

            // Check if click is on the button area
            const svgElement = svgRef.current
            if (!svgElement) return

            const rect = svgElement.getBoundingClientRect()
            // محاسبه موقعیت کلیک با در نظر گیری zoom و viewBoxOffset
            let clickX = (e.clientX - rect.left) / zoomLevel
            clickX = clickX + viewBoxOffset.x
            const buttonAreaStart = node.x + TABLE_WIDTH - 20

            if (clickX >= buttonAreaStart) {
              // Click on button area - don't drag
              return
            }

            // Click on drag area - start dragging
            handleTableMouseDown(e, node.id, node.x, node.y)
          }}
        />
        <text
          x={node.x + 10}
          y={node.y + 20}
          fontSize="11"
          fontWeight="bold"
          fill="#1f2937"
          style={{ cursor: (isFullscreen && isSpacePressed) ? 'grab' : 'move' }}
          onMouseDown={(e) => {
            e.stopPropagation()
            if (onTableMove && !(isFullscreen && isSpacePressed)) {
              handleTableMouseDown(e, node.id, node.x, node.y)
            }
          }}
        >
          <Database className="inline w-3 h-3 mr-1" />
          {node.table_name}
        </text>

        {/* Row count display */}
        <text
          x={node.x + TABLE_WIDTH - 10}
          y={node.y + 20}
          fontSize="9"
          fill="#6b7280"
          textAnchor="end"
        >
          {node.row_count?.toLocaleString() || '0'} rows
        </text>

        {/* Expand/Collapse Button */}
        {node.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT && (
          <g
            style={{ cursor: 'pointer' }}
            onClick={(e) => {
              e.stopPropagation()
              toggleTableExpansion(node.id)
            }}
          >
            <circle
              cx={node.x + TABLE_WIDTH - 12}
              cy={node.y + 17}
              r="7"
              fill={isExpanded ? "#059669" : "#6b7280"}
            />
            <text
              x={node.x + TABLE_WIDTH - 12}
              y={node.y + 22}
              fontSize="11"
              fill="white"
              textAnchor="middle"
              fontWeight="bold"
            >
              {isExpanded ? '−' : '+'}
            </text>
          </g>
        )}


        {/* Columns */}
        {visibleColumns.map((column, index) => {
          const actualIndex = scrollOffset + index
          return (
            <g key={`${column.name}-${actualIndex}`}>
              <rect
                x={node.x}
                y={node.y + 40 + index * COLUMN_HEIGHT}
                width={TABLE_WIDTH}
                height={COLUMN_HEIGHT - 2}
                fill={hoveredColumn?.tableId === node.id && hoveredColumn?.columnName === column.name ? "#eff6ff" : "transparent"}
                stroke={hoveredColumn?.tableId === node.id && hoveredColumn?.columnName === column.name ? "#2563eb" : "#e5e7eb"}
                strokeWidth={hoveredColumn?.tableId === node.id && hoveredColumn?.columnName === column.name ? "2" : "1"}
                rx="3"
                style={{ cursor: (isFullscreen && isSpacePressed) ? 'grab' : (onCreateRelationship ? 'pointer' : 'default') }}
                onMouseEnter={() => onCreateRelationship && !(isFullscreen && isSpacePressed) && setHoveredColumn({ tableId: node.id, columnName: column.name })}
                onMouseLeave={() => setHoveredColumn(null)}
                onClick={(e) => {
                  e.stopPropagation()
                  if (onOpenCreateRelationshipModal) {
                    onOpenCreateRelationshipModal(node.id, column.name)
                  }
                }}
              />
              <text
                x={node.x + 12}
                y={node.y + 40 + index * COLUMN_HEIGHT + 11}
                fontSize="9"
                fill={hoveredColumn?.tableId === node.id && hoveredColumn?.columnName === column.name ? "#1e40af" : "#374151"}
              >
                {column.is_primary_key && "🔑"}
                {column.name}
              </text>
            </g>
          )
        })}

        {/* Show column count */}
        {node.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT && (
          <text
            x={node.x + TABLE_WIDTH / 2}
            y={node.y + dynamicHeight - 5}
            fontSize="8"
            fill="#6b7280"
            textAnchor="middle"
          >
            {isExpanded
              ? `${scrollOffset + 1}-${Math.min(scrollOffset + maxVisible, node.columns.length)}/${node.columns.length}`
              : `${node.columns.length} cols • click +`
            }
          </text>
        )}
      </g>
    )
  }

  const renderRelationshipEdge = (edge: RelationshipEdge) => {
    try {
      const points = calculateEdgePoints(edge)
      const { relationship } = edge
      const isSecondary = (edge as any)._isSecondary

      // Check if points calculation failed
      if (!points || !points.sourceX || !points.targetX) {
        return null
      }

    // Determine line style based on visibility and secondary status
    const bothVisible = points.sourceVisible && points.targetVisible
    const strokeWidth = bothVisible ? (isSecondary ? "2" : "3") : "1.5"
    const strokeDasharray = bothVisible
      ? getRelationshipStrokeDashArray(relationship.relationship_type)
      : "4,2" // Dotted line if columns not visible
    const baseOpacity = bothVisible ? "1" : "0.7"
    const opacity = isSecondary ? (parseFloat(baseOpacity) * 0.5).toString() : baseOpacity

    return (
      <g key={edge.id} style={{ zIndex: getRelationshipZIndex(relationship.relationship_type) }}>
        {/* Connection point circles */}
        <circle
          cx={points.sourceX}
          cy={points.sourceY}
          r="4"
          fill="white"
          stroke={getRelationshipColor(relationship.relationship_type)}
          strokeWidth="2"
        />
        <circle
          cx={points.targetX}
          cy={points.targetY}
          r="4"
          fill="white"
          stroke={getRelationshipColor(relationship.relationship_type)}
          strokeWidth="2"
        />

        {/* Smart curved line */}
        <path
          d={points.path}
          stroke={getRelationshipColor(relationship.relationship_type)}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={strokeDasharray}
          opacity={opacity}
          className="cursor-pointer"
          onClick={() => onRelationshipClick ? onRelationshipClick(relationship) : setSelectedRelationship(relationship)}
        />

        {/* Arrow head */}
        <polygon
          points={`${points.targetX},${points.targetY} ${points.targetX-8},${points.targetY-4} ${points.targetX-8},${points.targetY+4}`}
          fill={getRelationshipColor(relationship.relationship_type)}
          opacity={opacity}
        />


        {/* Hidden column indicators */}
        {!points.sourceVisible && (
          <g>
            <circle
              cx={points.sourceX}
              cy={points.sourceY}
              r="3"
              fill={getRelationshipColor(relationship.relationship_type)}
              fillOpacity="0.5"
              stroke={getRelationshipColor(relationship.relationship_type)}
              strokeWidth="1"
            />
            <text
              x={points.sourceX}
              y={points.sourceY + 10}
              fontSize="7"
              fill={getRelationshipColor(relationship.relationship_type)}
              textAnchor="middle"
            >
              hid
            </text>
          </g>
        )}

        {!points.targetVisible && (
          <g>
            <circle
              cx={points.targetX}
              cy={points.targetY}
              r="3"
              fill={getRelationshipColor(relationship.relationship_type)}
              fillOpacity="0.5"
              stroke={getRelationshipColor(relationship.relationship_type)}
              strokeWidth="1"
            />
            <text
              x={points.targetX}
              y={points.targetY + 10}
              fontSize="7"
              fill={getRelationshipColor(relationship.relationship_type)}
              textAnchor="middle"
            >
              hid
            </text>
          </g>
        )}
      </g>
    )
    } catch (error) {
      return null
    }
  }

  // Calculate canvas bounds
  const padding = 100
  const minX = Math.min(...tableNodes.map(n => n.x)) - padding + viewBoxOffset.x
  const minY = Math.min(...tableNodes.map(n => n.y)) - padding + viewBoxOffset.y
  const maxX = Math.max(...tableNodes.map(n => n.x + TABLE_WIDTH)) + padding + viewBoxOffset.x
  const maxY = Math.max(...tableNodes.map(n => n.y + TABLE_HEIGHT)) + padding + viewBoxOffset.y
  const width = Math.max(maxX - minX, 1400) // Minimum width
  const height = Math.max(maxY - minY, 1000) // Minimum height

  // Smart grid pattern calculation based on zoom level
  const getGridConfig = () => {
    // Grid size adapts to zoom: smaller grid when zoomed in, larger when zoomed out
    let gridSize = 20
    if (zoomLevel > 1.5) {
      gridSize = 10 // Smaller grid when zoomed in
    } else if (zoomLevel < 0.7) {
      gridSize = 50 // Larger grid when zoomed out
    } else if (zoomLevel < 0.5) {
      gridSize = 100 // Even larger for very zoomed out
    }
    
    const majorGridSize = gridSize * 5
    const strokeWidth = zoomLevel > 1 ? 0.5 : 1
    const majorStrokeWidth = zoomLevel > 1 ? 1 : 1.5
    
    return {
      gridSize,
      majorGridSize,
      strokeWidth,
      majorStrokeWidth,
      minorTransform: `translate(${-viewBoxOffset.x % gridSize}, ${-viewBoxOffset.y % gridSize})`,
      majorTransform: `translate(${-viewBoxOffset.x % majorGridSize}, ${-viewBoxOffset.y % majorGridSize})`
    }
  }

  const gridConfig = getGridConfig()

  // Mini-map calculations
  const miniMapScale = 0.08 // Scale factor for mini-map
  const miniMapWidth = 200
  const miniMapHeight = 150
  const miniMapPadding = 10

  return (
    <div
      className="relative overflow-hidden w-full h-full"
      style={{
        height: isFullscreen ? '100%' : '600px',
        transition: 'height 0.2s ease-in-out',
        position: 'relative',
        zIndex: 1
      }}
    >
      <div
        className="w-full h-full"
        style={{
          transform: `scale(${zoomLevel})`,
          transformOrigin: '0 0', // top left برای حفظ موقعیت
          width: `${100 / zoomLevel}%`,
          height: `${100 / zoomLevel}%`,
          transition: zoomLevel !== 1 ? 'transform 0.2s ease-in-out' : 'none',
          cursor: (isFullscreen && isSpacePressed) ? 'grab' : (isPanning ? 'grabbing' : 'default'),
          position: 'relative',
          overflow: 'visible' // اجازه می‌دهد محتوا از container خارج شود
        }}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox={`${-viewBoxOffset.x} ${-viewBoxOffset.y} ${viewportSize.width} ${viewportSize.height}`}
          preserveAspectRatio="xMidYMid meet"
          className="border-2 border-gray-200 rounded-lg bg-gray-50"
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{
            height: isFullscreen ? '100%' : '600px',
            cursor: (isFullscreen && isSpacePressed) ? 'grab' : (isPanning ? 'grabbing' : 'default'),
            display: 'block',
            position: 'relative',
            zIndex: 1
          }}
        >
        {/* Smart Grid pattern - adjusts based on zoom level */}
        <defs>
          {/* Minor grid pattern */}
          <pattern 
            id="grid-minor" 
            width={gridConfig.gridSize} 
            height={gridConfig.gridSize} 
            patternUnits="userSpaceOnUse"
            patternTransform={gridConfig.minorTransform}
          >
            <path 
              d={`M ${gridConfig.gridSize} 0 L 0 0 0 ${gridConfig.gridSize}`} 
              fill="none" 
              stroke="#e5e7eb" 
              strokeWidth={gridConfig.strokeWidth}
              opacity="0.4"
            />
          </pattern>
          
          {/* Major grid pattern */}
          <pattern 
            id="grid-major" 
            width={gridConfig.majorGridSize} 
            height={gridConfig.majorGridSize} 
            patternUnits="userSpaceOnUse"
            patternTransform={gridConfig.majorTransform}
          >
            <path 
              d={`M ${gridConfig.majorGridSize} 0 L 0 0 0 ${gridConfig.majorGridSize}`} 
              fill="none" 
              stroke="#d1d5db" 
              strokeWidth={gridConfig.majorStrokeWidth}
              opacity="0.6"
            />
          </pattern>
        </defs>
        
        {/* Background with major grid lines first, then minor - extends to cover all content */}
        {/* Calculate extended bounds to ensure grid covers all tables */}
        {tableNodes.length > 0 && (() => {
          const padding = 500 // اضافه کردن padding برای اطمینان از پوشش کامل
          const contentMinX = Math.min(...tableNodes.map(n => n.x)) - padding
          const contentMinY = Math.min(...tableNodes.map(n => n.y)) - padding
          const contentMaxX = Math.max(...tableNodes.map(n => n.x + TABLE_WIDTH)) + padding
          const contentMaxY = Math.max(...tableNodes.map(n => {
            const isExpanded = expandedTables.has(n.id)
            const visibleColumns = isExpanded ? n.columns.length : Math.min(n.columns.length, MAX_VISIBLE_COLUMNS_DEFAULT)
            const tableHeight = 35 + visibleColumns * COLUMN_HEIGHT + (n.columns.length > MAX_VISIBLE_COLUMNS_DEFAULT ? 20 : 0)
            return n.y + tableHeight
          })) + padding
          
          const gridWidth = Math.max(contentMaxX - contentMinX, viewportSize.width)
          const gridHeight = Math.max(contentMaxY - contentMinY, viewportSize.height)
          const gridX = Math.min(contentMinX, -viewBoxOffset.x)
          const gridY = Math.min(contentMinY, -viewBoxOffset.y)
          
          return (
            <>
              {/* Background fill */}
              <rect 
                width={gridWidth} 
                height={gridHeight} 
                fill="#fafafa" 
                x={gridX} 
                y={gridY}
              />
              {/* Major grid */}
              <rect 
                width={gridWidth} 
                height={gridHeight} 
                fill="url(#grid-major)" 
                x={gridX} 
                y={gridY}
              />
              {/* Minor grid */}
              <rect 
                width={gridWidth} 
                height={gridHeight} 
                fill="url(#grid-minor)" 
                x={gridX} 
                y={gridY}
              />
            </>
          )
        })()}
        
        {/* Fallback for when no tables */}
        {tableNodes.length === 0 && (
          <>
            <rect 
              width="100%" 
              height="100%" 
              fill="#fafafa" 
              x={-viewBoxOffset.x} 
              y={-viewBoxOffset.y}
            />
            <rect 
              width="100%" 
              height="100%" 
              fill="url(#grid-major)" 
              x={-viewBoxOffset.x} 
              y={-viewBoxOffset.y}
            />
            <rect 
              width="100%" 
              height="100%" 
              fill="url(#grid-minor)" 
              x={-viewBoxOffset.x} 
              y={-viewBoxOffset.y}
            />
          </>
        )}

        {/* Render edges first (behind nodes) - sorted by importance */}
        {edges
          .sort((a, b) => getRelationshipZIndex(b.relationship.relationship_type) - getRelationshipZIndex(a.relationship.relationship_type))
          .map(renderRelationshipEdge)}


        {/* Render table nodes - render dragging/expanded tables last for proper z-ordering */}
        {tableNodes
          .sort((a, b) => {
            const aIsDragging = draggingTable?.tableId === a.id
            const bIsDragging = draggingTable?.tableId === b.id
            const aIsExpanded = expandedTables.has(a.id)
            const bIsExpanded = expandedTables.has(b.id)
            
            // اول جداولی که drag یا expand نشده‌اند، سپس expand شده، سپس drag شده
            if (aIsDragging && !bIsDragging) return 1
            if (!aIsDragging && bIsDragging) return -1
            if (aIsExpanded && !bIsExpanded && !aIsDragging) return 1
            if (!aIsExpanded && bIsExpanded && !bIsDragging) return -1
            return 0
          })
          .map((node, index) => {
            return renderTableNode(node)
          })}
        </svg>
      </div>

      {/* Mini-map */}
      {isFullscreen && tableNodes.length > 8 && (
        <div
          className="absolute bottom-4 right-4 bg-white border border-gray-300 rounded-lg shadow-lg p-2"
          style={{ zIndex: 1000, pointerEvents: 'auto' }}
        >
          <div className="text-xs font-medium text-gray-700 mb-1 text-center">Mini-map</div>
          <svg
            width={miniMapWidth}
            height={miniMapHeight}
            className="border border-gray-200 rounded"
            viewBox={`${minX} ${minY} ${width} ${height}`}
          >
            {/* Mini-map background */}
            <rect
              x={minX}
              y={minY}
              width={width}
              height={height}
              fill="#f9fafb"
              stroke="#e5e7eb"
              strokeWidth="1"
            />

            {/* Mini-map table nodes */}
            {tableNodes.map((node) => (
              <rect
                key={`mini-${node.id}`}
                x={node.x}
                y={node.y}
                width={TABLE_WIDTH}
                height={Math.min(node.columns.length * COLUMN_HEIGHT + 35, TABLE_HEIGHT)}
                fill="#3b82f6"
                fillOpacity="0.6"
                stroke="#2563eb"
                strokeWidth="1"
                rx="2"
              />
            ))}

            {/* Viewport indicator */}
            <rect
              x={-viewBoxOffset.x}
              y={-viewBoxOffset.y}
              width={width / zoomLevel}
              height={height / zoomLevel}
              fill="none"
              stroke="#ef4444"
              strokeWidth="2"
              strokeDasharray="5,3"
              rx="2"
            />
          </svg>
          <div className="text-xs text-gray-500 mt-1 text-center">
            {tableNodes.length} tables
          </div>
        </div>
      )}

      {/* Relationship details panel */}
      {selectedRelationship && (
        <Card className="absolute top-4 right-4 w-80" style={{ zIndex: 1001, pointerEvents: 'auto' }}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Relationship Details</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedRelationship(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant={
                selectedRelationship.relationship_type === "db_fk" ? "default" :
                selectedRelationship.relationship_type === "ai_suggested" ? "secondary" : "outline"
              }>
                {selectedRelationship.relationship_type === "db_fk" ? "DB FK" :
                 selectedRelationship.relationship_type === "ai_suggested" ? "AI Suggested" : "User Defined"}
              </Badge>
              {selectedRelationship.confidence_score && (
                <Badge variant="outline">
                  {Math.round(selectedRelationship.confidence_score * 100)}% confidence
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <div className="font-medium text-muted-foreground">Source</div>
                <div className="font-mono">{selectedRelationship.source_table}.{selectedRelationship.source_column}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Target</div>
                <div className="font-mono">{selectedRelationship.target_table}.{selectedRelationship.target_column}</div>
              </div>
            </div>

            <div className="flex items-center gap-4 text-sm">
              <div><span className="font-medium text-muted-foreground">Join:</span> {selectedRelationship.join_type}</div>
              <div><span className="font-medium text-muted-foreground">Cardinality:</span> {selectedRelationship.cardinality}</div>
            </div>

            {selectedRelationship.strength_score && (
              <div className="flex items-center gap-4 text-sm">
                <div>
                  <span className="font-medium text-muted-foreground">Strength Score:</span> {(selectedRelationship.strength_score * 100).toFixed(1)}%
                </div>
                {selectedRelationship.confidence_score && (
                  <div>
                    <span className="font-medium text-muted-foreground">Confidence:</span> {(selectedRelationship.confidence_score * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center gap-4 text-sm">
              <div>
                <span className="font-medium text-muted-foreground">Agent Approved:</span> {selectedRelationship.agent_approved ? "Yes" : "No"}
              </div>
              <div>
                <span className="font-medium text-muted-foreground">User Accepted:</span> {selectedRelationship.user_accepted ? "Yes" : "No"}
              </div>
            </div>

            <div>
              <div className="font-medium text-muted-foreground text-sm">Description</div>
              <div className="text-sm">{selectedRelationship.description}</div>
            </div>

            <div className="flex gap-2 pt-2">
              {onEditRelationship && (
                <Button size="sm" variant="outline" onClick={() => onEditRelationship(selectedRelationship)}>
                  <Edit className="h-4 w-4 mr-1" />
                  Edit
                </Button>
              )}
              {selectedRelationship.relationship_type !== "db_fk" && onDeleteRelationship && (
                <Button size="sm" variant="outline" onClick={() => onDeleteRelationship(selectedRelationship.id)}>
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete
                </Button>
              )}
              {selectedRelationship.relationship_type === "ai_suggested" && !selectedRelationship.is_confirmed && onAcceptRelationship && (
                <Button size="sm" onClick={() => onAcceptRelationship(selectedRelationship)}>
                  <Check className="h-4 w-4 mr-1" />
                  Accept
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

