import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useStore, startRealtime, stopRealtime } from './hooks/useWebSocket';

// Pages
import Feed from './pages/Feed';
import Dashboard from './pages/Dashboard';
import Cases from './pages/Cases';
import Graph from './pages/Graph';

import SystemStatusBar from './components/SystemStatusBar';
import AttackModeToggle from './components/AttackModeToggle';
import LiveAlertToast from './components/LiveAlertToast';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './components/Login';
import { getRole } from './roleStore';
import AICopilot from './components/AICopilot';
import { RoleProvider } from './RoleContext';

const App = () => {
  const connectionStatus = useStore((state) => state.connectionStatus);

  React.useEffect(() => {
    startRealtime();
    return () => {
      stopRealtime();
    };
  }, []);
  const role = getRole();

  if (!role) {
    return <Login />;
  }

  const handleLogout = () => {
    localStorage.removeItem("sentinel_role");
    window.location.reload();
  };

  return (
    <RoleProvider>
      <Router>
        <div className="flex min-h-screen bg-background text-foreground relative">
          <LiveAlertToast />
          <ErrorBoundary>
            <AICopilot />
          </ErrorBoundary>
          
          {/* Navigation Sidebar */}
          <aside className="w-72 border-r border-border bg-card/50 flex flex-col">
            <div className="p-6 space-y-4">
              <h2 className="text-xl font-bold tracking-tighter text-primary">SENTINEL</h2>
              <div className="px-3 py-1 rounded-full bg-primary/10 border border-primary/20 inline-block">
                <span className="text-[10px] font-black uppercase text-primary">Role: {role.toUpperCase()}</span>
              </div>
              <SystemStatusBar status={connectionStatus} />
              <AttackModeToggle />
            </div>
            
            <nav className="flex-1 px-4 space-y-2">
              <NavLink to="/feed" className={({ isActive }) => `block px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive ? 'bg-primary/20 text-primary shadow-sm' : 'hover:bg-muted'}`}>Real-time Feed</NavLink>
              <NavLink to="/dashboard" className={({ isActive }) => `block px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive ? 'bg-primary/20 text-primary shadow-sm' : 'hover:bg-muted'}`}>Analytics</NavLink>
              <NavLink to="/cases" className={({ isActive }) => `block px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive ? 'bg-primary/20 text-primary shadow-sm' : 'hover:bg-muted'}`}>Cases</NavLink>
            </nav>

            <div className="p-4 border-t border-border space-y-4">
              <button 
                onClick={handleLogout}
                className="w-full py-2 rounded-lg bg-muted hover:bg-muted/80 text-[10px] font-black uppercase tracking-widest transition-all"
              >
                Logout System
              </button>
              <div className="text-[10px] text-muted-foreground uppercase font-semibold text-center opacity-50">Phase 0 Foundational</div>
            </div>
          </aside>

          {/* Main Content Area */}
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Navigate to="/feed" replace />} />
              <Route path="/feed" element={<Feed />} />
              <Route path="/dashboard" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
              <Route path="/cases" element={<ErrorBoundary><Cases /></ErrorBoundary>} />
              <Route path="/graph/:caseId" element={<ErrorBoundary><Graph /></ErrorBoundary>} />
            </Routes>
          </main>
        </div>
      </Router>
    </RoleProvider>
  );
};

export default App;
