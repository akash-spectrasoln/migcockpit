import React from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Database, Settings, ArrowRight } from 'lucide-react'

export interface BaseNodeData {
  id: string
  label: string
  type: 'source' | 'transform' | 'destination'
  config?: any
  status?: 'idle' | 'running' | 'success' | 'error'
}

export interface SourceNodeData extends BaseNodeData {
  type: 'source'
  sourceId?: number
  sourceName?: string
  connectionType?: 'mysql' | 'oracle' | 'sqlserver'
}

export interface TransformNodeData extends BaseNodeData {
  type: 'transform'
  transformType?: 'map' | 'filter' | 'aggregate' | 'clean'
  rules?: any[]
}

export interface DestinationNodeData extends BaseNodeData {
  type: 'destination'
  destinationId?: number
  destinationName?: string
  connectionType?: 'hana'
}

const nodeStyles = {
  source: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    icon: Database,
    iconColor: 'text-blue-600',
  },
  transform: {
    bg: 'bg-purple-50',
    border: 'border-purple-300',
    icon: Settings,
    iconColor: 'text-purple-600',
  },
  destination: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    icon: ArrowRight,
    iconColor: 'text-green-600',
  },
}

const statusStyles = {
  idle: 'bg-gray-200',
  running: 'bg-yellow-400 animate-pulse',
  success: 'bg-green-400',
  error: 'bg-red-400',
}

export const SourceNode: React.FC<NodeProps<SourceNodeData>> = ({ data, selected }) => {
  const styles = nodeStyles.source
  const Icon = styles.icon

  return (
    <div
      className={`${styles.bg} ${styles.border} border-2 rounded-lg p-4 min-w-[200px] shadow-md ${
        selected ? 'ring-2 ring-blue-500' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`${styles.iconColor} w-5 h-5`} />
        <div className="font-semibold text-sm">{data.label || 'Source'}</div>
      </div>
      
      {data.sourceName && (
        <div className="text-xs text-gray-600 mb-2">{data.sourceName}</div>
      )}
      
      {data.connectionType && (
        <div className="text-xs text-gray-500 mb-2">
          Type: {data.connectionType.toUpperCase()}
        </div>
      )}

      <div className="flex items-center gap-2 mt-2">
        <div className={`w-2 h-2 rounded-full ${statusStyles[data.status || 'idle']}`} />
        <span className="text-xs text-gray-600 capitalize">{data.status || 'idle'}</span>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-blue-500"
      />
    </div>
  )
}

export const TransformNode: React.FC<NodeProps<TransformNodeData>> = ({ data, selected }) => {
  const styles = nodeStyles.transform
  const Icon = styles.icon

  return (
    <div
      className={`${styles.bg} ${styles.border} border-2 rounded-lg p-4 min-w-[200px] shadow-md ${
        selected ? 'ring-2 ring-purple-500' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`${styles.iconColor} w-5 h-5`} />
        <div className="font-semibold text-sm">{data.label || 'Transform'}</div>
      </div>

      {data.transformType && (
        <div className="text-xs text-gray-600 mb-2">
          Type: {data.transformType}
        </div>
      )}

      {data.rules && data.rules.length > 0 && (
        <div className="text-xs text-gray-500 mb-2">
          {data.rules.length} rule(s)
        </div>
      )}

      <div className="flex items-center gap-2 mt-2">
        <div className={`w-2 h-2 rounded-full ${statusStyles[data.status || 'idle']}`} />
        <span className="text-xs text-gray-600 capitalize">{data.status || 'idle'}</span>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-purple-500"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-purple-500"
      />
    </div>
  )
}

export const DestinationNode: React.FC<NodeProps<DestinationNodeData>> = ({ data, selected }) => {
  const styles = nodeStyles.destination
  const Icon = styles.icon

  return (
    <div
      className={`${styles.bg} ${styles.border} border-2 rounded-lg p-4 min-w-[200px] shadow-md ${
        selected ? 'ring-2 ring-green-500' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`${styles.iconColor} w-5 h-5`} />
        <div className="font-semibold text-sm">{data.label || 'Destination'}</div>
      </div>

      {data.destinationName && (
        <div className="text-xs text-gray-600 mb-2">{data.destinationName}</div>
      )}

      {data.connectionType && (
        <div className="text-xs text-gray-500 mb-2">
          Type: {data.connectionType.toUpperCase()}
        </div>
      )}

      <div className="flex items-center gap-2 mt-2">
        <div className={`w-2 h-2 rounded-full ${statusStyles[data.status || 'idle']}`} />
        <span className="text-xs text-gray-600 capitalize">{data.status || 'idle'}</span>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-green-500"
      />
    </div>
  )
}

export const nodeTypes = {
  source: SourceNode,
  transform: TransformNode,
  destination: DestinationNode,
}

