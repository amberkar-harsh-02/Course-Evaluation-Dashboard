import { createContext, useContext, useMemo, useState } from 'react';
import PropTypes from 'prop-types';

/**
 * The report that is open right now, so the sidebar can list its topics.
 * Shape: { id, course, term, topics: [{ topic, average }] } or null.
 */
const ReportNavContext = createContext({ openReport: null, setOpenReport: () => {} });

export function ReportNavProvider({ children }) {
  const [openReport, setOpenReport] = useState(null);
  const value = useMemo(() => ({ openReport, setOpenReport }), [openReport]);
  return <ReportNavContext.Provider value={value}>{children}</ReportNavContext.Provider>;
}

ReportNavProvider.propTypes = { children: PropTypes.node };

// eslint-disable-next-line react-refresh/only-export-components
export const useReportNav = () => useContext(ReportNavContext);
