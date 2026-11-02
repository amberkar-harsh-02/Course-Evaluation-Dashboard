import { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { CHART_COLORS, useTheme } from '../theme';
import { formatScore, scoreTone, shortName } from './model';

export const TONE_TEXT = { low: 'text-score-low', mid: 'text-score-mid', high: 'text-score-high', none: 'text-ink-muted' };

export function OverallGrade({ score, comments, scoredTopics }) {
  return (
    <section className="card flex flex-col justify-between" aria-labelledby="overall-title">
      <h2 id="overall-title" className="text-sm font-medium text-ink-soft">Overall grade</h2>
      <p className={`num my-6 text-center font-serif text-[4.25rem] font-medium leading-none ${TONE_TEXT[scoreTone(score)]}`}>
        {formatScore(score)}<span className="ml-1 text-2xl text-ink-muted">/ 5</span>
      </p>
      <p className="text-center text-sm text-ink-muted">
        {comments} student comments across {scoredTopics} scored topics
      </p>
    </section>
  );
}

OverallGrade.propTypes = { score: PropTypes.number, comments: PropTypes.number, scoredTopics: PropTypes.number };

function ChartTooltip({ active, payload, colors }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded border px-3 py-2 text-xs shadow-sm" style={{ background: colors.paper, borderColor: colors.grid, color: colors.ink }}>
      <p className="font-medium">{row.topic}</p>
      <p className="num mt-0.5">{row.score == null ? 'No scored comments' : `${formatScore(row.score)} / 5 from ${row.scored} comments`}</p>
    </div>
  );
}

ChartTooltip.propTypes = { active: PropTypes.bool, payload: PropTypes.array, colors: PropTypes.object };

export function CategoryChart({ topics, onSelect }) {
  const [mode, setMode] = useState('bar');
  const { theme } = useTheme();
  const colors = CHART_COLORS[theme];
  const data = topics.map((t) => ({ topic: t.topic, name: shortName(t.topic), score: t.average, scored: t.scored }));
  const toneColor = (score) => colors[scoreTone(score)] || colors.axis;

  return (
    <section className="card" aria-labelledby="chart-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="chart-title" className="text-sm font-medium text-ink-soft">Category breakdown</h2>
        <div className="inline-flex rounded border border-line p-0.5 text-xs" role="group" aria-label="Chart type">
          {['bar', 'radar'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
              className={`rounded-sm px-3 py-1 font-medium ${mode === m ? 'bg-accent text-accent-on' : 'text-ink-soft hover:text-ink'}`}
            >
              {m === 'bar' ? 'Bar' : 'Radar'}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 h-80">
        <ResponsiveContainer width="100%" height="100%">
          {mode === 'bar' ? (
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }}>
              <CartesianGrid horizontal={false} stroke={colors.grid} strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} stroke={colors.axis} fontSize={12} />
              <YAxis type="category" dataKey="name" width={118} stroke={colors.axis} fontSize={12} tickLine={false} interval={0} />
              <Tooltip cursor={{ fill: colors.grid, opacity: 0.4 }} content={<ChartTooltip colors={colors} />} />
              <Bar dataKey="score" barSize={14} radius={[0, 2, 2, 0]} isAnimationActive={false}
                   onClick={(row) => onSelect(row.topic)} className="cursor-pointer">
                {data.map((row) => <Cell key={row.topic} fill={toneColor(row.score)} />)}
                <LabelList dataKey="score" position="right" fontSize={12} fill={colors.ink}
                           formatter={(v) => (v == null ? '—' : Number(v).toFixed(1))} />
              </Bar>
            </BarChart>
          ) : (
            <RadarChart data={data} outerRadius="72%">
              <PolarGrid stroke={colors.grid} />
              <PolarAngleAxis dataKey="name" tick={{ fill: colors.axis, fontSize: 11 }} />
              <PolarRadiusAxis angle={90} domain={[0, 5]} tickCount={6} tick={false} axisLine={false} />
              <Radar dataKey="score" stroke={colors.accent} fill={colors.accent} fillOpacity={0.22} strokeWidth={2}
                     dot={{ r: 3, fill: colors.accent }} isAnimationActive={false} />
              <Tooltip content={<ChartTooltip colors={colors} />} />
            </RadarChart>
          )}
        </ResponsiveContainer>
      </div>
    </section>
  );
}

CategoryChart.propTypes = { topics: PropTypes.array.isRequired, onSelect: PropTypes.func.isRequired };

function Ring({ score }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const filled = score == null ? 0 : (score / 5) * circumference;
  const tone = scoreTone(score);
  return (
    <div className="relative h-[72px] w-[72px]">
      <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="32" cy="32" r={radius} fill="none" strokeWidth="5" className="stroke-line" />
        <circle cx="32" cy="32" r={radius} fill="none" strokeWidth="5" strokeLinecap="round"
                className={TONE_TEXT[tone]} stroke="currentColor" strokeDasharray={`${filled} ${circumference}`} />
      </svg>
      <span className={`num absolute inset-0 flex items-center justify-center font-serif text-lg font-medium ${TONE_TEXT[tone]}`}>
        {score == null ? '—' : score.toFixed(1)}
      </span>
    </div>
  );
}

Ring.propTypes = { score: PropTypes.number };

export function TopicCards({ topics, onSelect }) {
  return (
    <section aria-labelledby="cards-title">
      <h2 id="cards-title" className="section-title">Topic scores</h2>
      <p className="mt-1 text-sm text-ink-muted">Select a topic to see its summary and comments.</p>
      <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {topics.map((t) => (
          <li key={t.topic}>
            <button
              type="button"
              onClick={() => onSelect(t.topic)}
              title={t.topic}
              className={`flex h-full w-full flex-col items-center gap-2 rounded border border-line bg-paper px-3 py-4 text-center transition-colors hover:border-accent ${t.scored < 5 ? 'opacity-70' : ''}`}
            >
              <Ring score={t.average} />
              <span className="text-sm font-medium leading-tight text-ink">{shortName(t.topic)}</span>
              <span className="text-xs text-ink-muted">
                {t.scored === 0 ? 'No scored comments' : `${t.scored} scored${t.scored < 5 ? ', few' : ''}`}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

TopicCards.propTypes = { topics: PropTypes.array.isRequired, onSelect: PropTypes.func.isRequired };
