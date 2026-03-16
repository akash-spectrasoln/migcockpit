# Navigation Flow - Visual Guide

## Application Navigation Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION ENTRY                         │
│                    http://localhost:3000                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Route Check        │
              │   (React Router)    │
              └──────────┬───────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   /login          /canvas          /jobs
   (Public)      (Protected)      (Protected)
        │                │                │
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Login Page  │  │ Canvas Page  │  │  Jobs Page   │
└──────┬───────┘  └──────┬───────┘  └──────┬──────┘
       │                 │                  │
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                    (Navigation)
```

## Detailed Page Flows

### 1. Login Page Flow

```
┌─────────────────────────────────────┐
│         LOGIN PAGE                  │
│  ┌──────────────────────────────┐   │
│  │  Email Input                 │   │
│  │  Password Input              │   │
│  │  [Login Button]              │   │
│  └──────────────────────────────┘   │
└──────────────┬──────────────────────┘
               │
               │ User submits form
               ▼
        ┌──────────────┐
        │ POST /api-   │
        │ login/       │
        └──────┬───────┘
               │
        ┌──────┴───────┐
        │              │
        ▼ Success      ▼ Failure
   ┌─────────┐    ┌──────────┐
   │ Store   │    │ Show     │
   │ Tokens  │    │ Error    │
   └────┬────┘    └──────────┘
        │
        ▼
   ┌──────────────┐
   │ Navigate to  │
   │ /canvas      │
   └──────────────┘
```

### 2. Canvas Page Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    CANVAS PAGE                              │
│  ┌──────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │  Header  │  │                      │  │              │  │
│  │ [Jobs]  │  │                      │  │ Configuration│  │
│  │ [Logout]│  │    Canvas Area       │  │    Panel     │  │
│  └──────────┘  │  (React Flow)       │  │  (when node  │  │
│                │                      │  │  selected)   │  │
│  ┌──────────┐  │  - Nodes             │  └──────────────┘  │
│  │   Node   │  │  - Edges             │                    │
│  │  Palette │  │  - Connections       │                    │
│  │          │  │                      │                    │
│  │ [Source]│  │                      │                    │
│  │[Transform│  │                      │                    │
│  │[Dest]    │  │                      │                    │
│  └──────────┘  └──────────────────────┘                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Toolbar: [Design] [Validate] [Monitor] [Save]      │  │
│  │           [Validate] [Execute] [Delete]              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
    Add Node            Configure Node         Execute Job
         │                    │                    │
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Save Canvas    │
                    │  to Database    │
                    └─────────────────┘
```

### 3. Jobs Page Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    JOBS PAGE                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Header: [Back to Canvas] [Logout]                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Toolbar: [Filters] [Refresh]                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │   Jobs List Table    │  │   Job Details Sidebar    │   │
│  │                      │  │  (when job selected)     │   │
│  │  - Job ID            │  │                          │   │
│  │  - Canvas Name       │  │  - Job ID                │   │
│  │  - Status            │  │  - Status                │   │
│  │  - Progress          │  │  - Progress              │   │
│  │  - Created Date      │  │  - Current Step          │   │
│  │  - Actions           │  │  - Statistics           │   │
│  │                      │  │  - Logs (real-time)      │   │
│  └──────────────────────┘  └──────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  WebSocket Connection (for running jobs)             │   │
│  │  - Real-time status updates                          │   │
│  │  - Per-node progress                                 │   │
│  │  - Log streaming                                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
    Select Job          Cancel Job          Back to Canvas
         │                    │                    │
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Update UI      │
                    │  Real-Time      │
                    └─────────────────┘
```

## User Journey Examples

### Example 1: First-Time User

```
1. Opens app → No token → Login Page
2. Enters credentials → Login → Canvas Page
3. Sees empty canvas
4. Drags "MySQL Source" → Configures connection
5. Drags "Data Mapping" → Configures mappings
6. Drags "SAP HANA" → Configures destination
7. Connects nodes: Source → Transform → Destination
8. Clicks "Save" → Canvas saved
9. Clicks "Validate" → Validation passes
10. Clicks "Execute" → Job starts
11. Navigates to "Jobs" → Monitors progress
12. Job completes → Returns to Canvas
```

### Example 2: Returning User

```
1. Opens app → Has valid token → Canvas Page
2. Canvas loads with previous configuration
3. Modifies existing pipeline
4. Saves changes
5. Executes migration
6. Monitors in Jobs page
```

### Example 3: Monitoring Multiple Jobs

```
1. User on Canvas Page
2. Clicks "Jobs" button → Jobs Page
3. Sees list of all jobs
4. Filters by "Running" status
5. Selects a job → Sees details and logs
6. WebSocket provides real-time updates
7. Job completes → Status updates automatically
8. Returns to Canvas to create new pipeline
```

## Component Interaction Flow

```
┌──────────────┐
│  LoginPage   │
└──────┬───────┘
       │ uses
       ▼
┌──────────────┐
│  authStore   │
│  (Zustand)   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  CanvasPage  │
└──────┬───────┘
       │ uses
       ├───► authStore (check auth)
       ├───► canvasStore (canvas state)
       └───► canvasApi (load/save)
              │
              ▼
       ┌──────────────┐
       │ EnhancedData │
       │ FlowCanvas   │
       └──────┬───────┘
              │ uses
              ├───► canvasStore (nodes/edges)
              ├───► NodePalette (drag nodes)
              ├───► NodeConfigurationPanel (configure)
              └───► wsService (real-time updates)
                     │
                     ▼
              ┌──────────────┐
              │  JobsPage    │
              └──────┬───────┘
                     │ uses
                     ├───► migrationApi (job operations)
                     ├───► wsService (real-time updates)
                     └───► canvasStore (node status)
```

## Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│              AUTHENTICATION FLOW                        │
└─────────────────────────────────────────────────────────┘

User Action          Frontend              Backend
    │                   │                     │
    │─── Login ─────────►│                     │
    │                   │─── POST /api-login/ ──►│
    │                   │                     │─── Validate Credentials
    │                   │                     │─── Generate JWT Tokens
    │                   │◄─── {access, refresh} ──│
    │                   │                     │
    │                   │─── Store in localStorage
    │                   │─── Set isAuthenticated = true
    │                   │
    │◄─── Navigate to /canvas ────│
    │
    │─── Access Canvas ──►│
    │                   │─── Check token in localStorage
    │                   │─── Verify token (API call)
    │                   │◄─── Token valid
    │                   │─── Render Canvas
    │
    │─── API Request ────►│
    │                   │─── Add Bearer token to header
    │                   │─── POST /api/canvas/ ──►│
    │                   │                     │─── Validate JWT
    │                   │                     │─── Process request
    │                   │◄─── Response ────────│
    │
    │─── Token Expires ──►│
    │                   │─── 401 Response
    │                   │─── Use refresh token
    │                   │─── POST /api-refresh/ ──►│
    │                   │                     │─── Validate refresh token
    │                   │                     │─── New access token
    │                   │◄─── {access} ────────│
    │                   │─── Update token
    │                   │─── Retry original request
    │
    │─── Logout ────────►│
    │                   │─── Clear localStorage
    │                   │─── Set isAuthenticated = false
    │                   │─── Navigate to /login
```

## Canvas Workflow States

```
┌─────────────────────────────────────────────────────────┐
│              CANVAS WORKFLOW STATES                      │
└─────────────────────────────────────────────────────────┘

INITIAL STATE
    │
    ▼
┌──────────────┐
│ Empty Canvas │
└──────┬───────┘
       │
       │ User adds nodes
       ▼
┌──────────────┐
│ Nodes Added  │
│ (Unconfigured)│
└──────┬───────┘
       │
       │ User configures nodes
       ▼
┌──────────────┐
│ Nodes        │
│ Configured   │
└──────┬───────┘
       │
       │ User connects nodes
       ▼
┌──────────────┐
│ Pipeline     │
│ Connected    │
└──────┬───────┘
       │
       │ User saves
       ▼
┌──────────────┐
│ Canvas Saved │
└──────┬───────┘
       │
       │ User validates
       ▼
┌──────────────┐
│ Pipeline     │
│ Validated    │
└──────┬───────┘
       │
       │ User executes
       ▼
┌──────────────┐
│ Job Running  │
│ (Real-time   │
│  updates)    │
└──────┬───────┘
       │
       │ Job completes
       ▼
┌──────────────┐
│ Job Complete │
└──────────────┘
```

## Navigation Matrix

| From Page | To Page | Trigger | Condition |
|-----------|---------|---------|-----------|
| Login | Canvas | Login Success | Valid credentials |
| Login | Login | Login Failure | Invalid credentials |
| Canvas | Jobs | Click "Jobs" button | Always |
| Canvas | Login | Click "Logout" | Always |
| Jobs | Canvas | Click "Back to Canvas" | Always |
| Jobs | Login | Click "Logout" | Always |
| Any | Login | Token invalid/expired | Auto redirect |
| Any | Login | Not authenticated | Protected route |

## State Transitions

```
Authentication State:
  Not Authenticated ──[Login Success]──► Authenticated
  Authenticated ──[Logout]──► Not Authenticated
  Authenticated ──[Token Expired]──► Not Authenticated

Canvas State:
  Empty ──[Add Node]──► Has Nodes
  Has Nodes ──[Configure]──► Configured
  Configured ──[Connect]──► Connected
  Connected ──[Save]──► Saved
  Saved ──[Validate]──► Validated
  Validated ──[Execute]──► Executing

Job State:
  Pending ──[Start]──► Running
  Running ──[Complete]──► Completed
  Running ──[Error]──► Failed
  Running ──[Cancel]──► Cancelled
```

This comprehensive flow documentation shows exactly how users navigate through the application from login to canvas operations to job monitoring!

