import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api } from '../api';
import Dashboard, { cleanReportText, normalizeReport } from '../components/ReportDashboard';

const PIPELINE_OTHER = 'None of the above / Other';
const DISPLAY_OTHER = 'Uncategorized/Unrated';

// The dashboard shows "Uncategorized/Unrated"; the stored report keeps the pipeline's label
const toDisplay = (report) => JSON.parse(JSON.stringify(report).split(PIPELINE_OTHER).join(DISPLAY_OTHER));
const toStored = (report) => JSON.parse(JSON.stringify(report).split(DISPLAY_OTHER).join(PIPELINE_OTHER));

export default function ReportView() {
  const { reportId } = useParams();
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [analysisData, setAnalysisDataState] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [currentView, setCurrentView] = useState('dashboard');
  const [activeTopic, setActiveTopic] = useState(null);
  const [selectedTopicModal, setSelectedTopicModal] = useState(null);
  const loadedRaw = useRef(null);

  useEffect(() => {
    api(`/reports/${reportId}`)
      .then((result) => {
        const normalized = normalizeReport(cleanReportText(toDisplay(result.report)));
        loadedRaw.current = normalized.raw_report;
        setMeta(result);
        setAnalysisDataState(normalized);
      })
      .catch((err) => setError(err.message));
  }, [reportId]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode);
    return () => document.documentElement.classList.remove('dark');
  }, [isDarkMode]);

  // The dashboard calls this after "Save" in ignore mode; persist the edited report to the server
  const setAnalysisData = useCallback((next) => {
    setAnalysisDataState(next);
    if (next?.raw_report && next.raw_report !== loadedRaw.current) {
      loadedRaw.current = next.raw_report;
      api(`/reports/${reportId}`, { method: 'PUT', body: { report: toStored(next.raw_report) } })
        .then(() => toast.success('Changes saved to your report'))
        .catch((err) => toast.error(`Could not save: ${err.message}`));
    }
  }, [reportId]);

  if (error) {
    return (
      <div className="page">
        <p className="notice-error">{error}</p>
        <Link to="/" className="btn-secondary mt-4">Back to my reports</Link>
      </div>
    );
  }
  if (!analysisData) return <div className="p-8 text-sm text-slate-500">Loading report…</div>;

  return (
    <div className="flex h-screen flex-col bg-slate-50 text-slate-900 dark:bg-zinc-900 dark:text-zinc-100">
      <div className="flex items-center gap-3 border-b border-slate-200 bg-white px-6 py-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
        <Link to="/" className="text-blue-800 hover:underline dark:text-blue-400">← My reports</Link>
        <span className="text-slate-300">/</span>
        <span className="font-medium">{meta.course}</span>
        {meta.term && <span className="text-slate-500">· {meta.term}</span>}
      </div>
      <div className="min-h-0 flex-1">
        <Dashboard
          isDarkMode={isDarkMode} setIsDarkMode={setIsDarkMode}
          analysisData={analysisData} setAnalysisData={setAnalysisData}
          currentView={currentView} setCurrentView={setCurrentView}
          activeTopic={activeTopic} setActiveTopic={setActiveTopic}
          selectedTopicModal={selectedTopicModal} setSelectedTopicModal={setSelectedTopicModal}
          allowFileLoad={false}
          title={meta.course}
        />
      </div>
    </div>
  );
}
