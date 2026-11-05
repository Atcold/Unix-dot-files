---
paths:
  - "**/*.tex"
  - "**/*.sty"
  - "**/*.bib"
---

# LaTeX and TikZ

These apply to every LaTeX document I read: lessons, the Altair chapters, notes. The book has its own extra rules in its memory.

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
- **Boxes and figures:** a border, no fill; transparent backgrounds (`opacityback=0`), since I read in a dark viewer.
- **TikZ:** default arrow tips (`->`) and line widths; don't change TikZ defaults unless asked. Labels never touch their arrows: lift them and check the render.
- **Worksheets I follow** (lessons, stage chapters):
  - Every step I must do is in the PDF, with real names and exact commands. Write it there first, then point me to it.
  - Setup (installs, `PATH`) lives only in the README; the chapter says in one line that everything is set up.
