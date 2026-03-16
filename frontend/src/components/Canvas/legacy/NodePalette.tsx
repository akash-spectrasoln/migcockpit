/**
 * Node Palette Component
 * Draggable list of available node types
 */
import React from 'react'
import { Database, Settings, ArrowRight } from 'lucide-react'
import { getNodeTypesByCategory, NodeCategory } from '../../types/nodeRegistry'

interface NodePaletteProps {
  onDragStart: (nodeType: string, event: React.DragEvent) => void
}

const categoryIcons = {
  source: Database,
  transform: Settings,
  destination: ArrowRight,
}

const categoryColors = {
  source: 'blue',
  transform: 'purple',
  destination: 'green',
}

export const NodePalette: React.FC<NodePaletteProps> = ({ onDragStart }) => {
  const categories: NodeCategory[] = ['source', 'transform', 'destination']

  return (
    <div className="w-64 bg-white border-r border-gray-200 h-full flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h2 className="font-semibold text-gray-900">Node Palette</h2>
        <p className="text-xs text-gray-500 mt-1">Drag nodes to canvas</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {categories.map((category) => {
          const nodeTypes = getNodeTypesByCategory(category)
          const Icon = categoryIcons[category]
          const color = categoryColors[category]

          return (
            <div key={category}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-4 h-4 ${
                  color === 'blue' ? 'text-blue-600' :
                  color === 'purple' ? 'text-purple-600' :
                  'text-green-600'
                }`} />
                <h3 className="text-sm font-semibold text-gray-700 capitalize">
                  {category}
                </h3>
              </div>

              <div className="space-y-2">
                {nodeTypes.map((nodeType) => {
                  const colorClasses = {
                    blue: 'bg-blue-50 border-blue-300 hover:bg-blue-100',
                    purple: 'bg-purple-50 border-purple-300 hover:bg-purple-100',
                    green: 'bg-green-50 border-green-300 hover:bg-green-100',
                  }
                  return (
                    <div
                      key={nodeType.id}
                      draggable
                      onDragStart={(e) => onDragStart(nodeType.id, e)}
                      className={`p-3 ${colorClasses[color as keyof typeof colorClasses]} border rounded-lg cursor-move transition-colors`}
                    >
                    <div className="font-medium text-sm text-gray-900">
                      {nodeType.label}
                    </div>
                    <div className="text-xs text-gray-600 mt-1">
                      {nodeType.description}
                    </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

