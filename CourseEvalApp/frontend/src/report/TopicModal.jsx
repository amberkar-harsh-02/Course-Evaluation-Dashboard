import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import PropTypes from 'prop-types';
import TopicStats from './TopicStats';
import CommentList from './CommentList';

/** Quick look at one topic. "View more details" opens the full topic page (with ignore mode). */
export default function TopicModal({ topic, onClose, onOpenPage }) {
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  // Rendered on <body> so page animations (which use transforms) cannot change where the fixed overlay sits
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center animate-fade-in overflow-y-auto bg-ink/40 p-4 sm:items-center"
         onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="topic-modal-title"
           className="flex max-h-[90vh] w-full max-w-3xl animate-scale-in flex-col rounded-md border border-line bg-paper shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-6 py-4">
          <h2 id="topic-modal-title" className="font-serif text-2xl font-medium text-ink">{topic.topic}</h2>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-primary" onClick={onOpenPage}>View more details</button>
            <button type="button" ref={closeRef} className="btn-secondary" onClick={onClose}>Close</button>
          </div>
        </div>
        <div className="space-y-6 overflow-y-auto px-6 py-5">
          <TopicStats topic={topic} />
          <CommentList comments={topic.comments} idPrefix="modal" emptyText="No comments were assigned to this topic." />
        </div>
      </div>
    </div>,
    document.body,
  );
}

TopicModal.propTypes = {
  topic: PropTypes.object.isRequired,
  onClose: PropTypes.func.isRequired,
  onOpenPage: PropTypes.func.isRequired,
};
