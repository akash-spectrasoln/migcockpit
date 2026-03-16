/**
 * DataFlowCanvas - Re-export from Chakra UI version
 * This file exists for backward compatibility
 * Use DataFlowCanvasChakra.tsx directly for new code
 */

// Re-export the Chakra UI version
export { EnhancedDataFlowCanvas as DataFlowCanvas } from './DataFlowCanvasChakra'

// Export the props interface for TypeScript
export interface DataFlowCanvasProps {
  canvasId?: number
  initialNodes?: any[]
  initialEdges?: any[]
  onSave?: (nodes: any[], edges: any[]) => void
}
