import { useState, useRef, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';

const CustomSelect = ({ value, onChange, options, minWidth = "160px" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = options.find(o => o.value === value) || options[0];

  return (
    <div className="relative" style={{ minWidth }}>
      {isOpen && (
        <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)}></div>
      )}
      <button 
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative z-40 w-full bg-zinc-900 border border-zinc-700 text-zinc-300 text-sm rounded-lg p-2.5 flex justify-between items-center gap-3 hover:border-zinc-500 hover:bg-zinc-800/80 transition-all outline-none focus:ring-1 focus:ring-blue-500 shadow-sm"
      >
        <span className="truncate font-medium">{selectedOption?.label}</span>
        <motion.svg animate={{ rotate: isOpen ? 180 : 0 }} className="w-4 h-4 text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></motion.svg>
      </button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0, y: -5 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 mt-1.5 w-max min-w-full bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl overflow-hidden py-1 max-h-64 overflow-y-auto"
          >
            {options.map((opt) => (
              <div 
                key={opt.value}
                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                className={`px-4 py-2.5 text-sm cursor-pointer transition-colors ${value === opt.value ? 'bg-blue-600/20 text-blue-400 font-bold' : 'text-zinc-300 hover:bg-zinc-700/80 hover:text-zinc-100'}`}
              >
                {opt.label}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function App() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const [batchHistory, setBatchHistory] = useState([]);
  const [selectedForZip, setSelectedForZip] = useState(new Set());
  const [currentView, setCurrentView] = useState('dashboard'); 
  const [activeTopic, setActiveTopic] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [chartView, setChartView] = useState('bar');
  const fileInputRef = useRef(null);
  const hiddenJsonInputRef = useRef(null);

  const [isUploading, setIsUploading] = useState(false);
  const [extractedText, setExtractedText] = useState("");
  
  const [isRawCommentsOpen, setIsRawCommentsOpen] = useState(false);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);

  // 🚀 NEW: State for Model Selector
  const [selectedModel, setSelectedModel] = useState('local');

  const [scoreFilter, setScoreFilter] = useState('all');
  const [sortOrder, setSortOrder] = useState('desc'); 
  const [topicFilter, setTopicFilter] = useState('all');
  
  const [selectedTopicModal, setSelectedTopicModal] = useState(null);
  const [isCourseExpanded, setIsCourseExpanded] = useState(true);

  const hasData = extractedText || isUploading || isAnalyzing || analysisData;

  // 🚀 NEW: Dropdown options for the AI Models
  const modelOptions = [
    { value: 'local', label: 'Local LLM (qwen35b, Mac Studio)' },
    { value: 'openai', label: 'OpenAI (gpt-5.6-terra)' },
    { value: 'anthropic', label: 'Anthropic (claude-sonnet-4-6)' }
  ];

  const mockHistory = [
    { id: 1, course: "CHEM 14A", term: "Fall 2025", date: "Oct 12, 2025", score: 3.5, status: "Complete", institution: "University of California, Los Angeles (UCLA)" },
    { id: 2, course: "CS 31", term: "Spring 2025", date: "May 04, 2025", score: 3.8, status: "Complete", institution: "University of California, Los Angeles (UCLA)" },
    { id: 3, course: "PHYSICS 1A", term: "Winter 2025", date: "Feb 18, 2025", score: 4.6, status: "Complete", institution: "University of California, Los Angeles (UCLA)" },
    { id: 4, course: "CST 338", term: "Fall 2025", date: "Sep 10, 2025", score: 4.1, status: "Complete", institution: "California State University, Monterey Bay (CSUMB)" },
    { id: 5, course: "CST 311", term: "Spring 2026", date: "Apr 02, 2026", score: 3.9, status: "Complete", institution: "California State University, Monterey Bay (CSUMB)" },
  ];

  const historyByInstitution = useMemo(() => {
    return mockHistory.reduce((acc, item) => {
      if (!acc[item.institution]) acc[item.institution] = [];
      acc[item.institution].push(item);
      return acc;
    }, {});
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };

  const handleHiddenJsonUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const loadingToast = toast.loading('Parsing local JSON data...', { style: { background: '#3f3f46', color: '#fff' }});
    const reader = new FileReader();
    
    reader.onload = (event) => {
      try {
        const rawData = JSON.parse(event.target.result);
        let normalizedData = rawData;

        if (rawData.categories) {
          const commentsMap = {};
          rawData.categories.forEach(cat => {
            if (cat.comments) {
              cat.comments.forEach(comment => {
                const text = comment.feedback;
                const rating = (comment.score === "" || comment.score === null) ? 0 : Number(comment.score);
                if (!commentsMap[text]) {
                  commentsMap[text] = { text, rating, topics: [], topicRatings: {} };
                }
                if (!commentsMap[text].topics.includes(cat.topic)) {
                  commentsMap[text].topics.push(cat.topic);
                }
                commentsMap[text].topicRatings[cat.topic] = rating;
              });
            }
          });

          normalizedData = {
            course_id: rawData.course_id || "Unknown Course",
            overall_score: rawData.overall_score || 0,
            category_scores: rawData.category_scores.map(c => ({
              category: c.category,
              score: c.average_score || 0,
              comment_count: c.comment_count || 0
            })),
            analyzed_comments: Object.values(commentsMap),
            topic_summaries: rawData.topic_summaries || [],
            raw_categories: rawData.categories || []
          };
        }

        setAnalysisData(normalizedData);
        setCurrentView('dashboard');
        setIsAnalyzing(false);
        
        const rawTexts = normalizedData.analyzed_comments.map(c => `Comment: ${c.text}`).join('\n\n');
        setExtractedText(rawTexts);
        toast.success('Dashboard Updated Successfully!', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' } });
        
      } catch (error) {
        console.error("Error parsing JSON:", error);
        toast.error('Invalid JSON file format. Make sure it matches the pipeline output.', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' } });
      }
    };
    reader.readAsText(file);
    e.target.value = null; 
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFiles(Array.from(e.dataTransfer.files));
    }
  };

  const loadBatchHistory = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8001/api/history");
      if (res.ok) {
        const data = await res.json();
        setBatchHistory(data);
        setCurrentView('batchReport');
      }
    } catch (e) {
      toast.error('Failed to load batch history', { style: { background: '#3f3f46', color: '#fff' }});
    }
  };

  const handleZipDownload = async () => {
    if (selectedForZip.size === 0) return;
    const loadingToast = toast.loading('Generating ZIP...', { style: { background: '#3f3f46', color: '#fff' }});
    try {
      const res = await fetch("http://127.0.0.1:8001/api/download-zip", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_ids: Array.from(selectedForZip) })
      });
      if (!res.ok) throw new Error("Zip failed");
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "course_evaluations_export.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success('ZIP downloaded!', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' }});
    } catch (e) {
      toast.error('Failed to download ZIP', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' }});
    }
  };

  const handleClearHistory = async () => {
    const loadingToast = toast.loading('Clearing history...', { style: { background: '#3f3f46', color: '#fff' }});
    try {
      const res = await fetch("http://127.0.0.1:8001/api/history", { method: 'DELETE' });
      if (!res.ok) throw new Error("Clear failed");
      setBatchHistory([]);
      setSelectedForZip(new Set());
      toast.success('History cleared!', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' }});
    } catch (e) {
      toast.error('Failed to clear history', { id: loadingToast, style: { background: '#3f3f46', color: '#fff' }});
    }
  };

  const handleBatchExtract = async () => {
    if (selectedFiles.length === 0) return;
    
    setIsUploading(true);
    setIsAnalyzing(true);
    setCurrentView('dashboard');
    setIsModalOpen(false);
    
    const totalFiles = selectedFiles.length;
    setBatchProgress({ current: 0, total: totalFiles });

    for (let i = 0; i < totalFiles; i++) {
      const file = selectedFiles[i];
      setBatchProgress({ current: i + 1, total: totalFiles });
      const currentToast = toast.loading(`Processing ${i + 1}/${totalFiles}: ${file.name}...`, { style: { background: '#3f3f46', color: '#fff' }});
      
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("model_choice", selectedModel);

        const response = await fetch("http://127.0.0.1:8001/api/analyze", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error(`Server error`);
        
        toast.success(`${file.name} complete!`, { id: currentToast, style: { background: '#3f3f46', color: '#fff' } });
      } catch (error) {
        console.error("Error processing", file.name, error);
        toast.error(`Failed: ${file.name}`, { id: currentToast, style: { background: '#3f3f46', color: '#fff' } });
      }
    }
    
    setIsUploading(false);
    setIsAnalyzing(false);
    setSelectedFiles([]);
    setBatchProgress({ current: 0, total: 0 });
    
    loadBatchHistory(); // Automatically jump to report page when done
  };

  const handleExportJson = () => {
    if (!analysisData) return;
    const dataStr = JSON.stringify(analysisData, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${analysisData.course_id}_Evaluation_Data.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("JSON Exported Successfully!", { style: { background: '#3f3f46', color: '#fff' }});
  };

  const getScoreColor = (score) => {
    if (score === 0) return '#9ca3af'; 
    if (score < 1.5) return '#ef4444'; 
    if (score < 3.0) return '#f97316'; 
    if (score <= 4.0) return '#f59e0b'; 
    if (score <= 5.0) return '#22c55e'; 
  };

  const getBadgeColorClass = (score) => {
    if (score === 0) return 'bg-gray-400'; 
    if (score < 1.5) return 'bg-red-500'; 
    if (score < 3.0) return 'bg-orange-500'; 
    if (score <= 4.0) return 'bg-amber-500';
    if (score <= 5.0) return 'bg-green-500'; 
  };

  // 🚀 FIXED: Global Bypass filter for Topic Cards
  const getFilteredAndSortedComments = (baseComments = analysisData?.analyzed_comments, forceTopic = null, ignoreGlobalFilters = false) => {
    if (!baseComments) return [];
    
    const currentTopic = forceTopic || (topicFilter !== 'all' ? topicFilter : null);

    let filtered = baseComments.map(c => {
      if (currentTopic && c.topicRatings && c.topicRatings[currentTopic] !== undefined) {
        return { ...c, rating: c.topicRatings[currentTopic] };
      }
      return c;
    });

    if (currentTopic) {
      filtered = filtered.filter(c => c.topics && c.topics.includes(currentTopic));
    }

    if (!ignoreGlobalFilters && scoreFilter !== 'all') {
      if (scoreFilter === 'high') filtered = filtered.filter(c => c.rating >= 3);
      else if (scoreFilter === 'low') filtered = filtered.filter(c => c.rating < 3 && c.rating > 0);
      else if (scoreFilter === '0') filtered = filtered.filter(c => c.rating === 0);
      else filtered = filtered.filter(c => Math.round(c.rating) === parseInt(scoreFilter));
    }

    const activeSortOrder = ignoreGlobalFilters ? 'desc' : sortOrder;

    filtered.sort((a, b) => {
      return activeSortOrder === 'desc' ? b.rating - a.rating : a.rating - b.rating;
    });
    return filtered;
  };

  const renderMiniDonut = (cat) => {
    const radius = 28;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (circumference * (cat.score / 5));
    
    return (
      <motion.div 
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        key={cat.category} 
        onClick={() => setSelectedTopicModal(cat.category)}
        className="bg-zinc-800/50 border border-zinc-700 p-4 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:shadow-lg hover:border-zinc-500 transition-all group"
      >
        <div className="relative flex items-center justify-center mb-2">
          <svg className="w-20 h-20 transform -rotate-90">
            <circle cx="40" cy="40" r={radius} stroke="currentColor" strokeWidth="6" fill="transparent" className="text-zinc-700" />
            <circle cx="40" cy="40" r={radius} stroke="currentColor" strokeWidth="6" fill="transparent"
              strokeDasharray={circumference} strokeDashoffset={offset} 
              className={`${cat.score >= 3 ? 'text-green-500' : cat.score > 0 && cat.score <= 2 ? 'text-red-500' : cat.score === 0 ? 'text-zinc-500' : 'text-amber-500'} transition-all duration-1000`} />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="text-lg font-black text-zinc-100">{cat.score === 0 ? 'N/A' : cat.score.toFixed(1)}</span>
          </div>
        </div>
        <span className="text-xs font-semibold text-zinc-400 text-center leading-tight truncate w-full px-2" title={cat.category}>{cat.category}</span>
      </motion.div>
    );
  };

  const scoreOptions = [
    { value: 'all', label: 'All Scores' },
    { value: 'high', label: 'Positive (>= 3)' },
    { value: 'low', label: 'Needs Improvement (< 3)' },
    { value: '5', label: '5 Stars Only' },
    { value: '4', label: '4 Stars Only' },
    { value: '3', label: '3 Stars Only' },
    { value: '2', label: '2 Stars Only' },
    { value: '1', label: '1 Star Only' },
    { value: '0', label: 'Unrated / Generic' }
  ];

  const sortOptions = [
    { value: 'desc', label: 'Highest Rated First' },
    { value: 'asc', label: 'Lowest Rated First' }
  ];

  const topicOptions = analysisData ? [
    { value: 'all', label: 'All Topics' },
    ...analysisData.category_scores.map(cat => ({ value: cat.category, label: cat.category })),
    { value: 'None of the above / Other', label: 'Uncategorized' }
  ] : [];

  return (
    <div className="flex h-screen bg-zinc-900 font-sans text-zinc-100">
      
      <Toaster position="bottom-right" toastOptions={{ className: 'font-medium text-sm rounded-lg shadow-xl' }} />
      
      <input 
        type="file" 
        accept=".json" 
        className="hidden" 
        ref={hiddenJsonInputRef} 
        onChange={handleHiddenJsonUpload} 
      />

      <aside className="w-64 bg-zinc-950 text-zinc-100 flex flex-col border-r border-zinc-800 z-20 overflow-y-auto">
        <div className="p-6 border-b border-zinc-800 select-none">
          <h1 
            className="text-2xl font-bold tracking-wider cursor-pointer hover:text-blue-400 transition-colors"
            onDoubleClick={() => hiddenJsonInputRef.current?.click()}
            title="Double-click to load JSON data"
          >
            Course<span className="text-blue-500">Eval</span>
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <button onClick={loadBatchHistory} className={`w-full text-left py-2.5 px-4 font-semibold rounded-lg transition-colors ${currentView === 'batchReport' ? 'bg-blue-900/30 text-blue-400' : 'hover:bg-zinc-800 text-zinc-400'}`}>Batch Report</button>   
          {analysisData && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="pt-6 pb-2">
              <button 
                onClick={() => setIsCourseExpanded(!isCourseExpanded)} 
                className="flex items-center justify-between w-full text-left py-2 px-4 text-xs uppercase tracking-wider font-bold text-zinc-500 hover:text-zinc-200"
              >
                <span>{analysisData.course_id}</span>
                <span>{isCourseExpanded ? '▼' : '▶'}</span>
              </button>
              <AnimatePresence>
                {isCourseExpanded && (
                  <motion.div 
                    initial={{ opacity: 0, y: -10 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-2 space-y-1 pl-4 border-l border-zinc-800 ml-4 overflow-hidden"
                  >
                    {analysisData.category_scores.map(cat => (
                      <button 
                        key={cat.category}
                        onClick={() => { 
                          setActiveTopic(cat.category); 
                          setCurrentView('topic'); 
                          setSelectedTopicModal(null); 
                        }} 
                        className={`block w-full text-left py-1.5 px-2 text-sm rounded transition-colors truncate ${currentView === 'topic' && activeTopic === cat.category ? 'bg-blue-900/30 text-blue-400 font-bold' : 'text-zinc-400 hover:text-blue-400 hover:bg-zinc-800/50'}`}
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

      <main className="flex-1 flex flex-col overflow-hidden relative">
        <header className="bg-zinc-900 border-b border-zinc-800 px-8 py-5 flex justify-between items-center z-10 shadow-sm">
          <div>
            {currentView === 'topic' ? (
              <div className="flex items-center gap-4">
                <button onClick={() => setCurrentView('dashboard')} className="text-zinc-400 hover:text-white transition-colors bg-zinc-800 hover:bg-zinc-700 p-2 rounded-lg">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                </button>
                <h2 className="text-xl font-bold text-zinc-100">{activeTopic}</h2>
              </div>
            ) : (
              <h2 className="text-xl font-bold text-zinc-100">
                {isAnalyzing && batchProgress.total > 0 && (
              <div className="mt-2 w-72">
                <div className="flex justify-between text-xs text-blue-400 font-bold mb-1.5">
                  <span className="animate-pulse">Processing {batchProgress.current} of {batchProgress.total} Files...</span>
                  <span>{Math.round((batchProgress.current / batchProgress.total) * 100)}%</span>
                </div>
                <div className="w-full bg-zinc-800 rounded-full h-2.5 overflow-hidden border border-zinc-700 shadow-inner">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                    transition={{ duration: 0.3 }}
                    className="bg-blue-500 h-full rounded-full"
                  />
                </div>
              </div>
            )}
              </h2>
            )}
            
            {currentView === 'dashboard' && isAnalyzing && !analysisData && (
              <p className="text-sm text-blue-400 animate-pulse mt-1">
                Analyzing...
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {analysisData && (
              <button 
                onClick={handleExportJson} 
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-600 px-4 py-2.5 rounded-lg font-medium shadow-sm transition-all flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export JSON
              </button>
            )}
            <button onClick={() => setIsModalOpen(true)} className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-medium shadow-sm transition-all">
              + Analyze Course
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-8 flex flex-col">
          {currentView === 'batchReport' ? (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-zinc-800 rounded-xl shadow-lg border border-zinc-700 overflow-hidden">
              <div className="bg-zinc-900/50 px-6 py-4 border-b border-zinc-700 flex justify-between items-center">
                <h3 className="font-bold text-zinc-100 text-lg">Processed Files</h3>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={handleClearHistory}
                    disabled={!batchHistory || batchHistory.length === 0}
                    className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${batchHistory && batchHistory.length > 0 ? 'bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-900/50' : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'}`}
                  >
                    Clear History
                  </button>
                  <button 
                    onClick={handleZipDownload}
                    disabled={selectedForZip.size === 0}
                    className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${selectedForZip.size > 0 ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md' : 'bg-zinc-700 text-zinc-500 cursor-not-allowed'}`}
                  >
                    Download Selected ZIP ({selectedForZip.size})
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-zinc-800 border-b border-zinc-700 text-zinc-400 text-xs uppercase tracking-wider">
                      <th className="p-4 pl-6 font-semibold w-12">
                        <input type="checkbox" onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedForZip(new Set((batchHistory || []).filter(h => h.status === 'Success').map(h => h.course_id)));
                          } else {
                            setSelectedForZip(new Set());
                          }
                        }} />
                      </th>
                      <th className="p-4 font-semibold">Course ID</th>
                      <th className="p-4 font-semibold">Filename</th>
                      <th className="p-4 font-semibold">Date</th>
                      <th className="p-4 font-semibold">Status</th>
                      <th className="p-4 font-semibold text-right pr-6">Time (s)</th>
                      <th className="p-4 font-semibold text-right pr-6">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-700/50">
                    {(batchHistory || []).slice().reverse().map((item, idx) => (
                      <tr key={idx} className="hover:bg-zinc-700/30 transition-colors">
                        <td className="p-4 pl-6">
                          <input 
                            type="checkbox" 
                            disabled={item.status !== 'Success'}
                            checked={selectedForZip.has(item.course_id)}
                            onChange={(e) => {
                              const newSet = new Set(selectedForZip);
                              e.target.checked ? newSet.add(item.course_id) : newSet.delete(item.course_id);
                              setSelectedForZip(newSet);
                            }}
                          />
                        </td>
                        <td className="p-4 font-bold text-zinc-200">{item.course_id}</td>
                        <td className="p-4 text-zinc-400 text-sm truncate max-w-xs">{item.filename}</td>
                        <td className="p-4 text-zinc-500 text-sm">{item.date}</td>
                        <td className="p-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${item.status === 'Success' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                            {item.status === 'Success' ? '✓ ' : '✕ '} {item.status}
                          </span>
                        </td>
                        <td className="p-4 pr-6 text-right font-mono text-zinc-400">{item.runtime_seconds}s</td>
                        <td className="p-4 pr-6 text-right">
                          <button 
                            onClick={() => handleSingleDownload(item.course_id)}
                            disabled={item.status !== 'Success'}
                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-sm ${item.status === 'Success' ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-200 border border-zinc-600' : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'}`}
                          >
                            ↓ .json
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          ) : currentView === 'history' ? (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
              {Object.entries(historyByInstitution).map(([institution, records]) => (
                <div key={institution} className="bg-zinc-800 rounded-xl shadow-lg border border-zinc-700 overflow-hidden">
                  <div className="bg-zinc-900/50 px-6 py-4 border-b border-zinc-700">
                    <h3 className="font-bold text-zinc-100 text-lg">{institution}</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-zinc-800 border-b border-zinc-700 text-zinc-400 text-xs uppercase tracking-wider">
                          <th className="p-4 pl-6 font-semibold">Course ID</th>
                          <th className="p-4 font-semibold">Term</th>
                          <th className="p-4 font-semibold">Date Analyzed</th>
                          <th className="p-4 font-semibold">Overall Score</th>
                          <th className="p-4 font-semibold">Status</th>
                          <th className="p-4 pr-6 font-semibold text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-700/50">
                        {records.map((item) => (
                          <tr key={item.id} className="hover:bg-zinc-700/30 transition-colors">
                            <td className="p-4 pl-6 font-bold text-zinc-200">{item.course}</td>
                            <td className="p-4 text-zinc-400">{item.term}</td>
                            <td className="p-4 text-zinc-500 text-sm">{item.date}</td>
                            <td className="p-4">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${getBadgeColorClass(item.score)} text-white`}>
                                {item.score.toFixed(1)} / 5.0
                              </span>
                            </td>
                            <td className="p-4">
                              <span className="inline-flex items-center text-sm font-medium text-green-500">
                                <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path></svg>
                                {item.status}
                              </span>
                            </td>
                            <td className="p-4 pr-6 text-right">
                              <button className="text-blue-400 hover:text-blue-300 font-medium text-sm transition-colors">View Report</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </motion.div>
          ) : currentView === 'topic' && activeTopic && analysisData ? (
            
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6 pb-8">
              {(() => {
                const topicSummaryData = analysisData.topic_summaries?.find(s => s.topic === activeTopic);
                const topicCat = analysisData.category_scores?.find(c => c.category === activeTopic);
                const rawCat = analysisData.raw_categories?.find(c => c.topic === activeTopic);

                let stats = { assigned: null, scored: null, sentimentObj: null };

                if (rawCat && rawCat.comments) {
                  stats.assigned = rawCat.comments.length;
                  stats.scored = rawCat.comments.filter(c => c.score !== "" && c.score !== null).length;
                  stats.sentimentObj = {
                    pos: rawCat.comments.filter(c => c.sentiment === 'positive').length,
                    neu: rawCat.comments.filter(c => c.sentiment === 'neutral').length,
                    neg: rawCat.comments.filter(c => c.sentiment === 'negative').length,
                  };
                }

                if (!topicSummaryData && !topicCat && stats.assigned === null) return null;

                let avgValue = topicCat?.score > 0 ? (topicCat.score.toString().match(/\.\d{2,}/) ? topicCat.score.toFixed(2) : topicCat.score.toFixed(1)) + ' / 5.0' : 'N/A';

                let rawText = topicSummaryData ? topicSummaryData.summary : '';
                let cleanSummary = rawText.replace(new RegExp(`^Summary of ${activeTopic.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*`, 'i'), '').trim();
                cleanSummary = cleanSummary.replace(/^\d+\s+.*?(negative|positive|neutral|averages)\.\s*(Here is a concise sentence summarizing the qualitative themes:\s*)?/i, '').trim();

                if (!cleanSummary) cleanSummary = "No qualitative themes summarized.";

                return (
                  <div className="bg-[#222225] p-6 rounded-xl border border-zinc-700/60 shadow-lg flex flex-col gap-5">
                    
                    <div className="flex items-center justify-between pb-2">
                      <h4 className="text-xl font-bold text-zinc-100">Topic Analysis</h4>
                      <div className="text-right flex flex-col items-end">
                        <span className="text-zinc-500 text-[10px] uppercase tracking-widest font-bold block mb-1">Average Score</span>
                        <div className="text-2xl font-black text-blue-400">{avgValue}</div>
                      </div>
                    </div>
                    
                    {stats.assigned !== null && (
                      <div className="bg-[#1a1a1d] p-5 rounded-lg border border-zinc-700/40 flex flex-col gap-5">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col">
                            <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Assigned Comments</span>
                            <span className="text-zinc-200 font-bold text-lg">{stats.assigned}</span>
                          </div>
                          {stats.scored !== null && (
                            <div className="flex flex-col">
                              <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Scored Comments</span>
                              <span className="text-zinc-200 font-bold text-lg">{stats.scored}</span>
                            </div>
                          )}
                        </div>
                        {stats.sentimentObj && (
                          <div className="pt-4 border-t border-zinc-800/80">
                            <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-3 block">Sentiment Distribution</span>
                            <div className="flex flex-wrap items-center gap-6">
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-green-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.pos} Positive</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.neu} Neutral</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-red-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.neg} Negative</span></span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  
                    
                  </div>
                );
              })()}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-80">
                <div className="bg-zinc-800 p-6 rounded-xl border border-zinc-700 flex flex-col shadow-lg">
                  <h3 className="font-bold text-zinc-200 mb-4">Score Distribution</h3>
                  <div className="flex-1 bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-lg flex items-center justify-center text-zinc-500 font-medium">
                    [ Bar Chart Placeholder ]
                  </div>
                </div>
                <div className="bg-zinc-800 p-6 rounded-xl border border-zinc-700 flex flex-col shadow-lg">
                  <h3 className="font-bold text-zinc-200 mb-4">Historical Trend</h3>
                  <div className="flex-1 bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-lg flex items-center justify-center text-zinc-500 font-medium">
                    [ Line Chart Placeholder ]
                  </div>
                </div>
              </div>

              <div className="bg-zinc-800 p-6 rounded-xl shadow-lg border border-zinc-700 flex flex-col min-h-[400px] mt-2">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4 border-b border-zinc-700 pb-4">
                  <div>
                    <h3 className="font-bold text-zinc-200 text-lg">Topic Comments</h3>
                    <div className="text-zinc-500 font-medium text-sm mt-0.5">
                      {getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).length} {getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).length === 1 ? 'Comment' : 'Comments'}
                    </div>
                  </div>
                  
                  <div className="flex flex-wrap gap-3">
                    <CustomSelect value={scoreFilter} onChange={setScoreFilter} options={scoreOptions} minWidth="200px" />
                    <CustomSelect value={sortOrder} onChange={setSortOrder} options={sortOptions} minWidth="190px" />
                  </div>
                </div>
                
                <motion.div layout className="flex-1 overflow-auto pr-2 space-y-4 max-h-[500px]">
                  <AnimatePresence mode="popLayout">
                    {getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).length === 0 ? (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center text-zinc-500 py-10 font-medium">No comments match your current filter.</motion.div>
                    ) : (
                      getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).map((comment, idx) => (
                        <motion.div 
                          layout
                          initial={{ opacity: 0, scale: 0.95, y: 10 }}
                          animate={{ opacity: 1, scale: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }}
                          transition={{ duration: 0.2 }}
                          key={`${comment.text}-${idx}`}
                          className="relative bg-zinc-800/40 border border-zinc-700/60 rounded-xl p-6 hover:shadow-md hover:bg-zinc-800/80 transition-all flex gap-5 items-start overflow-hidden"
                          style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                        >
                          <svg className="absolute top-4 right-4 w-12 h-12 text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                          </svg>

                          <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>{comment.rating.toFixed(1)}</div>
                          <div className="pt-1 flex-1 relative z-10">
                            <p className="text-zinc-300 leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                            <div className="flex flex-wrap gap-2 items-center">
                              {comment.topics && comment.topics.map((t, i) => (
                                <span key={i} className="bg-zinc-900/80 text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-zinc-700/50 shadow-sm">
                                  {t}
                                </span>
                              ))}
                            </div>
                          </div>
                        </motion.div>
                      ))
                    )}
                  </AnimatePresence>
                </motion.div>
              </div>

              <div className="mt-4 flex flex-col items-center pb-8">
                <button 
                  onClick={() => setIsRawCommentsOpen(!isRawCommentsOpen)} 
                  className="flex items-center gap-2 px-6 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 font-medium rounded-full transition-colors border border-zinc-700 shadow-sm"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                  {isRawCommentsOpen ? 'Hide Raw OCR Text' : 'View Raw OCR Text'}
                </button>
                <AnimatePresence>
                  {isRawCommentsOpen && (
                    <motion.div 
                      initial={{ opacity: 0, height: 0, y: -10 }} 
                      animate={{ opacity: 1, height: 'auto', y: 0 }} 
                      exit={{ opacity: 0, height: 0, y: -10 }}
                      className="w-full mt-6 bg-black rounded-xl p-6 overflow-hidden border border-zinc-800 shadow-inner"
                    >
                      {extractedText ? (
                        <pre className="whitespace-pre-wrap font-mono text-xs text-green-500 leading-relaxed overflow-x-auto">
                          {extractedText}
                        </pre>
                      ) : (
                        <div className="text-center text-zinc-600 font-mono text-sm py-8">
                          No raw text available. Upload a file to see OCR output.
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

            </motion.div>

          ) : !hasData ? (
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex-1 flex flex-col items-center justify-center text-center max-w-2xl mx-auto">
              <div className="w-24 h-24 bg-blue-900/30 rounded-full flex items-center justify-center mb-8 border border-blue-800/50">
                <svg className="w-12 h-12 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              </div>
              <h2 className="text-4xl font-extrabold text-zinc-100 mb-4 tracking-tight">Upload a document</h2>
              <button onClick={() => setIsModalOpen(true)} className="bg-zinc-800 border-2 border-blue-600 text-blue-500 hover:bg-zinc-800/80 px-8 py-3 rounded-lg font-bold shadow-lg transition-all text-lg">
                Upload First File
              </button>
            </motion.div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6 pb-8">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[400px]">
                
                <div className="bg-zinc-800 p-6 rounded-xl shadow-lg border border-zinc-700 flex flex-col justify-center items-center relative overflow-hidden">
                  <h3 className="font-bold text-zinc-200 mb-6 absolute top-6 left-6">Overall Grade</h3>
                  {analysisData ? (
                    <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center justify-center flex-1 mt-8">
                      <div className="flex items-baseline gap-2">
                        <span 
                          className="text-7xl font-black tracking-tighter"
                          style={{ color: getScoreColor(analysisData.overall_score) }}
                        >
                          {analysisData.overall_score.toFixed(1)}
                        </span>
                        <span className="text-3xl font-bold text-zinc-600">/ 5</span>
                      </div>
                      <span className="mt-3 text-xs font-bold text-zinc-500 uppercase tracking-widest">
                        {analysisData.analyzed_comments.length} Total Comments
                      </span>
                    </motion.div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-lg text-zinc-500 text-sm font-medium">Awaiting NLP Analysis Data</div>
                  )}
                </div>

                <div className="bg-zinc-800 p-6 rounded-xl shadow-lg border border-zinc-700 flex flex-col">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-zinc-200">Category Breakdown</h3>
                    {analysisData && (
                      <div className="bg-zinc-900 p-1 rounded-lg flex text-xs font-bold border border-zinc-700">
                        <button onClick={() => setChartView('bar')} className={`px-3 py-1.5 rounded-md transition-all ${chartView === 'bar' ? 'bg-zinc-700 shadow-sm text-blue-400' : 'text-zinc-500 hover:text-zinc-300'}`}>Bar</button>
                        <button onClick={() => setChartView('radar')} className={`px-3 py-1.5 rounded-md transition-all ${chartView === 'radar' ? 'bg-zinc-700 shadow-sm text-blue-400' : 'text-zinc-500 hover:text-zinc-300'}`}>Radar</button>
                      </div>
                    )}
                  </div>
                  {analysisData ? (
                    <div className="flex-1 min-h-[350px]">
                      <AnimatePresence mode="wait">
                        {chartView === 'bar' ? (
                          <motion.div 
                            key="bar"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            transition={{ duration: 0.3 }}
                            className="w-full h-full"
                          >
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={analysisData.category_scores} layout="vertical" margin={{ top: 0, right: 20, left: -20, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#3f3f46" />
                                <XAxis type="number" domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} stroke="#a1a1aa" fontSize={12} />
                                <YAxis dataKey="category" type="category" width={220} stroke="#d4d4d8" fontSize={10} fontWeight={600} interval={0} />
                                <Tooltip 
                                  cursor={{ fill: '#27272a' }} 
                                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '8px', border: '1px solid #3f3f46', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.5)' }} 
                                  itemStyle={{ color: '#e4e4e7', fontWeight: 500 }} 
                                  labelStyle={{ color: '#f4f4f5', fontWeight: 'bold', marginBottom: '4px' }}
                                />
                                <Bar 
                                  dataKey="score" 
                                  radius={[0, 4, 4, 0]} 
                                  barSize={16}
                                  isAnimationActive={true}
                                  animationBegin={0}
                                  animationDuration={1200}
                                  animationEasing="ease-out"
                                >
                                  {analysisData.category_scores.map((entry, index) => <Cell key={`cell-${index}`} fill={getScoreColor(entry.score)} />)}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </motion.div>
                        ) : (
                          <motion.div
                            key="radar"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            transition={{ duration: 0.3 }}
                            className="w-full h-full"
                          >
                            <ResponsiveContainer width="100%" height="100%">
                              <RadarChart cx="50%" cy="50%" outerRadius="75%" data={analysisData.category_scores}>
                                <PolarGrid stroke="#3f3f46" />
                                <PolarAngleAxis dataKey="category" tick={{ fill: '#d4d4d8', fontSize: 10, fontWeight: 600 }} />
                                <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fontSize: 10, fill: '#71717a' }} />
                                <Radar 
                                  name="Score" 
                                  dataKey="score" 
                                  stroke="#3b82f6" 
                                  fill="#3b82f6" 
                                  fillOpacity={0.3} 
                                  dot={{ r: 4, fill: '#ffffff', strokeWidth: 2, stroke: '#3b82f6' }}
                                  activeDot={{ r: 6, fill: '#ffffff', stroke: '#3b82f6' }}
                                  isAnimationActive={true}
                                  animationBegin={0}
                                  animationDuration={1200}
                                  animationEasing="ease-out"
                                />
                                <Tooltip 
                                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '8px', border: '1px solid #3f3f46' }} 
                                  itemStyle={{ color: '#e4e4e7', fontWeight: 500 }}
                                  labelStyle={{ color: '#f4f4f5', fontWeight: 'bold', marginBottom: '4px' }}
                                />
                              </RadarChart>
                            </ResponsiveContainer>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center bg-zinc-900/50 border-2 border-dashed border-zinc-700 rounded-lg text-zinc-500 text-sm font-medium">Awaiting NLP Analysis Data</div>
                  )}
                </div>
              </div>

              {analysisData && (
                <div className="bg-zinc-800 p-6 rounded-xl shadow-lg border border-zinc-700 flex flex-col">
                  <h3 className="font-bold text-zinc-200 text-lg mb-4">Topic Performance Cards</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {analysisData.category_scores.map(renderMiniDonut)}
                  </div>
                </div>
              )}

              <div className="bg-zinc-800 p-6 rounded-xl shadow-lg border border-zinc-700 flex flex-col min-h-[400px]">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4 border-b border-zinc-700 pb-4">
                  <div>
                    <h3 className="font-bold text-zinc-200 text-lg">Analyzed Comments</h3>
                    <div className="text-zinc-500 font-medium text-sm mt-0.5">
                      {getFilteredAndSortedComments().length} {getFilteredAndSortedComments().length === 1 ? 'Comment' : 'Comments'}
                    </div>
                  </div>
                  
                  {/* 🚀 NEW CUSTOM DROPDOWNS (Main Dashboard) */}
                  {analysisData && (
                    <div className="flex flex-wrap gap-3">
                      <CustomSelect value={topicFilter} onChange={setTopicFilter} options={topicOptions} minWidth="220px" />
                      <CustomSelect value={scoreFilter} onChange={setScoreFilter} options={scoreOptions} minWidth="200px" />
                      <CustomSelect value={sortOrder} onChange={setSortOrder} options={sortOptions} minWidth="190px" />
                    </div>
                  )}
                </div>
                
                <motion.div layout className="flex-1 overflow-auto pr-2 space-y-4 max-h-[500px]">
                  <AnimatePresence mode="popLayout">
                    {!analysisData ? (
                      <div className="h-full flex items-center justify-center text-zinc-500 bg-zinc-900/50 rounded-lg border-2 border-dashed border-zinc-700 py-10">Awaiting NLP Analysis Data...</div>
                    ) : getFilteredAndSortedComments().length === 0 ? (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center text-zinc-500 py-10 font-medium">No comments match your current filter.</motion.div>
                    ) : (
                      getFilteredAndSortedComments().map((comment, idx) => (
                        <motion.div 
                          layout 
                          initial={{ opacity: 0, scale: 0.95, y: 10 }} 
                          animate={{ opacity: 1, scale: 1, y: 0 }} 
                          exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }}
                          transition={{ duration: 0.2 }}
                          key={`${comment.text}-${idx}`}
                          className="relative bg-zinc-800/40 border border-zinc-700/60 rounded-xl p-6 hover:shadow-md hover:bg-zinc-800/80 transition-all flex gap-5 items-start overflow-hidden"
                          style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                        >
                          <svg className="absolute top-4 right-4 w-12 h-12 text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                          </svg>

                          <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>
                            {comment.rating.toFixed(1)}
                          </div>
                          <div className="pt-1 flex-1 relative z-10">
                            <p className="text-zinc-300 leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                            <div className="flex flex-wrap gap-2 items-center">
                              {comment.topics && comment.topics.map((t, i) => (
                                <span key={i} className="bg-zinc-900/80 text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-zinc-700/50 shadow-sm">{t}</span>
                              ))}
                            </div>
                          </div>
                        </motion.div>
                      ))
                    )}
                  </AnimatePresence>
                </motion.div>
              </div>
            </motion.div>
          )}
        </div>
      </main>

      {/* JSON Import Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="bg-zinc-800 w-full max-w-lg rounded-2xl shadow-2xl transform transition-all border border-zinc-700">
            <div className="px-6 py-4 border-b border-zinc-700 flex justify-between items-center bg-zinc-900/50 rounded-t-2xl">
              <h3 className="font-bold text-lg text-zinc-200">Upload Evaluation</h3>
              <button onClick={() => { setIsModalOpen(false); setSelectedFile(null); setIsDragging(false); }} className="text-zinc-500 hover:text-zinc-300 text-2xl font-bold leading-none p-1">&times;</button>
            </div>
            <div className="p-8">
              <div className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${isDragging ? "border-blue-500 bg-blue-900/20 scale-[1.02]" : selectedFiles.length > 0 ? "border-blue-600 bg-blue-900/10" : "border-zinc-600 bg-zinc-900 hover:bg-zinc-800 hover:border-zinc-500"}`} onClick={() => fileInputRef.current.click()} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
                <div className={`p-4 rounded-full mb-4 shadow-sm transition-colors ${isDragging ? "bg-blue-900/50 text-blue-400" : "bg-zinc-800 text-blue-500 border border-zinc-700"}`}>
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                </div>
                {selectedFiles.length > 0 ? (
                  <div className="text-blue-400 font-bold text-lg mb-1 truncate w-full px-4">🚀 {selectedFiles.length} files selected</div>
                ) : isDragging ? (
                  <div className="text-blue-400 font-bold text-lg mb-1">Drop files here!</div>
                ) : (
                  <>
                    <p className="text-zinc-200 font-semibold mb-1">Click or drag files to upload</p>
                    <p className="text-sm text-zinc-500">Supports .PDF, .DOCX, .XLSX, and .CSV</p>
                  </>
                )}
                {/* 🚀 FIXED: Added 'multiple' to input */}
                <input type="file" multiple className="hidden" ref={fileInputRef} accept=".pdf,.docx,.xlsx,.csv" onChange={(e) => setSelectedFiles(Array.from(e.target.files))} />
              </div>

              <div className="mt-6 flex flex-col gap-2 relative z-50">
                <label className="text-sm font-semibold text-zinc-400 pl-1">Select Analysis Model:</label>
                <CustomSelect value={selectedModel} onChange={setSelectedModel} options={modelOptions} minWidth="100%" />
              </div>

              <div className="mt-8 flex justify-end gap-3">
                <button onClick={() => { setIsModalOpen(false); setSelectedFiles([]); }} className="px-6 py-2.5 rounded-lg font-medium text-zinc-400 hover:bg-zinc-700 transition-colors">Cancel</button>
                {/* 🚀 FIXED: Call handleBatchExtract */}
                <button onClick={handleBatchExtract} disabled={selectedFiles.length === 0 || isUploading} className={`px-6 py-2.5 rounded-lg font-medium shadow-sm transition-all ${selectedFiles.length === 0 || isUploading ? "bg-zinc-700 text-zinc-500 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-500 text-white"}`}>
                  {isUploading ? "Processing..." : "Analyze Batch"}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {selectedTopicModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="bg-zinc-800 w-full max-w-3xl max-h-[80vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-zinc-700">
            <div className="px-6 py-4 border-b border-zinc-700 flex justify-between items-start bg-zinc-900/50">
              <div>
                <h3 className="font-bold text-xl text-zinc-100">
                  Topic Details: {selectedTopicModal}
                </h3>
                <div className="text-zinc-500 font-medium text-sm mt-1">
                  {(() => {
                    const count = getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).length;
                    return `${count} ${count === 1 ? 'Comment' : 'Comments'}`;
                  })()}
                </div>
              </div>
              <div className="flex items-center gap-4 mt-1">
                <button onClick={() => {
                  setActiveTopic(selectedTopicModal);
                  setCurrentView('topic');
                  setSelectedTopicModal(null);
                }}
                  className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 text-zinc-100 px-5 py-2 rounded-2xl text-sm font-medium transition-all duration-200 shadow-md hover:shadow-lg hover:border-zinc-500">
                    View More Details
                </button>
                <button onClick={() => setSelectedTopicModal(null)} className="text-zinc-500 hover:text-zinc-300 text-3xl font-bold leading-none p-1">&times;</button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto flex-1 bg-zinc-900">
              
              {(() => {
                const topicSummaryData = analysisData.topic_summaries?.find(s => s.topic === selectedTopicModal);
                const topicCat = analysisData.category_scores?.find(c => c.category === selectedTopicModal);
                const rawCat = analysisData.raw_categories?.find(c => c.topic === selectedTopicModal);

                let stats = { assigned: null, scored: null, sentimentObj: null };

                if (rawCat && rawCat.comments) {
                  stats.assigned = rawCat.comments.length;
                  stats.scored = rawCat.comments.filter(c => c.score !== "" && c.score !== null).length;
                  stats.sentimentObj = {
                    pos: rawCat.comments.filter(c => c.sentiment === 'positive').length,
                    neu: rawCat.comments.filter(c => c.sentiment === 'neutral').length,
                    neg: rawCat.comments.filter(c => c.sentiment === 'negative').length,
                  };
                }

                if (!topicSummaryData && !topicCat && stats.assigned === null) return null;

                let avgValue = topicCat?.score > 0 ? (topicCat.score.toString().match(/\.\d{2,}/) ? topicCat.score.toFixed(2) : topicCat.score.toFixed(1)) + ' / 5.0' : 'N/A';

                let rawText = topicSummaryData ? topicSummaryData.summary : '';
                let cleanSummary = rawText.replace(new RegExp(`^Summary of ${selectedTopicModal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*`, 'i'), '').trim();
                cleanSummary = cleanSummary.replace(/^\d+\s+.*?(negative|positive|neutral|averages)\.\s*(Here is a concise sentence summarizing the qualitative themes:\s*)?/i, '').trim();

                if (!cleanSummary) cleanSummary = "No qualitative themes summarized.";

                return (
                  <div className="bg-[#222225] p-6 rounded-xl border border-zinc-700/60 mb-8 shadow-lg flex flex-col gap-5">
                    
                    <div className="flex items-center justify-between pb-2">
                      <h4 className="text-xl font-bold text-zinc-100">Topic Analysis</h4>
                      <div className="text-right flex flex-col items-end">
                        <span className="text-zinc-500 text-[10px] uppercase tracking-widest font-bold block mb-1">Average Score</span>
                        <div className="text-2xl font-black text-blue-400">{avgValue}</div>
                      </div>
                    </div>
                    
                    {stats.assigned !== null && (
                      <div className="bg-[#1a1a1d] p-5 rounded-lg border border-zinc-700/40 flex flex-col gap-5">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col">
                            <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Assigned Comments</span>
                            <span className="text-zinc-200 font-bold text-lg">{stats.assigned}</span>
                          </div>
                          {stats.scored !== null && (
                            <div className="flex flex-col">
                              <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Scored Comments</span>
                              <span className="text-zinc-200 font-bold text-lg">{stats.scored}</span>
                            </div>
                          )}
                        </div>
                        {stats.sentimentObj && (
                          <div className="pt-4 border-t border-zinc-800/80">
                            <span className="text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-3 block">Sentiment Distribution</span>
                            <div className="flex flex-wrap items-center gap-6">
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-green-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.pos} Positive</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.neu} Neutral</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-red-500"></div> <span className="text-zinc-200 font-semibold text-sm">{stats.sentimentObj.neg} Negative</span></span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}

              <div className="space-y-4">
                {getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).length === 0 ? (
                  <div className="text-center text-zinc-500 py-10 font-medium bg-zinc-800 rounded-xl border border-zinc-700">No comments explicitly matching this topic.</div>
                ) : (
                  getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).map((comment, idx) => (
                    <motion.div 
                      layout
                      initial={{ opacity: 0, scale: 0.95, y: 10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }}
                      transition={{ duration: 0.2 }}
                      key={`${comment.text}-${idx}`}
                      className="relative bg-zinc-800/40 border border-zinc-700/60 rounded-xl p-6 hover:shadow-md hover:bg-zinc-800/80 transition-all flex gap-5 items-start overflow-hidden"
                      style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                    >
                      <svg className="absolute top-4 right-4 w-12 h-12 text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                      </svg>

                      <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>{comment.rating.toFixed(1)}</div>
                      
                      <div className="flex-1 relative z-10 pt-1">
                        <p className="text-zinc-300 leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                        <div className="flex flex-col gap-2 items-start">
                          {comment.topics && comment.topics.map((t, i) => (
                            <span key={i} className="bg-zinc-900/80 text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-zinc-700/50 shadow-sm">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}

export default App;