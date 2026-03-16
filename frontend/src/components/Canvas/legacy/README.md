# Legacy Canvas Components

This directory contains the original Tailwind CSS-based canvas components that have been replaced by Chakra UI versions.

## Files

- **DataFlowCanvas.tsx** - Original canvas component (Tailwind)
- **EnhancedDataFlowCanvas.tsx** - Enhanced canvas with state management (Tailwind)
- **NodePalette.tsx** - Original node palette (Tailwind)
- **NodeConfigurationPanel.tsx** - Original config panel (Tailwind)
- **NodeTypes.tsx** - Original node types (Tailwind)

## Current Implementation

All these components have been replaced by Chakra UI versions:
- `../DataFlowCanvasChakra.tsx` - Main canvas (Chakra UI)
- `../NodePaletteChakra.tsx` - Node palette (Chakra UI)
- `../NodeConfigPanelChakra.tsx` - Config panel (Chakra UI)
- `../NodeTypesChakra.tsx` - Node types (Chakra UI)

## Note

These files are kept for reference only. They are not used in the current implementation.

**Import Note:** These legacy files import `EdgeTypes` from the parent directory (`../EdgeTypes`) since it's still actively used.

