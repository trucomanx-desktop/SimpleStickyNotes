# simple-sticky-notes

Simple, always-on-bottom sticky notes for quick thoughts and reminders.


## Install from PYPI

The homepage in pipy is https://pypi.org/project/simple_sticky_notes/

```bash
pip install --upgrade simple_sticky_notes
```

or (recommended for desktop applications)

```bash
pipx install simple_sticky_notes
```


Using:

```bash
simple-sticky-notes
```

If you would like the program to initialize at the start of the Linux session, use `simple-sticky-notes --autostart`.

## Install from source
Installing `simple-sticky-notes` program

```bash
git clone https://github.com/trucomanx-desktop/SimpleStickyNotes.git
cd SimpleStickyNotes
pip install -r requirements.txt
cd src
python -m build
pip install dist/simple_sticky_notes-*.tar.gz
```
Using:

```bash
simple-sticky-notes
```

## Uninstall

```bash
pip uninstall simple_sticky_notes
```
