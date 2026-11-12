---
paths:
  - "**/*.tex"
  - "**/*.sty"
  - "**/*.bib"
---

# LaTeX and TikZ

These apply to every LaTeX document I read: lessons, the Altair chapters, notes. The book has its own rules in its memory.

- **Names and literals:**
  - Names of things are sans (`\textsf`): programs, scripts, files, folders, hosts, software.
  - Monospace (`\texttt`) is only for literal text you would type or see printed: flags, shell syntax, code, output, protocol words (`GET`).
  - No bold monospace. The only underline is a link's, grey, as the lessons' `\lk` draws it.
- **Commands:** long flags (`--silent`, `head -n 15`), a `$ ` prompt on the first line, a trailing `# comment` per step. The prose adds only what the comments don't say.
- **Units:** every display equation shows its unit flush right, `\tag*{[A]}`. A chain with different units splits into one display per unit.
- **Citations:**
  - The label is the book's short name as in my PDF file names (`\bibitem[PP4]{lutz}`), never `[1]`.
  - Cite the section number, its title in italics and a single page: `\cite[§1.4.1 \textit{Capacitors}, p.~18]{horowitz}`.
  - Prefer my own books.
  - Internal pointers are `\Cref`.
  - URLs break anywhere: load `xurl` (before `hyperref`), and set the bibliography `\raggedright`, so a long URL never stretches the words before it.
- **Shared style:** a private document (a report or plan that stays on my machines) loads `alfdoc`, which `~/Library/texmf/tex/latex/alfdoc/` links to `learning-with-claude/style/alfdoc.sty`; it never rebuilds its preamble from scratch. A public repo (`learning-with-claude`, `altair-tn9k`) ships its own style file, so a clone builds alone. A review round marks each edit with `\here[note]`, a numbered hand with a note of about four words.
- **Revisions:** every document in a git repo carries its revision. Its `.latexmkrc` runs `revision.pl` (`do '../style/revision.pl';` in a lesson, `do "$ENV{HOME}/Library/texmf/tex/latex/alfdoc/revision.pl";` elsewhere), and `alfdoc` then puts `Revision 13 · Thu 12 Nov 2026 · fac5762` in the title page's header and leaves every other page without header or page number, so the Boox crops the white space between pages. The document ends with `\revisiontable`, one row per commit that touched its folder. A round's edits are listed in a `changes` box under the title, one item per hand.
- **Review rounds:** a draft I receive is committed before I comment on it, so it is its own revision. My feedback becomes the next revision, a new commit, and a revision I have reviewed is never amended. Same-round fixes before I review again are amended into the new one.
- **Second document in a folder:** `X.tex` next to a lesson builds with `latexmk -jobname=<folder>-X X.tex`; `revision.pl` gives it the history of `X.tex` alone, while the folder's main document keeps the whole folder's history.
- **Review comments:** each edit from a review round carries my comment verbatim as a `% Review: “…”` LaTeX comment beside it, so the diff shows why it changed. The next round's comments replace them, because by then they are stale.
- **Boxes and figures:** a border, no fill; transparent backgrounds (`opacityback=0`), since I read in a dark viewer.
- **TikZ:** default arrow tips (`->`) and line widths; don't change TikZ defaults unless asked. Never draw dashed or dotted lines: their high-frequency pattern distracts. A secondary outline or grouping is a thin, solid, semi-transparent line (*e.g.* `draw opacity=.35`).
- **Worksheets I follow** (lessons, stage chapters):
  - Every step I must do is in the PDF, with real names and exact commands. Write it there first, then point me to it.
  - Setup (installs, `PATH`) lives only in the README; the chapter says in one line that everything is set up.
