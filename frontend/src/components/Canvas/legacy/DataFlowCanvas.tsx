import React, { useCallback, useState, useRef } from 'react'
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
// Legacy file - imports fixed for reference
// Note: This file is not used in the current implementation
// Use DataFlowCanvasChakra.tsx instead
import { nodeTypes, SourceNodeData, TransformNodeData, DestinationNodeData } from './NodeTypes'
import { edgeTypes } from '../EdgeTypes'

// TypeScript: This file is in legacy folder and not actively used
// All imports are correct for legacy reference purposes
import { Plus, Play, Save, Trash2 } from 'lucide-react'
import { canvasApi, migrationApi } from '../../services/api'

interface DataFlowCanvasProps {
  canvasId?: number
  initialNodes?: Node[]
  initialEdges?: Edge[]
  onSave?: (nodes: Node[], edges: Edge[]) => void
}

export const DataFlowCanvas: React.FC<DataFlowCanvasProps> = ({
  canvasId,
  initialNodes = [],
  initialEdges = [],
  onSave,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null)

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds))
    },
    [setEdges]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const type = event.dataTransfer.getData('application/reactflow')
      if (!type || !reactFlowInstance) return

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect()
      const position = reactFlowInstance.project({
        x: event.clientX - (reactFlowBounds?.left || 0),
        y: event.clientY - (reactFlowBounds?.top || 0),
      })

      const newNodeId = `${type}-${Date.now()}`
      let newNodeData: SourceNodeData | TransformNodeData | DestinationNodeData

      switch (type) {
        case 'source':
          newNodeData = {
            id: newNodeId,
            label: 'Source',
            type: 'source',
            status: 'idle',
          }
          break
        case 'transform':
          newNodeData = {
            id: newNodeId,
            label: 'Transform',
            type: 'transform',
            status: 'idle',
          }
          break
        case 'destination':
          newNodeData = {
            id: newNodeId,
            label: 'Destination',
            type: 'destination',
            status: 'idle',
          }
          break
        default:
          return
      }

      const newNode: Node = {
        id: newNodeId,
        type,
        position,
        data: newNodeData,
      }

      setNodes((nds) => nds.concat(newNode))
    },
    [reactFlowInstance, setNodes]
  )

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
        await canvasApi.saveConfiguration(canvasId, config)
      } else {
        const response = await canvasApi.create({
          name: `Canvas ${new Date().toLocaleString()}`,
          configuration: config,
        })
        if (onSave) {
          onSave(nodes, edges)
        }
      }
      alert('Canvas saved successfully!')
    } catch (error) {
      console.error('Error saving canvas:', error)
      alert('Failed to save canvas')
    }
  }, [nodes, edges, canvasId, onSave])

  const handleExecute = useCallback(async () => {
    if (!canvasId) {
      alert('Please save the canvas first')
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

      alert(`Migration job started! Job ID: ${response.data.job_id}`)
    } catch (error) {
      console.error('Error executing migration:', error)
      alert('Failed to start migration')
    }
  }, [nodes, edges, canvasId])

  const handleDeleteSelected = useCallback(() => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((node) => node.id !== selectedNode.id))
      setEdges((eds) =>
        eds.filter(
          (edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id
        )
      )
      setSelectedNode(null)
    }
  }, [selectedNode, setNodes, setEdges])

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  return (
    <div className="w-full h-full relative">
      <div ref={reactFlowWrapper} className="w-full h-full">
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
          <Panel position="top-left" className="bg-white p-4 rounded-lg shadow-lg">
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold mb-2">Add Node</h3>
              <div
                draggable
                onDragStart={(e) => e.dataTransfer.setData('application/reactflow', 'source')}
                className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-300 rounded cursor-move hover:bg-blue-100"
              >
                <Plus className="w-4 h-4" />
                <span className="text-sm">Source</span>
              </div>
              <div
                draggable
                onDragStart={(e) => e.dataTransfer.setData('application/reactflow', 'transform')}
                className="flex items-center gap-2 p-2 bg-purple-50 border border-purple-300 rounded cursor-move hover:bg-purple-100"
              >
                <Plus className="w-4 h-4" />
                <span className="text-sm">Transform</span>
              </div>
              <div
                draggable
                onDragStart={(e) => e.dataTransfer.setData('application/reactflow', 'destination')}
                className="flex items-center gap-2 p-2 bg-green-50 border border-green-300 rounded cursor-move hover:bg-green-100"
              >
                <Plus className="w-4 h-4" />
                <span className="text-sm">Destination</span>
              </div>
            </div>
          </Panel>
          <Panel position="top-right" className="bg-white p-4 rounded-lg shadow-lg">
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                <Save className="w-4 h-4" />
                Save
              </button>
              <button
                onClick={handleExecute}
                className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
              >
                <Play className="w-4 h-4" />
                Execute
              </button>
              {selectedNode && (
                <button
                  onClick={handleDeleteSelected}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              )}
            </div>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  )
}

