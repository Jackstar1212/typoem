# -*- coding: utf-8 -*-
from __future__ import annotations

__version__ = "0.3.0"

import os
import platform
import re
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple, Union


# ─────────────────────────────────────────────────────────────────
#  排版样式
# ─────────────────────────────────────────────────────────────────

@dataclass
class TextStyle:
    """
    Span 的排版样式，支持连续字重、伪斜体、下划线、删除线、
    位移、旋转与上下标。

    所有参数均有合理默认值；未启用的效果零开销。样式方法可链式调用：

        cn.bold().italic()("粗斜体")
        cn.underline(width=2, count=2)("双下划线")
        cn("x²").sup()          # 上标
        cn("CO").sub()("2")     # 下标

    Parameters
    ----------
    weight : int
        CSS 风格字重：0~1000，默认 400（正常），700 约等价标准粗体。
    italic : bool
        启用伪斜体（水平剪切变形）。
    italic_slant : float
        倾斜量，推荐范围 0.15–0.40，默认 0.25。
    underline : bool
        启用下划线。
    underline_width : int
        下划线线宽（像素）。
    underline_count : int
        下划线条数（1 = 单线，2 = 双线）。
    underline_gap : int
        双线间距（像素）。
    strikethrough : bool
        启用删除线。
    strikethrough_width : int
        删除线线宽（像素）。
    shift_x : float
        水平偏移量（排版点，正方向向右）。
    shift_y : float
        垂直偏移量（排版点，正方向向上）。
    rotation : float
        旋转角度（度，正方向逆时针）。
    script : str
        上下标模式：``""``（无）、``"sup"``（上标）、``"sub"``（下标）。
    script_ratio : float
        上下标字号缩放比例，默认 0.65。
    """

    weight:             int   = 400
    italic:             bool  = False
    italic_slant:       float = 0.25
    underline:          bool  = False
    underline_width:    int   = 1
    underline_count:    int   = 1
    underline_gap:      int   = 3
    strikethrough:      bool  = False
    strikethrough_width: int  = 1
    shift_x:            float = 0.0
    shift_y:            float = 0.0
    rotation:           float = 0.0
    script:             str   = ""
    script_ratio:       float = 0.65

    def copy(self, **overrides) -> "TextStyle":
        """返回修改了指定字段的新 TextStyle（原对象不变）。"""
        return replace(self, **overrides)


# ─────────────────────────────────────────────────────────────────
#  字体名称 → 根据文件名候选映射
# ─────────────────────────────────────────────────────────────────

_FONT_ALIAS: dict[str, list[str]] = {
    "宋体":       ["simsun.ttc",   "simsun.ttf"],
    "新宋体":     ["simsun.ttc"],
    "黑体":       ["simhei.ttf"],
    "微软雅黑":   ["msyh.ttc",     "msyh.ttf"],
    "微软雅黑粗": ["msyhbd.ttc",   "msyhbd.ttf"],
    "楷体":       ["simkai.ttf",   "kaiti.ttf"],
    "仿宋":       ["simfang.ttf",  "fangsong.ttf"],
    "华文宋体":   ["stsong.ttf",   "STSong.ttf"],
    "华文黑体":   ["stheiti.ttf",  "STHEITI.TTF"],
    "苹方":       ["PingFang.ttc"],
    "苹方-简":    ["PingFang.ttc"],
    "思源宋体":   ["SourceHanSerif.ttc",  "NotoSerifCJK-Regular.ttc"],
    "思源黑体":   ["SourceHanSans.ttc",   "NotoSansCJK-Regular.ttc"],
    "arial":              ["arial.ttf"],
    "arial bold":         ["arialbd.ttf"],
    "times new roman":    ["times.ttf"],
    "calibri":            ["calibri.ttf"],
    "helvetica":          ["Helvetica.ttf",  "helvetica.ttf"],
    "georgia":            ["georgia.ttf"],
    "verdana":            ["verdana.ttf"],
    "courier new":        ["cour.ttf"],
    "tahoma":             ["tahoma.ttf"],
    "trebuchet ms":       ["trebuc.ttf"],
    "consolas":           ["consola.ttf"],
    "cambria":            ["cambria.ttc"],
    "cambria math":       ["cambria.ttc"],
}


def _font_dirs() -> list[Path]:
    """返回当前操作系统的字体搜索目录。"""
    system = platform.system()
    if system == "Windows":
        dirs = [Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"]
        local = Path(os.environ.get("LOCALAPPDATA", "~")) / "Microsoft/Windows/Fonts"
        dirs.append(local.expanduser())
        return dirs
    if system == "Darwin":
        return [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path.home() / "Library/Fonts",
        ]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local/share/fonts",
    ]


def _resolve_via_registry(name: str) -> Optional[str]:
    """
    Windows 专用：通过注册表按字族名查找字体文件路径。

    注册表项格式：值名 = "Arial (TrueType)"，值数据 = "arial.ttf" 或绝对路径。
    完全基于 stdlib winreg，无需任何第三方包。
    """
    try:
        import winreg
    except ImportError:
        return None

    query = name.strip().lower()
    font_dirs = _font_dirs()
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Fonts",
    ]
    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]

    import re as _re
    for hive in hives:
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(hive, reg_path)
            except OSError:
                continue
            try:
                i = 0
                while True:
                    try:
                        val_name, val_data, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    # 从 "Arial Bold (TrueType)" 提取字族名 "arial bold"
                    family = _re.sub(r"\s*\(.*\)$", "", val_name).strip().lower()
                    if family == query or query in family or family in query:
                        if Path(val_data).is_absolute() and Path(val_data).exists():
                            return str(val_data)
                        # val_data 只是文件名，在系统字体目录中查找
                        for d in font_dirs:
                            fp = d / val_data
                            if fp.exists():
                                return str(fp)
            finally:
                winreg.CloseKey(key)
    return None


def _resolve_via_fc(name: str) -> Optional[str]:
    """
    Linux / macOS 专用：通过 fc-list（fontconfig）按字族名查找字体文件路径。

    完全基于 subprocess，无需任何第三方包。
    """
    import subprocess
    try:
        result = subprocess.run(
            ["fc-list", f":family={name}", "--format=%{{file}}\n"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            p = Path(line.strip())
            if p.exists():
                return str(p)
    except Exception:
        pass
    return None


def _resolve_via_system(name: str) -> Optional[str]:
    """
    平台原生字体发现（stdlib only，不依赖任何第三方包）：
    - Windows：读取注册表
    - Linux / macOS：调用 fc-list
    """
    import platform
    if platform.system() == "Windows":
        return _resolve_via_registry(name)
    return _resolve_via_fc(name)


def _resolve(name: str) -> str:
    """
    将字体名或路径解析为字体文件的绝对路径。

    解析顺序：
    1. 若 name 本身是存在的文件路径，直接返回。
    2. 在内置别名表 _FONT_ALIAS 中精确匹配。
    3. 在系统字体目录中按文件名精确匹配。
    4. 在系统字体目录中按文件名词干模糊匹配。
    5. 通过平台原生接口按字族名查找（注册表 / fc-list，覆盖第三方字体）。
    """
    if Path(name).exists():
        return str(Path(name).resolve())

    key = name.strip()
    candidates: list[str] = (
        _FONT_ALIAS.get(key)
        or _FONT_ALIAS.get(key.lower())
        or [key]
    )
    dirs = _font_dirs()

    for d in dirs:
        if not d.exists():
            continue
        for fname in candidates:
            fp = d / fname
            if fp.exists():
                return str(fp)

    stems = {Path(c).stem.lower() for c in candidates}
    for d in dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in {".ttf", ".ttc", ".otf"} and f.stem.lower() in stems:
                return str(f)

    # 平台原生兜底：按字族名查找（覆盖第三方安装字体）
    sys_path = _resolve_via_system(name)
    if sys_path:
        return sys_path

    raise FileNotFoundError(
        f"找不到字体 '{name}'。\n"
        f"  • 可直接传入字体文件路径，例如 Font(r'C:\\Windows\\Fonts\\simsun.ttc')\n"
        f"  • 或调用 Font.list_fonts() 查看系统中所有可用字体。\n"
        f"  • 已搜索目录：{[str(d) for d in dirs]}"
    )


# ─────────────────────────────────────────────────────────────────
#  PIL 绘制辅助
# ─────────────────────────────────────────────────────────────────

def _bold_offsets(weight: float) -> list:
    """生成伪粗体多次绘制的 (dx, dy) 偏移列表。

    weight=1 → [(0,0),(1,0)]（轻，+1 px 右移）
    weight=2 → +2 px 横向，+1 px 纵向（中）
    weight=3 → +3 px 横向，+1 px 纵向（重）
    """
    if weight < 0.9:
        return [(0, 0)]

    r = max(1, int(round(weight)))
    result: list = [(0, 0)]
    for dx in range(1, r + 1):
        result.append((dx, 0))
    if weight > 1.5:
        for dx in range(r):
            result.append((dx, 1))
    return result


def _weight_to_synthetic_strength(weight: int) -> float:
    """将 0~1000 字重映射为伪粗体强度（用于 PIL / Matplotlib 统一绘制）。

    规则：
    - <= 400：不做伪粗体
    - 700：约等于标准粗体（强度 1.0）
    - 1000：强度 2.0
    """
    if weight <= 400:
        return 0.0
    return (weight - 400) / 300.0


def _coerce_css_weight(w: Union[int, float], *, stacklevel: int = 2) -> int:
    """校验并归一化 weight 参数为 0~1000 整数。"""
    if isinstance(w, bool) or not isinstance(w, (int, float)):
        raise TypeError("weight() 需要传入 0~1000 的数值，例如 300/400/700。")

    wi = int(round(float(w)))
    if wi < 0 or wi > 1000:
        raise ValueError(f"weight() 仅支持 0~1000，当前为 {w!r}。")

    return wi


def _try_apply_variable_weight(font, weight: int) -> bool:
    """对可变字体尝试设置 wght 轴。返回 True 表示已成功应用。"""
    try:
        axes = font.get_variation_axes()
    except Exception:
        return False

    wght_axis = None
    for a in axes:
        tag = a.get("tag", b"")
        if isinstance(tag, bytes):
            tag = tag.decode("ascii", errors="replace")
        if tag.strip() == "wght":
            wght_axis = a
            break

    if wght_axis is None:
        return False

    min_w = float(wght_axis.get("minimum", 100))
    max_w = float(wght_axis.get("maximum", 900))
    clamped = max(min_w, min(max_w, float(weight)))

    if int(clamped) != weight:
        warnings.warn(
            f"字体 wght 轴范围为 {int(min_w)}~{int(max_w)}，"
            f"weight={weight} 已钳制到 {int(clamped)}。",
            UserWarning, stacklevel=5,
        )

    values = []
    for a in axes:
        tag = a.get("tag", b"")
        if isinstance(tag, bytes):
            tag = tag.decode("ascii", errors="replace")
        if tag.strip() == "wght":
            values.append(clamped)
        else:
            default = float(a.get(
                "default",
                (float(a.get("minimum", 0)) + float(a.get("maximum", 1000))) / 2,
            ))
            values.append(default)

    try:
        font.set_variation_by_axes(values)
        return True
    except Exception:
        return False


def _load_pil_font_with_weight(path: str, size: int, weight: int):
    """加载 PIL 字体并应用字重，返回 (FreeTypeFont, synth_strength: float)。

    - 可变字体且有 wght 轴：轴值已设置，synth_strength=0.0
    - 静态字体 weight>400：synth_strength 为正（用于伪粗体）
    - 静态字体 weight<400：发出警告，synth_strength=0.0（保持默认字重）
    """
    from PIL import ImageFont
    font = ImageFont.truetype(path, size=size)

    if weight == 400:
        return font, 0.0

    if _try_apply_variable_weight(font, weight):
        return font, 0.0

    if weight < 400:
        warnings.warn(
            f"字体不支持可变字重（wght 轴），weight={weight} 无法变细；"
            "已保持默认自重 400。",
            UserWarning, stacklevel=4,
        )
        return font, 0.0

    return font, _weight_to_synthetic_strength(weight)


def _render_span_for_mpl(span, dpi_scale: float):
    """将 Span 以 RGBA 像素数组渲染，用于 Matplotlib OffsetImage 嵌入。

    对以下场景激活：
    - 斜体（italic）：通过 PIL 仿射剪切实现真实倾斜
    - 可变字体非默认字重（weight != 400 且字体有 wght 轴）
    其余情况返回 None，由调用方回退到 TextArea+patheffects 路径。

    Returns
    -------
    (ndarray H×W×4, ascent_px, descent_px) 或 None（不适用时）
    """
    is_variable_weight = span.style.weight != 400
    if not (is_variable_weight or span.style.italic):
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
    except ImportError:
        return None

    eff_size_pt = round(span.size * span.style.script_ratio) if span.style.script else span.size
    render_size = max(1, round(eff_size_pt * dpi_scale))

    font = ImageFont.truetype(span.font._path, render_size)
    if is_variable_weight and not _try_apply_variable_weight(font, span.style.weight):
        if not span.style.italic:
            return None  # 静态字体，无法变细，且非斜体，回退到 TextArea（含警告）

    ascent, descent = font.getmetrics()
    try:
        raw_advance = int(font.getlength(span.text))
    except AttributeError:
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bb = dummy.textbbox((0, 0), span.text, font=font, anchor="ls")
        raw_advance = bb[2] - bb[0]

    if span.style.italic:
        raw_advance += int(span.style.italic_slant * (ascent + descent))

    total_w = max(4, raw_advance + 4)
    total_h = ascent + descent + 2
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    _draw_span_pil(img, ImageDraw.Draw(img), 0, ascent,
                   span, font, float(raw_advance), ascent, descent,
                   (0, 0, 0, 255), 0.0)
    return np.array(img), ascent, descent


def _to_rgba(color) -> tuple:
    """将任意 PIL 颜色值转为 RGBA 整数元组（用于 RGBA 临时画布）。"""
    if isinstance(color, (tuple, list)):
        c = tuple(int(v) for v in color)
        return c if len(c) == 4 else (*c[:3], 255)
    try:
        from PIL import ImageColor
        r, g, b = ImageColor.getrgb(color)
        return (r, g, b, 255)
    except Exception:
        return (0, 0, 0, 255)


def _draw_span_pil(img, draw, x: float, baseline_y: float,
                   span, font, advance: float,
                   ascent: int, descent: int, color,
                   synth_strength: float = 0.0) -> None:
    """将单个 Span 渲染到 PIL Image，应用全部样式效果。

    PIL 后端支持：伪粗体（多偏移重绘）、伪斜体（仿射剪切）、
    旋转（仿射变换）、下划线（单/双，可调粗细间距）、删除线。

    Parameters
    ----------
    img        : PIL Image，供粘贴临时画布用（需支持 paste/alpha_composite）。
    draw       : ImageDraw 对象，用于直接绘制及装饰线。
    x          : 当前光标水平坐标。
    baseline_y : 基线 y 坐标（已含 shift_y / script 偏移）。
    advance    : 该 Span 的排版步进宽度（已含粗/斜体附加量）。
    """
    from PIL import Image

    style   = span.style
    h       = ascent + descent
    total_w = max(8, int(advance) + 4)
    rgba_fill = _to_rgba(color)

    needs_temp = style.italic or synth_strength >= 0.9 or style.rotation != 0

    if needs_temp:
        from PIL import ImageDraw as _PD
        temp  = Image.new("RGBA", (total_w, h + 2), (0, 0, 0, 0))
        tdraw = _PD.Draw(temp)
        if synth_strength >= 0.9:
            for dx, dy in _bold_offsets(synth_strength):
                tdraw.text((dx, ascent + dy), span.text, font=font,
                           fill=rgba_fill, anchor="ls")
        else:
            tdraw.text((0, ascent), span.text, font=font,
                       fill=rgba_fill, anchor="ls")

        if style.italic:
            slant    = style.italic_slant
            _affine  = getattr(getattr(Image, "Transform",  Image), "AFFINE",  2)
            _bicubic = getattr(getattr(Image, "Resampling", Image), "BICUBIC", 3)
            _lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
            _nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST", 0)
            tw, th = temp.size
            # 2× 超采样再缩回：消除仿射插值模糊（transform 只支持 BICUBIC 及以下）
            big   = temp.resize((tw * 2, th * 2), _nearest)
            big   = big.transform(
                (tw * 2, th * 2), _affine,
                (1, slant, -slant * th * 2, 0, 1, 0),
                resample=_bicubic,
            )
            temp  = big.resize((tw, th), _lanczos)

        paste_x = int(x)
        paste_y = int(baseline_y - ascent)
        if style.rotation != 0:
            _lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
            orig_cx   = total_w / 2
            orig_cy   = (h + 2) / 2
            temp      = temp.rotate(style.rotation, expand=True, resample=_lanczos)
            new_w, new_h = temp.size
            paste_x = round(int(x) + orig_cx - new_w / 2)
            paste_y = round(int(baseline_y - ascent) + orig_cy - new_h / 2)

        alpha_mask = temp.split()[3]
        if img.mode == "RGBA":
            tmp_full = Image.new("RGBA", img.size, (0, 0, 0, 0))
            tmp_full.paste(temp, (paste_x, paste_y))
            img.alpha_composite(tmp_full)
        else:
            img.paste(temp.convert(img.mode), (paste_x, paste_y), alpha_mask)
    else:
        draw.text((x, baseline_y), span.text, font=font,
                  fill=color, anchor="ls")

    # 下划线（绘制在基线下方，不受斜体/旋转影响）
    if style.underline:
        lw   = max(1, style.underline_width)
        gap  = style.underline_gap
        y0   = int(baseline_y) + 2
        for i in range(max(1, style.underline_count)):
            top = y0 + i * (lw + gap)
            draw.rectangle([int(x), top, int(x + advance), top + lw - 1], fill=color)

    # 删除线（绘制在字形中部）
    if style.strikethrough:
        lw    = max(1, style.strikethrough_width)
        mid_y = int(baseline_y - ascent * 0.35)
        draw.rectangle([int(x), mid_y, int(x + advance), mid_y + lw - 1], fill=color)


# ─────────────────────────────────────────────────────────────────
#  Matplotlib 装饰辅助
# ─────────────────────────────────────────────────────────────────

def _register_mpl_decorations(ax, text_areas: list, spans) -> None:
    """注册 draw_event 回调，在 Span 绘制完成后叠加下划线 / 删除线。

    利用 AnnotationBbox 渲染后各 TextArea 已具备像素坐标的特性，
    直接通过 renderer.draw_path 在显示坐标系（IdentityTransform）
    中绘制填充矩形。对 PNG / SVG / PDF 等主流后端均有效。

    Note
    ----
    回调在每次 figure 重绘时触发，装饰始终与文本位置保持一致。
    """
    from matplotlib.path import Path as MplPath
    import matplotlib.transforms as _mtr

    fig = ax.get_figure()

    def _on_draw(event):
        renderer = getattr(event, "renderer", None)
        if renderer is None:
            return
        gc       = renderer.new_gc()
        gc.set_linewidth(0)
        identity = _mtr.IdentityTransform()
        black    = (0.0, 0.0, 0.0)

        for ta, span in zip(text_areas, spans):
            style = span.style
            if not (style.underline or style.strikethrough):
                continue
            try:
                bbox = ta.get_window_extent(renderer)
            except Exception:
                continue

            x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1

            def _rect(rx0, ry0, rx1, ry1):
                if rx1 <= rx0 or ry1 <= ry0:
                    return
                verts = [(rx0, ry0), (rx1, ry0), (rx1, ry1),
                         (rx0, ry1), (rx0, ry0)]
                codes = [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO,
                         MplPath.LINETO, MplPath.CLOSEPOLY]
                renderer.draw_path(gc, MplPath(verts, codes),
                                   identity, rgbFace=black)

            if style.strikethrough:
                lw  = max(1, style.strikethrough_width)
                mid = y0 + (y1 - y0) * 0.45
                _rect(x0, mid, x1, mid + lw)

            if style.underline:
                lw   = max(1, style.underline_width)
                base = y0 - 2
                for i in range(max(1, style.underline_count)):
                    ry1 = base - i * (lw + style.underline_gap)
                    _rect(x0, ry1 - lw, x1, ry1)

        gc.restore()

    fig.canvas.mpl_connect("draw_event", _on_draw)


# ─────────────────────────────────────────────────────────────────
#  核心类
# ─────────────────────────────────────────────────────────────────

class Font:
    """
    可调用字体对象。

    调用实例即可生成绑定了该字体的 :class:`Span` 文本片段::

        cn   = Font("宋体", size=9)
        en   = Font("Arial", size=10)
        line = cn("中文") + en(" English")

    Parameters
    ----------
    name_or_path : str
        字体名称（如 ``"宋体"``、``"Arial"``）或字体文件路径。
    size : int
        默认字号（磅），默认 ``12``。
    """

    def __init__(self, name_or_path: str, size: int = 12) -> None:
        self._path: str = _resolve(name_or_path)
        self.size: int = size
        self.name: str = name_or_path
        self._style: TextStyle = TextStyle()

    def __call__(self, text: str, size: Optional[int] = None) -> "Span":
        """生成绑定当前字体及样式的文本片段 Span。"""
        return Span(text, self, size if size is not None else self.size, self._style)

    def at(self, size: int) -> "Font":
        """
        返回相同字体但指定字号的新 Font 对象（不修改原对象）。

        Examples
        --------
        >>> cn.at(14)("大号标题")
        """
        f = Font.__new__(Font)
        f._path  = self._path
        f.name   = self.name
        f.size   = size
        f._style = self._style
        return f

    def _clone(self, **overrides) -> "Font":
        """返回复制了所有属性的新 Font，并应用 overrides 中的覆盖。"""
        f = Font.__new__(Font)
        f._path  = self._path
        f.name   = self.name
        f.size   = self.size
        f._style = self._style
        for k, v in overrides.items():
            object.__setattr__(f, k, v)
        return f

    def bold(self) -> "Font":
        """返回启用伪粗体的新 Font（原对象不变）。

        即使字体没有粗体字形，也能通过多次偏移重绘实现视觉加粗。
        等价于 ``.weight(700)``。

        Examples
        --------
        >>> cn.bold()("加粗文字")       # ✓ 两层括号：先 .bold() 得到 Font，再传文字
        >>> cn.bold().italic()("粗斜体")
        """
        return self._clone(_style=self._style.copy(weight=700))

    def b(self) -> "Font":
        """.bold() 的简写。"""
        return self.bold()

    def italic(self, slant: float = 0.25) -> "Font":
        """返回启用伪斜体的新 Font（原对象不变）。

        通过水平剪切变形实现斜体效果，即使字体无斜体字形。

        Parameters
        ----------
        slant : float
            倾斜量（水平剪切系数），推荐范围 0.15–0.40。

        Examples
        --------
        >>> cn.italic()("斜体文字")
        >>> cn.italic(0.3)("更斜")
        """
        return self._clone(_style=self._style.copy(
            italic=True, italic_slant=slant))

    def i(self, slant: float = 0.25) -> "Font":
        """.italic() 的简写。"""
        return self.italic(slant)

    def underline(self, width: int = 1, count: int = 1,
                  gap: int = 3) -> "Font":
        """返回启用下划线的新 Font（原对象不变）。

        Parameters
        ----------
        width : int
            线宽（像素）。
        count : int
            条数，1 = 单线，2 = 双线。
        gap : int
            双线之间的间距（像素）。

        Examples
        --------
        >>> cn.underline()("下划线")
        >>> cn.underline(width=2)("粗下划线")
        >>> cn.underline(count=2, gap=2)("双下划线")
        """
        return self._clone(_style=self._style.copy(
            underline=True, underline_width=width,
            underline_count=count, underline_gap=gap))

    def u(self, width: int = 1, count: int = 1, gap: int = 3) -> "Font":
        """.underline() 的简写。"""
        return self.underline(width=width, count=count, gap=gap)

    def strikethrough(self, width: int = 1) -> "Font":
        """返回启用删除线的新 Font（原对象不变）。

        Parameters
        ----------
        width : int
            线宽（像素）。

        Examples
        --------
        >>> cn.strikethrough()("删除线文字")
        >>> cn.strikethrough(2)("粗删除线")
        """
        return self._clone(_style=self._style.copy(
            strikethrough=True, strikethrough_width=width))

    def st(self, width: int = 1) -> "Font":
        """.strikethrough() 的简写。"""
        return self.strikethrough(width=width)

    def weight(self, w: float = 400) -> "Font":
        """返回设置字重的新 Font（原对象不变）。

        参数采用 CSS 风格范围 ``0~1000``：
        - ``400`` = 默认自重（normal）
        - ``700`` = 标准粗体（约等于 ``.bold()``）

        当前版本暂不支持真正"变细"，当 ``w < 400`` 时会回落到 400 并提示。

        Examples
        --------
        >>> cn.weight()("默认自重")
        >>> cn.weight(500)("中等偏粗")
        >>> cn.weight(700)("标准粗")
        """
        css_w = _coerce_css_weight(w, stacklevel=2)
        return self._clone(_style=self._style.copy(weight=css_w))

    def w(self, w: float = 400) -> "Font":
        """.weight() 的简写。"""
        return self.weight(w)

    def shift(self, x: float = 0.0, y: float = 0.0) -> "Font":
        """返回设置基线偏移的新 Font（原对象不变）。

        Parameters
        ----------
        x, y : float
            偏移量（排版点）。y 正方向为上，x 正方向为右。

        Examples
        --------
        >>> en.shift(y=2)("略微上移")
        """
        return self._clone(_style=self._style.copy(shift_x=x, shift_y=y))

    def offset(self, x: float = 0.0, y: float = 0.0) -> "Font":
        """.shift() 的语义别名。"""
        return self.shift(x=x, y=y)

    def sh(self, x: float = 0.0, y: float = 0.0) -> "Font":
        """.shift() 的简写。"""
        return self.shift(x=x, y=y)

    def off(self, x: float = 0.0, y: float = 0.0) -> "Font":
        """.offset() 的简写。"""
        return self.offset(x=x, y=y)

    def rotate(self, angle: float) -> "Font":
        """返回设置旋转角度的新 Font（原对象不变）。

        Parameters
        ----------
        angle : float
            旋转角度（度）。正方向逆时针。

        Examples
        --------
        >>> cn.rotate(15)("斜向文字")
        """
        return self._clone(_style=self._style.copy(rotation=angle))

    def r(self, angle: float) -> "Font":
        """.rotate() 的简写。"""
        return self.rotate(angle)

    def sup(self, ratio: float = 0.65) -> "Font":
        """返回上标样式的新 Font（原对象不变）。

        字号缩小为 ratio 倍并上移至上标位置。

        Examples
        --------
        >>> cn("x") + en.sup()("2")   # x²
        """
        return self._clone(_style=self._style.copy(script="sup", script_ratio=ratio))

    def sub(self, ratio: float = 0.65) -> "Font":
        """返回下标样式的新 Font（原对象不变）。

        字号缩小为 ratio 倍并下移至下标位置。

        Examples
        --------
        >>> cn("CO") + en.sub()("2")   # CO₂
        """
        return self._clone(_style=self._style.copy(script="sub", script_ratio=ratio))

    @staticmethod
    def list_fonts() -> list[str]:
        """列出系统字体目录中所有可用的字体文件名（已排序）。"""
        found: list[str] = []
        for d in _font_dirs():
            if d.exists():
                for f in d.rglob("*"):
                    if f.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                        found.append(f.name)
        return sorted(set(found))

    def __repr__(self) -> str:
        s = self._style
        parts = []
        if s.weight != 400: parts.append(f"weight={s.weight}")
        if s.italic:        parts.append(f"italic={s.italic_slant}")
        if s.underline:     parts.append(f"underline(×{s.underline_count},w={s.underline_width})")
        if s.strikethrough: parts.append(f"strikethrough(w={s.strikethrough_width})")
        if s.script:        parts.append(f"{s.script}(×{s.script_ratio})")
        if s.shift_x or s.shift_y: parts.append(f"shift({s.shift_x},{s.shift_y})")
        if s.rotation:      parts.append(f"rotate({s.rotation}°)")
        suffix = f", {', '.join(parts)}" if parts else ""
        return f"Font({self.name!r}, size={self.size}{suffix})"


class Span:
    """
    单一字体的文本片段，由 :class:`Font` 调用产生。

    两个 Span 相加得到 :class:`TextLine`::

        line = cn("中文") + en(" English")
    """

    __slots__ = ("text", "font", "size", "style")

    def __init__(self, text: str, font: Font, size: int,
                 style: Optional[TextStyle] = None) -> None:
        self.text:  str       = text
        self.font:  Font      = font
        self.size:  int       = size
        self.style: TextStyle = style if style is not None else TextStyle()

    def __add__(self, other: Union["Span", "TextLine"]) -> "TextLine":
        if isinstance(other, Span):
            return TextLine([self, other])
        if isinstance(other, TextLine):
            return TextLine([self] + other._spans)
        return NotImplemented

    def _as_line(self) -> "TextLine":
        return TextLine([self])

    def draw(self, target, x: float = 0.5, y: float = 0.5, **kwargs):
        """渲染到 Matplotlib Axes 或 PIL Image（自动识别）。"""
        return self._as_line().draw(target, x, y, **kwargs)

    def render(self, **kwargs):
        """生成 PIL Image。"""
        return self._as_line().render(**kwargs)

    def preview(self, **kwargs):
        """弹窗预览。"""
        return self._as_line().preview(**kwargs)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Span({self.font.name!r}, {self.text!r}, size={self.size})"

    # ── Span 级样式方法（返回新 Span，原对象不变）──────────────────

    def _with_style(self, **kw) -> "Span":
        """返回应用了样式修改的新 Span（原对象不变）。"""
        return Span(self.text, self.font, self.size, self.style.copy(**kw))

    def bold(self) -> "Span":
        """Span 级粗体（等价于 .weight(700)）。"""
        return self._with_style(weight=700)

    def b(self) -> "Span":
        """.bold() 的简写。"""
        return self.bold()

    def weight(self, w: float = 400) -> "Span":
        """Span 级字重（0~1000，默认 400，700=标准粗）。"""
        css_w = _coerce_css_weight(w, stacklevel=2)
        return self._with_style(weight=css_w)

    def w(self, w: float = 400) -> "Span":
        """.weight() 的简写。"""
        return self.weight(w)

    def italic(self, slant: float = 0.25) -> "Span":
        """Span 级伪斜体。"""
        return self._with_style(italic=True, italic_slant=slant)

    def i(self, slant: float = 0.25) -> "Span":
        """.italic() 的简写。"""
        return self.italic(slant)

    def underline(self, width: int = 1, count: int = 1,
                  gap: int = 3) -> "Span":
        """Span 级下划线。"""
        return self._with_style(underline=True, underline_width=width,
                                underline_count=count, underline_gap=gap)

    def u(self, width: int = 1, count: int = 1, gap: int = 3) -> "Span":
        """.underline() 的简写。"""
        return self.underline(width=width, count=count, gap=gap)

    def strikethrough(self, width: int = 1) -> "Span":
        """Span 级删除线。"""
        return self._with_style(strikethrough=True, strikethrough_width=width)

    def st(self, width: int = 1) -> "Span":
        """.strikethrough() 的简写。"""
        return self.strikethrough(width=width)

    def shift(self, x: float = 0.0, y: float = 0.0) -> "Span":
        """Span 级位移（排版点，y 正向为上）。"""
        return self._with_style(shift_x=x, shift_y=y)

    def offset(self, x: float = 0.0, y: float = 0.0) -> "Span":
        """.shift() 的语义别名。"""
        return self.shift(x=x, y=y)

    def sh(self, x: float = 0.0, y: float = 0.0) -> "Span":
        """.shift() 的简写。"""
        return self.shift(x=x, y=y)

    def off(self, x: float = 0.0, y: float = 0.0) -> "Span":
        """.offset() 的简写。"""
        return self.offset(x=x, y=y)

    def rotate(self, angle: float) -> "Span":
        """Span 级旋转（度，正方向逆时针）。"""
        return self._with_style(rotation=angle)

    def r(self, angle: float) -> "Span":
        """.rotate() 的简写。"""
        return self.rotate(angle)

    def sup(self, ratio: float = 0.65) -> "Span":
        """Span 级上标（字号 × ratio，上移）。"""
        return self._with_style(script="sup", script_ratio=ratio)

    def sub(self, ratio: float = 0.65) -> "Span":
        """Span 级下标（字号 × ratio，下移）。"""
        return self._with_style(script="sub", script_ratio=ratio)


class TextLine:
    """
    多字体文本行，由若干 :class:`Span` 拼接而成，是最终的渲染单元。

    Examples
    --------
    ::

        line = cn("实验") + en(" Results ") + bold("重要")

        # 直接渲染
        line.draw(ax, 0.5, 0.5)          # Matplotlib
        line.draw(img, 10, 20)           # PIL Image
        line.render().save("out.png")
        line.preview()

        # 套进 bind() 后的原生 Axes 方法
        ax = bind(ax)
        ax.set_title(line)
        ax.set_xlabel(cn("X轴") + en(" X-axis"))
    """

    def __init__(self, spans: list[Span]) -> None:
        self._spans: list[Span] = list(spans)

    # ── 拼接 ────────────────────────────────────────────────────

    def __add__(self, other: Union[Span, "TextLine"]) -> "TextLine":
        if isinstance(other, Span):
            return TextLine(self._spans + [other])
        if isinstance(other, TextLine):
            return TextLine(self._spans + other._spans)
        return NotImplemented

    def __radd__(self, other: Union[Span, "TextLine"]) -> "TextLine":
        if isinstance(other, Span):
            return TextLine([other] + self._spans)
        if isinstance(other, TextLine):
            return TextLine(other._spans + self._spans)
        return NotImplemented

    # ── 属性 ────────────────────────────────────────────────────

    @property
    def text(self) -> str:
        """所有片段拼接的纯文本。"""
        return "".join(s.text for s in self._spans)

    def __len__(self) -> int:
        return len(self._spans)

    def __iter__(self):
        return iter(self._spans)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        parts = " + ".join(f"{s.font.name!r}({s.text!r})" for s in self._spans)
        return f"TextLine({parts})"

    # ── 智能渲染入口 ─────────────────────────────────────────────

    def draw(self, target, x: float = 0.5, y: float = 0.5, **kwargs):
        """
        智能渲染：自动识别 Matplotlib Axes 或 PIL Image。

        Parameters
        ----------
        target : matplotlib.axes.Axes 或 PIL.Image.Image
        x, y : float
            Matplotlib 下为轴比例坐标（0~1）；PIL 下为像素坐标。
        **kwargs
            传递给后端的额外参数。
        """
        _AxesType = _try_mpl_axes()
        if _AxesType and isinstance(target, _AxesType):
            return self.draw_mpl(target, x, y, **kwargs)

        _ImageType = _try_pil_image()
        if _ImageType and isinstance(target, _ImageType):
            return self.draw_pil(target, int(x), int(y), **kwargs)

        # 兼容 BoundAxes
        if isinstance(target, BoundAxes):
            return self.draw_mpl(target._ax, x, y, **kwargs)

        raise TypeError(
            f"不支持的渲染目标类型：{type(target).__name__}\n"
            "  支持：matplotlib.axes.Axes / PIL.Image.Image / BoundAxes"
        )

    # ── Matplotlib 后端 ─────────────────────────────────────────

    def draw_mpl(
        self,
        ax,
        x: float = 0.5,
        y: float = 0.5,
        coords: str = "axes fraction",
        orientation: str = "horizontal",
        rotation: int = 0,
        pad: int = 0,
        sep: int = 0,
    ):
        """
        渲染到 Matplotlib Axes（使用 AnnotationBbox）。

        Parameters
        ----------
        ax : matplotlib.axes.Axes
        x, y : float
            坐标，由 ``coords`` 参数决定坐标系。
        coords : str
            ``'axes fraction'``（默认）、``'data'``、``'figure fraction'``
            或任意 matplotlib Transform 对象。
        orientation : str
            ``'horizontal'``（横排）或 ``'vertical'``（竖排）。
        rotation : int
            整体文字旋转角度（度）；可被 Span 级 .rotate() 叠加。
        pad : int
            整体内边距（像素）。
        sep : int
            各片段间距（排版点）。
        """
        from matplotlib.font_manager import FontProperties
        from matplotlib.offsetbox import HPacker, VPacker, TextArea, AnnotationBbox

        if not self._spans:
            return None

        def _make_ta(span):
            eff_size = round(span.size * span.style.script_ratio) if span.style.script else span.size
            fp = FontProperties(fname=span.font._path, size=eff_size)
            if span.style.italic:
                fp.set_style("italic")
            textprops = dict(fontproperties=fp)
            total_rot = rotation + span.style.rotation
            if total_rot:
                textprops["rotation"] = total_rot
            ta = TextArea(span.text, textprops=textprops)
            # 伪字重：用 patheffects.Stroke 描边笔画，对任何无粗体字形的字体均有效
            # fp.set_weight() 只能选字体变体，宋体/楷体/仿宋等无粗体字形时无效。
            # linewidth 按字号比例缩放（约为字号的 1/14），避免在高 DPI 下晕边。
            synth_strength = _weight_to_synthetic_strength(span.style.weight)
            if synth_strength >= 0.9:
                try:
                    import matplotlib.patheffects as _pe
                    lw = (eff_size / 14.0) * synth_strength
                    ta._text.set_path_effects([
                        _pe.Stroke(linewidth=lw),
                        _pe.Normal(),
                    ])
                except Exception:
                    pass
            return ta

        # ── 竖排：VPacker ────────────────────────────────────────
        if orientation == "vertical":
            children = [_make_ta(s) for s in self._spans]
            packer = VPacker(children=children, align="center", pad=pad, sep=sep)
            ab = AnnotationBbox(packer, (x, y), xycoords=coords, frameon=False,
                                pad=pad, box_alignment=(0.5, 0.5))
            ax.add_artist(ab)
            if any(s.style.underline or s.style.strikethrough for s in self._spans):
                _register_mpl_decorations(ax, children, self._spans)
            return ab

        # ── 横排：若任一 span 有 y 偏移/上下标/非默认字重，改用逐 span 独立定位 ──
        needs_individual = (
            coords == "axes fraction"
            and any(s.style.shift_y != 0 or s.style.shift_x != 0 or s.style.script
                    or s.style.weight != 400 or s.style.italic
                    for s in self._spans)
        )
        if needs_individual:
            try:
                from PIL import ImageFont, Image, ImageDraw
                import numpy as np
            except ImportError:
                needs_individual = False

        if needs_individual:
            fig     = ax.get_figure()
            ax_pos  = ax.get_position()
            ax_w_in = ax_pos.width  * fig.get_figwidth()
            ax_h_in = ax_pos.height * fig.get_figheight()

            metrics  = self._pil_metrics()
            dummy    = ImageDraw.Draw(Image.new("RGB", (1, 1)))

            # 先算总宽，居中
            total_pts = sum(m[1] for m in metrics) + sep * max(0, len(metrics) - 1)
            start_x   = x - (total_pts / 2) / (72 * ax_w_in)

            text_areas, artists, cursor_pts = [], [], 0.0
            # 以高固定 DPI 渲染 PIL 图像，避免存图时因 dpi_cor 放大而模糊
            _PIL_RENDER_DPI = 600
            dpi_scale = _PIL_RENDER_DPI / 72.0
            pil_zoom  = fig.dpi / _PIL_RENDER_DPI
            for (font, advance, ascent, descent, _synth), span in zip(metrics, self._spans):
                span_x = start_x + (cursor_pts + span.style.shift_x) / (72 * ax_w_in)

                eff_size = round(span.size * span.style.script_ratio) if span.style.script else span.size
                script_y = 0.0
                if span.style.script == "sup":
                    script_y = (span.size - eff_size) * 0.9
                elif span.style.script == "sub":
                    script_y = -(eff_size * 0.25)
                span_y = y + (span.style.shift_y + script_y) / (72 * ax_h_in)

                # 变细字重：尝试可变字体 PIL 光栅化嵌入
                pil_result = _render_span_for_mpl(span, dpi_scale)
                if pil_result is not None:
                    from matplotlib.offsetbox import OffsetImage
                    arr, img_asc, img_desc = pil_result
                    oi = OffsetImage(arr, zoom=pil_zoom)
                    bf = img_desc / max(1, img_asc + img_desc)
                    ab = AnnotationBbox(oi, (span_x, span_y), xycoords=coords,
                                        frameon=False, pad=0, box_alignment=(0.0, bf))
                    ax.add_artist(ab)
                    artists.append(ab)
                    text_areas.append(oi)
                    cursor_pts += advance + sep
                    continue

                ta = _make_ta(span)
                text_areas.append(ta)

                # 逐 span 基线分数
                try:
                    _, fd = font.getmetrics()
                    lp_bb = dummy.textbbox((0, 0), "lp", font=font, anchor="ls")
                    lp_h  = -lp_bb[1]
                    t_bb  = dummy.textbbox((0, 0), span.text, font=font, anchor="ls")
                    g_asc = max(0, -t_bb[1])
                    asc   = max(lp_h, g_asc)
                    tot   = fd + asc
                    bf    = fd / tot if tot > 0 else 0.5
                except Exception:
                    bf = 0.5

                ab = AnnotationBbox(ta, (span_x, span_y), xycoords=coords,
                                    frameon=False, pad=0, box_alignment=(0.0, bf))
                ax.add_artist(ab)
                artists.append(ab)
                cursor_pts += advance + sep

            if any(s.style.underline or s.style.strikethrough for s in self._spans):
                _register_mpl_decorations(ax, text_areas, self._spans)
            return artists[0] if artists else None

        # ── 横排默认：HPacker ─────────────────────────────────────
        children = [_make_ta(s) for s in self._spans]
        packer = HPacker(children=children, align="baseline", pad=pad, sep=sep)
        box_alignment = (0.5, _mpl_baseline_fraction(self._spans, ax))
        ab = AnnotationBbox(packer, (x, y), xycoords=coords, frameon=False, pad=pad,
                            box_alignment=box_alignment)
        ax.add_artist(ab)
        if any(s.style.underline or s.style.strikethrough for s in self._spans):
            _register_mpl_decorations(ax, children, self._spans)
        return ab

    # ── Matplotlib 快捷方法（直接调用，不需要 bind）──────────────

    def title(self, ax, x: float = 0.5, y: float = 1.02,
              loc: str = "center", **kwargs):
        """添加为图表标题（居中，位于坐标轴上方）。"""
        locs = {"left": 0.0, "center": 0.5, "right": 1.0}
        x = locs.get(loc, x)
        return self.draw_mpl(ax, x, y, **kwargs)

    def xlabel(self, ax, x: float = 0.5, y: float = -0.12, **kwargs):
        """添加为 X 轴标签（居中，位于坐标轴下方）。"""
        return self.draw_mpl(ax, x, y, **kwargs)

    def ylabel(self, ax, x: float = -0.15, y: float = 0.5,
               rotation: int = 90, **kwargs):
        """添加为 Y 轴标签（位于坐标轴左侧，旋转 90°）。"""
        return self.draw_mpl(ax, x, y, rotation=rotation, **kwargs)

    # ── PIL 后端 ────────────────────────────────────────────────

    def _pil_metrics(self):
        """
        计算每个 Span 的 PIL 字体排版度量值。

        Returns
        -------
        list of (ImageFont, advance_px, ascent_px, descent_px, synth_strength)
            - advance_px：字符串的排版步进宽度（用 getlength，比 bbox 更精确）
            - ascent_px / descent_px：字体的上升沿/下降沿高度
            - synth_strength：伪粗体强度（0=无需伪粗体，可变字体已处理或不需要）
        """
        from PIL import Image, ImageDraw
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        result = []
        for span in self._spans:
            eff_size = max(9, round(span.size * span.style.script_ratio)) if span.style.script else span.size
            font, synth_strength = _load_pil_font_with_weight(
                span.font._path, eff_size, span.style.weight
            )
            ascent, descent = font.getmetrics()
            try:
                advance = font.getlength(span.text)   # Pillow 9.2+，更精确
            except AttributeError:
                bbox = dummy.textbbox((0, 0), span.text, font=font, anchor="ls")
                advance = float(bbox[2] - bbox[0])
            # 为粗体预留横向偏移量
            if synth_strength >= 0.9:
                advance += float(max(1, int(round(synth_strength))))
            # 为斜体预留顶部右倾宽度（防止裁切）
            if span.style.italic:
                advance += span.style.italic_slant * (ascent + descent)
            result.append((font, float(advance), ascent, descent, synth_strength))
        return result

    def draw_pil(
        self,
        img,
        x: int = 0,
        y: int = 0,
        color: Union[Tuple, str] = (0, 0, 0),
        spacing: int = 0,
    ) -> None:
        """
        渲染到 PIL Image（横排，基线对齐）。

        使用 ``anchor='ls'``（left-baseline）确保不同字号的片段基线水平对齐，
        而非顶部对齐。y 为文字块顶边像素坐标，基线由内部最大上升沿自动推算。
        """
        try:
            from PIL import ImageDraw, ImageFont
        except ImportError:
            raise ImportError("PIL 渲染需要安装 Pillow：pip install Pillow")

        metrics = self._pil_metrics()
        if not metrics:
            return

        max_ascent = max(m[2] for m in metrics)
        baseline_y = y + max_ascent   # 顶边 → 基线

        draw = ImageDraw.Draw(img)
        cursor = float(x)
        for (font, advance, ascent, descent, synth_strength), span in zip(metrics, self._spans):
            eff_x = cursor + span.style.shift_x
            eff_y = baseline_y - span.style.shift_y   # pt = px at 72 DPI；正向上 = PIL y 减小
            if span.style.script:
                eff_size = round(span.size * span.style.script_ratio)
                if span.style.script == "sup":
                    eff_y -= (span.size - eff_size) * 0.9   # 上移
                elif span.style.script == "sub":
                    eff_y += eff_size * 0.25                 # 下移
            _draw_span_pil(img, draw, eff_x, eff_y,
                           span, font, advance, ascent, descent, color, synth_strength)
            cursor += advance + spacing

    def render(
        self,
        bg: Union[str, Tuple] = "white",
        padding: int = 6,
        color: Union[Tuple, str] = (0, 0, 0),
        spacing: int = 0,
    ):
        """
        将文本行渲染为 PIL Image 并返回（自动计算合适尺寸）。

        图像高度基于字体的真实上升沿+下降沿，宽度基于排版步进值，
        保证不裁切任何字形。
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("PIL 渲染需要安装 Pillow：pip install Pillow")

        metrics = self._pil_metrics()
        if not metrics:
            return Image.new("RGB", (padding * 2, padding * 2), bg)

        total_w    = sum(m[1] for m in metrics) + spacing * max(0, len(metrics) - 1)
        max_ascent  = max(m[2] for m in metrics)
        max_descent = max(m[3] for m in metrics)
        # 下标可能超出字体下降沿，额外预留空间
        for span, m in zip(self._spans, metrics):
            if span.style.script == "sub":
                eff_size = round(span.size * span.style.script_ratio)
                max_descent = max(max_descent, m[3] + int(eff_size * 0.25) + 2)

        img = Image.new(
            "RGB",
            (int(total_w) + padding * 2, max_ascent + max_descent + padding * 2),
            bg,
        )
        self.draw_pil(img, padding, padding, color=color, spacing=spacing)
        return img

    def preview(self, figsize: Tuple[float, float] = (8, 1.5)) -> None:
        """弹出 Matplotlib 窗口预览文本行。"""
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_axis_off()
        self.draw_mpl(ax, 0.5, 0.5)
        ax.set_title(repr(self), fontsize=7, color="gray")
        plt.tight_layout()
        plt.show()


# ─────────────────────────────────────────────────────────────────
#  bind(ax) — Axes 代理，原生函数直接接受 TextLine
# ─────────────────────────────────────────────────────────────────

class BoundAxes:
    """
    Matplotlib Axes 的薄代理层。

    由 :func:`bind` 创建。拦截 ``set_title``、``set_xlabel``、
    ``set_ylabel``、``text`` 四个方法，使其能直接接受 :class:`TextLine`
    或 :class:`Span` 对象；传入普通字符串时行为与原生完全相同。

    除上述四个方法外，所有属性和方法均透明代理到底层 Axes。

    Examples
    --------
    ::

        ax = bind(ax)
        ax.set_title(cn("实验结果") + en(" Results"))
        ax.set_xlabel(cn("X轴") + en(" X-axis"))
        ax.set_ylabel(cn("Y轴") + en(" Y-axis"))
        ax.text(0.5, 0.5, cn("标注") + en(" note"),
                transform=ax.transAxes)
        ax.plot(x, y)   # 非文本方法照常工作
    """

    def __init__(self, ax) -> None:
        # 直接写入 __dict__ 避免触发自定义 __setattr__
        object.__setattr__(self, "_ax", ax)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_ax"), name)

    def __setattr__(self, name: str, value) -> None:
        if name == "_ax":
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_ax"), name, value)

    def __dir__(self):
        return dir(object.__getattribute__(self, "_ax"))

    def __repr__(self) -> str:
        return f"BoundAxes({object.__getattribute__(self, '_ax')!r})"

    # ── 拦截 set_title ───────────────────────────────────────────

    def set_title(
        self,
        label,
        loc: str = "center",
        xy: Optional[Tuple[float, float]] = None,
        pad: int = 6,
        sep: int = 0,
        orientation: str = "horizontal",
        **kwargs,
    ):
        """
        支持 TextLine/Span；普通字符串透传给原生 set_title。

        Extra Parameters（仅在 label 为 TextLine/Span 时生效）
        --------------------------------------------------------
        xy : (float, float), optional
            自定义位置（axes fraction），默认按 loc 参数自动计算。
        pad : int
            内边距（像素）。
        sep : int
            片段间距（像素）。
        orientation : str
            ``'horizontal'`` 或 ``'vertical'``。
        """
        ax = object.__getattribute__(self, "_ax")
        if isinstance(label, (TextLine, Span)):
            line = label if isinstance(label, TextLine) else label._as_line()
            locs = {"left": 0.0, "center": 0.5, "right": 1.0}
            x, y = xy if xy else (locs.get(loc, 0.5), 1.02)
            return line.draw_mpl(ax, x, y, coords="axes fraction",
                                 pad=pad, sep=sep, orientation=orientation)
        return ax.set_title(label, loc=loc, **kwargs)

    # ── 拦截 set_xlabel ──────────────────────────────────────────

    def set_xlabel(
        self,
        label,
        xy: Optional[Tuple[float, float]] = None,
        pad: int = 6,
        sep: int = 0,
        **kwargs,
    ):
        """支持 TextLine/Span；普通字符串透传给原生 set_xlabel。"""
        ax = object.__getattribute__(self, "_ax")
        if isinstance(label, (TextLine, Span)):
            line = label if isinstance(label, TextLine) else label._as_line()
            x, y = xy if xy else (0.5, -0.12)
            return line.draw_mpl(ax, x, y, coords="axes fraction",
                                 pad=pad, sep=sep)
        return ax.set_xlabel(label, **kwargs)

    # ── 拦截 set_ylabel ──────────────────────────────────────────

    def set_ylabel(
        self,
        label,
        xy: Optional[Tuple[float, float]] = None,
        rotation: int = 90,
        pad: int = 6,
        sep: int = 0,
        **kwargs,
    ):
        """支持 TextLine/Span；普通字符串透传给原生 set_ylabel。"""
        ax = object.__getattribute__(self, "_ax")
        if isinstance(label, (TextLine, Span)):
            line = label if isinstance(label, TextLine) else label._as_line()
            x, y = xy if xy else (-0.15, 0.5)
            return line.draw_mpl(ax, x, y, coords="axes fraction",
                                 rotation=rotation, pad=pad, sep=sep)
        return ax.set_ylabel(label, **kwargs)

    # ── 拦截 text ────────────────────────────────────────────────

    def text(
        self,
        x: float,
        y: float,
        s,
        transform=None,
        rotation: int = 0,
        pad: int = 0,
        sep: int = 0,
        orientation: str = "horizontal",
        **kwargs,
    ):
        """
        支持 TextLine/Span；普通字符串透传给原生 text。

        坐标系：
        - 传入 TextLine/Span 时默认使用轴比例坐标（``'axes fraction'``）
        - 传入 ``transform=ax.transAxes`` 则显式使用轴比例坐标
        - 传入 ``transform=fig.transFigure`` 则使用图比例坐标
        - 传入 ``transform=ax.transData`` 则使用数据坐标
        - 普通字符串默认行为与原生 text 相同（数据坐标）
        """
        ax = object.__getattribute__(self, "_ax")
        if isinstance(s, (TextLine, Span)):
            line = s if isinstance(s, TextLine) else s._as_line()

            if transform is None:
                coords: object = "axes fraction"
            elif transform is ax.transAxes:
                coords = "axes fraction"
            elif transform is ax.get_figure().transFigure:
                coords = "figure fraction"
            else:
                coords = transform  # 直接传入 Transform 对象

            return line.draw_mpl(ax, x, y, coords=coords, rotation=rotation,
                                 pad=pad, sep=sep, orientation=orientation)
        return ax.text(x, y, s, transform=transform, **kwargs)


def bind(ax) -> BoundAxes:
    """
    将 Matplotlib Axes 包装为 :class:`BoundAxes`，
    使 ``set_title``、``set_xlabel``、``set_ylabel``、``text``
    能直接接受 :class:`TextLine` 或 :class:`Span`。

    其余所有方法与属性均透明代理，行为完全不变。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        要包装的坐标轴对象。

    Returns
    -------
    BoundAxes

    Examples
    --------
    ::

        fig, ax = plt.subplots()
        ax = bind(ax)

        cn = Font("宋体", size=9)
        en = Font("Arial", size=10)

        ax.set_title(cn("实验结果") + en(" Results"))
        ax.set_xlabel(cn("X轴") + en(" X-axis"))
        ax.set_ylabel(cn("Y轴") + en(" Y-axis"))
        ax.text(0.5, 0.5, cn("标注") + en(" note"), transform=ax.transAxes)
        ax.plot([1, 2, 3], [1, 4, 9])   # 非文本调用照常工作
    """
    return BoundAxes(ax)


# ─────────────────────────────────────────────────────────────────
#  辅助：基线锚点计算（修正 AnnotationBbox 下沉问题）
# ─────────────────────────────────────────────────────────────────

def _mpl_baseline_fraction(spans: list, ax) -> float:
    """
    计算 HPacker 包围盒中基线所在的纵向比例（从底部算起），
    供 ``AnnotationBbox(box_alignment=(0.5, fraction))`` 使用。

    原理
    ----
    Matplotlib 原生 ``ax.text(x, y, text)`` 默认 ``va='baseline'``，
    即文字基线位于 y。但 ``AnnotationBbox`` 默认以包围盒中心锚定
    （``box_alignment=(0.5, 0.5)``），导致基线偏低，英文短字母（如"mm"）视觉上比原生 fallback 下沉更多。

    本函数用 PIL 字体度量近似 Matplotlib TextArea 的基线位置：

    * ``yd_max``    ← 各 Span 字体 descent（下伸量）取最大值，换算至图形 DPI
    * ``asc_max``   ← 各 Span 取 max(lp字形上伸, 实际文字上伸)，换算至图形 DPI
    * ``fraction``  = yd_max / (yd_max + asc_max)

    和原生比对，在 100 DPI 下误差 < 0.02px，可以实现像素级基线对齐。
    如果 PIL 不可用则回退到 0.5（居中）。
    """
    try:
        from PIL import ImageFont, Image, ImageDraw
    except ImportError:
        return 0.5

    try:
        scale = ax.get_figure().dpi / 72.0
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        yd_vals: list[float] = []
        asc_vals: list[float] = []
        for span in spans:
            eff_size = round(span.size * span.style.script_ratio) if span.style.script else span.size
            f = ImageFont.truetype(span.font._path, size=eff_size)
            _, font_descent = f.getmetrics()

            # lp 字形高度近似 TextArea 的 h_-d_（参考上伸量）
            lp_bbox = dummy.textbbox((0, 0), "lp", font=f, anchor="ls")
            lp_cap_h = -lp_bbox[1]                     # "l" 字形上伸

            # 实际文本字形的上伸量
            text_bbox = dummy.textbbox((0, 0), span.text, font=f, anchor="ls")
            glyph_asc = max(0, -text_bbox[1])

            yd_vals.append(font_descent * scale)
            asc_vals.append(max(lp_cap_h, glyph_asc) * scale)

        yd_max = max(yd_vals)
        asc_max = max(asc_vals)
        total = yd_max + asc_max
        return yd_max / total if total > 0 else 0.5
    except Exception:
        return 0.5


# ─────────────────────────────────────────────────────────────────
#  辅助：惰性导入
# ─────────────────────────────────────────────────────────────────

def _try_mpl_axes():
    try:
        from matplotlib.axes import Axes
        return Axes
    except ImportError:
        return None


def _try_pil_image():
    try:
        from PIL import Image
        return Image.Image
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────
#  AutoFont — 自动检测中英文字符并切换字体
# ─────────────────────────────────────────────────────────────────

_CN_RE = re.compile(
    r'[\u4e00-\u9fff'
    r'\u3400-\u4dbf'
    r'\u3000-\u303f'
    r'\uff00-\uffef]+'
)


class AutoFont:
    """
    可选辅助类：自动检测中英文字符并切换字体，生成 TextLine。

    Examples
    --------
    ::

        from typoem import Font, AutoFont

        cn   = Font("宋体", size=9)
        en   = Font("Arial", size=10)
        auto = AutoFont(cn, en)

        line = auto("中英文自动 Auto Mix 混排")
        line.preview()
    """

    def __init__(self, cn_font: "Union[Font, str]", en_font: "Union[Font, str]",
                 size: int = 12) -> None:
        self.cn = cn_font if isinstance(cn_font, Font) else Font(cn_font, size)
        self.en = en_font if isinstance(en_font, Font) else Font(en_font, size)

    def __call__(self, text: str) -> TextLine:
        """将文本按中英文分段，返回 TextLine。"""
        spans: list[Span] = []
        prev = 0
        for m in _CN_RE.finditer(text):
            if m.start() > prev:
                spans.append(self.en(text[prev:m.start()]))
            spans.append(self.cn(m.group()))
            prev = m.end()
        if prev < len(text):
            spans.append(self.en(text[prev:]))

        spans = [s for s in spans if s.text]
        return TextLine(spans)

    def __repr__(self) -> str:
        return f"AutoFont(cn={self.cn}, en={self.en})"


# ─────────────────────────────────────────────────────────────────

def _print_help() -> None:
    print(
        "typoem — 通用多字体混排引擎\n"
        "\n"
        "基本用法：\n"
        "  from typoem import Font, bind\n"
        "\n"
        "  cn   = Font('宋体',   size=9)\n"
        "  en   = Font('Arial',  size=10)\n"
        "  bold = Font('黑体',   size=11)\n"
        "\n"
        "  # 拼接片段\n"
        "  line = cn('实验结果') + en(' Results ') + bold('重要')\n"
        "\n"
        "  # 方式一：直接渲染\n"
        "  line.draw(ax, 0.5, 0.5)        # Matplotlib（自动识别）\n"
        "  line.draw(img, 10, 20)         # PIL Image（自动识别）\n"
        "  line.render().save('out.png')\n"
        "  line.preview()\n"
        "\n"
        "  # 方式二：bind 套进原生函数\n"
        "  ax = bind(ax)\n"
        "  ax.set_title(cn('实验结果') + en(' Results'))\n"
        "  ax.set_xlabel(cn('X轴') + en(' X-axis'))\n"
        "  ax.set_ylabel(cn('Y轴') + en(' Y-axis'))\n"
        "  ax.text(0.5, 0.5, cn('标注') + en(' note'), transform=ax.transAxes)\n"
        "\n"
        "  # 临时换字号\n"
        "  cn.at(14)('大标题') + en.at(12)(' Title')\n"
        "\n"
        "  # 自动中英文检测\n"
        "  from typoem import AutoFont\n"
        "  auto = AutoFont(cn, en)\n"
        "  auto('中英文 Auto Mix').preview()\n"
        "\n"
        "  # 查看系统字体\n"
        "  print(Font.list_fonts())\n"
    )


def main() -> None:
    import argparse
    import sys
    parser = argparse.ArgumentParser(prog="typoem", add_help=False)
    parser.add_argument("-V", "--version", action="version",
                        version=f"typoem {__version__}")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()
    if args.help or len(sys.argv) == 1:
        _print_help()


if __name__ == "__main__":
    main()
