Windows build instructions
==========================

IMPORTANT — GITHUB REPOSITORY LAYOUT
------------------------------------
When uploading this project to GitHub, upload the CONTENTS of this
JARVIS_Desktop folder to the repository root. Do not upload the enclosing
JARVIS_Desktop folder as one extra nested directory.

The desktop workflow must be at:
  .github/workflows/build-desktop.yml

The desktop requirements file must be at:
  requirements.txt

The desktop source tests must be at:
  tests/test_project.py

Run the GitHub Actions workflow: .github/workflows/build-desktop.yml
It builds a Windows PyInstaller --onedir package and includes the nested
JARVIS_USB source tree. The nested USB workflow is preserved at:
  JARVIS_USB/.github/workflows/build-usb.yml

Visible README.txt files preserve otherwise-empty resource folders in Git and
are readable in Windows File Explorer. The hidden .keep placeholders have been
removed from this source package.

This source archive has not been built or runtime-tested on Windows in this
conversation. Do not treat a successful CI build as proof that every menu,
voice component, knowledge importer or USB split-off works.
