/**
 * Enhanced Data Flow Canvas
 * Main canvas component with integrated state management, side panels, and view modes
 */
import React, { useCallback, useRef, useEffect, useState } from 'react'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  Panel,
  NodeTypes,
  EdgeTypes,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useCanvasStore } from '../../store/canvasStore'
import { nodeTypes } from './NodeTypes'
import { edgeTypes } from '../EdgeTypes'
import { NodePalette } from './NodePalette'
import { NodeConfigurationPanel } from './NodeConfigurationPanel'
import { getNodeTypeDefinition } from '../../types/nodeRegistry'
import { canvasApi, migrationApi } from '../../services/api'
import { Save, Play, CheckCircle, Eye, BarChart3, X } from 'lucide-react'
import { wsService } from '../../services/websocket'

interface EnhancedDataFlowCanvasProps {
  canvasId?: number
  initialNodes?: Node[]
  initialEdges?: Edge[]
}

export const EnhancedDataFlowCanvas: React.FC<EnhancedDataFlowCanvasProps> = ({
  canvasId,
  initialNodes = [],
  initialEdges = [],
}) => {
  const {
    nodes,
    edges,
    selectedNode,
    viewMode,
    setNodes,
    setEdges,
    addNode,
    updateNode,
    deleteNode,
    addEdge: addEdgeToStore,
    deleteEdge: deleteEdgeFromStore,
    setSelectedNode,
    setViewMode,
    setCanvas,
    updateNodeStatus,
  } = useCanvasStore()

  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)
  const [showConfigPanel, setShowConfigPanel] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  // Initialize canvas state
  useEffect(() => {
    if (initialNodes.length > 0) {
      setNodes(initialNodes)
    }
    if (initialEdges.length > 0) {
      setEdges(initialEdges)
    }
    if (canvasId) {
      setCanvas(canvasId, `Canvas ${canvasId}`)
    }
  }, [canvasId, initialNodes, initialEdges, setNodes, setEdges, setCanvas])

  const onNodesChange = useCallback(
    (changes: any) => {
      // React Flow's useNodesState handles most changes
      // We sync to our store
      const updatedNodes = changes.reduce((acc: Node[], change: any) => {
        if (change.type === 'remove') {
          return acc.filter((n) => n.id !== change.id)
        }
        if (change.type === 'add') {
          return [...acc, change.item]
        }
        if (change.type === 'position' || change.type === 'dimensions') {
          return acc.map((n) =>
            n.id === change.id ? { ...n, ...change } : n
          )
        }
        return acc
      }, nodes)
      setNodes(updatedNodes)
    },
    [nodes, setNodes]
  )

  const onEdgesChange = useCallback(
    (changes: any) => {
      const updatedEdges = changes.reduce((acc: Edge[], change: any) => {
        if (change.type === 'remove') {
          return acc.filter((e) => e.id !== change.id)
        }
        if (change.type === 'add') {
          return [...acc, change.item]
        }
        return acc
      }, edges)
      setEdges(updatedEdges)
    },
    [edges, setEdges]
  )

  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge = addEdge(params, edges)
      setEdges(newEdge)
    },
    [edges, setEdges]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const nodeTypeId = event.dataTransfer.getData('application/reactflow')
      if (!nodeTypeId || !reactFlowInstance) return

      const nodeTypeDef = getNodeTypeDefinition(nodeTypeId)
      if (!nodeTypeDef) return

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect()
      const position = reactFlowInstance.project({
        x: event.clientX - (reactFlowBounds?.left || 0),
        y: event.clientY - (reactFlowBounds?.top || 0),
      })

      const newNodeId = `${nodeTypeDef.category}-${Date.now()}`
      const newNode: Node = {
        id: newNodeId,
        type: nodeTypeDef.category, // Use category as type for now
        position,
        data: {
          id: newNodeId,
          label: nodeTypeDef.label,
          type: nodeTypeDef.category,
          status: 'idle',
          config: { ...nodeTypeDef.defaultConfig },
        },
      }

      addNode(newNode)
    },
    [reactFlowInstance, addNode]
  )

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node)
      setShowConfigPanel(true)
    },
    [setSelectedNode]
  )

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
    setShowConfigPanel(false)
  }, [setSelectedNode])

  const handleSave = useCallback(async () => {
    try {
      const config = {
        nodes: nodes.map((node) => ({
          id: node.id,
          type: node.type,
          position: node.position,
          data: node.data,
        })),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
        })),
      }

      if (canvasId) {
        await canvasApi.saveConfiguration(canvasId, { configuration: config })
      } else {
        const response = await canvasApi.create({
          name: `Canvas ${new Date().toLocaleString()}`,
          configuration: config,
        })
        if (response.data.id) {
          setCanvas(response.data.id, response.data.name)
        }
      }
      alert('Canvas saved successfully!')
    } catch (error) {
      console.error('Error saving canvas:', error)
      alert('Failed to save canvas')
    }
  }, [nodes, edges, canvasId, setCanvas])

  const handleValidate = useCallback(() => {
    const errors: string[] = []

    // Check for at least one source node
    const sourceNodes = nodes.filter((n) => n.data.type === 'source')
    if (sourceNodes.length === 0) {
      errors.push('At least one source node is required')
    }

    // Check for at least one destination node
    const destNodes = nodes.filter((n) => n.data.type === 'destination')
    if (destNodes.length === 0) {
      errors.push('At least one destination node is required')
    }

    // Check that all source nodes have required config
    sourceNodes.forEach((node) => {
      const config = node.data.config || {}
      if (!config.sourceId || !config.tableName) {
        errors.push(`Source node "${node.data.label}" is missing required configuration`)
      }
    })

    // Check that all destination nodes have required config
    destNodes.forEach((node) => {
      const config = node.data.config || {}
      if (!config.destinationId || !config.tableName) {
        errors.push(`Destination node "${node.data.label}" is missing required configuration`)
      }
    })

    // Check graph connectivity
    const nodeIds = new Set(nodes.map((n) => n.id))
    edges.forEach((edge) => {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        errors.push('Invalid edge: connected to non-existent node')
      }
    })

    setValidationErrors(errors)
    setViewMode('validate')

    if (errors.length === 0) {
      alert('Pipeline validation passed!')
    }
  }, [nodes, edges, setViewMode])

  const handleExecute = useCallback(async () => {
    if (!canvasId) {
      alert('Please save the canvas first')
      return
    }

    // Validate before executing
    handleValidate()
    if (validationErrors.length > 0) {
      alert('Please fix validation errors before executing')
      return
    }

    try {
      const response = await migrationApi.execute(canvasId, {
        nodes: nodes.map((node) => ({
          id: node.id,
          type: node.type,
          data: node.data,
        })),
        edges: edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
        })),
      })

      const jobId = response.data.job_id
      alert(`Migration job started! Job ID: ${jobId}`)
      setViewMode('monitor')
      
      // Connect WebSocket for real-time updates
      wsService.subscribeToJobUpdates(jobId, {
        onStatus: (data) => {
          // Update overall job status
        },
        onNodeProgress: (data) => {
          if (data.node_id) {
            updateNodeStatus(data.node_id, (data.status as any) || 'running')
            if (data.progress !== undefined) {
              updateJobProgress(data.node_id, data.progress)
            }
          }
        },
        onComplete: () => {
          // Job completed
        },
        onError: () => {
          // Job failed
        },
      })
    } catch (error) {
      console.error('Error executing migration:', error)
      alert('Failed to start migration')
    }
  }, [nodes, edges, canvasId, handleValidate, validationErrors, setViewMode, updateNodeStatus, updateJobProgress])

  const handleDeleteSelected = useCallback(() => {
    if (selectedNode) {
      deleteNode(selectedNode.id)
      setSelectedNode(null)
      setShowConfigPanel(false)
    }
  }, [selectedNode, deleteNode, setSelectedNode])

  return (
    <div className="w-full h-full flex relative">
      {/* Node Palette */}
      <NodePalette
        onDragStart={(nodeType, event) => {
          event.dataTransfer.setData('application/reactflow', nodeType)
        }}
      />

      {/* Canvas Area */}
      <div ref={reactFlowWrapper} className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={setReactFlowInstance}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes as NodeTypes}
          edgeTypes={edgeTypes as EdgeTypes}
          fitView
        >
          <Controls />
          <Background />
          <MiniMap />

          {/* Top Toolbar */}
          <Panel position="top-center" className="bg-white p-2 rounded-lg shadow-lg flex gap-2">
            {/* View Mode Buttons */}
            <div className="flex gap-1 border-r border-gray-200 pr-2">
              <button
                onClick={() => setViewMode('design')}
                className={`px-3 py-1 rounded text-sm ${
                  viewMode === 'design'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Eye className="w-4 h-4 inline mr-1" />
                Design
              </button>
              <button
                onClick={() => setViewMode('validate')}
                className={`px-3 py-1 rounded text-sm ${
                  viewMode === 'validate'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <CheckCircle className="w-4 h-4 inline mr-1" />
                Validate
              </button>
              <button
                onClick={() => setViewMode('monitor')}
                className={`px-3 py-1 rounded text-sm ${
                  viewMode === 'monitor'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <BarChart3 className="w-4 h-4 inline mr-1" />
                Monitor
              </button>
            </div>

            {/* Action Buttons */}
            <button
              onClick={handleSave}
              className="px-4 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 flex items-center gap-1"
            >
              <Save className="w-4 h-4" />
              Save
            </button>
            <button
              onClick={handleValidate}
              className="px-4 py-1 bg-purple-500 text-white rounded text-sm hover:bg-purple-600 flex items-center gap-1"
            >
              <CheckCircle className="w-4 h-4" />
              Validate
            </button>
            <button
              onClick={handleExecute}
              className="px-4 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600 flex items-center gap-1"
            >
              <Play className="w-4 h-4" />
              Execute
            </button>
            {selectedNode && (
              <button
                onClick={handleDeleteSelected}
                className="px-4 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600 flex items-center gap-1"
              >
                <X className="w-4 h-4" />
                Delete
              </button>
            )}
          </Panel>

          {/* Validation Errors Panel */}
          {viewMode === 'validate' && validationErrors.length > 0 && (
            <Panel position="top-right" className="bg-red-50 border border-red-200 rounded-lg shadow-lg p-4 max-w-md">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-red-900">Validation Errors</h3>
                <button onClick={() => setValidationErrors([])}>
                  <X className="w-4 h-4 text-red-600" />
                </button>
              </div>
              <ul className="list-disc list-inside space-y-1 text-sm text-red-700">
                {validationErrors.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Configuration Panel */}
      {showConfigPanel && selectedNode && (
        <NodeConfigurationPanel
          node={selectedNode}
          onClose={() => {
            setShowConfigPanel(false)
            setSelectedNode(null)
          }}
        />
      )}
    </div>
  )
}

