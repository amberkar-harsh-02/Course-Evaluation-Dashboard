import { useNavigate, useOutletContext } from 'react-router-dom';
import { motion } from 'framer-motion';
import imgLoad from './assets/dash.png';
import imgDashboard from './assets/dashdata.png';
import imgRadar from './assets/radar.png';
import imgBar from './assets/cat.png';
import imgTopic from './assets/topdet.png';
import imgFilter from './assets/filter.png';

function Help() {
  const navigate = useNavigate();
  // Pull shared state from App.jsx
  const { isDarkMode, setIsDarkMode } = useOutletContext();

  const theme = {
    btnBg: isDarkMode ? 'bg-zinc-800' : 'bg-white',
    btnHover: isDarkMode ? 'hover:bg-zinc-700' : 'hover:bg-slate-100',
    border: isDarkMode ? 'border-zinc-800' : 'border-slate-200',
    textHeading: isDarkMode ? 'text-zinc-200' : 'text-slate-800',
    textSub: isDarkMode ? 'text-zinc-400' : 'text-slate-600',
    cardBg: isDarkMode ? 'bg-zinc-800/50' : 'bg-white',
    cardBorder: isDarkMode ? 'border-zinc-700/60' : 'border-slate-300',
    imgBorder: isDarkMode ? 'border-zinc-700' : 'border-slate-300'
  };

  return (
    <main className="flex-1 overflow-y-auto">
      <div className="p-8 max-w-4xl mx-auto">
        
        <header className={`flex items-center justify-between mb-12 border-b pb-6 ${theme.border}`}>
          <div>
            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-zinc-100' : 'text-slate-900'}`}>
              Course<span className="text-blue-500">Eval</span> User Manual
            </h1>
            <p className={`font-medium mt-2 ${isDarkMode ? 'text-zinc-500' : 'text-slate-500'}`}>
              Faculty Guide to Automated NLP Course Evaluations
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`${theme.btnBg} ${theme.btnHover} ${theme.border} border p-2.5 rounded-lg shadow-sm transition-all flex items-center justify-center text-slate-500 dark:text-zinc-400`}
              title="Toggle Theme"
            >
              {isDarkMode ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
              )}
            </button>

            <button 
              onClick={() => navigate('/dashboard')} 
              className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-bold shadow-md transition-all text-sm flex items-center gap-2 border border-blue-400/30"
            >
              Go to Dashboard
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </button>
          </div>
        </header>

        <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-16">
          <h2 className="text-2xl font-bold text-blue-500 mb-4">1. Overview</h2>
          <div className={`${theme.cardBg} p-6 rounded-xl border ${theme.cardBorder} leading-relaxed space-y-4`}>
            <p>Welcome to the CourseEval dashboard.</p>
            <p>
              The Course Evaluation Analytics Platform is an automated pipeline that reads raw, unstructured student course
              evaluations and turns them into a clear, navigable dashboard of insights. Instead of a professor scrolling through
              hundreds of loose comments at the end of a semester, the platform reads every comment, determines what each
              one is actually about, scores the sentiment behind it, and organizes everything into topic-based cards on a
              website, each with a score, a written takeaway, and a reliability flag.
            </p>
            <p>We have analyzed your submitted course evaluations, and you can now investigate the results using this platform.</p>
            <p><b>Analysis Description:</b> Please review the following document for an overview of the analysis performed and guidance on interpreting your results.</p>
            <p>
                <a 
                href="https://drive.google.com/file/d/1qSiXn0aJ2M5cgBKqwrhvDSuceaB9F2kk/view?usp=drive_link" 
                target="_blank" 
                rel="noopener noreferrer"
                className="inline-flex bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-bold shadow-md transition-all text-sm items-center gap-2 border border-blue-400/30"
              >
                Analysis Description Document
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
              </a>
            </p>
            <p>Next, follow the instructions in the following section to download your results file and learn how to use the platform.</p>
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="space-y-12">
          <h2 className="text-2xl font-bold text-blue-500 mb-6">2. Step-by-Step Walkthrough</h2>

          <div className="flex flex-col gap-4">
            <h3 className={`text-xl font-bold ${theme.textHeading}`}>A. Importing a Report</h3>
            
            <p className={theme.textSub}>
              To begin, you will need to download your analysis results and import them into the dashboard.
            </p>

            <ol className={`list-decimal list-outside ml-5 space-y-2 ${theme.textSub}`}>
              <li>Click the download button below to open the shared Google Drive folder.</li>
              <li>Locate the folder labeled with <strong className={theme.textHeading}>your initials and university name</strong>.</li>
              <li>Download the <strong className={theme.textHeading}>JSON</strong> results file from your folder.</li>
              <li>Go to the <strong className={theme.textHeading}>Dashboard</strong> page and click <strong className={theme.textHeading}>Load JSON File</strong>.</li>
              <li>Select the downloaded JSON file to import your analysis results into the platform.</li>
            </ol>

            <div className="mt-2 mb-2">
              <a 
                href="https://drive.google.com/drive/folders/1u9bE1VYYXE9HXX6t8H7UPZ11k8YfnKnN?usp=drive_link" 
                target="_blank" 
                rel="noopener noreferrer"
                className="inline-flex bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-bold shadow-md transition-all text-sm items-center gap-2 border border-blue-400/30"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                Download Result File(s)
              </a>
            </div>

            <p className={theme.textSub}>
              <strong className={theme.textHeading}>Note:</strong> Each participant has a dedicated folder containing their analysis results. Be sure to download the JSON file from <strong className={theme.textHeading}>your folder</strong>.
            </p>

            <img src={imgLoad} alt="Select a Report View" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder} mt-4`} />
          </div>

          <div className="flex flex-col gap-4">
            <h3 className={`text-xl font-bold ${theme.textHeading}`}>B. Analyzing the Dashboard</h3>
            <p className={theme.textSub}>The main dashboard provides your Overall Grade, a Category Breakdown, and quick-glance performance donuts for every academic topic.</p>
            <img src={imgDashboard} alt="Dashboard Overview" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder}`} />
          </div>
          
          <div className="flex flex-col gap-4">
            <h3 className={`text-xl font-bold ${theme.textHeading}`}>C. Category Breakdown Charts</h3>
            <p className={theme.textSub}>You can toggle the Category Breakdown between a standard Bar chart and a Radar chart. Hovering over any data point will reveal the exact numerical score for that category.</p>
            <div className="grid grid-cols-2 gap-4">
              <img src={imgBar} alt="Bar Chart View" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder}`} />
              <img src={imgRadar} alt="Radar Chart View" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder}`} />
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <h3 className={`text-xl font-bold ${theme.textHeading}`}>D. Topic Deep-Dive</h3>
            <p className={theme.textSub}>Clicking on any topic donut will open a detailed modal showing sentiment distribution (Positive, Neutral, Negative) and the specific comments assigned to that theme.</p>
            <img src={imgTopic} alt="Topic Details Modal" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder}`} />
          </div>

          <div className="flex flex-col gap-4">
            <h3 className={`text-xl font-bold ${theme.textHeading}`}>E. Filtering Feedback</h3>
            <p className={theme.textSub}>Use the dropdown filters located above the comment lists to sort by specific topics, targeted scores, or highest/lowest rated feedback.</p>
            <img src={imgFilter} alt="Filters Demo" className={`w-full rounded-xl border shadow-lg ${theme.imgBorder}`} />
          </div>
        </motion.section>

        {/* Section 3: Feedback */}
          <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="space-y-6 mt-16">
            <h2 className="text-2xl font-bold text-blue-500 mb-4">3. Feedback & Evaluation</h2>
            <div className={`${theme.cardBg} p-8 rounded-xl border ${theme.cardBorder} flex flex-col items-center text-center shadow-sm`}>
              <div className="w-16 h-16 bg-blue-50 dark:bg-blue-900/20 rounded-full flex items-center justify-center mb-4 border border-blue-100 dark:border-blue-800/50">
                <svg className="w-8 h-8 text-blue-600 dark:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
              </div>
              <h3 className={`text-xl font-bold ${theme.textHeading} mb-3`}>Help Us Improve CourseEval</h3>
              <p className={`${theme.textSub} max-w-2xl leading-relaxed mb-8`}>
                As part of our project, we invite you to complete a brief survey about your experience with the analysis results and this web tool. Your feedback is crucial in helping us evaluate the quality of the analysis and improve the platform for future use.
              </p>
              <a 
                href="https://forms.gle/ABn8jdDPNi3EgSBw5" 
                target="_blank" 
                rel="noopener noreferrer"
                className="bg-white dark:bg-zinc-800 text-blue-600 dark:text-blue-400 border-2 border-blue-600 dark:border-blue-500 hover:bg-blue-50 dark:hover:bg-zinc-700 px-8 py-3 rounded-lg font-bold shadow-md transition-all flex items-center gap-2"
              >
                Take the Evaluation Survey
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
              </a>
            </div>
          </motion.section>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-16 mb-8 pt-8 border-t border-slate-200 dark:border-zinc-800 flex justify-center">
          <button 
            onClick={() => navigate('/dashboard')} 
            className="bg-blue-600 hover:bg-blue-500 text-white px-10 py-5 rounded-2xl font-bold shadow-xl hover:shadow-2xl hover:-translate-y-1 transition-all text-xl flex items-center gap-3 border border-blue-400/30"
          >
            Go to Dashboard
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
          </button>
        </motion.div>

        

      </div>
    </main>
  );
}

export default Help;