$pdf_mode = 4;                                   # lualatex
$out_dir = 'build';
@default_files = ('*.tex');
do "$ENV{HOME}/Library/texmf/tex/latex/alfdoc/revision.pl";  # the revision line, from git
