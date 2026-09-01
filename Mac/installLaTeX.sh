echo 'Installing LaTeX, TeXstudio, and PowerPoint plugin'

brew install mactex

# texstudio@all is the tap's build, bundling the dictionaries and the thesaurus.
brew tap texstudio-org/texstudio
brew trust texstudio-org/texstudio
brew install texstudio@all

if [ -d "/Applications/Microsoft PowerPoint.app" ]
then
    echo "PowerPoint found. Installing IguanaTex."
    brew tap tsung-ju/iguanatexmac
    brew install --cask --no-quarantine iguanatexmac latexit-metadata
else
    echo "PowerPoint not found. Skipping IguanaTex installation."
fi

# TeXstudio's editor font. Qt names a font by *family*, and a family covers every
# weight, so a light face cannot be asked for by name -- there is no font-weight setting
# in TeXstudio to go with it. This gives the ExtraLight face a family of its own.
FONT="$HOME/Library/Fonts/CaskaydiaCoveNerdFont-ExtraLight.ttf"
if [ -f "$FONT" ]; then
    "$(dirname "$0")/../LaTeX/rename-font.py" "$FONT" \
        "$HOME/Library/Fonts/CascadiaExtraLight-Regular.ttf" \
        "Cascadia ExtraLight" CascadiaExtraLight-Regular
else
    echo "Skipping the editor font: $FONT is not installed (brew install font-caskaydia-cove-nerd-font)."
fi

# TeXstudio writes this file on exit, so it must be closed while this is copied in.
cp "$(dirname "$0")/../LaTeX/texstudio.ini" "$HOME/.config/texstudio/texstudio.ini"

echo 'Done.'
