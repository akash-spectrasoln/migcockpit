/**
 * Filter Configuration Panel Component
 * Allows users to define filter conditions with multiple operators and logical connections
 */
import React, { useState, useEffect } from 'react'
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Select,
  Input,
  IconButton,
  Alert,
  AlertIcon,
  useColorModeValue,
  FormControl,
  FormLabel,
  Textarea,
} from '@chakra-ui/react'
import { Plus, X, CheckCircle, Trash2 } from 'lucide-react'
import { Node } from 'reactflow'

interface FilterCondition {
  id: string
  column: string
  operator: string
  value: any
  logicalOperator?: 'AND' | 'OR'
}

interface FilterConfigPanelProps {
  node: Node | null
  onUpdate: (nodeId: string, config: any) => void
}

const operators = [
  { value: '=', label: 'Equals (=)' },
  { value: '!=', label: 'Not Equals (!=)' },
  { value: '>', label: 'Greater Than (>)' },
  { value: '<', label: 'Less Than (<)' },
  { value: '>=', label: 'Greater or Equal (>=)' },
  { value: '<=', label: 'Less or Equal (<=)' },
  { value: 'LIKE', label: 'Contains (LIKE)' },
  { value: 'ILIKE', label: 'Contains (Case Insensitive)' },
  { value: 'IN', label: 'In List (IN)' },
  { value: 'NOT IN', label: 'Not In List (NOT IN)' },
  { value: 'IS NULL', label: 'Is Null' },
  { value: 'IS NOT NULL', label: 'Is Not Null' },
]

const valueOperators = ['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'IN', 'NOT IN']
const noValueOperators = ['IS NULL', 'IS NOT NULL']

export const FilterConfigPanel: React.FC<FilterConfigPanelProps> = ({ node, onUpdate }) => {
  const [conditions, setConditions] = useState<FilterCondition[]>([])
  const [availableColumns, setAvailableColumns] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [previewCount, setPreviewCount] = useState<number | null>(null)

  const bg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.700')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  useEffect(() => {
    if (node) {
      const config = node.data.config || {}
      setConditions(config.conditions || [])

      // Load available columns from input node
      loadAvailableColumns()
    }
  }, [node])

  const loadAvailableColumns = async () => {
    if (!node) return

    // Find input node (connected to this filter node)
    // For now, we'll need to get columns from the source node
    // This will be enhanced when we have proper node connection tracking
    try {
      // TODO: Get columns from connected input node
      // For now, use empty array
      setAvailableColumns([])
    } catch (err: any) {
      setError(err.message || 'Failed to load columns')
    }
  }

  const addCondition = () => {
    const newCondition: FilterCondition = {
      id: `condition-${Date.now()}`,
      column: '',
      operator: '=',
      value: '',
      logicalOperator: conditions.length > 0 ? 'AND' : undefined,
    }
    setConditions([...conditions, newCondition])
  }

  const removeCondition = (id: string) => {
    setConditions(conditions.filter((c) => c.id !== id))
  }

  const updateCondition = (id: string, updates: Partial<FilterCondition>) => {
    setConditions(
      conditions.map((c) => (c.id === id ? { ...c, ...updates } : c))
    )
  }

  const handleSave = () => {
    if (!node) return

    // Validate conditions
    const validConditions = conditions.filter(
      (c) => c.column && c.operator && (noValueOperators.includes(c.operator) || c.value !== '')
    )

    if (validConditions.length === 0) {
      setError('At least one valid condition is required')
      return
    }

    const config = {
      ...node.data.config,
      conditions: validConditions,
    }

    // SCHEMA PROPAGATION: Filter must be schema-transparent
    // Copy input schema to output_metadata
    let outputMetadata = null

    // Get input node schema from node.data.input_nodes or edges
    // This requires access to nodes and edges - we need to add them as props
    // For now, preserve existing output_metadata if it exists
    if (node.data.output_metadata) {
      outputMetadata = node.data.output_metadata
    }

    onUpdate(node.id, {
      config: config,
      output_metadata: outputMetadata
    })
    setError(null)
  }



  const handleClear = () => {
    if (!node) return

    // Clear all filter conditions
    setConditions([])
    setPreviewCount(null)
    setError(null)

    // Reset node to pass-through mode
    // Remove filter config and preserve only upstream schema
    onUpdate(node.id, {
      config: {
        conditions: []
      },
      output_metadata: null  // Will be re-populated from upstream on next execution
    })
  }

  if (!node) {
    return (
      <Box
        w="320px"
        h="100%"
        bg={bg}
        borderLeftWidth="1px"
        borderColor={borderColor}
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <Text fontSize="sm" color={useColorModeValue('gray.500', 'gray.400')}>
          Select a filter node to configure
        </Text>
      </Box>
    )
  }

  return (
    <Box
      w="320px"
      h="100%"
      bg={bg}
      borderLeftWidth="1px"
      borderColor={borderColor}
      display="flex"
      flexDirection="column"
      overflow="hidden"
    >
      {/* Header */}
      <Box p={4} borderBottomWidth="1px" borderColor={borderColor} bg={headerBg}>
        <HStack justify="space-between" align="center" mb={2}>
          <Text fontSize="lg" fontWeight="semibold">
            Filter Configuration
          </Text>
          <HStack spacing={2}>
            <Button
              leftIcon={<Trash2 size={16} />}
              size="sm"
              variant="ghost"
              colorScheme="red"
              onClick={handleClear}
            >
              Clear
            </Button>
            <Button
              leftIcon={<CheckCircle size={16} />}
              size="sm"
              colorScheme="green"
              onClick={handleSave}
            >
              Save
            </Button>
          </HStack>
        </HStack>
        <Text fontSize="xs" color="gray.500">
          {node.data.label || 'Filter Node'}
        </Text>
      </Box>

      {/* Content */}
      <Box flex={1} overflowY="auto" p={4}>
        {error && (
          <Alert status="error" size="sm" mb={4}>
            <AlertIcon />
            <Text fontSize="sm">
              {typeof error === 'string'
                ? error
                : (() => {
                    try {
                      return JSON.stringify(error)
                    } catch {
                      return 'An unexpected error occurred'
                    }
                  })()}
            </Text>
          </Alert>
        )}

        {previewCount !== null && (
          <Alert status="info" size="sm" mb={4}>
            <AlertIcon />
            <Text fontSize="sm">
              Filtered rows: <strong>{previewCount.toLocaleString()}</strong>
            </Text>
          </Alert>
        )}

        <VStack align="stretch" spacing={4}>
          {conditions.length === 0 ? (
            <Box textAlign="center" py={8}>
              <Text fontSize="sm" color="gray.500" mb={4}>
                No filter conditions defined
              </Text>
              <Button
                leftIcon={<Plus />}
                size="sm"
                colorScheme="blue"
                onClick={addCondition}
              >
                Add Condition
              </Button>
            </Box>
          ) : (
            <>
              {conditions.map((condition, index) => (
                <Box key={condition.id}>
                  {index > 0 && (
                    <HStack mb={2}>
                      <Select
                        size="sm"
                        value={condition.logicalOperator || 'AND'}
                        onChange={(e) =>
                          updateCondition(condition.id, {
                            logicalOperator: e.target.value as 'AND' | 'OR',
                          })
                        }
                        w="80px"
                      >
                        <option value="AND">AND</option>
                        <option value="OR">OR</option>
                      </Select>
                      <Text fontSize="xs" color="gray.500">
                        (previous condition)
                      </Text>
                    </HStack>
                  )}

                  <Box
                    p={3}
                    borderWidth="1px"
                    borderColor={borderColor}
                    borderRadius="md"
                  >
                    <VStack align="stretch" spacing={2}>
                      <HStack justify="space-between">
                        <Text fontSize="sm" fontWeight="semibold">
                          Condition {index + 1}
                        </Text>
                        <IconButton
                          aria-label="Remove condition"
                          icon={<X size={14} />}
                          size="xs"
                          variant="ghost"
                          colorScheme="red"
                          onClick={() => removeCondition(condition.id)}
                        />
                      </HStack>

                      <FormControl>
                        <FormLabel fontSize="xs">Column</FormLabel>
                        <Select
                          size="sm"
                          value={condition.column}
                          onChange={(e) =>
                            updateCondition(condition.id, { column: e.target.value })
                          }
                          placeholder="Select column"
                        >
                          {availableColumns.map((col) => (
                            <option key={col} value={col}>
                              {col}
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      <FormControl>
                        <FormLabel fontSize="xs">Operator</FormLabel>
                        <Select
                          size="sm"
                          value={condition.operator}
                          onChange={(e) =>
                            updateCondition(condition.id, {
                              operator: e.target.value,
                              value: noValueOperators.includes(e.target.value) ? null : '',
                            })
                          }
                        >
                          {operators.map((op) => (
                            <option key={op.value} value={op.value}>
                              {op.label}
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      {valueOperators.includes(condition.operator) && (
                        <FormControl>
                          <FormLabel fontSize="xs">
                            Value
                            {condition.operator === 'IN' || condition.operator === 'NOT IN' ? (
                              <Text as="span" fontSize="xs" color="gray.500" ml={1}>
                                (comma-separated)
                              </Text>
                            ) : null}
                          </FormLabel>
                          {condition.operator === 'IN' || condition.operator === 'NOT IN' ? (
                            <Textarea
                              size="sm"
                              value={Array.isArray(condition.value) ? condition.value.join(', ') : condition.value || ''}
                              onChange={(e) => {
                                const value = e.target.value
                                const values = value.split(',').map((v) => v.trim()).filter((v) => v)
                                updateCondition(condition.id, { value: values.length > 1 ? values : value })
                              }}
                              placeholder="Enter values separated by commas"
                              rows={2}
                            />
                          ) : (
                            <Input
                              size="sm"
                              type={condition.operator === '>' || condition.operator === '<' || condition.operator === '>=' || condition.operator === '<=' ? 'number' : 'text'}
                              value={condition.value || ''}
                              onChange={(e) =>
                                updateCondition(condition.id, { value: e.target.value })
                              }
                              placeholder="Enter value"
                            />
                          )}
                        </FormControl>
                      )}
                    </VStack>
                  </Box>
                </Box>
              ))}

              <Button
                leftIcon={<Plus />}
                size="sm"
                variant="outline"
                onClick={addCondition}
              >
                Add Condition
              </Button>
            </>
          )}
        </VStack>
      </Box>
    </Box>
  )
}

