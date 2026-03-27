"""
MathSnap — Desktop LaTeX OCR
Uses pix2tex to convert math images to LaTeX for Obsidian.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from pathlib import Path

# ── Optional: suppress tensorflow/torch noise ──────────────────────────────
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# ── PIL / Pillow ─────────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageTk
except ImportError:
    messagebox.showerror("Missing dependency", "Run: pip install Pillow")
    sys.exit(1)

# ── pix2tex ──────────────────────────────────────────────────────────────────
try:
    from pix2tex.cli import LatexOCR
except ImportError:
    messagebox.showerror(
        "Missing dependency",
        "pix2tex not found.\nRun: pip install pix2tex"
    )
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS & THEME
# ═══════════════════════════════════════════════════════════════════════════

BG        = "#0e0e14"
SURFACE   = "#16161f"
SURFACE2  = "#1e1e2a"
BORDER    = "#2c2c3e"
ACCENT    = "#7c6af7"
ACCENT2   = "#4fd1c5"
TEXT      = "#e4e4f0"
MUTED     = "#6a6a80"
SUCCESS   = "#4fd1c5"
ERROR_COL = "#f87171"

FONT_MONO  = ("Courier New", 11)
FONT_MONO_SM = ("Courier New", 10)
FONT_TITLE = ("Georgia", 22, "bold")
FONT_LABEL = ("Segoe UI", 9)
FONT_BTN   = ("Segoe UI", 10, "bold")
FONT_TAG   = ("Courier New", 8, "bold")


# ═══════════════════════════════════════════════════════════════════════════
#  ROUNDED BUTTON HELPER
# ═══════════════════════════════════════════════════════════════════════════

class FlatButton(tk.Canvas):
    """A simple flat button drawn on a Canvas (works on all platforms)."""

    def __init__(self, parent, text, command, bg=ACCENT, fg="white",
                 width=160, height=36, radius=8, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"] if hasattr(parent, "__getitem__") else BG,
                         highlightthickness=0, **kw)
        self._bg = bg
        self._hover_bg = self._darken(bg)
        self._fg = fg
        self._text = text
        self._cmd = command
        self._r = radius
        self._btn_width = width
        self._btn_height = height
        self._disabled = False

        self._draw(self._bg)
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _darken(self, hex_color):
        r = max(0, int(hex_color[1:3], 16) - 20)
        g = max(0, int(hex_color[3:5], 16) - 20)
        b = max(0, int(hex_color[5:7], 16) - 20)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw(self, bg):
        self.delete("all")
        r, w, h = self._r, self._btn_width, self._btn_height
        self.create_arc(0, 0, 2*r, 2*r, start=90, extent=90, fill=bg, outline=bg)
        self.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90, fill=bg, outline=bg)
        self.create_arc(0, h-2*r, 2*r, h, start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h-r, fill=bg, outline=bg)
        self.create_text(w//2, h//2, text=self._text, fill=self._fg,
                         font=FONT_BTN)

    def _on_enter(self, _):
        if not self._disabled:
            self._draw(self._hover_bg)

    def _on_leave(self, _):
        if not self._disabled:
            self._draw(self._bg)

    def _on_click(self, _):
        if not self._disabled and self._cmd:
            self._cmd()

    def set_text(self, t):
        self._text = t
        self._draw(self._bg)

    def disable(self):
        self._disabled = True
        self._draw(MUTED)

    def enable(self):
        self._disabled = False
        self._draw(self._bg)


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════

class MathSnapApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MathSnap")
        self.root.configure(bg=BG)
        self.root.geometry("800x680")
        self.root.minsize(700, 560)

        self._model: LatexOCR | None = None
        self._model_loading = False
        self._current_image: Image.Image | None = None
        self._photo_ref = None          # keep ref to prevent GC

        self._build_ui()
        self._load_model_async()        # load model in background on startup

    # ── UI BUILD ─────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=32, pady=(28, 0))

        tk.Label(hdr, text="Math", font=FONT_TITLE, bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text="Snap", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text="  —  Image → LaTeX for Obsidian",
                 font=("Segoe UI", 10), bg=BG, fg=MUTED).pack(side="left", pady=6)

        # status pill (top right)
        self._status_var = tk.StringVar(value="● Loading model…")
        self._status_lbl = tk.Label(hdr, textvariable=self._status_var,
                                    font=FONT_TAG, bg=SURFACE2, fg=MUTED,
                                    padx=10, pady=4)
        self._status_lbl.pack(side="right")

        # ── Divider ───────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=32, pady=12)

        # ── Main two-column area ──────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=32, pady=0)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # LEFT — image panel
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)

        tk.Label(left, text="IMAGE", font=FONT_TAG, bg=BG, fg=MUTED).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        self._drop_frame = tk.Frame(left, bg=SURFACE, highlightbackground=BORDER,
                                    highlightthickness=1)
        self._drop_frame.grid(row=1, column=0, sticky="nsew")
        self._drop_frame.rowconfigure(0, weight=1)
        self._drop_frame.columnconfigure(0, weight=1)

        self._img_label = tk.Label(self._drop_frame, bg=SURFACE,
                                   text="Drop image here\nor click Browse",
                                   font=FONT_LABEL, fg=MUTED,
                                   compound="center", cursor="hand2")
        self._img_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._img_label.bind("<Button-1>", lambda _: self._browse_file())

        # RIGHT — output panel
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.rowconfigure(1, weight=1)

        out_hdr = tk.Frame(right, bg=BG)
        out_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(out_hdr, text="LATEX OUTPUT", font=FONT_TAG, bg=BG, fg=MUTED).pack(side="left")

        self._copy_btn_small = tk.Button(
            out_hdr, text="Copy", font=FONT_TAG,
            bg=SURFACE2, fg=TEXT, relief="flat",
            activebackground=BORDER, activeforeground=TEXT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_latex
        )
        self._copy_btn_small.pack(side="right")

        self._obsidian_var = tk.BooleanVar(value=True)
        tk.Checkbutton(out_hdr, text="Obsidian $$", variable=self._obsidian_var,
                       bg=BG, fg=MUTED, selectcolor=SURFACE2,
                       activebackground=BG, activeforeground=MUTED,
                       font=FONT_TAG).pack(side="right", padx=(0, 8))

        # Text area
        txt_frame = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        txt_frame.grid(row=1, column=0, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._output_text = tk.Text(
            txt_frame, bg=SURFACE, fg="#c8b8ff",
            font=FONT_MONO, relief="flat",
            insertbackground=ACCENT, wrap="word",
            padx=12, pady=12,
            state="disabled"
        )
        self._output_text.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(txt_frame, command=self._output_text.yview, bg=SURFACE2)
        self._output_text["yscrollcommand"] = scroll.set

        # ── Bottom bar ────────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=SURFACE, pady=12)
        bar.pack(fill="x", padx=0, pady=(12, 0), side="bottom")

        inner = tk.Frame(bar, bg=SURFACE)
        inner.pack(padx=32)

        self._browse_btn = FlatButton(inner, "  Browse Image",
                                      command=self._browse_file,
                                      bg=SURFACE2, fg=TEXT,
                                      width=150, height=36)
        self._browse_btn.pack(side="left", padx=(0, 10))

        self._paste_btn = FlatButton(inner, "  Paste (Ctrl+V)",
                                     command=self._paste_image,
                                     bg=SURFACE2, fg=TEXT,
                                     width=150, height=36)
        self._paste_btn.pack(side="left", padx=(0, 10))

        self._convert_btn = FlatButton(inner, "⚡  Convert",
                                       command=self._run_ocr,
                                       bg=ACCENT, fg="white",
                                       width=150, height=36)
        self._convert_btn.pack(side="left")

        self._prog_lbl = tk.Label(bar, text="", font=FONT_LABEL,
                                   bg=SURFACE, fg=MUTED)
        self._prog_lbl.pack(side="right", padx=32)

        # ── Keybindings ────────────────────────────────────────────────────
        self.root.bind("<Control-v>", lambda _: self._paste_image())
        self.root.bind("<Control-V>", lambda _: self._paste_image())
        self.root.bind("<Return>", lambda _: self._run_ocr())

    # ── MODEL LOADING ─────────────────────────────────────────────────────

    def _load_model_async(self):
        self._model_loading = True
        self._convert_btn.disable()
        t = threading.Thread(target=self._load_model_worker, daemon=True)
        t.start()

    def _load_model_worker(self):
        try:
            self._model = LatexOCR()
            self.root.after(0, self._on_model_ready)
        except Exception as e:
            self.root.after(0, lambda: self._on_model_error(str(e)))

    def _on_model_ready(self):
        self._model_loading = False
        self._status_var.set("● Ready")
        self._status_lbl.config(fg=SUCCESS)
        self._convert_btn.enable()
        self._set_progress("")

    def _on_model_error(self, msg):
        self._status_var.set("● Model error")
        self._status_lbl.config(fg=ERROR_COL)
        self._set_progress(f"Error: {msg}")

    # ── IMAGE LOADING ─────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select math image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                       ("All files", "*.*")]
        )
        if path:
            self._load_image_path(path)

    def _paste_image(self):
        try:
            # On Windows, PIL can grab clipboard image directly
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                self._set_current_image(img)
            elif isinstance(img, list) and img:
                # list of file paths
                self._load_image_path(img[0])
            else:
                self._set_progress("No image found in clipboard.")
        except Exception as e:
            self._set_progress(f"Paste failed: {e}")

    def _load_image_path(self, path: str):
        try:
            img = Image.open(path).convert("RGB")
            self._set_current_image(img)
        except Exception as e:
            self._set_progress(f"Could not open image: {e}")

    def _set_current_image(self, img: Image.Image):
        self._current_image = img
        self._show_preview(img)
        self._set_progress("Image loaded. Press Convert or Enter.")

    def _show_preview(self, img: Image.Image):
        # Fit image inside the label area
        frame_w = max(self._drop_frame.winfo_width(), 280)
        frame_h = max(self._drop_frame.winfo_height(), 220)
        img_copy = img.copy()
        img_copy.thumbnail((frame_w - 16, frame_h - 16), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_copy)
        self._photo_ref = photo
        self._img_label.config(image=photo, text="")

    # ── OCR ───────────────────────────────────────────────────────────────

    def _run_ocr(self):
        if self._model_loading:
            self._set_progress("Model still loading, please wait…")
            return
        if self._model is None:
            self._set_progress("Model not loaded.")
            return
        if self._current_image is None:
            self._set_progress("No image loaded. Browse or paste one first.")
            return

        self._convert_btn.disable()
        self._set_output("⏳ Running OCR…")
        self._set_progress("Converting…")
        t = threading.Thread(target=self._ocr_worker, daemon=True)
        t.start()

    def _ocr_worker(self):
        try:
            latex = self._model(self._current_image)
            self.root.after(0, lambda: self._on_ocr_done(latex))
        except Exception as e:
            self.root.after(0, lambda: self._on_ocr_error(str(e)))

    def _on_ocr_done(self, latex: str):
        if self._obsidian_var.get():
            # Wrap for Obsidian block math
            latex = f"$$\n{latex}\n$$"
        self._set_output(latex)
        self._set_progress("✓ Done! Click Copy to grab the LaTeX.")
        self._convert_btn.enable()

    def _on_ocr_error(self, msg: str):
        self._set_output(f"Error: {msg}")
        self._set_progress("OCR failed.")
        self._convert_btn.enable()

    # ── OUTPUT HELPERS ────────────────────────────────────────────────────

    def _set_output(self, text: str):
        self._output_text.config(state="normal")
        self._output_text.delete("1.0", "end")
        self._output_text.insert("1.0", text)
        self._output_text.config(state="disabled")

    def _copy_latex(self):
        content = self._output_text.get("1.0", "end").strip()
        if not content or content.startswith("⏳"):
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._set_progress("✓ Copied to clipboard!")
        self._copy_btn_small.config(text="Copied ✓", fg=SUCCESS)
        self.root.after(2000, lambda: self._copy_btn_small.config(text="Copy", fg=TEXT))

    def _set_progress(self, msg: str):
        self._prog_lbl.config(text=msg)


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.resizable(True, True)

    # App icon (∑ character as window title icon — fallback if no .ico)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    app = MathSnapApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
