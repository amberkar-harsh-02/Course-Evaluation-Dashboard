import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { api } from '../api';
import { useAuth } from '../auth';

const ANALYSIS_DOC = 'https://drive.google.com/file/d/1qSiXn0aJ2M5cgBKqwrhvDSuceaB9F2kk/view?usp=drive_link';
const SURVEY = 'https://forms.gle/ABn8jdDPNi3EgSBw5';

// Screenshots of this site taken with made-up demo data (src/assets/guide). Missing files are simply skipped.
const SHOTS = Object.fromEntries(
  Object.entries(import.meta.glob('../assets/guide/*.png', { eager: true, import: 'default' }))
    .map(([path, url]) => [path.split('/').pop().replace('.png', ''), url]),
);

function Shot({ name, alt }) {
  if (!SHOTS[name]) return null;
  return (
    <figure className="mt-4 overflow-hidden rounded-md border border-line bg-page shadow-sm">
      <img src={SHOTS[name]} alt={alt} loading="lazy" className="block w-full" />
    </figure>
  );
}

Shot.propTypes = { name: PropTypes.string.isRequired, alt: PropTypes.string.isRequired };

const STEPS = [
  {
    id: 'upload',
    title: 'Upload an evaluation file',
    body: (
      <>
        <p>Open <Link to="/new" className="link">New analysis</Link> and drag your course evaluation export into the box, or choose it from your computer. PDF, Word, Excel and CSV exports work.</p>
        <p>Give the report a course name and, if you like, the term. Then select <strong className="font-medium text-ink">Start analysis</strong>. Most files finish in about a minute, and you can leave the page while it runs; the report appears under My reports.</p>
      </>
    ),
    shot: 'upload',
    alt: 'The New analysis page with a file chosen and the course and term filled in',
  },
  {
    id: 'overview',
    title: 'Read the overview',
    body: (
      <p>Each report opens on an overview: the overall grade out of 5, a chart of every teaching topic, and a score card for each topic. Scores run from 1 (needs attention) to 5 (strong). Topics with fewer than five scored comments are faded and marked &ldquo;few&rdquo;, so read those as an indication only.</p>
    ),
    shot: 'overview',
    alt: 'A report overview with the overall grade, the category chart and topic score cards',
  },
  {
    id: 'chart',
    title: 'Switch the chart',
    body: (
      <p>The category breakdown can be shown as bars or as a radar. Hover over a bar or point to see the exact score and how many comments it is based on. Selecting a bar opens that topic.</p>
    ),
    shot: 'radar',
    alt: 'The category breakdown shown as a radar chart',
  },
  {
    id: 'topic',
    title: 'Look closer at a topic',
    body: (
      <>
        <p>Select a topic card to open a quick view: the average score, how many comments were positive, neutral or negative, how the scores spread from 1 to 5, a short written summary, and the comments themselves. For Pace, it also says how many students found the course too fast or too slow.</p>
        <p>Select <strong className="font-medium text-ink">View more details</strong> for the full topic page. The topics of the open report are also listed in the sidebar under My reports, so you can move between them directly.</p>
      </>
    ),
    shot: 'topic',
    alt: 'The topic pop-up for Pace with its score spread and summary',
  },
  {
    id: 'comments',
    title: 'Filter the comments',
    body: (
      <p>Below the topic cards, every analyzed comment is listed once. Search for a word, or narrow the list to one topic, to low, mixed or positive scores, and sort from lowest to highest. When a topic is selected, the score shown is the score for that topic.</p>
    ),
    shot: 'comments',
    alt: 'The comment list filtered to one topic and sorted lowest first',
  },
  {
    id: 'ignore',
    title: 'Leave out comments that do not apply',
    body: (
      <p>On a full topic page, select <strong className="font-medium text-ink">Ignore comments</strong>, tick any comment that should not count for that topic, and select <strong className="font-medium text-ink">Save and recalculate</strong>. The topic and overall grades update, and ignored comments stay visible, crossed out. Use <strong className="font-medium text-ink">Download JSON</strong> to keep a copy of the report.</p>
    ),
    shot: 'ignore',
    alt: 'A topic page in ignore mode with two comments ticked',
  },
  {
    id: 'compare',
    title: 'Compare terms',
    body: (
      <p>Once you have more than one report for a course, tick them on My reports and select <strong className="font-medium text-ink">Compare</strong> to see how each topic changed from term to term.</p>
    ),
    shot: 'compare',
    alt: 'The Compare page with two terms of the same course',
  },
];

export default function Guide() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const firstVisit = !user?.guide_seen_at;
  const [welcome] = useState(firstVisit); // keep the greeting after the seen flag is saved

  // Opening the Guide counts as seeing it, so it never opens on its own again
  useEffect(() => {
    if (firstVisit) api('/auth/guide-seen', { method: 'POST' }).then(refresh).catch(() => {});
  }, [firstVisit, refresh]);

  return (
    <div className="page max-w-3xl">
      <header>
        <h1 className="page-title">{welcome ? `Welcome, ${user?.name || 'professor'}` : 'Guide'}</h1>
        <p className="page-subtitle">
          How to upload a course evaluation, read the results, and compare terms. You can come back to this page any time from Guide in the sidebar.
        </p>
      </header>

      <nav aria-label="On this page" className="mt-6 rounded-md border border-line bg-paper px-5 py-4">
        <p className="text-sm font-medium text-ink">On this page</p>
        <ol className="mt-2 gap-x-8 space-y-1 text-sm sm:columns-2 [&>li]:break-inside-avoid">
          <li><a href="#about" className="link font-normal">What this site does</a></li>
          {STEPS.map((s, i) => <li key={s.id}><a href={`#${s.id}`} className="link font-normal">{i + 1}. {s.title}</a></li>)}
          <li><a href="#feedback" className="link font-normal">Tell us what you think</a></li>
        </ol>
      </nav>

      <section id="about" className="mt-10 scroll-mt-6">
        <h2 className="section-title">What this site does</h2>
        <div className="mt-3 max-w-[68ch] space-y-3 leading-relaxed text-ink-soft">
          <p>
            This site reads the written comments from your course evaluations and turns them into a report you can navigate.
            Instead of scrolling through hundreds of loose comments at the end of a term, you see what each comment is about,
            how positive or negative it is, and a short written takeaway for every teaching topic, along with a note when a
            topic has too few comments to rely on.
          </p>
          <p>Your reports are private. Only you can open them.</p>
          <p>
            The analysis description explains how comments are sorted and scored, and how to interpret the results.
          </p>
        </div>
        <a href={ANALYSIS_DOC} target="_blank" rel="noopener noreferrer" className="btn-secondary mt-4">
          Read the analysis description (opens Google Drive)
        </a>
      </section>

      <section aria-labelledby="steps-title" className="mt-12">
        <h2 id="steps-title" className="section-title">Step by step</h2>
        <ol className="mt-6 space-y-12">
          {STEPS.map((step, i) => (
            <li key={step.id} id={step.id} className="scroll-mt-6">
              <div className="flex items-baseline gap-3">
                <span className="num flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-tint font-serif text-sm font-medium text-accent">{i + 1}</span>
                <h3 className="font-serif text-lg font-medium text-ink">{step.title}</h3>
              </div>
              <div className="mt-2 max-w-[68ch] space-y-3 pl-10 leading-relaxed text-ink-soft">{step.body}</div>
              <div className="sm:pl-10"><Shot name={step.shot} alt={step.alt} /></div>
            </li>
          ))}
        </ol>
      </section>

      <section id="feedback" className="card mt-14 scroll-mt-6">
        <h2 className="section-title">Tell us what you think</h2>
        <p className="mt-2 max-w-[64ch] leading-relaxed text-ink-soft">
          This site is part of a research project. A short survey about the analysis results and this tool helps us judge the
          quality of the analysis and improve the site for future use.
        </p>
        <a href={SURVEY} target="_blank" rel="noopener noreferrer" className="btn-secondary mt-4">Take the evaluation survey</a>
      </section>

      <div className="mt-10 flex flex-wrap gap-3 border-t border-line pt-6">
        <button type="button" className="btn-primary" onClick={() => navigate('/new')}>Start a new analysis</button>
        <button type="button" className="btn-secondary" onClick={() => navigate('/')}>Go to my reports</button>
      </div>
    </div>
  );
}
