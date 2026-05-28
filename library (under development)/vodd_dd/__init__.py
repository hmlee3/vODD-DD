"""vODD-DD Protocol Generator — generates PDF + SVG + PNG automatically.
PNG requires PyMuPDF:  pip install pymupdf
"""

import io
import os

from .models import (
    VODDProtocol, Dataset, DataPipeline,
    Agents, Submodel, Interactions, Environment, ABMCore,
    OutputPattern, Calibration, Validation, ModelEvaluation, Scenario,
)
from .renderer import VODDRenderer


def _make_png(renderer: VODDRenderer, path: str, dpi: int = 150) -> bool:

    # ── 1. PyMuPDF — pip install pymupdf ─────────────────────────────────────
    try:
        import fitz  # noqa: F401 — PyMuPDF
        renderer.render_png(path, dpi=dpi)
        if os.path.exists(path):
            return True
    except ImportError:
        pass
    except Exception:
        pass

    # ── 2. Direct PyMuPDF fallback (renders PDF in-memory, no temp file) ─────
    try:
        import fitz
        from reportlab.pdfgen import canvas as rl_canvas
        lo  = renderer._layout()
        buf = io.BytesIO()
        ph  = max(lo["H"], renderer.A4_H)
        c   = rl_canvas.Canvas(buf, pagesize=(renderer.A4_W, ph))
        if ph > lo["H"]:
            c.translate(0, ph - lo["H"])
        renderer._draw(c, lo)
        c.save()
        doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        pix.save(path)
        doc.close()
        if os.path.exists(path):
            return True
    except ImportError:
        pass
    except Exception:
        pass

    # ── 3. pdftoppm — system tool (Linux / macOS) ────────────────────────────
    import subprocess, shutil, tempfile
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        renderer.render_pdf(tmp)
        prefix = path[:-4] if path.endswith(".png") else path
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-singlefile", tmp, prefix],
            capture_output=True
        )
        if not os.path.exists(path):
            cand = prefix + "-1.png"
            if os.path.exists(cand):
                shutil.move(cand, path)
        if os.path.exists(path):
            return True
    except Exception:
        pass
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    return False


def generate(protocol: VODDProtocol,
             output_path: str = "vodd_protocol.pdf",
             dpi: int = 150) -> dict:
    """
    Render a vODD-DD protocol diagram to PDF + SVG + PNG.

    PNG requires PyMuPDF — install once with:
        pip install pymupdf

    Returns dict: {'pdf': '...', 'svg': '...', 'png': '...' or None}
    """
    r        = VODDRenderer(protocol)
    svg_path = output_path.replace(".pdf", ".svg")
    png_path = output_path.replace(".pdf", ".png")

    r.render_pdf(output_path)
    r.render_svg(svg_path)

    png_out = None
    if _make_png(r, png_path, dpi=dpi):
        png_out = png_path
    else:
        print("  ⚠️  PNG skipped — run:  pip install pymupdf")

    parts = [f for f in [output_path, svg_path, png_out] if f]
    print("✅  Diagram saved →", " + ".join(parts))
    return {"pdf": output_path, "svg": svg_path, "png": png_out}


__all__ = [
    "generate", "VODDProtocol", "Dataset", "DataPipeline",
    "Agents", "Submodel", "Interactions", "Environment", "ABMCore",
    "OutputPattern", "Calibration", "Validation", "ModelEvaluation", "Scenario",
]
