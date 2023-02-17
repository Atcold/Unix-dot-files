echo 'Installing LaTeX, TeXstudio, and PowerPoint plugin'

brew install mactex texstudio

if [ -d "/Applications/Microsoft PowerPoint.app" ]
then
    echo "PowerPoint found. Installing IguanaTex."
    brew tap tsung-ju/iguanatexmac
    brew install --cask --no-quarantine iguanatexmac latexit-metadata
else
    echo "PowerPoint not found. Skipping IguanaTex installation."
fi

echo 'Done.'
