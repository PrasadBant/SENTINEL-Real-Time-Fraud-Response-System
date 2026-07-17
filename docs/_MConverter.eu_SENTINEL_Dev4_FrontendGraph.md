**SENTINEL**

Real-Time Fraud Response System

**FRONTEND DEV (GRAPH)**

**Dev 4**

*Graph View · Action Panel · Timer UI · Cytoscape.js*

|                 |                     |
|-----------------|---------------------|
| **Time Budget** | **\~16 hrs active** |

Hackathon Edition \| 19-Hour Build \| Version 2.0

**Role Overview**

As Frontend Developer (Graph), you own the most visually impressive screens of the demo --- the live money-flow graph and the real-time action panel. These are the screens that make judges say \'wow\'. You work in parallel with Dev 3 and build on the shared component library they establish.

**Screens You Own**

- Screen 3 --- Graph View: live Cytoscape.js directed graph per case (US-03)

- Screen 4 --- Action Panel: persistent sidebar with top-3 cases, one-click actions, action log stream

- Supporting: Golden Timer animations, Recoverable Amount progress bar

**19-Hour Timeline**

|                 |                               |                                                                                                                                                                                                                                 |            |
|-----------------|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|
| **Hours**       | **Phase**                     | **Tasks**                                                                                                                                                                                                                       | **Status** |
| **0 -- 2 hr**   | **Team Setup**                | Join React project setup. Install Cytoscape.js: npm install cytoscape. Explore Cytoscape.js docs for live node/edge updates. Review all data models (Case, AccountNode, ActionLog) so you understand graph shape.               | 🟡 Setup   |
| **2 -- 10 hr**  | **Graph + Panel (Mock Data)** | Build Screen 3 Graph View with mock static graph data (no backend yet). Build Screen 4 Action Panel with mock case list. Focus on: Cytoscape layout, node styling by status, edge labels, freeze animation, recovery bar.       | 🟢 Active  |
| **10 -- 14 hr** | **Live Integration**          | Connect Graph View to GET /graph/:caseId. Animate new nodes/edges as case_updated WS events arrive (within 2s --- US-03 AC2). Wire Action Panel to priority queue from useWebSocket() hook (Dev 3\'s hook).                     | 🟢 Active  |
| **14 -- 17 hr** | **Actions + Polish**          | Wire Freeze/Flag/Alert Police buttons to backend POST /action/\* endpoints. Show inline ACK confirmation per action. Update frozen nodes visually (grey + lock icon) without full graph re-render. Animate recovery bar update. | 🟢 Active  |
| **17 -- 19 hr** | **E2E + Demo Polish**         | Full demo walk-through. Fix graph animation glitches. Ensure frozen node styling is pixel-perfect. Validate recovery % updates within 1s of freeze (US-04 AC4). Check parallel case independence.                               | 🔵 Collab  |

**Screen 3 --- Graph View**

**Cytoscape.js Setup**

|                                                                         |
|-------------------------------------------------------------------------|
| Library: Cytoscape.js (cytoscape npm package)                           
 Layout: dagre or breadthfirst --- both work well for directed chains     
 Do NOT use D3.js for the graph --- Cytoscape is already decided.         
 Max nodes per case: 5 hops (capped by backend). No performance concern.  |

**Node Styling by Status**

|            |                   |                     |                  |
|------------|-------------------|---------------------|------------------|
| **Status** | **Fill Color**    | **Border**          | **Label / Icon** |
| active     | \#3B82F6 (Blue)   | 2px solid \#1D4ED8  | Account ID       |
| frozen     | \#9CA3AF (Grey)   | 2px solid \#6B7280  | Account ID + 🔒  |
| flagged    | \#F97316 (Orange) | 2px solid \#EA580C  | Account ID + ⚠   |
| withdrawn  | \#EF4444 (Red)    | 2px dashed \#B91C1C | Account ID + ✗   |

**Edge Styling**

- Directed arrows on all edges (→ direction of fund flow)

- Edge label: ₹ amount + transaction timestamp (e.g. \'₹2,00,000 · 14:32\')

- Edge color: \#6B7280 (grey) for normal; \#EF4444 (red) for HIGH_RISK case edges

**Animation Requirements**

- New hop: new node + edge animate in with fade + scale-up (0.3s transition)

- Freeze action: node transitions grey smoothly (0.4s color animation) --- do NOT full re-render

- All animations must complete within 2 seconds of WS event (US-03 AC2)

|                                                                                                                   |
|-------------------------------------------------------------------------------------------------------------------|
| Use cy.batch() when adding multiple nodes/edges at once to avoid multiple re-renders and ensure the 2-second SLA. |

**Graph View Side Panel**

A side panel sits alongside the Cytoscape canvas and shows:

|                   |                                                                                                    |
|-------------------|----------------------------------------------------------------------------------------------------|
| **Panel Section** | **Content**                                                                                        |
| Recovery Bar      | Recharts progress bar: Frozen ₹X \| In-Flight ₹Y \| Lost ₹Z. Updates within 1s of any freeze.      |
| Chain Stats       | Case ID \| Status badge \| Chain depth \| Origin account \| Golden Timer countdown                 |
| Per-Node Actions  | For each node in chain: \[Freeze\] \[Flag\] buttons. Show node status. Disabled if already frozen. |
| Case Selector     | Dropdown to switch between active cases (when multiple exist). Auto-selects highest urgency case.  |

**Screen 4 --- Action Panel**

The Action Panel is a persistent right sidebar visible on both Screen 2 (Alert Dashboard) and Screen 3 (Graph View). It surfaces top-3 urgent cases at all times.

**Top-3 Urgent Cases Section**

- Show top 3 cases sorted by urgency_score (from useWebSocket() hook state)

- Each case shows: Case ID, Risk Score badge, Golden Timer (colour-coded)

- Per case: 3 action buttons --- \[Freeze Lead Node\] \[Flag Number\] \[Alert Police\]

- After action: show inline confirmation --- e.g. \'Bank_B ACK --- ₹1.85L frozen \[120ms\]\'

- Confirmation message stays for 5 seconds then fades

**Action Log Stream Section**

- Scrollable list of latest 20 action events

- Each entry: timestamp \| action type \| target \| status (ACK/NACK) \| latency_ms

- New entries slide in from top; oldest slide off the bottom

- Color code: ACK = green text, NACK = red text

|                                                                                                                                                       |
|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| The Action Log is used by the presenter to prove the audit trail works. Make sure it is always visible and updating in real time throughout the demo. |

**Action Button --- API Call**

When an action button is clicked, POST to the relevant endpoint:

|                  |                     |                                                    |
|------------------|---------------------|----------------------------------------------------|
| **Button**       | **Endpoint**        | **Request Body**                                   |
| Freeze Lead Node | POST /action/freeze | { case_id, account_id, actor_role: \"analyst\" }   |
| Flag Number      | POST /action/flag   | { case_id, phone_number, actor_role: \"analyst\" } |
| Alert Police     | POST /action/alert  | { case_id, actor_role: \"analyst\" }               |

- Show loading spinner on button while awaiting response

- On 422 (already frozen): show \'Already frozen\' message in amber --- do not crash

- On success: ACK confirmation inline + action_taken WS event updates the log stream

**Integration Points with Dev 3**

|                         |                                 |                             |
|-------------------------|---------------------------------|-----------------------------|
| **You Need From Dev 3** | **Component / Hook**            | **Available By**            |
| Real-time case state    | useWebSocket() hook             | Hour 10 (live backend)      |
| Golden Timer component  | \<GoldenTimer minutes={n} /\>   | Hour 2--4 (mock data phase) |
| Risk badge component    | \<RiskBadge score={n} /\>       | Hour 2--4 (mock data phase) |
| Action button component | \<ActionButton /\> or build own | Hour 4--6                   |

|                                                                                                                                                                                            |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Until Hour 10: use hardcoded mock graph data for the Cytoscape graph. A static JSON with 3 nodes and 2 edges is enough to build and test all visual features. Don\'t wait for the backend. |

**Deliverables Checklist**

- Cytoscape.js installed and canvas rendering without errors

- Graph View: nodes rendered with correct colours for all 4 status values

- Graph View: directed edges with ₹ amount + timestamp labels

- Graph View: new node/edge animation within 2 seconds of WS event

- Graph View: frozen node transitions grey + lock icon without full re-render

- Graph View side panel: recovery bar, chain stats, per-node action buttons

- Action Panel: top-3 cases from urgency queue, all 3 action buttons

- Action Panel: inline ACK/NACK confirmation with latency display

- Action Panel: scrollable action log stream, 20 latest events, colour-coded

- All buttons disabled appropriately (already frozen → disabled)

- Recovery bar updates within 1 second of freeze action (US-04 AC4)

- EC-02: late detection --- graph backfills chain retroactively, renders correctly

- EC-03: partial recovery --- withdrawn nodes shown in red with \'Lost\' label

|                                                                                                                                                                                                                                         |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 🎯 Demo moment: The presenter clicks \'Freeze \#2001\' and the judge watches the node turn grey with a lock icon, the recovery bar jump from ₹0 to ₹1.85L, and the action log update --- all within 1 second. Make this moment perfect. |
