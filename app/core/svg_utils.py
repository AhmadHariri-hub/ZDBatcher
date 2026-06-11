from pathlib import Path


try:
    import resvg_py as _resvg_py
    _SVG_BACKEND = "resvg"
except Exception:
    _resvg_py = None
    try:
        import cairosvg as _cairosvg
        _SVG_BACKEND = "cairo"
    except Exception:
        _cairosvg = None
        _SVG_BACKEND = None


def svg_backend_name() -> str | None:
    return _SVG_BACKEND


def svg_supported() -> bool:
    return _SVG_BACKEND is not None


def svg_to_png_bytes(svg_path: Path, output_width: int = 2400) -> bytes:
    svg_text = svg_path.read_text(encoding="utf-8", errors="replace")

    if _SVG_BACKEND == "resvg":
        if hasattr(_resvg_py, "svg_to_bytes"):
            try:
                return _resvg_py.svg_to_bytes(svg_string=svg_text, width=output_width)
            except TypeError:
                try:
                    return _resvg_py.svg_to_bytes(svg_string=svg_text)
                except TypeError:
                    return _resvg_py.svg_to_bytes(svg_text)

        if hasattr(_resvg_py, "svg2png"):
            return _resvg_py.svg2png(bytearray(svg_text.encode("utf-8")))

        raise RuntimeError(
            "resvg_py is installed, but no supported SVG conversion function was found."
        )

    if _SVG_BACKEND == "cairo":
        return _cairosvg.svg2png(url=str(svg_path), output_width=output_width)

    raise RuntimeError(
        "SVG support requires one of these packages:\n\n"
        "  py -m pip install resvg-py\n"
        "  py -m pip install cairosvg"
    )