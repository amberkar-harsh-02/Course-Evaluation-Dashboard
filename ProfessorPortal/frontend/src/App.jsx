import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';

function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // --- Master State (Never unmounts!) ---
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  
  const [currentView, setCurrentView] = useState('dashboard'); 
  const [activeTopic, setActiveTopic] = useState(null);
  const [selectedTopicModal, setSelectedTopicModal] = useState(null);
  const [isCourseExpanded, setIsCourseExpanded] = useState(true);

  // Apply Dark Mode Class to HTML Root globally
  useEffect(() => {
    if (isDarkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDarkMode]);

  const theme = {
    bg: isDarkMode ? 'bg-zinc-900' : 'bg-slate-50',
    sidebarBg: isDarkMode ? 'bg-zinc-950' : 'bg-white',
    sidebarBorder: isDarkMode ? 'border-zinc-800' : 'border-slate-200',
    textMain: isDarkMode ? 'text-zinc-100' : 'text-slate-900',
    navActiveBg: isDarkMode ? 'bg-blue-900/30' : 'bg-blue-50',
    navActiveText: isDarkMode ? 'text-blue-400' : 'text-blue-600',
    navInactiveText: isDarkMode ? 'text-zinc-400' : 'text-slate-500',
    navInactiveHover: isDarkMode ? 'hover:bg-zinc-800' : 'hover:bg-slate-100',
  };

  return (
    <div className={`flex h-screen font-sans transition-colors duration-200 ${theme.bg} ${theme.textMain}`}>
      <Toaster position="bottom-right" toastOptions={{ className: 'font-medium text-sm rounded-lg shadow-xl' }} />

      {/* Shared Master Sidebar */}
      <aside className={`w-64 flex flex-col border-r z-20 shrink-0 overflow-y-auto transition-colors duration-200 ${theme.sidebarBg} ${theme.sidebarBorder}`}>
        <div className={`p-6 border-b select-none transition-colors duration-200 ${theme.sidebarBorder}`}>
          <h1 className="text-2xl font-bold tracking-wider text-slate-900 dark:text-zinc-100">
            Course<span className="text-blue-600 dark:text-blue-500">Eval</span>
          </h1>
          <p className="text-xs font-bold tracking-widest uppercase mt-1 text-slate-500 dark:text-zinc-500">Faculty Portal</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button 
            onClick={() => navigate('/')} 
            className={`w-full text-left py-2.5 px-4 font-semibold rounded-lg transition-colors ${location.pathname === '/' ? `${theme.navActiveBg} ${theme.navActiveText}` : `${theme.navInactiveText} ${theme.navInactiveHover}`}`}
          >
            User Manual
          </button>
          
          <button 
            onClick={() => { 
              navigate('/dashboard');
              if (analysisData) setCurrentView('dashboard');
            }} 
            className={`w-full text-left py-2.5 px-4 font-semibold rounded-lg transition-colors ${location.pathname === '/dashboard' ? `${theme.navActiveBg} ${theme.navActiveText}` : `${theme.navInactiveText} ${theme.navInactiveHover}`}`}
          >
            Dashboard
          </button>
          
          {/* Sub-navigation for loaded course */}
          {analysisData && location.pathname === '/dashboard' && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="pt-6 pb-2">
              <button 
                onClick={() => setIsCourseExpanded(!isCourseExpanded)} 
                className="flex items-center justify-between w-full text-left py-2 px-4 text-xs uppercase tracking-wider font-bold text-slate-500 dark:text-zinc-500 hover:text-slate-800 dark:hover:text-zinc-200"
              >
                <span className="truncate pr-2">{analysisData.course_id}</span>
                <span>{isCourseExpanded ? '▼' : '▶'}</span>
              </button>
              <AnimatePresence>
                {isCourseExpanded && (
                  <motion.div 
                    initial={{ opacity: 0, y: -10 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-2 space-y-1 pl-4 border-l border-slate-200 dark:border-zinc-800 ml-4 overflow-hidden"
                  >
                    {analysisData.category_scores.map(cat => (
                      <button 
                        key={cat.category}
                        onClick={() => { 
                          setActiveTopic(cat.category); 
                          setCurrentView('topic'); 
                          setSelectedTopicModal(null); 
                        }} 
                        className={`block w-full text-left py-1.5 px-2 text-sm rounded transition-colors truncate ${currentView === 'topic' && activeTopic === cat.category ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-bold' : 'text-slate-500 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-zinc-800/50'}`}
                        title={cat.category}
                      >
                        {cat.category}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </nav>
      </aside>

      {/* Dynamic Content Outlet */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        <Outlet context={{ 
          isDarkMode, setIsDarkMode, 
          analysisData, setAnalysisData,
          currentView, setCurrentView,
          activeTopic, setActiveTopic,
          selectedTopicModal, setSelectedTopicModal
        }} />
      </div>
    </div>
  );
}

export default App;