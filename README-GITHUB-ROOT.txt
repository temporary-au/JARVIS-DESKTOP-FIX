GITHUB UPLOAD INSTRUCTIONS
==========================

Open the JARVIS_Desktop folder and upload its CONTENTS to the root of your
GitHub repository. The .github folder is hidden in Windows File Explorer by
default, so enable View > Show > Hidden items before copying it, or use the
GitHub web interface to verify that .github/workflows/build-desktop.yml exists.

Do not place the entire JARVIS_Desktop folder inside another folder in the
repository. GitHub Actions expects app.py, requirements.txt, tests, core and
.github to be at the repository root.

The nested USB source remains inside JARVIS_USB. Its own .github workflow is
kept there for the standalone USB source tree; it is not an automatically
executed workflow while nested in this desktop repository.
