**SENTINEL**

Real-Time Fraud Response System

**FRONTEND LEAD**

**Dev 3**

*Live Feed · Alert Dashboard · Case List · WebSocket Integration*

|                 |                     |
|-----------------|---------------------|
| **Time Budget** | **\~16 hrs active** |

Hackathon Edition \| 19-Hour Build \| Version 2.0

**Role Overview**

As Frontend Lead, you own 3 of the 5 screens and the WebSocket integration layer. You establish the React project, design system, and component architecture that Dev 4 builds on top of. Your screens are the primary demo-facing interfaces --- judges will spend 80% of their attention here.

**Screens You Own**

- Screen 1 --- Live Transaction Feed (US-01, US-02)

- Screen 2 --- Alert Dashboard with urgency cards (US-06)

- Screen 5 --- Case List with filter, detail expand, JSON export (US-05)

- WebSocket integration --- all real-time state management

- Project setup --- React/Vite, routing, component library, global state

**19-Hour Timeline**

|                 |                          |                                                                                                                                                                                                                    |            |
|-----------------|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|
| **Hours**       | **Phase**                | **Tasks**                                                                                                                                                                                                          | **Status** |
| **0 -- 2 hr**   | **Team Setup**           | React/Vite project init. Install dependencies: shadcn/ui, Recharts, React Router. Set up project folder structure. Create mock data file (mock_data.js) for offline frontend dev.                                  | 🟡 Setup   |
| **2 -- 10 hr**  | **UI Shell + Mock Data** | Build all 5 screen layouts with mock static data. Do NOT wait for backend. Create reusable components: RiskBadge, GoldenTimer, CaseCard, ActionButton. Establish all routing and page transitions.                 | 🟢 Active  |
| **10 -- 14 hr** | **Live Integration**     | Replace mock data with live WebSocket connection. Build useWebSocket() custom hook. Wire up transaction feed to tx_scored events. Wire Alert Dashboard to case_updated events. Test with Dev 2\'s running backend. | 🟢 Active  |
| **14 -- 17 hr** | **Case List + Polish**   | Implement Screen 5 Case List: filter by status, row click for detail, JSON export button. Add header bar stats (tx/min, active cases, total at-risk). Fix all animation issues. Review with Dev 4.                 | 🟢 Active  |
| **17 -- 19 hr** | **E2E + Demo Polish**    | Full demo walkthrough. Fix UI bugs. Ensure all 5 screens transition correctly. Validate alert detail side panel opens/closes without state loss (US-02 AC4).                                                       | 🔵 Collab  |

**Screen Specifications**

**Screen 1 --- Live Transaction Feed**

This is the first screen shown in the demo. It must immediately impress with live streaming data.

**Table Columns**

|          |               |             |                       |            |                |
|----------|---------------|-------------|-----------------------|------------|----------------|
| **TxID** | **Timestamp** | **Channel** | **Sender → Receiver** | **Amount** | **Risk Score** |
| TX-001   | 14:32:00      | UPI         | ACC-1001 → ACC-2001   | ₹2,00,000  | 87 \[RED\]     |

**Risk Badge Colours**

- Score ≥ 70 → RED badge --- row highlight red (#FEE2E2)

- Score 40--69 → AMBER badge --- row highlight amber (#FEF3C7)

- Score \< 40 → GREEN badge --- no row highlight

**Behaviour Rules**

- Feed refreshes within 1 second of new WS event (US-01 AC1)

- New rows animate in from the top --- use CSS slide-down transition

- Maximum 100 rows; oldest rows scroll off without page reload

- Click any row → opens Alert Detail side panel (no page navigation)

- Header stats bar: tx/min rate \| active case count \| total at-risk ₹

|                                                                                                                                                                                                                 |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Alert Detail Side Panel must show: factor name, weight, triggered value, contribution. Factors in descending contribution order (US-02 AC1--AC3). Panel must close and return to feed WITHOUT state loss (AC4). |

**Screen 2 --- Alert Dashboard**

**Card Grid Specification**

|                |                                                                                                    |
|----------------|----------------------------------------------------------------------------------------------------|
| **Card Field** | **Display Rules**                                                                                  |
| Case ID        | Bold, monospace font, click to expand                                                              |
| Risk Score     | Coloured badge: red ≥70 / amber 40--69 / green \<40                                                |
| Chain Depth    | Number of hops, e.g. \'3 hops (A→B→C)\'                                                            |
| Fraud Amount   | ₹ formatted, e.g. ₹2,00,000                                                                        |
| Recoverable    | ₹ formatted + % e.g. ₹1,85,000 (92.5%)                                                             |
| Golden Timer   | Countdown MM:SS. Green \>15min / Amber 5--15min / Red \<5min. Timer expiry → MONITORING (no crash) |
| Quick Actions  | 3 buttons: \[Freeze Lead Node\] \[Alert Police\] \[Escalate\]                                      |

- Cards sorted descending by urgency_score from backend

- Click card → expands inline to show chain accounts + factor breakdown

- Queue updates on every case_updated WS event

**Screen 5 --- Case List**

**Table Columns**

- Case ID \| Status \| Risk Level \| Chain Depth \| Fraud Amount \| Recovery % \| Created At \| Actions

**Filter Bar**

- Status filter chips: ALL / NEW / HIGH_RISK / ACTIONED / MONITORING / CLOSED / CLOSED_FP

- Filter applies client-side --- no backend call needed

**Export Button**

- \'Export JSON\' button → downloads action_log\[\] from GET /actions/log as a .json file

- Filename: sentinel_audit\_{timestamp}.json

|                                                                                   |
|-----------------------------------------------------------------------------------|
| The JSON export is a key demo moment. Make sure it works reliably before Hour 17. |

**WebSocket Integration --- useWebSocket() Hook**

Build a custom React hook that Dev 4 can also import. This is the single source of truth for real-time state.

|                                                             |
|-------------------------------------------------------------|
| Hook API:                                                   
 useWebSocket(url: string)                                    
 Returns: { transactions, cases, actions, connectionStatus }  
 Events handled:                                              
 • tx_scored → prepend to transactions\[\], cap at 100        
 • case_updated → upsert case in cases\[\] by case_id         
 • action_taken → prepend to actions\[\]                      |

- On WS disconnect: activate HTTP polling every 2s against GET /cases (fallback)

- Show connection status indicator in header: 🟢 Live / 🟡 Polling / 🔴 Disconnected

**Component Library --- Reusable Components**

|                       |                                           |                                       |
|-----------------------|-------------------------------------------|---------------------------------------|
| **Component**         | **Props**                                 | **Used In**                           |
| \<RiskBadge /\>       | score: number                             | Feed row, Dashboard card, Case list   |
| \<GoldenTimer /\>     | minutes: number, onExpire: fn             | Dashboard card (Dev 4 also uses this) |
| \<CaseCard /\>        | case: CaseObject, onAction: fn            | Alert Dashboard                       |
| \<ActionButton /\>    | label, actionType, caseId, onComplete: fn | All action surfaces                   |
| \<FactorBreakdown /\> | factors: RiskFactor\[\]                   | Alert Detail panel, CaseCard expand   |

|                                                                                                                                         |
|-----------------------------------------------------------------------------------------------------------------------------------------|
| Share \<GoldenTimer /\> and \<RiskBadge /\> with Dev 4 immediately after Hour 2. Dev 4 needs these for the Graph View and Action Panel. |

**Deliverables Checklist**

- React/Vite project initialised, runs on localhost:5173

- All 5 screen layouts built (with mock data by Hour 10)

- useWebSocket() hook --- handles 3 event types, fallback polling

- Screen 1: Live Feed --- columns, row colours, 100-row cap, animations

- Screen 1: Alert Detail panel --- factor breakdown, no state loss on close

- Screen 2: Alert Dashboard --- cards, golden timer, quick actions, urgency sort

- Screen 5: Case List --- all columns, status filter, JSON export working

- Header stats bar showing tx/min, active cases, total at-risk

- Connection status indicator working (Live/Polling/Disconnected)

- All components shared with Dev 4 by Hour 10
