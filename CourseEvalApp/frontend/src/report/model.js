// Report data helpers: clean-up, the per-topic view, ignoring comments and export.
// Works on the pipeline's report format (NLP/README.md "Output format"). The recalculation mirrors
// NLP/main.py exactly, so scores after ignoring comments match what the pipeline would compute.

export const OTHER_LABEL = 'None of the above / Other';
const MIN_RELIABLE = 5;
const LOW_CONFIDENCE = 0.35;

// The pipeline writes null scores as "", so only real integers count as scored
export const toScore = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const score = Number(value);
  return Number.isInteger(score) ? score : null;
};

// Same as Python round(value, 2): half-to-even on the exact binary value
const roundTo2 = (value) => {
  const [whole, frac] = Math.abs(value).toFixed(60).split('.');
  let cents = Number(whole) * 100 + Number(frac.slice(0, 2));
  const rest = frac.slice(2);
  const half = `5${'0'.repeat(rest.length - 1)}`;
  if (rest > half || (rest === half && cents % 2 === 1)) cents += 1;
  return (Math.sign(value) * cents) / 100;
};

const meanScore = (scores) => (scores.length ? roundTo2(scores.reduce((sum, s) => sum + s, 0) / scores.length) : null);

const reliabilityFor = (comments) => {
  const scored = comments.filter((c) => toScore(c.score) !== null);
  if (scored.length === 0) return 'unscored';
  if (comments.some((c) => c.scoring_status === 'model_error')) return 'needs_review';
  if (scored.length < MIN_RELIABLE) return 'low_sample';
  if (scored.some((c) => typeof c.confidence === 'number' && c.confidence < LOW_CONFIDENCE)) return 'mixed_confidence';
  return 'reliable';
};

export const recalculate = (report) => {
  const perFeedback = {};
  const categories = (report.categories || []).map((cat) => {
    if (cat.topic === OTHER_LABEL) return cat;
    const active = (cat.comments || []).filter((c) => c.ignored !== true);
    const scores = [];
    active.forEach((c) => {
      const score = toScore(c.score);
      if (score === null) return;
      scores.push(score);
      (perFeedback[c.feedback] ||= []).push(score);
    });
    return { ...cat, average_score: meanScore(scores), scored_comment_count: scores.length, reliability: reliabilityFor(active) };
  });
  const byTopic = Object.fromEntries(categories.map((cat) => [cat.topic, cat]));
  const categoryScores = (report.category_scores || []).map((cs) => (
    byTopic[cs.category] ? { ...cs, average_score: byTopic[cs.category].average_score, comment_count: byTopic[cs.category].comment_count } : cs
  ));
  const perComment = Object.values(perFeedback).map((s) => s.reduce((a, b) => a + b, 0) / s.length);
  return { ...report, overall_score: meanScore(perComment), category_scores: categoryScores, categories };
};

// Older exports store list bullets as "•" or the replacement character; same rules as the pipeline
const BULLETS = '•●○◦▪▫■□‣⁃∙·➢➤►▶✓✔�';
const escapeClass = (chars) => chars.replace(/[\\\]^-]/g, '\\$&');
const LINE_BULLET = `(?:[${escapeClass(BULLETS)}*]|-(?=\\s))`;

export const stripBullets = (text) => {
  if (typeof text !== 'string') return text;
  return text
    .replace(new RegExp(`\\n[ \\t]*${LINE_BULLET}[ \\t]*`, 'g'), '; ')
    .replace(new RegExp(`^[ \\t]*${LINE_BULLET}[ \\t]*`), '')
    .replace(new RegExp(`[ \\t]+[${escapeClass(BULLETS)}][ \\t]+`, 'g'), '; ')
    .replace(/:\s*;\s*/g, ': ')
    .replace(/(;\s*)+/g, '; ')
    .replace(/�/g, "'");
};

export const cleanReport = (report) => ({
  ...report,
  categories: (report.categories || []).map((cat) => ({
    ...cat,
    topic: cat.topic === 'Uncategorized/Unrated' ? OTHER_LABEL : cat.topic,
    comments: (cat.comments || []).map((c) => ({ ...c, feedback: stripBullets(c.feedback) })),
  })),
  topic_summaries: (report.topic_summaries || []).map((s) => ({
    ...s,
    topic: s.topic === 'Uncategorized/Unrated' ? OTHER_LABEL : s.topic,
    summary: stripBullets(s.summary),
  })),
});

// The pipeline prefixes summaries with counts ("Summary of Pace: 8 assigned comments; ... negative.").
// The page shows those numbers itself, so keep only the written themes.
const themeText = (summary, topic) => {
  if (!summary) return '';
  let text = summary.replace(/^Summary of .*?(positive|neutral|negative)\.\s*/i, '');
  text = text.replace(new RegExp(`^Summary of ${topic.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*`, 'i'), '');
  // The "Other" group only gets a count sentence, which the page already says in words
  text = text.replace(/^\d+ generic or uncategorized comments?; excluded from rubric averages\.\s*/i, '');
  return text.trim();
};

// Short topic names for charts and cards (full name is shown in titles and tooltips)
const SHORT_NAMES = {
  'Course organization and structure': 'Organization',
  'Student engagement and participation': 'Engagement',
  'Clarity of explanations': 'Clarity',
  'Effectiveness of assignments': 'Assignments',
  'Classroom atmosphere': 'Atmosphere',
  "Instructor's communication and availability": 'Communication',
  'Inclusivity and sense of belonging': 'Inclusivity',
  'Grading and feedback': 'Grading and feedback',
  'Learning resources and materials': 'Resources',
};
export const shortName = (topic) => SHORT_NAMES[topic] || topic;

export const scoreTone = (score) => {
  if (score === null || score === undefined) return 'none';
  if (score < 2.5) return 'low';
  if (score < 3.75) return 'mid';
  return 'high';
};

export const formatScore = (value, digits = 2) => (value === null || value === undefined ? '—' : Number(value).toFixed(digits));

// Everything the report page shows, derived from the stored report
export const buildView = (report) => {
  const summaries = Object.fromEntries((report.topic_summaries || []).map((s) => [s.topic, s.summary]));
  const commentMap = new Map();
  const topics = [];
  let other = null;

  (report.categories || []).forEach((cat) => {
    const comments = (cat.comments || []).map((c) => ({
      text: c.feedback,
      question: c.question || '',
      score: toScore(c.score),
      sentiment: c.sentiment || '',
      evidence: c.evidence_quote || '',
      reasoning: c.reasoning || '',
      direction: c.direction || '',
      ignored: c.ignored === true,
      generalScore: toScore(c.general_score),
    }));
    comments.forEach((c) => {
      const entry = commentMap.get(c.text) || { text: c.text, question: c.question, topics: [], scores: {}, ignoredIn: [], generalScore: c.generalScore };
      entry.topics.push(cat.topic);
      if (c.score !== null) entry.scores[cat.topic] = c.score;
      if (c.ignored) entry.ignoredIn.push(cat.topic);
      commentMap.set(c.text, entry);
    });

    if (cat.topic === OTHER_LABEL) {
      other = { topic: cat.topic, comments, summary: themeText(summaries[cat.topic], cat.topic) };
      return;
    }
    const activeScores = comments.filter((c) => !c.ignored && c.score !== null).map((c) => c.score);
    const distribution = [1, 2, 3, 4, 5].map((k) => activeScores.filter((s) => s === k).length);
    topics.push({
      topic: cat.topic,
      average: cat.average_score ?? null,
      scored: cat.scored_comment_count ?? activeScores.length,
      assigned: comments.length,
      ignored: comments.filter((c) => c.ignored).length,
      reliability: cat.reliability || '',
      distribution,
      sentiment: {
        positive: activeScores.filter((s) => s >= 4).length,
        neutral: activeScores.filter((s) => s === 3).length,
        negative: activeScores.filter((s) => s <= 2).length,
      },
      directions: cat.direction_counts || null,
      summary: themeText(summaries[cat.topic], cat.topic),
      comments,
    });
  });

  const metadata = report.metadata || {};
  return {
    overall: report.overall_score ?? null,
    general: report.general_sentiment || null,
    topics,
    other,
    allComments: [...commentMap.values()],
    ratings: report.quantitative || [],
    notes: [...(metadata.warnings || []), ...(metadata.extraction_warnings || [])],
    commentsAnalyzed: metadata.processed_comments ?? commentMap.size,
    modelId: metadata.model_id || report.model || '',
  };
};

// Mark which comments are ignored for one topic, then recalculate every score
export const withIgnored = (report, topic, ignoredTexts) => recalculate({
  ...report,
  categories: report.categories.map((cat) => {
    if (cat.topic !== topic) return cat;
    return {
      ...cat,
      comments: cat.comments.map((c) => {
        if (ignoredTexts.has(c.feedback)) return { ...c, ignored: true };
        const rest = { ...c };
        delete rest.ignored;
        return rest;
      }),
    };
  }),
});

export const downloadJson = (report, fileName) => {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};
