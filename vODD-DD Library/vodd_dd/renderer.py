# -*- coding: utf-8 -*-
# This file is intentionally ASCII-only for maximum portability.
"""
vODD-DD Protocol -- Renderer v6
True A4 portrait. 3-column layout. Measure and draw are always in sync.
PNG via PyMuPDF (pip install pymupdf) -- pure Python, works on Windows.
"""
import os, sys, subprocess, shutil, tempfile, textwrap, io
from typing import List
from reportlab.pdfgen import canvas as rl_canvas
from .models import VODDProtocol, Submodel

# -- Page ---------------------------------------------------------------------
A4_W = 595.28
A4_H = 841.89

# -- Palette -------------------------------------------------------------------
# Banner backgrounds are dark so WHITE text is always readable.
# Card content titles use #1A1A2E (near-black) on light backgrounds.
C = dict(
    # Purpose strip
    purpose_bg  = "#0D7377", purpose_txt = "#B2EBF2",

    # -- Data Inputs -- dark purple banner (white text); colour-matched card titles
    inp_hdr     = "#4A148C",   # banner -> white
    inp_bdr     = "#6A1BA3",
    ds_title    = "#4A148C",   # dataset name: deep purple on white  OK
    pipe_bg     = "#FFFDE7",  pipe_bdr = "#E65100",  pipe_title = "#BF360C",

    # -- ABM Core -- colour-matched titles on tinted backgrounds
    abm_bg      = "#E0F7FA",  abm_bdr  = "#006064",  abm_title  = "#006064",
    ag_bg       = "#E0F7FA",  ag_bdr   = "#006064",  ag_title   = "#006064",
    sub_bg      = "#E8FDFF",  sub_bdr  = "#006064",  sub_title  = "#006064",
    intr_bg     = "#FFF3E0",  intr_bdr = "#BF360C",  intr_title = "#BF360C",
    env_bg      = "#E8F5E9",  env_bdr  = "#1B5E20",  env_title  = "#1B5E20",
    temp_bg     = "#FFFDE7",  temp_bdr = "#E65100",

    # -- Observations -- deep indigo banner (white text); colour-matched titles
    obs_hdr     = "#1A237E",   # banner -> white
    out_bgs     = ["#EDE7F6", "#E3F2FD", "#FFF8E1"],
    out_bdrs    = ["#4527A0", "#0D47A1", "#BF360C"],
    out_titles  = ["#4527A0", "#0D47A1", "#BF360C"],  # coloured titles on light bg OK

    # -- Model Evaluation -- dark purple banner (white text)
    eval_hdr    = "#4A148C",   # banner -> white
    cal_bg      = "#FFEBEE",  cal_bdr  = "#B71C1C",  cal_title  = "#B71C1C",
    val_bg      = "#E8F5E9",  val_bdr  = "#1B5E20",  val_title  = "#1B5E20",

    # -- Scenarios
    sc_bg       = "#ECEFF1",  sc_bdr   = "#78909C",
    sc_card     = "#FFFFFF",  sc_card_bdr = "#CFD8DC",
    sc_hl       = "#EDE7F6",  sc_hl_bdr   = "#4527A0",  sc_hl_txt = "#4527A0",

    # -- Badges -- dark fills, white text
    static_bg   = "#01579B",  dynamic_bg = "#1B5E20",  badge_txt = "#FFFFFF",

    # -- Text
    link        = "#4A148C",
    dark        = "#212121",  mid = "#424242",  muted = "#616161",
    white       = "#FFFFFF",  page_bg = "#F5F7FA",
    card_bg     = "#FAFAFA",  card_bdr = "#CFD8DC",
    stop_c      = "#B71C1C",
)

# -- Typography ----------------------------------------------------------------
FS = dict(
    purpose_lbl = 15, purpose_txt = 10,
    sec_hdr     = 12, card_ttl    = 10,
    body        = 10, label       = 10,
    italic      = 10, badge       =  8, temporal = 10,
)
LH  = 1.40   # line-height multiplier
PAD =  7     # internal padding
GAP =  5     # gap between elements
MAR = 11     # page margin

# Font used for all rendered text (sans-serif -> Helvetica in the PDF backend,
# and the SVG backend declares font-family:sans-serif which the renderers map
# to a Helvetica-metrics-compatible face). We measure against Helvetica so that
# wrapping decisions in the height calculators match the drawn output exactly.
_WRAP_FONT = "Helvetica"
# Glyph ascent as a fraction of font size (Helvetica ~= 0.718). The first line of
# any text block must be dropped by this amount below the box top, otherwise the
# ascenders poke above the container (the original "header overflow" bug).
ASCENT = 0.718

# -- Emoji / labels ------------------------------------------------------------
def _kw(text, table, fallback):
    t = text.lower()
    for kws, em in table:
        if any(k in t for k in kws): return em
    return fallback

_DS_KW = [(["census","population","demographic"],"[pop]"),
          (["gps","mobility","location","trace"],"[gps]"),
          (["health","disease","hospital","clinical"],"[med]"),
          (["survey","questionnaire"],"[sur]"),
          (["economic","financial","market"],"[eco]"),
          (["weather","climate"],"[wea]")]
_DS_FB = {"STATIC":"[S]","DYNAMIC":"[D]"}
_SM_KW = [(["move","movement","mobility","travel"],">>"),
          (["transmit","infect","spread"],"~~"),
          (["recover","heal","immune"],"++"),
          (["comply","adherence"],"!!")]
_OP_KW = [(["curve","time","series","epidemic"],"[~]"),
          (["spatial","map","geography"],"[#]"),
          (["compare","impact","difference"],"[=]")]

def emoji_ds(name, desc, freq): return _kw(f"{name} {desc}", _DS_KW, _DS_FB.get(freq,"[?]"))
def emoji_sm(name, desc=""): return _kw(f"{name} {desc}", _SM_KW, "[*]")
def emoji_op(name, what=""): return _kw(f"{name} {what}", _OP_KW, "[>]")

# -- Text helpers --------------------------------------------------------------
from reportlab.pdfbase.pdfmetrics import stringWidth

# Wrapping is measured against Helvetica metrics, which the reportlab/PDF backend
# uses exactly. The SVG backend declares font-family:sans-serif, and some SVG
# viewers substitute a slightly wider face. This factor shrinks the usable line
# width by a few percent so wrapped lines keep a small buffer and never spill past
# the box edge under font substitution. It is invisible in the PDF (text just
# wraps a hair earlier) and keeps measurement and drawing perfectly in sync.
WRAP_SAFETY = 0.95

def _sw(s: str, fs: float) -> float:
    """Rendered width of a string at the given font size (real Helvetica metrics)."""
    return stringWidth(s, _WRAP_FONT, fs)

def _wrap(text: str, max_w: float, fs: float) -> List[str]:
    """Greedy word-wrap using real glyph widths so measurement == drawing.

    Falls back to character-level breaking for words longer than max_w, so no
    single long token (e.g. a URL or 'adherence_prob') overflows the box edge.
    """
    if max_w <= 0:
        max_w = fs  # degenerate guard
    max_w *= WRAP_SAFETY
    out: List[str] = []
    for raw in str(text).split("\n"):
        words = raw.split(" ")
        line = ""
        for word in words:
            # Break a single word that is itself wider than the line.
            while _sw(word, fs) > max_w and len(word) > 1:
                cut = len(word)
                # find the largest prefix that fits
                for i in range(1, len(word) + 1):
                    if _sw(word[:i], fs) > max_w:
                        cut = max(1, i - 1)
                        break
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:cut])
                word = word[cut:]
            candidate = word if not line else f"{line} {word}"
            if _sw(candidate, fs) <= max_w or not line:
                line = candidate
            else:
                out.append(line)
                line = word
        out.append(line)
    return out or [""]

def _lh(fs): return fs * LH
def _h(text, max_w, fs): return len(_wrap(text, max_w, fs)) * _lh(fs)
def _hb(items, max_w, fs, ind=12):
    return sum(len(_wrap(i, max_w-ind, fs)) * _lh(fs) for i in items)
def _hdr_h(fs=None): return (fs or FS["sec_hdr"]) + PAD * 1.6

# -- SVG context ---------------------------------------------------------------
def _esc(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

class SVGCtx:
    def __init__(self, W, H):
        self.W=W; self.H=H; self._els=[]
        self._fill="#000000"; self._stroke="#000000"; self._lw=1.0
        self._bold=False; self._italic=False; self._fs=10.0

    def _sy(self, y): return self.H - y
    def setFillColor(self, c): self._fill = c if isinstance(c,str) else self._hex(c)
    def setStrokeColor(self, c): self._stroke = c if isinstance(c,str) else self._hex(c)
    def setLineWidth(self, w): self._lw = w
    def setFont(self, name, size):
        self._fs=size
        self._bold="Bold" in name
        self._italic="Oblique" in name or "Italic" in name

    def _hex(self, c):
        try: return f"#{int(c.red*255):02X}{int(c.green*255):02X}{int(c.blue*255):02X}"
        except: return "#000000"

    def _fa(self):
        w = "bold" if self._bold else "normal"
        s = "italic" if self._italic else "normal"
        # Prefer Helvetica/Arial -- the metrics wrapping is measured against -- so the
        # SVG renders with the same glyph widths the layout was computed for.
        return (f'font-family="Helvetica, Arial, sans-serif" font-size="{self._fs:.1f}" '
                f'font-weight="{w}" font-style="{s}"')

    def roundRect(self, x, y, w, h, r):
        sy = self._sy(y+h)
        self._els.append(f'<rect x="{x:.1f}" y="{sy:.1f}" width="{w:.1f}" height="{h:.1f}" '
                         f'rx="{r}" ry="{r}" fill="{self._fill}" stroke="{self._stroke}" '
                         f'stroke-width="{self._lw:.1f}"/>')

    def drawString(self, x, y, text):
        self._els.append(f'<text x="{x:.1f}" y="{self._sy(y):.1f}" {self._fa()} '
                         f'fill="{self._fill}">{_esc(text)}</text>')

    def drawCentredString(self, x, y, text):
        self._els.append(f'<text x="{x:.1f}" y="{self._sy(y):.1f}" text-anchor="middle" '
                         f'{self._fa()} fill="{self._fill}">{_esc(text)}</text>')

    def to_svg(self, display_scale=1.0):
        W = self.W * display_scale; H = self.H * display_scale
        body = "\n  ".join(self._els)
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
                f'viewBox="0 0 {self.W:.0f} {self.H:.0f}">\n'
                f'  <rect width="{self.W:.0f}" height="{self.H:.0f}" fill="white"/>\n'
                f'  {body}\n</svg>')

# -- Drawing primitives --------------------------------------------------------
def rrect(ctx, x, y, w, h, r=4, fill="#FFFFFF", stroke="#AAAAAA", sw=1.0):
    ctx.setFillColor(fill); ctx.setStrokeColor(stroke); ctx.setLineWidth(sw)
    try:    ctx.roundRect(x, y, w, h, r, stroke=1, fill=1)
    except: ctx.roundRect(x, y, w, h, r)

def _fit_fs(text, max_w, fs, min_fs=7.0, bold=True):
    """Largest font size <= fs (down to min_fs) at which `text` fits in max_w."""
    f = fs
    while f > min_fs and stringWidth(text, "Helvetica-Bold" if bold else "Helvetica", f) > max_w:
        f -= 0.5
    return f

def banner(ctx, x, y, w, h, text, bg, fg="#FFFFFF", fs=None):
    # NOTE: reportlab reads 3-digit hex like "#FFF" as the integer 0x000FFF
    # (pure blue), NOT as white -- it does not expand shorthand the way CSS does.
    # Always use full 6-digit hex for colors passed to the canvas.
    fs = fs or FS["sec_hdr"]
    rrect(ctx, x, y, w, h, r=4, fill=bg, stroke=bg, sw=0)
    # Shrink the label if it would otherwise overflow the banner width.
    fs = _fit_fs(text, w - 2*PAD, fs)
    ctx.setFillColor(fg); ctx.setFont("Helvetica-Bold", fs)
    ctx.drawCentredString(x+w/2, y+h/2-fs*0.36, text)

def pill(ctx, x, y, text, bg, w=50, h=15):
    rrect(ctx, x, y, w, h, r=3, fill=bg, stroke=bg, sw=0)
    ctx.setFillColor(C["badge_txt"]); ctx.setFont("Helvetica-Bold", FS["badge"])
    ctx.drawCentredString(x+w/2, y+h/2-FS["badge"]*0.36, text)

def wt(ctx, text, x, y, max_w, fs=None, color=None, bold=False, italic=False) -> float:
    """Draw wrapped text. `y` is the TOP of the text area; the first baseline is
    dropped by the glyph ascent so ascenders stay inside the container. Returns
    the y (top) for the next block."""
    fs  = fs or FS["body"]
    fn  = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
    if color: ctx.setFillColor(color)
    ctx.setFont(fn, fs)
    base = y - ASCENT * fs            # first-line baseline, ascent below the top
    for line in _wrap(text, max_w, fs):
        ctx.drawString(x, base, line)
        base -= _lh(fs)
        y    -= _lh(fs)
    return y

def wb(ctx, items, x, y, max_w, fs=None, color=None, ind=12) -> float:
    """Draw a bulleted list. `y` is the TOP of the text area (see `wt`)."""
    fs = fs or FS["body"]
    if color: ctx.setFillColor(color)
    ctx.setFont("Helvetica", fs)
    base = y - ASCENT * fs
    for item in items:
        lines = _wrap(item, max_w-ind, fs)
        ctx.drawString(x, base, "\u2022")
        ctx.drawString(x+ind, base, lines[0] if lines else "")
        base -= _lh(fs); y -= _lh(fs)
        for cont in lines[1:]:
            ctx.drawString(x+ind, base, cont)
            base -= _lh(fs); y -= _lh(fs)
    return y

# -- Layout constants ----------------------------------------------------------
PILL_TXT_W = 50   # visible pill width
PILL_H     = 15   # pill height
PILL_GAP   = 6    # gap between name column and pill
PILL_W     = PILL_TXT_W + PILL_GAP   # total horizontal space reserved for the badge

# ===============================================================================
# Height calculators -- MUST match draw exactly
# Each returns the height of the element given the available width.
# ===============================================================================

def _h_ds_card(w, ds):
    """Height of a single dataset card. The STATIC/DYNAMIC badge sits to the
    RIGHT of the name (template layout), so the name wraps within the width left
    of the badge and the badge never overlaps body text."""
    iw       = w - 2*PAD
    name_w   = iw - PILL_W                 # name column, leaving room for the badge
    h  = PAD
    name_h   = _h(ds.name, name_w, FS["card_ttl"])
    h += max(name_h, PILL_H)               # name/badge row (badge is one pill tall)
    h += GAP * 0.5
    h += _h(ds.description, iw, FS["body"])
    h += GAP * 0.5
    h += _h(f"-> {ds.how_used}", iw, FS["italic"])
    h += PAD
    return h

def _h_pipeline(w, p):
    """p = DataPipeline"""
    iw = w - 2*PAD
    h  = PAD
    h += _lh(FS["card_ttl"])    # title
    h += GAP * 0.5
    for _, items in [("",p.collection),("",p.preprocessing),("",p.analysis)]:
        h += _lh(FS["label"])   # stage label
        h += _h("  |  ".join(items) if items else "--", iw, FS["body"])
        h += GAP * 0.4
    h += PAD
    return h

def _h_col1(w, p):
    iw = w - 2*PAD
    h  = PAD + _hdr_h() + PAD
    for ds in p.datasets: h += _h_ds_card(iw, ds) + GAP
    h += _h_pipeline(iw, p.pipeline) + PAD
    return h

def _h_submodels(w, subs):
    iw = w - 2*PAD
    h  = PAD + _lh(FS["card_ttl"]) + GAP * 0.5
    for sm in subs:
        h += _lh(FS["body"])                      # name line
        h += _h(sm.description, iw-PAD, FS["body"])
        h += GAP * 0.4
    h += PAD
    return h

def _h_agents(w, ag):
    iw = w - 2*PAD
    h  = PAD + _lh(FS["card_ttl"]) + GAP * 0.4
    if ag.types:
        h += _h("Types: " + ", ".join(ag.types), iw, FS["body"]) + GAP * 0.3
    h += _lh(FS["label"]) + GAP * 0.2
    h += _hb(ag.state_variables, iw, FS["body"]) + GAP * 0.4
    if ag.data_source:
        h += _h(f"-> {ag.data_source}", iw, FS["italic"]) + GAP
    if ag.submodels:
        h += _h_submodels(iw, ag.submodels) + GAP * 0.5
    h += PAD
    return h

def _h_interactions(w, intr):
    iw = w - 2*PAD
    h  = PAD + _lh(FS["card_ttl"]) + GAP * 0.4
    for items in [intr.agent_agent, intr.agent_environment, intr.topology]:
        if not items: continue
        h += _lh(FS["label"])
        for item in items: h += _h(item, iw-PAD, FS["body"])
        h += GAP * 0.3
    if intr.data_source:
        h += GAP * 0.5 + _h(f"-> {intr.data_source}", iw, FS["italic"])
    h += PAD
    return h

def _h_environment(w, env):
    iw = w - 2*PAD
    h  = PAD + _lh(FS["card_ttl"]) + GAP * 0.4
    for row in [f"Grid: {env.grid}", f"Resolution: {env.resolution}",
                ("Layers: " + ", ".join(env.layers)) if env.layers else ""]:
        if row.strip().strip("Grid:").strip("Resolution:").strip():
            h += _h(row, iw, FS["body"])
    if env.data_source:
        h += GAP * 0.5 + _h(f"-> {env.data_source}", iw, FS["italic"])
    h += PAD
    return h

def _h_temporal(w=None, abm=None):
    """Height of the temporal/stop strip. When given the available width and the
    ABM data, it measures real wrapped line counts so long durations or stop
    conditions can't overflow the strip; otherwise it falls back to two lines."""
    if w is None or abm is None:
        return _lh(FS["temporal"]) * 2 + PAD * 2.4
    iw = w - 2*PAD
    line1 = (f"Temporal: {abm.temporal_unit}"
             + (f"  |  Duration: {abm.duration}" if abm.duration else ""))
    n1 = len(_wrap(line1, iw, FS["temporal"]))
    n2 = len(_wrap(f"Stop: {abm.stop_condition}", iw, FS["temporal"]))
    return _lh(FS["temporal"]) * (n1 + n2) + PAD * 2.4

def _h_col2(w, abm):
    ip    = PAD + 2
    iw    = w - 2*ip
    ag_w  = int(iw * 0.52) - GAP // 2
    ri_w  = iw - ag_w - GAP
    ag_h  = _h_agents(ag_w, abm.agents)
    env_h = _h_environment(ri_w, abm.environment)
    intr_h= _h_interactions(ri_w, abm.interactions)
    ch    = max(ag_h, env_h + GAP + intr_h)
    return _hdr_h(FS["sec_hdr"]+1) + ip + ch + _h_temporal(iw, abm) + ip * 3

def _h_out_card(w, op):
    iw = w - 2*PAD
    h  = PAD + _lh(FS["card_ttl"]) + GAP * 0.3
    h += _h(op.what_measured, iw-PAD, FS["body"])
    h += _h(op.pattern_type,  iw-PAD, FS["body"])
    if op.emergent:
        h += _h(f"Emergent: {op.emergent}", iw-PAD, FS["italic"])
    h += PAD
    return h

def _h_col3_obs(w, ops):
    iw = w - 2*PAD
    h  = PAD + _hdr_h() + PAD
    for op in ops: h += _h_out_card(iw, op) + GAP
    h += PAD
    return h

def _h_col3_eval(w, ev):
    iw  = w - 2*PAD
    vw  = iw - 50 - PAD   # value column width
    cal = ev.calibration
    val = ev.validation
    h   = PAD + _hdr_h() + PAD
    # calibration card
    h += PAD + _lh(FS["card_ttl"]) + GAP * 0.4
    for _, v in [("",cal.method), ("",", ".join(cal.target_params)),
                 ("",cal.data_source), ("",cal.result)]:
        h += max(_h(v, vw, FS["body"]), _lh(FS["body"]))
    h += GAP
    # validation card
    h += PAD + _lh(FS["card_ttl"]) + GAP * 0.4
    h += _hb(val.approaches, iw-PAD, FS["body"])
    if val.result: h += _h(f"Result: {val.result}", iw-PAD, FS["body"])
    h += PAD * 2.5
    return h

def _h_col3(w, p):
    return _h_col3_obs(w, p.output_patterns) + GAP + _h_col3_eval(w, p.evaluation)

def _h_scenarios(W, p):
    if not p.scenarios: return 70
    n  = len(p.scenarios)
    sw = (W - 2*MAR - 2*PAD - GAP*(n-1)) / n
    cw = sw - 2*PAD
    # Tallest card = name lines + gap + description lines, measured per scenario.
    body = max(_h(sc.name, cw, FS["card_ttl"]) + GAP*0.3 + _h(sc.description, cw, FS["body"])
               for sc in p.scenarios)
    return PAD + _hdr_h() + PAD + body + PAD * 2


# ===============================================================================
# Renderer
# ===============================================================================

class VODDRenderer:
    A4_W = 595.28
    A4_H = 841.89

    def __init__(self, p: VODDProtocol):
        self.p = p

    def _layout(self):
        W      = self.A4_W
        usable = W - 2*MAR
        c1w = int(usable * 0.265)
        c2w = int(usable * 0.445)
        c3w = usable - c1w - c2w - 2*GAP

        pw    = W - 2*MAR - 2*PAD
        pur_h = (PAD + _lh(FS["purpose_lbl"]) + GAP*0.4
                 + _h(str(self.p.purpose), pw, FS["purpose_txt"]) + PAD * 1.5)

        h1 = _h_col1(c1w, self.p)
        h2 = _h_col2(c2w, self.p.abm_core)
        h3 = _h_col3(c3w, self.p)
        main_h = max(h1, h2, h3)
        sc_h   = _h_scenarios(W, self.p)
        H      = MAR + pur_h + GAP + main_h + GAP + sc_h + MAR

        return dict(W=W, H=H,
                    c1w=c1w, c2w=c2w, c3w=c3w,
                    pur_h=pur_h, main_h=main_h, sc_h=sc_h,
                    h1=h1, h2=h2, h3=h3)

    # -- Public API ------------------------------------------------------------
    def render_pdf(self, path: str):
        """A4-width portrait PDF. Height is content-driven (fits on one A4 page
        for typical models). Print with 'scale to fit' if taller than A4."""
        lo     = self._layout()
        page_h = max(lo["H"], self.A4_H)
        y_off  = page_h - lo["H"]
        c = rl_canvas.Canvas(path, pagesize=(self.A4_W, page_h))
        c.setTitle("vODD-DD Protocol Diagram")
        if y_off > 0: c.translate(0, y_off)
        self._draw(c, lo)
        c.save()

    def render_svg(self, path: str):
        """SVG at 2x display resolution."""
        lo  = self._layout()
        ctx = SVGCtx(lo["W"], lo["H"])
        self._draw(ctx, lo)
        with open(path, "w", encoding="utf-8") as f:
            f.write(ctx.to_svg(display_scale=2.0))

    def render_png(self, path: str, dpi: int = 150):
        """
        PNG via PyMuPDF (pure Python, works on Windows/Mac/Linux).
        Install:  pip install pymupdf
        Fallback: pdftoppm (Linux/Mac system tool)
        """
        # -- PyMuPDF -----------------------------------------------------------
        try:
            import fitz
            buf = io.BytesIO()
            lo  = self._layout()
            ph  = max(lo["H"], self.A4_H)
            c   = rl_canvas.Canvas(buf, pagesize=(self.A4_W, ph))
            if ph > lo["H"]: c.translate(0, ph - lo["H"])
            self._draw(c, lo)
            c.save()
            doc  = fitz.open(stream=buf.getvalue(), filetype="pdf")
            pix  = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
            pix.save(path)
            doc.close()
            return
        except ImportError:
            pass

        # -- pdftoppm fallback (Linux/macOS) -----------------------------------
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            self.render_pdf(tmp)
            prefix = path[:-4] if path.endswith(".png") else path
            subprocess.run(["pdftoppm","-png","-r",str(dpi),"-singlefile",tmp,prefix],
                           capture_output=True)
            if not os.path.exists(path):
                cand = prefix + "-1.png"
                if os.path.exists(cand): shutil.move(cand, path)
        finally:
            if os.path.exists(tmp): os.remove(tmp)

        if not os.path.exists(path):
            raise RuntimeError(
                "PNG generation failed.\n"
                "  Windows/Mac/Linux: pip install pymupdf\n"
                "  Linux/Mac only:    sudo apt install poppler-utils"
            )

    # -- Draw ------------------------------------------------------------------
    def _draw(self, ctx, lo):
        W, H   = lo["W"], lo["H"]
        c1x    = MAR
        c2x    = c1x + lo["c1w"] + GAP
        c3x    = c2x + lo["c2w"] + GAP
        sc_y   = MAR
        main_y = sc_y  + lo["sc_h"] + GAP
        pur_y  = main_y + lo["main_h"] + GAP

        rrect(ctx, 0, 0, W, H, r=0, fill=C["page_bg"], stroke=C["page_bg"], sw=0)
        self._d_purpose(ctx, MAR, pur_y, W-2*MAR, lo["pur_h"])
        self._d_col1(ctx, c1x, main_y + lo["main_h"] - lo["h1"], lo["c1w"], lo["h1"])
        self._d_col2(ctx, c2x, main_y + lo["main_h"] - lo["h2"], lo["c2w"], lo["h2"])
        self._d_col3(ctx, c3x, main_y + lo["main_h"] - lo["h3"], lo["c3w"], lo["h3"])
        self._d_scenarios(ctx, MAR, sc_y, W-2*MAR, lo["sc_h"])

    # -- Purpose ---------------------------------------------------------------
    def _d_purpose(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=6, fill=C["purpose_bg"], stroke=C["purpose_bg"], sw=0)
        iw = w - 2*PAD
        ty = y + h - PAD
        ty = wt(ctx, "PURPOSE & PATTERNS", x+PAD, ty, iw,
                fs=FS["purpose_lbl"], color="#FFFFFF", bold=True)
        ty -= GAP*0.4
        wt(ctx, str(self.p.purpose), x+PAD, ty, iw,
           fs=FS["purpose_txt"], color=C["purpose_txt"], italic=True)

    # -- Col 1: Data Inputs + Pipeline -----------------------------------------
    def _d_col1(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=6, fill=C["card_bg"], stroke=C["card_bdr"], sw=1)
        iw = w - 2*PAD
        ty = y + h - PAD

        # Header
        hh = _hdr_h()
        ty -= hh
        banner(ctx, x+PAD, ty, iw, hh, "DATA INPUTS", C["inp_hdr"])
        ty -= PAD

        # Dataset cards
        for ds in self.p.datasets:
            ch = _h_ds_card(iw, ds)
            ty -= ch
            self._d_ds_card(ctx, x+PAD, ty, iw, ch, ds)
            ty -= GAP

        # Pipeline
        ph = _h_pipeline(iw, self.p.pipeline)
        ty -= ph
        self._d_pipeline(ctx, x+PAD, ty, iw, ph)

    def _d_ds_card(self, ctx, x, y, w, h, ds):
        rrect(ctx, x, y, w, h, r=4, fill=C["white"], stroke=C["inp_bdr"], sw=1)
        iw     = w - 2*PAD
        name_w = iw - PILL_W
        top    = y + h - PAD

        # Badge: top-right of the card, vertically aligned with the first name line.
        bg = C["dynamic_bg"] if ds.frequency == "DYNAMIC" else C["static_bg"]
        pill(ctx, x + PAD + name_w + PILL_GAP, top - PILL_H, ds.frequency, bg,
             w=PILL_TXT_W, h=PILL_H)

        # Name (wraps within the column left of the badge).
        name_h = _h(ds.name, name_w, FS["card_ttl"])
        ty = wt(ctx, ds.name, x+PAD, top, name_w,
                fs=FS["card_ttl"], color=C["ds_title"], bold=True)
        # Advance past whichever is taller -- the name block or the badge.
        ty = top - max(name_h, PILL_H)
        ty -= GAP * 0.5

        # Description + link (full width, below the name/badge row).
        ty = wt(ctx, ds.description, x+PAD, ty, iw,
                fs=FS["body"], color=C["mid"])
        ty -= GAP * 0.5
        wt(ctx, f"-> {ds.how_used}", x+PAD, ty, iw,
           fs=FS["italic"], color=C["link"], italic=True)

    def _d_pipeline(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=4, fill=C["pipe_bg"], stroke=C["pipe_bdr"], sw=1.5)
        iw = w - 2*PAD
        ty = y + h - PAD

        ty = wt(ctx, "DATA PIPELINE", x+PAD, ty, iw,
                fs=FS["card_ttl"], color=C["pipe_title"], bold=True)
        ty -= GAP * 0.5

        for lbl, items in [("1. Collection", self.p.pipeline.collection),
                            ("2. Pre-processing", self.p.pipeline.preprocessing),
                            ("3. Analysis", self.p.pipeline.analysis)]:
            ty = wt(ctx, lbl, x+PAD, ty, iw, fs=FS["label"], color=C["dark"], bold=True)
            ty = wt(ctx, "  |  ".join(items) if items else "--",
                    x+PAD+5, ty, iw-5, fs=FS["body"], color=C["muted"])
            ty -= GAP * 0.4

    # -- Col 2: ABM Core -------------------------------------------------------
    def _d_col2(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=7, fill=C["abm_bg"], stroke=C["abm_bdr"], sw=2)
        ip    = PAD + 2
        iw    = w - 2*ip
        tfs   = FS["sec_hdr"] + 1

        # Title strip
        th = _hdr_h(tfs)
        ty_top = y + h - th
        abm_title = f"ABM CORE:  {self.p.abm_core.model_name}"
        tfs = _fit_fs(abm_title, w - 2*ip, tfs)
        ctx.setFont("Helvetica-Bold", tfs); ctx.setFillColor(C["abm_title"])
        ctx.drawCentredString(x+w/2, ty_top+th/2-tfs*0.36, abm_title)

        # Temporal strip at bottom
        ts_h = _h_temporal(iw, self.p.abm_core)
        ts_y = y + ip
        self._d_temporal(ctx, x+ip, ts_y, iw, ts_h)

        # Content area between title and temporal
        c_bot = ts_y + ts_h + ip
        c_top = ty_top - ip

        ag_w  = int(iw * 0.52) - GAP // 2
        ri_w  = iw - ag_w - GAP
        ri_x  = x + ip + ag_w + GAP

        ag_h    = _h_agents(ag_w, self.p.abm_core.agents)
        env_h   = _h_environment(ri_w, self.p.abm_core.environment)
        intr_h  = _h_interactions(ri_w, self.p.abm_core.interactions)

        # Top-align agents; top-align env, stretch intr to fill remaining right space
        ag_y   = c_top - ag_h
        env_y  = c_top - env_h
        intr_h2= env_y - GAP - c_bot        # stretch intr to fill right space
        intr_y = c_bot

        self._d_agents(ctx, x+ip, ag_y, ag_w, ag_h)
        self._d_env   (ctx, ri_x, env_y, ri_w, env_h)
        self._d_intr  (ctx, ri_x, intr_y, ri_w, max(intr_h, intr_h2))

    def _d_agents(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=5, fill=C["ag_bg"], stroke=C["ag_bdr"], sw=1.5)
        iw = w - 2*PAD
        ag = self.p.abm_core.agents
        ty = y + h - PAD

        ty = wt(ctx, f"AGENTS  (n=[{ag.n_expression}])", x+PAD, ty, iw,
                fs=FS["card_ttl"], color=C["ag_title"], bold=True)
        ty -= GAP * 0.4

        if ag.types:
            ty = wt(ctx, "Types: " + ", ".join(ag.types),
                    x+PAD, ty, iw, fs=FS["body"], color=C["dark"])
            ty -= GAP * 0.3

        ty = wt(ctx, "State variables:", x+PAD, ty, iw,
                fs=FS["label"], color=C["dark"], bold=True)
        ty -= GAP * 0.2
        ty = wb(ctx, ag.state_variables, x+PAD, ty, iw,
                fs=FS["body"], color=C["mid"])
        ty -= GAP * 0.4

        if ag.data_source:
            ty = wt(ctx, f"-> {ag.data_source}", x+PAD, ty, iw,
                    fs=FS["italic"], color=C["link"], italic=True)
            ty -= GAP

        if ag.submodels:
            sub_h = _h_submodels(iw, ag.submodels)
            sub_y = max(y + 2, ty - sub_h)
            self._d_submodels(ctx, x+PAD, sub_y, iw, sub_h, ag.submodels)

    def _d_submodels(self, ctx, x, y, w, h, subs):
        rrect(ctx, x, y, w, h, r=4, fill=C["sub_bg"], stroke=C["sub_bdr"], sw=1)
        iw = w - 2*PAD
        ty = y + h - PAD

        ty = wt(ctx, "Submodels (Behaviors)", x+PAD, ty, iw,
                fs=FS["card_ttl"], color=C["sub_title"], bold=True)
        ty -= GAP * 0.5

        for sm in subs:
            if ty < y + PAD: break
            ty = wt(ctx, sm.name, x+PAD, ty, iw,
                    fs=FS["body"], color=C["dark"], bold=True)
            ty = wt(ctx, sm.description, x+PAD*2, ty, iw-PAD,
                    fs=FS["body"], color=C["muted"], italic=True)
            ty -= GAP * 0.4

    def _d_intr(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=5, fill=C["intr_bg"], stroke=C["intr_bdr"], sw=1.5)
        iw = w - 2*PAD
        ty = y + h - PAD

        ty = wt(ctx, "INTERACTIONS", x+PAD, ty, iw,
                fs=FS["card_ttl"], color=C["intr_title"], bold=True)
        ty -= GAP * 0.4

        intr = self.p.abm_core.interactions
        for lbl, items in [("Agent <> Agent", intr.agent_agent),
                            ("Agent <> Env",  intr.agent_environment),
                            ("Topology",      intr.topology)]:
            if not items: continue
            ty = wt(ctx, f"* {lbl}", x+PAD, ty, iw,
                    fs=FS["label"], color=C["dark"], bold=True)
            for item in items:
                ty = wt(ctx, item, x+PAD*2, ty, iw-PAD,
                        fs=FS["body"], color=C["mid"])
            ty -= GAP * 0.3
        if intr.data_source:
            ty -= GAP * 0.5
            wt(ctx, f"-> {intr.data_source}", x+PAD, ty, iw,
               fs=FS["italic"], color=C["link"], italic=True)

    def _d_env(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=5, fill=C["env_bg"], stroke=C["env_bdr"], sw=1.5)
        iw = w - 2*PAD
        ty = y + h - PAD

        ty = wt(ctx, "ENVIRONMENT", x+PAD, ty, iw,
                fs=FS["card_ttl"], color=C["env_title"], bold=True)
        ty -= GAP * 0.4

        env = self.p.abm_core.environment
        for row in [f"Grid: {env.grid}", f"Resolution: {env.resolution}",
                    ("Layers: " + ", ".join(env.layers)) if env.layers else ""]:
            stripped = row.replace("Grid: ","").replace("Resolution: ","").strip()
            if stripped:
                ty = wt(ctx, row, x+PAD, ty, iw, fs=FS["body"], color=C["dark"])
        if env.data_source:
            ty -= GAP * 0.5
            wt(ctx, f"-> {env.data_source}", x+PAD, ty, iw,
               fs=FS["italic"], color=C["link"], italic=True)

    def _d_temporal(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=4, fill=C["temp_bg"], stroke=C["temp_bdr"], sw=1.2)
        abm  = self.p.abm_core
        iw   = w - 2*PAD
        ty   = y + h - PAD
        line1 = (f"Temporal: {abm.temporal_unit}"
                 + (f"  |  Duration: {abm.duration}" if abm.duration else ""))
        ty = wt(ctx, line1, x+PAD, ty, iw,
                fs=FS["temporal"], color=C["dark"], bold=True)
        wt(ctx, f"Stop: {abm.stop_condition}", x+PAD, ty, iw,
           fs=FS["temporal"], color=C["stop_c"])

    # -- Col 3: Observations + Evaluation --------------------------------------
    def _d_col3(self, ctx, x, y, w, h):
        obs_h  = _h_col3_obs(w, self.p.output_patterns)
        eval_h = _h_col3_eval(w, self.p.evaluation)
        obs_y  = y + h - obs_h
        eval_y = obs_y - GAP - eval_h
        self._d_obs (ctx, x, obs_y,  w, obs_h)
        self._d_eval(ctx, x, eval_y, w, eval_h)

    def _d_obs(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=6, fill=C["card_bg"], stroke=C["card_bdr"], sw=1)
        iw = w - 2*PAD
        ty = y + h - PAD

        hh = _hdr_h()
        ty -= hh
        banner(ctx, x+PAD, ty, iw, hh, "OBSERVATIONS", C["obs_hdr"])
        ty -= PAD

        bgs  = C["out_bgs"]
        bdrs = C["out_bdrs"]
        ttls = C["out_titles"]
        for i, op in enumerate(self.p.output_patterns):
            bg  = bgs[i % len(bgs)]
            bdr = bdrs[i % len(bdrs)]
            ttl = ttls[i % len(ttls)]
            ch  = _h_out_card(iw, op)
            ty -= ch
            rrect(ctx, x+PAD, ty, iw, ch, r=4, fill=bg, stroke=bdr, sw=1.2)
            oty = ty + ch - PAD

            icon = emoji_op(op.name, op.what_measured)
            oty = wt(ctx, f"{icon} {op.name}", x+PAD*2, oty, iw-PAD,
                     fs=FS["card_ttl"], color=ttl, bold=True)
            oty -= GAP * 0.3
            oty = wt(ctx, op.what_measured, x+PAD*2, oty, iw-PAD,
                     fs=FS["body"], color=C["dark"])
            oty = wt(ctx, op.pattern_type, x+PAD*2, oty, iw-PAD,
                     fs=FS["body"], color=C["mid"])
            if op.emergent:
                wt(ctx, f"Emergent: {op.emergent}", x+PAD*2, oty, iw-PAD,
                   fs=FS["italic"], color=C["muted"], italic=True)
            ty -= GAP

    def _d_eval(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=6, fill=C["card_bg"], stroke=C["card_bdr"], sw=1)
        iw = w - 2*PAD
        vw = iw - 50 - PAD
        ty = y + h - PAD

        hh = _hdr_h()
        ty -= hh
        banner(ctx, x+PAD, ty, iw, hh, "MODEL EVALUATION", C["eval_hdr"])
        ty -= PAD

        cal = self.p.evaluation.calibration
        val = self.p.evaluation.validation

        # Calibration card
        cal_rows = [("Method:", cal.method), ("Params:", ", ".join(cal.target_params)),
                    ("Data:", cal.data_source), ("Result:", cal.result)]
        cal_h = (PAD + _lh(FS["card_ttl"]) + GAP*0.4
                 + sum(max(_h(v, vw, FS["body"]), _lh(FS["body"])) for _,v in cal_rows)
                 + PAD)
        ty -= cal_h
        rrect(ctx, x+PAD, ty, iw, cal_h, r=4, fill=C["cal_bg"], stroke=C["cal_bdr"], sw=1.2)
        cty = ty + cal_h - PAD

        cty = wt(ctx, "Calibration", x+PAD*2, cty, iw-PAD,
                 fs=FS["card_ttl"], color=C["cal_title"], bold=True)
        cty -= GAP * 0.4

        fsb  = FS["body"]
        base = cty - ASCENT * fsb        # first row baseline, ascent below the cursor
        for lbl, val_str in cal_rows:
            ctx.setFont("Helvetica-Bold", fsb); ctx.setFillColor(C["dark"])
            ctx.drawString(x+PAD*2, base, lbl)
            lines = _wrap(val_str, vw, fsb)
            ctx.setFont("Helvetica", fsb); ctx.setFillColor(C["mid"])
            ctx.drawString(x+PAD*2+50, base, lines[0] if lines else "")
            base -= _lh(fsb)
            for ln in lines[1:]:
                ctx.drawString(x+PAD*2+50, base, ln)
                base -= _lh(fsb)

        ty -= GAP

        # Validation card
        val_items_h = _hb(val.approaches, iw-PAD, FS["body"])
        res_h = _h(f"Result: {val.result}", iw-PAD, FS["body"]) if val.result else 0
        val_h = PAD + _lh(FS["card_ttl"]) + GAP*0.4 + val_items_h + res_h + PAD*2.5
        ty -= val_h
        rrect(ctx, x+PAD, ty, iw, val_h, r=4, fill=C["val_bg"], stroke=C["val_bdr"], sw=1.2)
        vty = ty + val_h - PAD

        vty = wt(ctx, "Validation", x+PAD*2, vty, iw-PAD,
                 fs=FS["card_ttl"], color=C["val_title"], bold=True)
        vty -= GAP * 0.4
        vty = wb(ctx, val.approaches, x+PAD*2, vty, iw-PAD,
                 fs=FS["body"], color=C["dark"])
        if val.result:
            wt(ctx, f"Result: {val.result}", x+PAD*2, vty, iw-PAD,
               fs=FS["body"], color=C["val_title"], bold=True)

    # -- Scenarios -------------------------------------------------------------
    def _d_scenarios(self, ctx, x, y, w, h):
        rrect(ctx, x, y, w, h, r=6, fill=C["sc_bg"], stroke=C["sc_bdr"], sw=1)
        hh = _hdr_h()
        # Header (left-aligned), ascent-positioned inside its band.
        wt(ctx, "SCENARIOS (if applicable):", x+PAD, y+h-PAD, w-2*PAD,
           fs=FS["sec_hdr"], color=C["dark"], bold=True)

        scs = self.p.scenarios
        if not scs: return
        n      = len(scs)
        sw_    = (w - 2*PAD - GAP*(n-1)) / n
        sx     = x + PAD
        card_y = y + PAD
        card_h = h - PAD - hh - PAD - PAD     # top PAD + header + PAD gap, bottom PAD

        for sc in scs:
            hl  = sc.highlighted
            bg  = C["sc_hl"]     if hl else C["sc_card"]
            bdr = C["sc_hl_bdr"] if hl else C["sc_card_bdr"]
            tc  = C["sc_hl_txt"] if hl else C["dark"]
            lw_ = 2.5            if hl else 1
            rrect(ctx, sx, card_y, sw_, card_h, r=4, fill=bg, stroke=bdr, sw=lw_)
            ity = card_y + card_h - PAD
            ity = wt(ctx, sc.name, sx+PAD, ity, sw_-2*PAD,
                     fs=FS["card_ttl"], color=tc, bold=True)
            ity -= GAP * 0.3
            wt(ctx, sc.description, sx+PAD, ity, sw_-2*PAD,
               fs=FS["body"], color=C["mid"] if not hl else tc)
            sx += sw_ + GAP
