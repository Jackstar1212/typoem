# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import platform
import re
from pathlib import Path
from typing import Optional, Tuple, Union


# ─────────────────────────────────────────────────────────────────
#  字体名称 → 文件名候选映射
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

    def __call__(self, text: str, size: Optional[int] = None) -> "Span":
        """生成绑定当前字体的文本片段 Span。"""
        return Span(text, self, size if size is not None else self.size)

    def at(self, size: int) -> "Font":
        """
        返回相同字体但指定字号的新 Font 对象（不修改原对象）。

        Examples
        --------
        >>> cn.at(14)("大号标题")
        """
        f = Font.__new__(Font)
        f._path = self._path
        f.name  = self.name
        f.size  = size
        return f

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
        return f"Font({self.name!r}, size={self.size})"


class Span:
    """
    单一字体的文本片段，由 :class:`Font` 调用产生。

    两个 Span 相加得到 :class:`TextLine`::

        line = cn("中文") + en(" English")
    """

    __slots__ = ("text", "font", "size")

    def __init__(self, text: str, font: Font, size: int) -> None:
        self.text: str  = text
        self.font: Font = font
        self.size: int  = size

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
        sep: int = 1,
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
            文字旋转角度（度）。
        pad : int
            整体内边距（像素）。
        sep : int
            各片段间距（像素）。
        """
        from matplotlib.font_manager import FontProperties
        from matplotlib.offsetbox import HPacker, VPacker, TextArea, AnnotationBbox

        children = []
        for span in self._spans:
            fp = FontProperties(fname=span.font._path, size=span.size)
            ta = TextArea(
                span.text,
                textprops=dict(fontproperties=fp, rotation=rotation),
            )
            children.append(ta)

        if not children:
            return None

        if orientation == "vertical":
            packer = VPacker(children=children, align="center", pad=pad, sep=sep)
        else:
            packer = HPacker(children=children, align="baseline", pad=pad, sep=sep)

        ab = AnnotationBbox(packer, (x, y), xycoords=coords, frameon=False, pad=pad)
        ax.add_artist(ab)
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
        list of (ImageFont, advance_px, ascent_px, descent_px)
            - advance_px：字符串的排版步进宽度（用 getlength，比 bbox 更精确）
            - ascent_px / descent_px：字体的上升沿/下降沿高度
        """
        from PIL import ImageFont, Image, ImageDraw
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        result = []
        for span in self._spans:
            font = ImageFont.truetype(span.font._path, size=span.size)
            ascent, descent = font.getmetrics()
            try:
                advance = font.getlength(span.text)   # Pillow 9.2+，更精确
            except AttributeError:
                bbox = dummy.textbbox((0, 0), span.text, font=font, anchor="ls")
                advance = float(bbox[2] - bbox[0])
            result.append((font, float(advance), ascent, descent))
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
        for (font, advance, ascent, descent), span in zip(metrics, self._spans):
            draw.text((cursor, baseline_y), span.text, font=font,
                      fill=color, anchor="ls")
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
        sep: int = 1,
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
        sep: int = 1,
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
        sep: int = 1,
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
        sep: int = 1,
        orientation: str = "horizontal",
        **kwargs,
    ):
        """
        支持 TextLine/Span；普通字符串透传给原生 text。

        坐标系与 matplotlib 原生行为一致：
        - 默认使用数据坐标（``'data'``）
        - 传入 ``transform=ax.transAxes`` 则使用轴比例坐标
        - 传入 ``transform=fig.transFigure`` 则使用图比例坐标
        """
        ax = object.__getattribute__(self, "_ax")
        if isinstance(s, (TextLine, Span)):
            line = s if isinstance(s, TextLine) else s._as_line()

            if transform is None:
                coords: object = "data"
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

if __name__ == "__main__":
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
