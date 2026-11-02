"""Builds the figures for Documentation V2 (docs/documentation-v2/figures/).

Every number below is copied from a source named in the comment next to it; nothing is read from student data.
Run:  python docs/documentation-v2/tools/make_figures.py   (needs matplotlib and pillow)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(exist_ok=True)

# Same palette as the website ("Monterey Bay")
INK, MUTED, LINE, ACCENT = "#1C2128", "#5F6670", "#C3C6C2", "#1E5A8A"
LOW, MID, HIGH = "#B42318", "#B26B00", "#1E7A4F"
TINT = "#E8F0F7"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": LINE,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK})


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


# 1. Project timeline. Dates: git history, document metadata and file timestamps (see Documentation V2, section 3).
def timeline():
    phases = [
        ("Model comparison research, spring\n(Llama3, Gemma, RoBERTa, DistilRoBERTa)", "2026-03-01", "2026-04-13", MUTED),
        ("Text extraction server\n(FastAPI, DOCX and PDF)", "2026-04-13", "2026-05-31", ACCENT),
        ("Rubric design and LLM pipeline\n(12 topics, 1-5 rubric, RAG, Qwen and OpenAI tests)", "2026-04-23", "2026-07-16", ACCENT),
        ("Pilot: Professor Portal and\nfaculty feedback (17 responses)", "2026-07-16", "2026-09-15", MID),
        ("Backend review and rebuild\n(whole answers, one structured call, evaluation harness)", "2026-10-07", "2026-10-08", HIGH),
        ("Merged web app\n(accounts, credits, uploads, compare, redesign)", "2026-11-01", "2026-11-02", HIGH),
    ]
    milestones = [("2026-04-13", "First commit"), ("2026-06-12", "Methodology guide"), ("2026-07-16", "Documentation V1"),
                  ("2026-10-08", "Backend report"), ("2026-11-02", "App live with\nguide and new design")]
    from datetime import date
    d = lambda s: date.fromisoformat(s).toordinal()
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for i, (label, start, end, color) in enumerate(phases):
        y = len(phases) - i
        width = max(d(end) - d(start), 4)
        ax.barh(y, width, left=d(start), height=0.55, color=color, alpha=0.9)
        ax.text(d(start) + width + 3, y, label, va="center", fontsize=8.5)
    for k, (when, label) in enumerate(milestones):
        ax.axvline(d(when), color=LINE, lw=0.8, ls="--", zorder=0)
        # Alternate label heights so neighbouring milestones never overlap
        ax.text(d(when), 0.25 if k % 2 == 0 else -0.35, label, ha="center", va="top", fontsize=7.5, color=MUTED,
                bbox=dict(fc="white", ec="none", pad=1))
    months = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01",
              "2026-10-01", "2026-11-01", "2026-12-01"]
    ax.set_xticks([d(m) for m in months], [date.fromisoformat(m).strftime("%b") for m in months])
    ax.set_yticks([])
    ax.set_xlim(d("2026-02-25"), d("2027-02-15"))
    ax.set_ylim(-1.3, len(phases) + 0.7)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title("Project timeline, 2026", loc="left", fontsize=12, color=INK)
    save(fig, "timeline.png")


# 2. Architecture then (July 2026, Documentation V1) and now (November 2026).
def box(ax, x, y, w, h, text, fill="white", edge=ACCENT, size=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04", fc=fill, ec=edge, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, wrap=True)


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.1))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.07, label, ha="center", fontsize=7.5, color=MUTED)


def architecture():
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.2))
    ax = axes[0]
    ax.set_title("Then: pilot set-up (July to October 2026)", loc="left", fontsize=11)
    box(ax, 0.0, 0.55, 1.6, 0.35, "Research team\nadmin dashboard")
    box(ax, 2.1, 0.55, 1.7, 0.35, "NLP API + pipeline\nclassify, then score\neach topic separately", size=8)
    box(ax, 4.3, 0.55, 1.5, 0.35, "OCR server\nPDF / DOCX text")
    box(ax, 2.1, 0.0, 1.7, 0.3, "Local Qwen (Mac Studio)\nor OpenAI", edge=MUTED)
    box(ax, 6.3, 0.55, 1.6, 0.35, "JSON report file\nshared by hand", edge=MID)
    box(ax, 8.4, 0.55, 1.6, 0.35, "Professor Portal\nload JSON in browser", edge=MID)
    arrow(ax, 1.6, 0.72, 2.1, 0.72, "upload")
    arrow(ax, 3.8, 0.72, 4.3, 0.72)
    arrow(ax, 2.95, 0.55, 2.95, 0.3)
    arrow(ax, 5.8, 0.72, 6.3, 0.72)
    arrow(ax, 7.9, 0.72, 8.4, 0.72, "Drive")
    ax = axes[1]
    ax.set_title("Now: merged web app (November 2026)", loc="left", fontsize=11)
    box(ax, 0.0, 0.55, 1.7, 0.35, "Professor in browser\nsign in, upload, review", fill=TINT)
    box(ax, 0.0, 0.0, 1.7, 0.33, "Admin in browser\napprovals, caps, usage", fill=TINT)
    box(ax, 2.2, 0.48, 2.4, 0.47, "Course Eval app API\naccounts and approval, credits,\njobs, private reports", fill=TINT)
    box(ax, 2.2, -0.05, 2.4, 0.33, "PostgreSQL\nusers, reports, usage log\nnightly backup", edge=HIGH, size=8)
    box(ax, 5.1, 0.6, 2.2, 0.35, "OCR server\nwhole answers + questions", size=8)
    box(ax, 5.1, 0.08, 2.2, 0.4, "NLP pipeline\n1 structured call per comment\nparallel + cached", size=8)
    box(ax, 7.8, 0.08, 2.2, 0.4, "OpenAI\nlab credit or the\nprofessor's own key", edge=MUTED, size=8)
    arrow(ax, 1.7, 0.72, 2.2, 0.72, "HTTPS")
    arrow(ax, 1.7, 0.17, 2.2, 0.55)
    arrow(ax, 4.6, 0.8, 5.1, 0.78)
    arrow(ax, 4.6, 0.6, 5.1, 0.32)
    arrow(ax, 7.3, 0.28, 7.8, 0.28)
    arrow(ax, 3.4, 0.48, 3.4, 0.28)
    for a in axes:
        a.set_xlim(-0.1, 10.1)
        a.set_ylim(-0.12, 1.0)
        a.axis("off")
    fig.tight_layout()
    save(fig, "architecture.png")


# 3. Measured improvement on 88 human-labeled comments (Backend_Improvements_Report.pdf, Oct 8 2026,
#    and NLP/eval_runs/20261008_131258_openai/summary.json for the "after" column).
def results():
    rows = [("Topic F1 (micro)", 0.815, 0.857, True), ("Exact topic set", 0.21, 0.38, True),
            ("Sentiment agreement", 0.915, 0.957, True), ("Score MAE (1-5)", 0.38, 0.27, False)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [3, 1.2]})
    ax = axes[0]
    y = range(len(rows))
    ax.barh([i + 0.18 for i in y], [r[1] for r in rows], height=0.34, color=LINE, label="Before (Oct 7)")
    ax.barh([i - 0.18 for i in y], [r[2] for r in rows], height=0.34, color=ACCENT, label="After (Oct 8)")
    for i, r in enumerate(rows):
        ax.text(r[1] + 0.01, i + 0.18, f"{r[1]:.3g}", va="center", fontsize=8, color=MUTED)
        ax.text(r[2] + 0.01, i - 0.18, f"{r[2]:.3g}", va="center", fontsize=8, color=INK)
    ax.set_yticks(list(y), [r[0] + ("" if r[3] else "  (lower is better)") for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    ax.set_title("Accuracy against human labels", loc="left", fontsize=11)
    ax = axes[1]
    ax.bar(["Before", "After"], [525, 28.5], color=[LINE, ACCENT], width=0.55)
    ax.text(0, 525 + 10, "525 s", ha="center", fontsize=8)
    ax.text(1, 28.5 + 10, "28.5 s", ha="center", fontsize=8)
    ax.set_title("Time for 88 comments", loc="left", fontsize=11)
    ax.set_ylim(0, 600)
    for a in axes:
        for side in ("right", "top"):
            a.spines[side].set_visible(False)
    fig.tight_layout()
    save(fig, "results.png")


# 4. Pilot faculty survey, 17 responses, Aug 6 to Sep 15 2026 (aggregate counts from the feedback form;
#    1 = strongly disagree, 5 = strongly agree). No respondent-level data is included.
SURVEY = [
    ("Structure was easy to follow", {4: 3, 5: 14}),
    ("Graphs helped interpret results", {3: 1, 4: 4, 5: 12}),
    ("Comment counts (N) were useful", {3: 2, 4: 4, 5: 11}),
    ("Topics reflected my comments", {3: 2, 4: 4, 5: 11}),
    ("Sentiment matched my reading", {2: 1, 3: 1, 4: 8, 5: 7}),
    ("Summaries captured main themes", {3: 4, 4: 3, 5: 10}),
    ("Trust that it represents feedback", {3: 4, 4: 3, 5: 10}),
    ("Showed patterns hard to see by hand", {3: 5, 4: 1, 5: 11}),
    ("Revealed insights I had not noticed", {1: 1, 2: 1, 3: 2, 4: 9, 5: 4}),
    ("Prompted reflection on teaching", {1: 1, 3: 2, 4: 4, 5: 10}),
    ("Would use to inform course revisions", {1: 1, 4: 7, 5: 9}),
    ("Would use as evidence of development", {1: 1, 3: 3, 4: 4, 5: 9}),
    ("Likely to use every evaluation cycle", {1: 1, 3: 1, 4: 5, 5: 10}),
]


def survey():
    colors = {1: LOW, 2: "#D9826F", 3: "#C9CDC8", 4: "#7FB3E0", 5: ACCENT}
    fig, ax = plt.subplots(figsize=(10, 5.2))
    for i, (label, counts) in enumerate(SURVEY):
        left = 0
        for level in (1, 2, 3, 4, 5):
            n = counts.get(level, 0)
            if n:
                ax.barh(i, n, left=left, color=colors[level], height=0.66)
                if n >= 2:
                    ax.text(left + n / 2, i, str(n), ha="center", va="center", fontsize=7.5,
                            color="white" if level in (1, 5) else INK)
                left += n
        mean = sum(k * v for k, v in counts.items()) / sum(counts.values())
        ax.text(17.4, i, f"{mean:.2f}", va="center", fontsize=8.5)
    ax.set_yticks(range(len(SURVEY)), [s[0] for s in SURVEY])
    ax.invert_yaxis()
    ax.set_xlim(0, 19)
    ax.set_xticks(range(0, 18, 2))
    ax.set_xlabel("Number of faculty respondents (n = 17)")
    ax.text(17.4, -1.1, "mean", fontsize=8, color=MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[k]) for k in (1, 2, 3, 4, 5)]
    ax.legend(handles, ["1 strongly disagree", "2", "3", "4", "5 strongly agree"], ncol=5, frameon=False,
              loc="upper center", bbox_to_anchor=(0.45, -0.1), fontsize=8)
    for side in ("right", "top"):
        ax.spines[side].set_visible(False)
    ax.set_title("Pilot faculty survey", loc="left", fontsize=11)
    save(fig, "pilot_survey.png")


# 5. Screenshots. The old portal image is cropped above its comment list so no student text appears; the new-app
#    images are the Guide screenshots, taken with made-up demo data (CHEM 110, "illustrative data").
def screenshots():
    from shutil import copyfile
    from PIL import Image
    root = Path(__file__).resolve().parents[3]
    old = Image.open(root / "ProfessorPortal/frontend/src/assets/dashdata.png")
    old.crop((0, 0, old.width, 985)).save(OUT / "then_portal.png")
    for name in ("overview", "topic", "upload", "compare", "ignore"):
        copyfile(root / f"CourseEvalApp/frontend/src/assets/guide/{name}.png", OUT / f"now_{name}.png")
    print("wrote screenshots")


if __name__ == "__main__":
    timeline()
    architecture()
    results()
    survey()
    screenshots()
