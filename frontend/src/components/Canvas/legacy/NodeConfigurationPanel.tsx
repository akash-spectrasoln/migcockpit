/**
 * Node Configuration Panel
 * Reusable, schema-driven form for configuring nodes
 */
import React, { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { Node } from 'reactflow'
import { useCanvasStore } from '../../store/canvasStore'
import { getNodeTypeDefinition, ConfigField } from '../../types/nodeRegistry'
import { connectionApi } from '../../services/api'

interface NodeConfigurationPanelProps {
  node: Node | null
  onClose: () => void
}

export const NodeConfigurationPanel: React.FC<NodeConfigurationPanelProps> = ({
  node,
  onClose,
}) => {
  const { updateNode } = useCanvasStore()
  const [config, setConfig] = useState<Record<string, any>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [sourceOptions, setSourceOptions] = useState<{ value: string; label: string }[]>([])
  const [destinationOptions, setDestinationOptions] = useState<{ value: string; label: string }[]>([])

  useEffect(() => {
    if (node) {
      setConfig(node.data.config || {})
      
      // Load connection options if needed
      const nodeType = node.type || 'source'
      if (nodeType.startsWith('source-') || nodeType === 'source') {
        loadSourceConnections()
      } else if (nodeType.startsWith('destination-') || nodeType === 'destination') {
        loadDestinationConnections()
      }
    }
  }, [node])

  const loadSourceConnections = async () => {
    try {
      const response = await connectionApi.getSources()
      const options = response.data.map((source: any) => ({
        value: source.id.toString(),
        label: `${source.name} (${source.db_type})`,
      }))
      setSourceOptions(options)
    } catch (error) {
      console.error('Failed to load source connections:', error)
    }
  }

  const loadDestinationConnections = async () => {
    try {
      const response = await connectionApi.getDestinations()
      const options = response.data.map((dest: any) => ({
        value: dest.id.toString(),
        label: `${dest.name} (${dest.db_type})`,
      }))
      setDestinationOptions(options)
    } catch (error) {
      console.error('Failed to load destination connections:', error)
    }
  }

  if (!node) return null

  const nodeTypeDef = getNodeTypeDefinition(node.type || '')
  if (!nodeTypeDef) {
    return (
      <div className="w-80 bg-white border-l border-gray-200 h-full flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Node Configuration</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <div className="p-4 text-sm text-gray-500">
          Unknown node type: {node.type}
        </div>
      </div>
    )
  }

  const handleFieldChange = (fieldName: string, value: any) => {
    const newConfig = { ...config, [fieldName]: value }
    setConfig(newConfig)
    
    // Validate field
    const field = nodeTypeDef.configSchema.find((f) => f.name === fieldName)
    if (field?.validation) {
      const error = field.validation(value)
      setErrors((prev) => ({
        ...prev,
        [fieldName]: error || '',
      }))
    } else {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors[fieldName]
        return newErrors
      })
    }
  }

  const handleSave = () => {
    // Validate all required fields
    const newErrors: Record<string, string> = {}
    nodeTypeDef.configSchema.forEach((field) => {
      if (field.required && !config[field.name]) {
        newErrors[field.name] = `${field.label} is required`
      }
    })

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    // Update node with new config
    updateNode(node.id, {
      data: {
        ...node.data,
        config,
        label: config.label || node.data.label || nodeTypeDef.label,
      },
    })

    onClose()
  }

  const renderField = (field: ConfigField) => {
    const value = config[field.name] ?? field.defaultValue ?? ''
    const error = errors[field.name]
    const options = field.name === 'sourceId' 
      ? sourceOptions 
      : field.name === 'destinationId'
      ? destinationOptions
      : field.options || []

    switch (field.type) {
      case 'text':
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            className={`w-full px-3 py-2 border rounded-md ${
              error ? 'border-red-500' : 'border-gray-300'
            }`}
          />
        )
      
      case 'number':
        return (
          <input
            type="number"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value ? Number(e.target.value) : null)}
            placeholder={field.placeholder}
            className={`w-full px-3 py-2 border rounded-md ${
              error ? 'border-red-500' : 'border-gray-300'
            }`}
          />
        )
      
      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className={`w-full px-3 py-2 border rounded-md ${
              error ? 'border-red-500' : 'border-gray-300'
            }`}
          >
            <option value="">Select...</option>
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )
      
      case 'textarea':
        return (
          <textarea
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            rows={3}
            className={`w-full px-3 py-2 border rounded-md ${
              error ? 'border-red-500' : 'border-gray-300'
            }`}
          />
        )
      
      case 'checkbox':
        return (
          <input
            type="checkbox"
            checked={value}
            onChange={(e) => handleFieldChange(field.name, e.target.checked)}
            className="w-4 h-4"
          />
        )
      
      case 'json':
        return (
          <textarea
            value={typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value)
                handleFieldChange(field.name, parsed)
              } catch {
                handleFieldChange(field.name, e.target.value)
              }
            }}
            placeholder={field.placeholder}
            rows={6}
            className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
              error ? 'border-red-500' : 'border-gray-300'
            }`}
          />
        )
      
      default:
        return null
    }
  }

  return (
    <div className="w-80 bg-white border-l border-gray-200 h-full flex flex-col shadow-lg">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">{nodeTypeDef.label}</h3>
            <p className="text-xs text-gray-500 mt-1">{nodeTypeDef.description}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Configuration Form */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {nodeTypeDef.configSchema.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              {renderField(field)}
              {errors[field.name] && (
                <p className="text-xs text-red-500 mt-1">{errors[field.name]}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 flex gap-2">
        <button
          onClick={onClose}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
        >
          Save
        </button>
      </div>
    </div>
  )
}

