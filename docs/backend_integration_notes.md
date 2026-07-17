# Backend Integration Guide

This guide explains how to connect the SENTINEL frontend to a real backend.

## 1. REST API Integration
The abstraction layer is located in `src/services/dataProvider.js`.

**Steps:**
1. Set `USE_MOCK = false`.
2. Update `getTransactions`, `getCases`, and `getActions` to use `fetch` or `axios`.
3. Ensure the backend response matches the contracts defined in `docs/frontend_contracts.md`.
4. If the backend schema differs, implement normalization logic in `src/services/adapters/`.

## 2. WebSocket Integration
The WebSocket client logic should be integrated into `src/hooks/useWebSocket.js`.

**Integration Points:**
- Replace the `setInterval` simulation engine with a real `WebSocket` connection.
- Map incoming messages to the reducer actions:
    - `TX_SCORED`
    - `CASE_UPDATED`
    - `ACTION_TAKEN`
- Maintain the `initialState` initialization via the `dataProvider`.

## 3. Reducer Events
The state is managed via `src/hooks/useWebSocket.js` reducer.

**Action Mapping:**
- `EVENT_TYPES.TX_SCORED`: Used for live feed and risk trend analytics.
- `EVENT_TYPES.CASE_UPDATED`: Used for dashboard cards and investigation sidebar updates.
- `EVENT_TYPES.ACTION_TAKEN`: Used for the audit timeline and export system.

## 4. Graph Visualization
The graph in `src/pages/Graph.jsx` uses Cytoscape.js.

**Data Requirements:**
- The graph currently expects a static `mockGraphData` object.
- For integration, you should update `Graph.jsx` to fetch case-specific graph data (nodes and edges) from the backend based on the `caseId` parameter.

## 5. Security & Authentication
- Authentication is not currently implemented.
- Recommended: Wrap the `App` component in a `ProtectedProvider` and add an `authAdapter` to manage JWT or session tokens.
