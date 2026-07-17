import { useMemo, useState, useCallback } from 'react';
import { useStore } from '../hooks/useWebSocket';
import CaseCard from '../components/CaseCard';
import InvestigationSidebar from '../components/InvestigationSidebar';
import { getRole } from '../roleStore';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  BarChart, Bar
} from 'recharts';

const Dashboard = () => {
  const cases = useStore((state) => state.cases);
  const actions = useStore((state) => state.actions);
  const transactions = useStore((state) => state.transactions);
  const [sidebarState, setSidebarState] = useState({ isOpen: false, caseId: null, tx: null });
  const role = getRole();

  // Urgency Score Logic: risk_level * (1 + 1 / max(golden_window_minutes, 1))
  const calculateUrgency = (caseData) => {
    const risk = caseData.risk_level;
    const window = Math.max(caseData.golden_window_minutes, 1);
    return risk * (1 + 1 / window);
  };

  // Sort cases by urgency_score (descending)
  const sortedCases = useMemo(
    () => [...cases].sort((a, b) => calculateUrgency(b) - calculateUrgency(a)),
    [cases]
  );

  const handleAnalyze = useCallback((c, tx) => {
    setSidebarState({ isOpen: true, caseId: c.case_id, tx });
  }, []);

  const activeCase = useMemo(() => {
    return sidebarState.caseId ? cases.find(c => c.case_id === sidebarState.caseId) : null;
  }, [cases, sidebarState.caseId]);

  const activeActions = useMemo(() => {
    return sidebarState.caseId ? actions.filter(a => a.case_id === sidebarState.caseId) : [];
  }, [actions, sidebarState.caseId]);

  // --- Analytics Data Preparation ---
  
  // 1. Risk Trend (Latest 20 transactions)
  const riskTrendData = useMemo(
    () => [...transactions].reverse().slice(-20).map((tx, idx) => ({
      name: idx,
      score: tx.risk_score,
      id: String(tx.tx_id || '').slice(-4)
    })),
    [transactions]
  );

  // 2. Channel Distribution
  const channels = ['UPI', 'IMPS', 'NEFT', 'CARD'];
  const channelData = useMemo(
    () => channels.map(name => ({
      name,
      value: transactions.filter(tx => tx.channel === name).length
    })),
    [transactions]
  );
  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

  // 3. Recovery Totals
  const totalFraud = useMemo(() => cases.reduce((sum, c) => sum + c.total_fraud_amount, 0), [cases]);
  const totalRecoverable = useMemo(() => cases.reduce((sum, c) => sum + c.recoverable_amount, 0), [cases]);
  const estimatedLoss = totalFraud - totalRecoverable;

  // 4. Risk Factor Frequency
  const factorData = useMemo(() => {
    const factorMap = {};
    transactions.forEach(tx => {
      tx.risk_factors?.forEach(f => {
        factorMap[f.name] = (factorMap[f.name] || 0) + 1;
      });
    });
    return Object.entries(factorMap)
      .map(([name, count]) => ({ name: name.replace(/_/g, ' '), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [transactions]);

  return (
    <div className="p-8 bg-background min-h-screen animate-in fade-in duration-500 overflow-x-hidden">
      <header className="mb-10">
        <h1 className="text-4xl font-black tracking-tighter uppercase italic text-primary">Alert Center</h1>
        <div className="flex items-center gap-4 mt-2">
          <span className="text-[10px] bg-red-500 text-white px-2 py-0.5 rounded-full font-bold">Priority View</span>
          <p className="text-xs text-muted-foreground font-medium">Cases sorted by recovery urgency and risk impact</p>
        </div>
      </header>

      {/* Case Grid */}
      <section className="mb-16">
        <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground mb-6">Active Investigations</h2>
        {sortedCases.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sortedCases.map((c) => (
              <CaseCard 
                key={c.case_id} 
                caseData={c} 
                onAnalyze={handleAnalyze}
                transactions={transactions}
                role={role}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-[50vh] border-2 border-dashed border-border rounded-3xl opacity-50">
            <span className="text-4xl mb-4">🛡️</span>
            <h2 className="text-xl font-bold uppercase tracking-widest">No active cases</h2>
            <p className="text-sm">The system is currently secure.</p>
          </div>
        )}
      </section>

      {/* Operational Intelligence Section */}
      <section className="mt-20 pt-16 border-t border-border/50">
        <header className="mb-12">
          <h2 className="text-3xl font-black tracking-tighter uppercase italic">Operational Intelligence</h2>
          <p className="text-xs text-muted-foreground mt-1">Live analytics and anomaly distribution</p>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
           {[
             { label: 'Total Exposure', value: `₹${(totalFraud/100000).toFixed(1)}L`, color: 'text-foreground' },
             { label: 'Recoverable', value: `₹${(totalRecoverable/100000).toFixed(1)}L`, color: 'text-green-500' },
             { label: 'Frozen Assets', value: `₹${(totalRecoverable * 0.8 / 100000).toFixed(1)}L`, color: 'text-blue-500' },
             { label: 'Estimated Loss', value: `₹${(estimatedLoss/100000).toFixed(1)}L`, color: 'text-red-500' },
           ].map((stat, i) => (
             <div key={i} className="bg-card/30 border border-border p-6 rounded-2xl shadow-sm">
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{stat.label}</span>
                <p className={`text-2xl font-black mt-1 ${stat.color}`}>{stat.value}</p>
             </div>
           ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Risk Trend */}
          <div className="lg:col-span-2 bg-card border border-border rounded-3xl p-6 shadow-xl">
             <h3 className="text-xs font-bold uppercase tracking-widest mb-6">Risk Velocity Trend</h3>
             <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                 <LineChart data={riskTrendData}>
                   <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                   <XAxis dataKey="id" hide />
                   <YAxis domain={[0, 100]} stroke="#64748b" fontSize={10} />
                   <Tooltip 
                     contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '12px' }}
                     itemStyle={{ fontSize: '10px', fontWeight: 'bold' }}
                   />
                   <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="#3b82f6" 
                    strokeWidth={4} 
                    dot={{ fill: '#3b82f6', r: 4 }} 
                    activeDot={{ r: 8, stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={1000}
                   />
                 </LineChart>
               </ResponsiveContainer>
             </div>
          </div>

          {/* Channel Dist */}
          <div className="bg-card border border-border rounded-3xl p-6 shadow-xl">
             <h3 className="text-xs font-bold uppercase tracking-widest mb-6">Channel Distribution</h3>
             <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                 <PieChart>
                   <Pie
                     data={channelData}
                     innerRadius={60}
                     outerRadius={100}
                     paddingAngle={5}
                     dataKey="value"
                   >
                     {channelData.map((entry, index) => (
                       <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                     ))}
                   </Pie>
                   <Tooltip />
                   <Legend verticalAlign="bottom" height={36}/>
                 </PieChart>
               </ResponsiveContainer>
             </div>
          </div>

          {/* Risk Factors */}
          <div className="lg:col-span-3 bg-card border border-border rounded-3xl p-8 shadow-xl">
             <h3 className="text-xs font-bold uppercase tracking-widest mb-8 text-center">Top Fraud Indicators</h3>
             <div className="h-[250px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={factorData} layout="vertical">
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={10} width={100} />
                    <Tooltip 
                      cursor={{fill: 'transparent'}}
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }}
                    />
                    <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
             </div>
          </div>

        </div>
      </section>

      <footer className="mt-32 pb-12 border-t border-border flex justify-between items-center text-[10px] text-muted-foreground font-bold uppercase tracking-widest">
        <span>Sentinel Intelligence Engine v1.1</span>
        <div className="flex gap-4">
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 bg-green-500 rounded-full" /> Operational</span>
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" /> Neural Scanning</span>
        </div>
      </footer>

      <InvestigationSidebar 
        isOpen={sidebarState.isOpen}
        selectedCase={activeCase}
        selectedTransaction={sidebarState.tx}
        actions={activeActions}
        onClose={() => setSidebarState({ ...sidebarState, isOpen: false })}
        role={role}
      />
    </div>
  );
};

export default Dashboard;
