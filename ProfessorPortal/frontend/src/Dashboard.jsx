import { useState, useRef } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { useOutletContext } from 'react-router-dom';

const CustomSelect = ({ value, onChange, options, minWidth = "160px" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = options.find(o => o.value === value) || options[0];

  return (
    <div className="relative shrink-0" style={{ minWidth }}>
      {isOpen && <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)}></div>}
      <button 
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative z-40 w-full bg-white dark:bg-zinc-900 border border-gray-300 dark:border-zinc-700 text-gray-700 dark:text-zinc-300 text-sm rounded-lg p-2.5 flex justify-between items-center gap-3 hover:border-gray-400 dark:hover:border-zinc-500 hover:bg-gray-50 dark:hover:bg-zinc-800/80 transition-all outline-none shadow-sm"
      >
        <span className="truncate font-medium">{selectedOption?.label}</span>
        <motion.svg animate={{ rotate: isOpen ? 180 : 0 }} className="w-4 h-4 text-gray-400 dark:text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></motion.svg>
      </button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.15 }}
            className="absolute z-50 mt-1.5 w-max min-w-full bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg shadow-xl overflow-hidden py-1 max-h-64 overflow-y-auto"
          >
            {options.map((opt) => (
              <div 
                key={opt.value}
                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                className={`px-4 py-2.5 text-sm cursor-pointer transition-colors ${value === opt.value ? 'bg-blue-50 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 font-bold' : 'text-gray-600 dark:text-zinc-300 hover:bg-gray-100 dark:hover:bg-zinc-700/80'}`}
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

function Dashboard() {
  const { 
    isDarkMode, setIsDarkMode, 
    analysisData, setAnalysisData,
    currentView, setCurrentView,
    activeTopic, setActiveTopic,
    selectedTopicModal, setSelectedTopicModal
  } = useOutletContext();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isGlobalDragging, setIsGlobalDragging] = useState(false);
  const [chartView, setChartView] = useState('bar');
  const fileInputRef = useRef(null);

  const [isUploading, setIsUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [scoreFilter, setScoreFilter] = useState('all');
  const [sortOrder, setSortOrder] = useState('desc'); 
  const [topicFilter, setTopicFilter] = useState('all');

  const getToastStyle = () => ({
    background: isDarkMode ? '#3f3f46' : '#ffffff',
    color: isDarkMode ? '#ffffff' : '#1f2937',
    border: isDarkMode ? 'none' : '1px solid #e5e7eb'
  });

  const processFile = (file) => {
    if (!file) return;
    setIsUploading(true);
    
    const loadingToast = toast.loading('Reading local JSON...', { style: getToastStyle() });
    const reader = new FileReader();
    
    reader.onload = (event) => {
      try {
        let rawString = event.target.result;
        rawString = rawString.replace(/None of the above \/ Other/gi, "Uncategorized/Unrated");
        rawString = rawString.replace(/None of the above\/other/gi, "Uncategorized/Unrated");
        
        const rawData = JSON.parse(rawString);
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
            course_id: rawData.course_id || "Imported Report",
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
        setIsModalOpen(false);
        setSelectedFile(null);
        setSearchQuery(''); // Reset search on new file
        toast.success('Dashboard Loaded!', { id: loadingToast, style: getToastStyle() });
        
      } catch (error) {
        console.error("Error parsing JSON:", error);
        toast.error('Invalid JSON file format.', { id: loadingToast, style: getToastStyle() });
      } finally {
        setIsUploading(false);
        setIsGlobalDragging(false);
      }
    };
    reader.readAsText(file);
  };

  const handleUpload = () => processFile(selectedFile);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      processFile(file); // Instant load
    }
  };

  const getScoreColor = (score) => {
    if (score === 0) return '#9ca3af'; 
    if (score < 1.5) return '#ef4444'; 
    if (score < 3.0) return '#f97316'; 
    if (score < 4.0) return '#f59e0b'; 
    if (score <= 5.0) return '#22c55e'; 
  };

  const getBadgeColorClass = (score) => {
    if (score === 0) return 'bg-gray-400'; 
    if (score < 1.5) return 'bg-red-500'; 
    if (score < 3.0) return 'bg-orange-500'; 
    if (score < 4.0) return 'bg-amber-500'; 
    if (score <= 5.0) return 'bg-green-500'; 
  };

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

    // Apply Search Query Filter
    if (searchQuery.trim() !== '') {
      const lowerQuery = searchQuery.toLowerCase();
      filtered = filtered.filter(c => c.text.toLowerCase().includes(lowerQuery));
    }

    const activeSort = ignoreGlobalFilters ? 'desc' : sortOrder;
    filtered.sort((a, b) => {
      return activeSort === 'desc' ? b.rating - a.rating : a.rating - b.rating;
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
        className="bg-gray-50 dark:bg-zinc-800/50 border border-gray-200 dark:border-zinc-700 p-4 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:shadow-lg dark:hover:border-zinc-500 transition-all group"
      >
        <div className="relative flex items-center justify-center mb-2">
          <svg className="w-20 h-20 transform -rotate-90">
            <circle cx="40" cy="40" r={radius} stroke="currentColor" strokeWidth="6" fill="transparent" className="text-gray-200 dark:text-zinc-700" />
            <circle cx="40" cy="40" r={radius} stroke={getScoreColor(cat.score)} strokeWidth="6" fill="transparent"
              strokeDasharray={circumference} strokeDashoffset={offset} 
              className="transition-all duration-1000" />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="text-lg font-black text-gray-900 dark:text-zinc-100">{cat.score === 0 ? 'N/A' : cat.score.toFixed(1)}</span>
          </div>
        </div>
        <span className="text-xs font-semibold text-gray-500 dark:text-zinc-400 text-center leading-tight truncate w-full px-2" title={cat.category}>{cat.category}</span>
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
    { value: '0', label: 'Unrated' }
  ];

  const sortOptions = [
    { value: 'desc', label: 'Highest Rated First' },
    { value: 'asc', label: 'Lowest Rated First' }
  ];

  const topicOptions = analysisData ? [
    { value: 'all', label: 'All Topics' },
    ...analysisData.category_scores.map(cat => ({ value: cat.category, label: cat.category })),
    { value: 'Uncategorized/Unrated', label: 'Uncategorized/Unrated' }
  ] : [];

  return (
    <div 
      className="relative flex flex-col h-full w-full"
      onDragOver={(e) => { e.preventDefault(); setIsGlobalDragging(true); }}
      onDragLeave={(e) => { 
        e.preventDefault(); 
        if (!e.currentTarget.contains(e.relatedTarget)) setIsGlobalDragging(false); 
      }}
      onDrop={(e) => {
        e.preventDefault();
        setIsGlobalDragging(false);
        if (e.dataTransfer.files?.length > 0) {
          processFile(e.dataTransfer.files[0]);
        }
      }}
    >
      {/* Global Drag & Drop Overlay */}
      <AnimatePresence>
        {isGlobalDragging && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="absolute inset-0 z-[100] bg-blue-500/20 backdrop-blur-sm border-4 border-blue-500 border-dashed flex items-center justify-center m-4 rounded-2xl pointer-events-none"
          >
            <div className="bg-white dark:bg-zinc-800 p-8 rounded-xl shadow-2xl flex flex-col items-center">
              <svg className="w-16 h-16 text-blue-500 mb-4 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
              <h2 className="text-3xl font-bold text-gray-800 dark:text-zinc-100">Drop JSON Report Here to Load</h2>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <header className="bg-white dark:bg-zinc-900 border-b border-gray-200 dark:border-zinc-800 px-8 py-5 flex justify-between items-center z-10 shadow-sm transition-colors duration-300">
        <div className="flex items-center gap-4">
          {currentView === 'topic' ? (
            <>
              <button onClick={() => setCurrentView('dashboard')} className="text-gray-500 dark:text-zinc-400 hover:text-gray-900 dark:hover:text-white transition-colors bg-gray-100 dark:bg-zinc-800 hover:bg-gray-200 dark:hover:bg-zinc-700 p-2 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
              </button>
              <h2 className="text-xl font-bold">{activeTopic}</h2>
            </>
          ) : (
            <h2 className="text-xl font-bold">
              {!analysisData ? 'Welcome to CourseEval' : 'Analytics Overview'}
            </h2>
          )}
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsDarkMode(!isDarkMode)} 
            className="p-2 rounded-lg bg-gray-100 dark:bg-zinc-800 text-gray-500 dark:text-zinc-400 hover:text-gray-900 dark:hover:text-zinc-100 transition-all border border-gray-200 dark:border-zinc-700 shadow-sm"
            title="Toggle Theme"
          >
            {isDarkMode ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
            )}
          </button>
          <button onClick={() => setIsModalOpen(true)} className="bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium shadow-sm transition-all text-sm">
            + Load JSON file
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-8 flex flex-col">
        {!analysisData ? (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex-1 flex flex-col items-center justify-center text-center max-w-2xl mx-auto">
            <div className="w-24 h-24 bg-blue-50 dark:bg-blue-900/30 rounded-full flex items-center justify-center mb-8 border border-blue-100 dark:border-blue-800/50">
              <svg className="w-12 h-12 text-blue-600 dark:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            </div>
            <h2 className="text-4xl font-extrabold mb-4 tracking-tight">Select a Report</h2>
            <p className="text-gray-500 dark:text-zinc-400 mb-8 font-medium">Drag & Drop anywhere or select a file to load.</p>
            <button onClick={() => setIsModalOpen(true)} className="bg-white dark:bg-zinc-800 border-2 border-blue-600 dark:border-blue-500 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-zinc-800/80 px-8 py-3 rounded-lg font-bold shadow-lg transition-all text-lg">
              Load JSON File
            </button>
          </motion.div>
        ) : currentView === 'topic' && activeTopic ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6 pb-8">
            {(() => {
              const topicSummaryData = analysisData.topic_summaries?.find(s => s.topic === activeTopic);
              const topicCat = analysisData.category_scores?.find(c => c.category === activeTopic);
              const rawCat = analysisData.raw_categories?.find(c => c.topic === activeTopic);
              let stats = { assigned: null, scored: null, sentimentObj: null };

              if (rawCat && rawCat.comments) {
                stats.assigned = rawCat.comments.length;
                
                const validScoredComments = rawCat.comments.filter(c => c.score !== "" && c.score !== null && Number(c.score) !== 0);
                stats.scored = validScoredComments.length;

                stats.sentimentObj = {
                  pos: validScoredComments.filter(c => Number(c.score) >= 4).length,
                  neu: validScoredComments.filter(c => Number(c.score) >= 3 && Number(c.score) < 4).length,
                  neg: validScoredComments.filter(c => Number(c.score) < 3).length,
                };
              }

              if (!topicSummaryData && !topicCat && stats.assigned === null) return null;
              let avgValue = topicCat?.score > 0 ? (topicCat.score.toString().match(/\.\d{2,}/) ? topicCat.score.toFixed(2) : topicCat.score.toFixed(1)) + ' / 5.0' : 'N/A';

              let cleanSummary = null;
              if (topicSummaryData && topicSummaryData.summary) {
                cleanSummary = topicSummaryData.summary.replace(/^Summary of.*?(positive|neutral|negative)\.\s*/i, '');
              }

              return (
                <div className="bg-white dark:bg-[#222225] p-6 rounded-xl border border-gray-200 dark:border-zinc-700/60 shadow-md flex flex-col gap-5">
                  <div className="flex items-center justify-between pb-2">
                    <h4 className="text-xl font-bold">Topic Analysis</h4>
                    <div className="text-right flex flex-col items-end">
                      <span className="text-gray-500 dark:text-zinc-500 text-[10px] uppercase tracking-widest font-bold block mb-1">Average Score</span>
                      <div className="text-2xl font-black text-blue-600 dark:text-blue-400">{avgValue}</div>
                    </div>
                  </div>
                  
                  {stats.assigned !== null && (
                    <div className="bg-gray-50 dark:bg-[#1a1a1d] p-5 rounded-lg border border-gray-200 dark:border-zinc-700/40 flex flex-col gap-5">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col">
                          <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Assigned Comments</span>
                          <span className="font-bold text-lg">{stats.assigned}</span>
                        </div>
                        {stats.scored !== null && (
                          <div className="flex flex-col">
                            <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Scored Comments</span>
                            <span className="font-bold text-lg">{stats.scored}</span>
                          </div>
                        )}
                      </div>
                      {stats.sentimentObj && (
                        <div className="pt-4 border-t border-gray-200 dark:border-zinc-800/80">
                          <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-3 block">Sentiment Distribution</span>
                          <div className="flex flex-wrap items-center gap-6">
                            <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-green-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.pos} Positive</span></span>
                            <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.neu} Neutral</span></span>
                            <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-red-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.neg} Negative</span></span>
                          </div>
                        </div>
                      )}
                      
                      {cleanSummary && (
                        <div className="pt-4 border-t border-gray-200 dark:border-zinc-800/80">
                          <p className="text-gray-700 dark:text-zinc-300 text-sm leading-relaxed">
                            <span className="text-blue-600 dark:text-blue-400 font-bold mr-2">AI Summary:</span>
                            {cleanSummary}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })()}

            <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-md border border-gray-200 dark:border-zinc-700 flex flex-col min-h-[400px]">
              <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-6 gap-4 border-b border-gray-200 dark:border-zinc-700 pb-4">
                <div className="shrink-0">
                  <h3 className="font-bold text-lg">Topic Comments</h3>
                  <div className="text-gray-500 dark:text-zinc-500 font-medium text-sm mt-0.5">
                    {getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).length} Comments
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-3 w-full xl:w-auto">
                  <div className="relative flex-1 xl:flex-none xl:min-w-[250px]">
                    <input 
                      type="text" 
                      placeholder="Search comments..." 
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-white dark:bg-zinc-900 border border-gray-300 dark:border-zinc-700 text-gray-700 dark:text-zinc-300 text-sm rounded-lg pl-10 pr-4 py-2.5 outline-none focus:border-blue-500 transition-all shadow-sm"
                    />
                    <svg className="absolute left-3 top-3 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  </div>
                  <CustomSelect value={scoreFilter} onChange={setScoreFilter} options={scoreOptions} minWidth="160px" />
                  <CustomSelect value={sortOrder} onChange={setSortOrder} options={sortOptions} minWidth="160px" />
                </div>
              </div>
              
              <motion.div layout className="flex-1 overflow-auto pr-2 space-y-4 max-h-[500px]">
                <AnimatePresence mode="popLayout">
                  {getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).length === 0 ? (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center text-gray-500 dark:text-zinc-500 py-10 font-medium">No comments match your current filter.</motion.div>
                  ) : (
                    getFilteredAndSortedComments(analysisData.analyzed_comments, activeTopic).map((comment, idx) => (
                      <motion.div 
                        layout initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }} transition={{ duration: 0.2 }} key={`${comment.text}-${idx}`}
                        className="relative bg-gray-50 dark:bg-zinc-800/40 border border-gray-200 dark:border-zinc-700/60 rounded-xl p-6 hover:shadow-md transition-all flex gap-5 items-start overflow-hidden"
                        style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                      >
                        <svg className="absolute top-4 right-4 w-12 h-12 text-gray-200 dark:text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                        </svg>

                        <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>{comment.rating === 0 ? "-" : comment.rating.toFixed(1)}</div>
                        <div className="pt-1 flex-1 relative z-10">
                          <p className="leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                          <div className="flex flex-wrap gap-2 items-center">
                            {comment.topics && comment.topics.map((t, i) => (
                              <span key={i} className="bg-white dark:bg-zinc-900/80 text-blue-600 dark:text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-gray-200 dark:border-zinc-700/50 shadow-sm">
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
          </motion.div>

        ) : (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6 pb-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[400px]">
              
              <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-md border border-gray-200 dark:border-zinc-700 flex flex-col justify-center items-center relative overflow-hidden">
                <h3 className="font-bold mb-6 absolute top-6 left-6">Overall Grade</h3>
                <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex flex-col items-center justify-center flex-1 mt-8">
                  <div className="flex items-baseline gap-2">
                    <span className="text-7xl font-black tracking-tighter" style={{ color: getScoreColor(analysisData.overall_score) }}>
                      {analysisData.overall_score.toFixed(1)}
                    </span>
                    <span className="text-3xl font-bold text-gray-400 dark:text-zinc-600">/ 5</span>
                  </div>
                  <span className="mt-3 text-xs font-bold text-gray-400 dark:text-zinc-500 uppercase tracking-widest">
                    {analysisData.analyzed_comments.length} Total Comments
                  </span>
                </motion.div>
              </div>

              <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-md border border-gray-200 dark:border-zinc-700 flex flex-col">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-bold">Category Breakdown</h3>
                  <div className="bg-gray-100 dark:bg-zinc-900 p-1 rounded-lg flex text-xs font-bold border border-gray-200 dark:border-zinc-700">
                    <button onClick={() => setChartView('bar')} className={`px-3 py-1.5 rounded-md transition-all ${chartView === 'bar' ? 'bg-white dark:bg-zinc-700 shadow-sm text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-zinc-500'}`}>Bar</button>
                    <button onClick={() => setChartView('radar')} className={`px-3 py-1.5 rounded-md transition-all ${chartView === 'radar' ? 'bg-white dark:bg-zinc-700 shadow-sm text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-zinc-500'}`}>Radar</button>
                  </div>
                </div>
                <div className="flex-1 min-h-[350px]">
                  <AnimatePresence mode="wait">
                    {chartView === 'bar' ? (
                      <motion.div key="bar" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.3 }} className="w-full h-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={analysisData.category_scores} layout="vertical" margin={{ top: 0, right: 20, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={isDarkMode ? "#3f3f46" : "#e5e7eb"} />
                            <XAxis type="number" domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} stroke={isDarkMode ? "#a1a1aa" : "#6b7280"} fontSize={12} />
                            <YAxis dataKey="category" type="category" width={220} stroke={isDarkMode ? "#d4d4d8" : "#374151"} fontSize={10} fontWeight={600} interval={0} />
                            <Tooltip cursor={{ fill: isDarkMode ? '#27272a' : '#f3f4f6' }} contentStyle={{ backgroundColor: isDarkMode ? '#18181b' : '#ffffff', borderColor: isDarkMode ? '#3f3f46' : '#e5e7eb', borderRadius: '8px' }} />
                            <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={true}>
                              {analysisData.category_scores.map((entry, index) => <Cell key={index} fill={getScoreColor(entry.score)} />)}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </motion.div>
                    ) : (
                      <motion.div key="radar" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.3 }} className="w-full h-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={analysisData.category_scores}>
                            <PolarGrid stroke={isDarkMode ? "#3f3f46" : "#e5e7eb"} />
                            <PolarAngleAxis dataKey="category" tick={{ fill: isDarkMode ? '#d4d4d8' : '#374151', fontSize: 10, fontWeight: 600 }} />
                            <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fontSize: 10, fill: isDarkMode ? '#71717a' : '#9ca3af' }} />
                            <Radar name="Score" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} dot={{ r: 4, fill: '#ffffff', strokeWidth: 2, stroke: '#3b82f6' }} isAnimationActive={true} />
                            <Tooltip contentStyle={{ backgroundColor: isDarkMode ? '#18181b' : '#ffffff', borderColor: isDarkMode ? '#3f3f46' : '#e5e7eb', borderRadius: '8px' }} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>

            <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-md border border-gray-200 dark:border-zinc-700 flex flex-col">
              <h3 className="font-bold text-lg mb-4">Topic Performance Cards</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {analysisData.category_scores.map(renderMiniDonut)}
              </div>
            </div>

            <div className="bg-white dark:bg-zinc-800 p-6 rounded-xl shadow-md border border-gray-200 dark:border-zinc-700 flex flex-col min-h-[400px]">
              <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-6 gap-4 border-b border-gray-200 dark:border-zinc-700 pb-4">
                <div className="shrink-0">
                  <h3 className="font-bold text-lg">Analyzed Comments</h3>
                  <div className="text-gray-500 dark:text-zinc-500 font-medium text-sm mt-0.5">
                    {getFilteredAndSortedComments().length} Comments
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-3 w-full xl:w-auto">
                  <div className="relative flex-1 xl:flex-none xl:min-w-[250px]">
                    <input 
                      type="text" 
                      placeholder="Search comments..." 
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-white dark:bg-zinc-900 border border-gray-300 dark:border-zinc-700 text-gray-700 dark:text-zinc-300 text-sm rounded-lg pl-10 pr-4 py-2.5 outline-none focus:border-blue-500 transition-all shadow-sm"
                    />
                    <svg className="absolute left-3 top-3 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  </div>
                  <CustomSelect value={topicFilter} onChange={setTopicFilter} options={topicOptions} minWidth="180px" />
                  <CustomSelect value={scoreFilter} onChange={setScoreFilter} options={scoreOptions} minWidth="150px" />
                  <CustomSelect value={sortOrder} onChange={setSortOrder} options={sortOptions} minWidth="150px" />
                </div>
              </div>
              
              <motion.div layout className="flex-1 overflow-auto pr-2 space-y-4 max-h-[500px]">
                <AnimatePresence mode="popLayout">
                  {getFilteredAndSortedComments().length === 0 ? (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center text-gray-500 dark:text-zinc-500 py-10 font-medium">No comments match your current filter.</motion.div>
                  ) : (
                    getFilteredAndSortedComments().map((comment, idx) => (
                      <motion.div 
                        layout initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }} transition={{ duration: 0.2 }} key={`${comment.text}-${idx}`}
                        className="relative bg-gray-50 dark:bg-zinc-800/40 border border-gray-200 dark:border-zinc-700/60 rounded-xl p-6 hover:shadow-md transition-all flex gap-5 items-start overflow-hidden"
                        style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                      >
                        <svg className="absolute top-4 right-4 w-12 h-12 text-gray-200 dark:text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                        </svg>

                        <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>
                          {comment.rating === 0 ? "-" : comment.rating.toFixed(1)}
                        </div>
                        <div className="pt-1 flex-1 relative z-10">
                          <p className="leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                          <div className="flex flex-wrap gap-2 items-center">
                            {comment.topics && comment.topics.map((t, i) => (
                              <span key={i} className="bg-white dark:bg-zinc-900/80 text-blue-600 dark:text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-gray-200 dark:border-zinc-700/50 shadow-sm">{t}</span>
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

      {/* JSON Import Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-gray-900/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="bg-white dark:bg-zinc-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden border border-gray-200 dark:border-zinc-700">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-zinc-700 flex justify-between items-center bg-gray-50 dark:bg-zinc-900/50">
              <h3 className="font-bold text-lg">Load Report JSON</h3>
              <button onClick={() => { setIsModalOpen(false); setSelectedFile(null); setIsDragging(false); }} className="text-gray-400 dark:text-zinc-500 hover:text-gray-600 dark:hover:text-zinc-300 text-2xl font-bold p-1">&times;</button>
            </div>
            <div className="p-8">
              <div 
                className={`border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${isDragging ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 scale-[1.02]" : selectedFile ? "border-blue-600 bg-blue-50 dark:bg-blue-900/10" : "border-gray-300 dark:border-zinc-600 bg-gray-50 dark:bg-zinc-900 hover:bg-gray-100 dark:hover:bg-zinc-800"}`} 
                onClick={() => fileInputRef.current.click()} 
                onDragOver={handleDragOver} 
                onDragLeave={handleDragLeave} 
                onDrop={handleDrop}
              >
                <div className={`p-4 rounded-full mb-4 shadow-sm transition-colors ${isDragging ? "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400" : "bg-white dark:bg-zinc-800 text-blue-500 border border-gray-200 dark:border-zinc-700"}`}>
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                </div>
                {selectedFile ? (
                  <div className="text-blue-600 dark:text-blue-400 font-bold text-lg mb-1 truncate w-full px-4">{selectedFile.name}</div>
                ) : (
                  <>
                    <p className="font-semibold mb-1">Click or drag JSON file to load</p>
                    <p className="text-sm text-gray-500 dark:text-zinc-500">Only accepts AI-generated .json reports</p>
                  </>
                )}
                <input type="file" className="hidden" ref={fileInputRef} accept=".json" onChange={(e) => {
                  if (e.target.files.length > 0) {
                    setSelectedFile(e.target.files[0]);
                    processFile(e.target.files[0]); // Instantly load when selected
                  }
                }} />
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <button onClick={() => { setIsModalOpen(false); setSelectedFile(null); }} className="px-6 py-2.5 rounded-lg text-gray-500 dark:text-zinc-400 hover:bg-gray-100 dark:hover:bg-zinc-700 font-medium transition-colors">Cancel</button>
                <button onClick={handleUpload} disabled={!selectedFile || isUploading} className={`px-6 py-2.5 rounded-lg font-medium shadow-sm transition-all ${!selectedFile || isUploading ? "bg-gray-200 dark:bg-zinc-700 text-gray-400 dark:text-zinc-500 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 text-white"}`}>
                  {isUploading ? "Loading..." : "Load Dashboard"}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Topic Details Modal */}
      {selectedTopicModal && (
        <div className="fixed inset-0 bg-gray-900/60 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="bg-white dark:bg-zinc-800 w-full max-w-3xl max-h-[80vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-200 dark:border-zinc-700">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-zinc-700 flex justify-between items-start bg-gray-50 dark:bg-zinc-900/50">
              <div className="flex-1 pr-4 min-w-0">
                <h3 className="font-bold text-xl truncate">
                  Topic Details: {selectedTopicModal}
                </h3>
                <div className="text-gray-500 dark:text-zinc-500 font-medium text-sm mt-1">
                  {(() => {
                    const count = getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).length;
                    return `${count} ${count === 1 ? 'Comment' : 'Comments'}`;
                  })()}
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0 mt-1">
                <button onClick={() => {
                  setActiveTopic(selectedTopicModal);
                  setCurrentView('topic');
                  setSelectedTopicModal(null);
                }}
                  className="bg-gray-100 dark:bg-zinc-800 hover:bg-gray-200 dark:hover:bg-zinc-700 border border-gray-300 dark:border-zinc-600 px-5 py-2 rounded-xl text-sm font-medium transition-all duration-200 shadow-sm hover:shadow-md whitespace-nowrap">
                    View More Details
                </button>
                <button onClick={() => setSelectedTopicModal(null)} className="text-gray-400 dark:text-zinc-500 hover:text-gray-600 dark:hover:text-zinc-300 text-3xl font-bold leading-none p-1">&times;</button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto flex-1 bg-white dark:bg-zinc-900">
              {(() => {
                const topicSummaryData = analysisData.topic_summaries?.find(s => s.topic === selectedTopicModal);
                const topicCat = analysisData.category_scores?.find(c => c.category === selectedTopicModal);
                const rawCat = analysisData.raw_categories?.find(c => c.topic === selectedTopicModal);
                let stats = { assigned: null, scored: null, sentimentObj: null };

                if (rawCat && rawCat.comments) {
                  stats.assigned = rawCat.comments.length;

                  const validScoredComments = rawCat.comments.filter(c => c.score !== "" && c.score !== null && Number(c.score) !== 0);
                  stats.scored = validScoredComments.length;

                  stats.sentimentObj = {
                    pos: validScoredComments.filter(c => Number(c.score) >= 4).length,
                    neu: validScoredComments.filter(c => Number(c.score) >= 3 && Number(c.score) < 4).length,
                    neg: validScoredComments.filter(c => Number(c.score) < 3).length,
                  };
                }

                if (!topicSummaryData && !topicCat && stats.assigned === null) return null;
                let avgValue = topicCat?.score > 0 ? (topicCat.score.toString().match(/\.\d{2,}/) ? topicCat.score.toFixed(2) : topicCat.score.toFixed(1)) + ' / 5.0' : 'N/A';

                let cleanSummary = null;
                if (topicSummaryData && topicSummaryData.summary) {
                  cleanSummary = topicSummaryData.summary.replace(/^Summary of.*?(positive|neutral|negative)\.\s*/i, '');
                }

                return (
                  <div className="bg-gray-50 dark:bg-[#222225] p-6 rounded-xl border border-gray-200 dark:border-zinc-700/60 mb-8 shadow-md flex flex-col gap-5">
                    <div className="flex items-center justify-between pb-2">
                      <h4 className="text-xl font-bold">Topic Analysis</h4>
                      <div className="text-right flex flex-col items-end">
                        <span className="text-gray-500 dark:text-zinc-500 text-[10px] uppercase tracking-widest font-bold block mb-1">Average Score</span>
                        <div className="text-2xl font-black text-blue-600 dark:text-blue-400">{avgValue}</div>
                      </div>
                    </div>
                    
                    {stats.assigned !== null && (
                      <div className="bg-white dark:bg-[#1a1a1d] p-5 rounded-lg border border-gray-200 dark:border-zinc-700/40 flex flex-col gap-5">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="flex flex-col">
                            <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Assigned Comments</span>
                            <span className="font-bold text-lg">{stats.assigned}</span>
                          </div>
                          {stats.scored !== null && (
                            <div className="flex flex-col">
                              <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-1">Scored Comments</span>
                              <span className="font-bold text-lg">{stats.scored}</span>
                            </div>
                          )}
                        </div>
                        {stats.sentimentObj && (
                          <div className="pt-4 border-t border-gray-200 dark:border-zinc-800/80">
                            <span className="text-gray-500 dark:text-zinc-500 text-[10px] font-bold uppercase tracking-widest mb-3 block">Sentiment Distribution</span>
                            <div className="flex flex-wrap items-center gap-6">
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-green-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.pos} Positive</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-amber-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.neu} Neutral</span></span>
                              <span className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-red-500"></div> <span className="font-semibold text-sm">{stats.sentimentObj.neg} Negative</span></span>
                            </div>
                          </div>
                        )}

                        {cleanSummary && (
                          <div className="pt-4 border-t border-gray-200 dark:border-zinc-800/80">
                            <p className="text-gray-700 dark:text-zinc-300 text-sm leading-relaxed">
                              <span className="text-blue-600 dark:text-blue-400 font-bold mr-2">AI Summary:</span>
                              {cleanSummary}
                            </p>
                          </div>
                        )}

                      </div>
                    )}
                  </div>
                );
              })()}

              <div className="space-y-4">
                {getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).length === 0 ? (
                  <div className="text-center text-gray-500 dark:text-zinc-500 py-10 font-medium bg-gray-50 dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700">No comments explicitly matching this topic.</div>
                ) : (
                  getFilteredAndSortedComments(analysisData.analyzed_comments, selectedTopicModal, true).map((comment, idx) => (
                    <motion.div 
                      layout initial={{ opacity: 0, scale: 0.95, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.1 } }} transition={{ duration: 0.2 }} key={`${comment.text}-${idx}`}
                      className="relative bg-gray-50 dark:bg-zinc-800/40 border border-gray-200 dark:border-zinc-700/60 rounded-xl p-6 hover:shadow-md transition-all flex gap-5 items-start overflow-hidden"
                      style={{ borderLeft: `4px solid ${getScoreColor(comment.rating)}` }}
                    >
                      <svg className="absolute top-4 right-4 w-12 h-12 text-gray-200 dark:text-zinc-700/30 pointer-events-none" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                      </svg>

                      <div className={`flex items-center justify-center font-bold w-12 h-12 rounded-full shrink-0 shadow-sm text-lg ${getBadgeColorClass(comment.rating)} text-white relative z-10`}>{comment.rating === 0 ? "-" : comment.rating.toFixed(1)}</div>
                      <div className="pt-1 flex-1 relative z-10">
                        <p className="leading-relaxed font-medium mb-4 pr-8">{comment.text}</p>
                        <div className="flex flex-wrap gap-2 items-center">
                          {comment.topics && comment.topics.map((t, i) => (
                            <span key={i} className="bg-white dark:bg-zinc-900/80 text-blue-600 dark:text-blue-400 text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-md font-bold border border-gray-200 dark:border-zinc-700/50 shadow-sm">
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

export default Dashboard;