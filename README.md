# MathSnap — Image to LaTeX Desktop App

Convert photos/screenshots of math equations to LaTeX for Obsidian. Runs fully **offline** using pix2tex.

---

## Setup (one time)

### 1. Python version
Requires **Python 3.8 – 3.10**. pix2tex has issues with 3.11+.

Check your version:
```
python --version
```

If needed, download Python 3.10 from https://www.python.org/downloads/

---

### 2. Create a virtual environment (recommended)
```bash
# In the mathsnap folder:
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

---

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> First install downloads the pix2tex model (~1.3 GB). This only happens once.

---

### 4. Run the app
```bash
python app.py
```

---

## Usage

| Action | How |
|--------|-----|
| Load image | Click **Browse Image** or drag a file |
| Paste screenshot | `Ctrl+V` after taking a screenshot |
| Convert | Click **⚡ Convert** or press `Enter` |
| Copy output | Click **Copy** button (top right of output) |
| Obsidian wrapping | Keep **Obsidian $$** checked for `$$\n...\n$$` format |

---

## Obsidian paste format

- With **Obsidian $$ checked**: paste directly into a blank line in Obsidian, it renders as a display math block.
- With it **unchecked**: you get raw LaTeX, wrap it yourself with `$...$` (inline) or `$$...$$` (block).

---

## Tips for best accuracy

- Use **high contrast** images (dark text on white background works best)
- **Crop tightly** around the equation before converting
- Printed/typed math is much more accurate than handwriting
- Screenshots work better than phone photos

---

## Troubleshooting

**`No module named 'pix2tex'`** → Run `pip install pix2tex[gui]`

**Model download fails** → Check your internet connection; the model is ~1.3 GB

**Paste doesn't work on Linux** → Install `xclip`: `sudo apt install xclip`

**Wrong Python version** → Use pyenv or install Python 3.10 specifically
