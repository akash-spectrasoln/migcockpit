# Data Migration Cockpit - Project Flowchart

## Complete Application Flow

```
═══════════════════════════════════════════════════════════════════════
                    APPLICATION START
═══════════════════════════════════════════════════════════════════════
                              │
                              ▼
                    ┌─────────────────┐
                    │  Check Auth     │
                    │  Token Exists?  │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │   NO TOKEN   │          │  HAS TOKEN   │
        │              │          │              │
        │  Redirect to │          │  Verify Token│
        │  Login Page  │          │  via API     │
        └──────┬───────┘          └──────┬───────┘
                │                         │
                │                         ├─── Invalid ──► Login
                │                         │
                │                         └─── Valid ──► Canvas
                │
                └─────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   LOGIN PAGE    │
                    │                 │
                    │  Email: [____]  │
                    │  Pass:  [____]  │
                    │  [Login Button] │
                    └────────┬────────┘
                             │
                             │ Submit
                             ▼
                    ┌─────────────────┐
                    │  POST /api-     │
                    │  login/         │
                    │  (Django API)   │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼ Success                 ▼ Failure
        ┌──────────────┐          ┌──────────────┐
        │ Store JWT    │          │ Show Error   │
        │ Tokens       │          │ Message      │
        │              │          └──────────────┘
        │ - access     │
        │ - refresh    │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │ Set Auth     │
        │ State = true │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │ Navigate to  │
        │ /canvas      │
        └──────┬───────┘
               │
               ▼
═══════════════════════════════════════════════════════════════════════
                    CANVAS PAGE
═══════════════════════════════════════════════════════════════════════
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌──────────┐  ┌──────────────┐  ┌──────────┐
        │   Node   │  │   Canvas     │  │ Config   │
        │  Palette │  │    Area      │  │  Panel   │
        │          │  │              │  │          │
        │ [Source] │  │  ┌──────┐    │  │ (Shows   │
        │[Transform│  │  │ Node │    │  │  when    │
        │[Dest]    │  │  └──┬───┘    │  │  node    │
        └────┬─────┘  │     │        │  │ selected)│
             │        │  ┌──▼───┐    │  └──────────┘
             │        │  │ Edge │    │
             │        │  └──────┘    │
             │        └──────────────┘
             │
             │ Drag & Drop
             ▼
        ┌──────────────┐
        │ Node Added   │
        │ to Canvas    │
        └──────┬───────┘
               │
               │ Click Node
               ▼
        ┌──────────────┐
        │ Open Config  │
        │ Panel        │
        └──────┬───────┘
               │
               │ Fill Form & Save
               ▼
        ┌──────────────┐
        │ Node         │
        │ Configured   │
        └──────┬───────┘
               │
               │ Connect Nodes
               ▼
        ┌──────────────┐
        │ Pipeline     │
        │ Connected    │
        └──────┬───────┘
               │
               │ Click "Save"
               ▼
        ┌──────────────┐
        │ POST /api/    │
        │ canvas/{id}/  │
        │ save-config/  │
        └──────┬───────┘
               │
               │ Click "Validate"
               ▼
        ┌──────────────┐
        │ POST /api/    │
        │ metadata/     │
        │ validate_     │
        │ pipeline/     │
        └──────┬───────┘
               │
               │ Click "Execute"
               ▼
═══════════════════════════════════════════════════════════════════════
                    MIGRATION EXECUTION
═══════════════════════════════════════════════════════════════════════
                              │
                              ▼
                    ┌─────────────────┐
                    │ POST /api/      │
                    │ migration-jobs/ │
                    │ execute/        │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Django Creates  │
                    │ MigrationJob    │
                    │ Record         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Call Migration  │
                    │ Service         │
                    │ (FastAPI :8003) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Build Pipeline  │
                    │ (Topological    │
                    │  Sort)          │
                    └────────┬────────┘
                             │
                             ▼
        ┌─────────────────────┴─────────────────────┐
        │                                             │
        ▼                                             ▼
┌──────────────┐                            ┌──────────────┐
│ SOURCE NODE  │                            │ TRANSFORM    │
│              │                            │ NODE         │
│ Extract Data │                            │              │
│ (Port 8001)  │──────Data──────►│ Transform Data │
│              │                            │ (Port 8002)  │
└──────────────┘                            └──────┬───────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │ DESTINATION  │
                                            │ NODE         │
                                            │              │
                                            │ Load to HANA │
                                            │ (Port 8003)  │
                                            └──────────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │ Broadcast    │
                                            │ Progress     │
                                            │ (WebSocket   │
                                            │  Port 8004)  │
                                            └──────┬───────┘
                                                   │
                                                   ▼
═══════════════════════════════════════════════════════════════════════
                    REAL-TIME MONITORING
═══════════════════════════════════════════════════════════════════════
                              │
                              ▼
                    ┌─────────────────┐
                    │ Frontend        │
                    │ Subscribes to   │
                    │ WebSocket       │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Update   │  │ Update   │  │ Update   │
        │ Job      │  │ Node     │  │ Canvas   │
        │ Status   │  │ Progress │  │ Node     │
        │          │  │          │  │ Status   │
        └──────────┘  └──────────┘  └──────────┘
                │            │            │
                └────────────┴────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Jobs Page       │
                    │ (or Canvas      │
                    │  Monitor View)  │
                    └─────────────────┘
```

## Simplified User Journey

```
┌─────────────────────────────────────────────────────────────┐
│                    USER JOURNEY                             │
└─────────────────────────────────────────────────────────────┘

1. START
   │
   ├─► Login Page
   │   │
   │   ├─► Enter Credentials
   │   │   │
   │   │   └─► Submit
   │   │       │
   │   │       └─► Django Validates
   │   │           │
   │   │           └─► Returns JWT Tokens
   │   │
   │   └─► Navigate to Canvas
   │
2. CANVAS PAGE
   │
   ├─► Load Existing Canvas (or Empty)
   │
   ├─► BUILD PIPELINE
   │   │
   │   ├─► Drag Source Node (MySQL/Oracle/SQL Server)
   │   │   └─► Configure: Connection, Table, Filters
   │   │
   │   ├─► Drag Transform Node (Map/Filter/Clean/Validate)
   │   │   └─► Configure: Rules, Mappings, Conditions
   │   │
   │   ├─► Drag Destination Node (SAP HANA)
   │   │   └─► Configure: Connection, Table, Load Mode
   │   │
   │   └─► Connect Nodes: Source → Transform → Destination
   │
   ├─► SAVE CANVAS
   │   └─► Stores to PostgreSQL Database
   │
   ├─► VALIDATE PIPELINE
   │   └─► Checks: Sources, Destinations, Configurations, Connectivity
   │
   └─► EXECUTE MIGRATION
       │
       └─► Creates Job & Starts Execution
           │
           └─► Navigate to Jobs Page (or Monitor View)
   
3. JOBS PAGE
   │
   ├─► View All Jobs (with Filters)
   │
   ├─► Select Job → See Details & Logs
   │
   ├─► Real-Time Updates via WebSocket
   │   │
   │   ├─► Job Status Updates
   │   ├─► Progress Updates
   │   ├─► Per-Node Status
   │   └─► Log Streaming
   │
   └─► Cancel Job (if running)
   
4. NAVIGATION
   │
   ├─► Canvas ←→ Jobs (via header buttons)
   │
   └─► Any Page → Logout → Login Page
```

## Component Hierarchy

```
App (React Router)
│
├─► LoginPage
│   └─► Uses: authStore.login()
│
├─► ProtectedRoute (Wrapper)
│   │
│   └─► Checks: authStore.isAuthenticated
│       │
│       ├─► CanvasPage
│       │   ├─► Uses: authStore, canvasStore, canvasApi
│       │   │
│       │   └─► EnhancedDataFlowCanvas
│       │       ├─► Uses: canvasStore (nodes, edges, selection)
│       │       ├─► NodePalette (left panel)
│       │       ├─► React Flow Canvas (center)
│       │       ├─► NodeConfigurationPanel (right panel)
│       │       └─► Toolbar (top)
│       │
│       └─► JobsPage
│           ├─► Uses: migrationApi, wsService, canvasStore
│           │
│           ├─► Job List Table
│           ├─► Filters Panel
│           └─► Job Details Sidebar
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW                                │
└─────────────────────────────────────────────────────────────┘

USER INPUT
    │
    ▼
┌──────────────┐
│  Frontend    │
│  (React)     │
└──────┬───────┘
       │
       ├─► State Management (Zustand)
       │   ├─► authStore
       │   └─► canvasStore
       │
       ├─► API Calls (Axios)
       │   ├─► canvasApi
       │   ├─► migrationApi
       │   └─► metadataApi
       │
       └─► WebSocket (Socket.IO)
           └─► wsService
               │
               ▼
┌──────────────┐
│  Django REST │
│  API (:8000) │
└──────┬───────┘
       │
       ├─► Authentication
       │   └─► JWT Token Management
       │
       ├─► Canvas CRUD
       │   └─► PostgreSQL Database
       │
       ├─► Migration Jobs
       │   ├─► Create Job Record
       │   └─► Call FastAPI Services
       │
       └─► Metadata
           └─► Query Source DBs
               │
               ▼
┌──────────────┐
│ FastAPI      │
│ Services     │
└──────┬───────┘
       │
       ├─► Extraction Service (:8001)
       │   └─► Extract from MySQL/Oracle/SQL Server
       │
       ├─► Transformation Service (:8002)
       │   └─► Transform Data
       │
       ├─► Migration Service (:8003)
       │   └─► Orchestrate Pipeline → Load to HANA
       │
       └─► WebSocket Server (:8004)
           └─► Broadcast Real-Time Updates
```

## Key Navigation Paths

```
Path 1: Login → Canvas
   Login Page
      │ (successful login)
      ▼
   Canvas Page
      │ (load canvas)
      ▼
   Build Pipeline
      │ (save)
      ▼
   Execute Job
      │ (navigate)
      ▼
   Jobs Page
      │ (monitor)
      ▼
   Job Complete
      │ (back)
      ▼
   Canvas Page

Path 2: Direct Canvas Access (with token)
   App Start
      │ (has valid token)
      ▼
   Canvas Page
      │ (load existing)
      ▼
   Continue Work

Path 3: Jobs → Canvas
   Jobs Page
      │ (click "Back to Canvas")
      ▼
   Canvas Page
      │ (create new pipeline)
      ▼
   Build & Execute
```

## Authentication & Authorization Flow

```
┌─────────────────────────────────────────────────────────────┐
│         AUTHENTICATION & AUTHORIZATION                       │
└─────────────────────────────────────────────────────────────┘

Request Flow:
    Frontend Request
         │
         ├─► Has Token?
         │   │
         │   ├─► NO ──► Redirect to /login
         │   │
         │   └─► YES ──► Add Bearer Token to Header
         │       │
         │       └─► Send to Django API
         │           │
         │           ├─► Token Valid?
         │           │   │
         │           │   ├─► NO ──► 401 Unauthorized
         │           │   │   │
         │           │   │   └─► Try Refresh Token
         │           │   │       │
         │           │   │       ├─► Refresh Success ──► Retry Request
         │           │   │       │
         │           │   │       └─► Refresh Fails ──► Logout → Login
         │           │   │
         │           │   └─► YES ──► Process Request
         │           │       │
         │           │       └─► Check Permissions
         │           │           │
         │           │           └─► Return Response
```

## Canvas Operations Flow

```
┌─────────────────────────────────────────────────────────────┐
│              CANVAS OPERATIONS                              │
└─────────────────────────────────────────────────────────────┘

Operation: Add Node
    Drag from Palette
         │
         ▼
    Drop on Canvas
         │
         ▼
    Node Created (with default config)
         │
         ▼
    Click Node
         │
         ▼
    Configuration Panel Opens
         │
         ▼
    Fill Configuration Form
         │
         ▼
    Save Configuration
         │
         ▼
    Node Updated in Canvas Store

Operation: Connect Nodes
    Drag from Source Node Output Handle
         │
         ▼
    Drop on Target Node Input Handle
         │
         ▼
    Edge Created
         │
         ▼
    Validation: Check if connection is valid
         │
         ▼
    Edge Added to Canvas Store

Operation: Save Canvas
    Click "Save" Button
         │
         ▼
    Collect Nodes & Edges from Store
         │
         ▼
    POST /api/canvas/{id}/save-configuration/
         │
         ▼
    Django Saves to Database
         │
         ▼
    Success Message Shown

Operation: Execute Migration
    Click "Execute" Button
         │
         ├─► Check Canvas Saved
         │   └─► Not Saved ──► Prompt to Save
         │
         ├─► Validate Pipeline
         │   └─► Has Errors ──► Show Errors
         │
         └─► All Checks Pass
             │
             ▼
         POST /api/migration-jobs/execute/
             │
             ▼
         Job Created & Started
             │
             ▼
         Subscribe to WebSocket
             │
             ▼
         Navigate to Monitor/Jobs
```

This flowchart provides a complete visual representation of how the application works from login through canvas operations to job monitoring!

