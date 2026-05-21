# typoem

**A lightweight mixed-font typesetting engine for Python.**  
把字体做成可调用对象，用 `+` 拼接，哪里都能渲染。

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---
## 为什么需要 typoem

Matplotlib 的文本系统在中英混排场景下经常遇到：

- 中文字体 fallback 不稳定
- 不同字体基线难以对齐
- 标题/标签混排代码繁琐
- 难以实现高出版质量的图表排版

Typoem 并未取代 Matplotlib 的字体回退系统。
它提供了一个轻量级的对象模型，用于实现明确的混合字体排版。

Typoem does not replace Matplotlib's font fallback system.
It provides a lightweight object model for explicit mixed-font typography.

## 设计理念

typoem 不只是一个字体混排工具，而是一个面向科研绘图场景的轻量排版层：

- **Font → Span → TextLine** — 声明式排版对象模型
- **核心模块仅依赖 Python stdlib** — Matplotlib / Pillow 均按需使用
- **平台原生字体发现** — Windows 读注册表，Linux/macOS 调 `fc-list`，无需配置路径
- **零侵入 Matplotlib 集成** — `bind(ax)` 一行包装，原有代码无需修改

*Inspired by the idea that typography should feel native in scientific plotting.*

---

## 安装

```bash
pip install typoem
```

> 仅需 Python 3.9+，无强制依赖。  
> 渲染功能按需安装：`pip install matplotlib pillow`

---

## 快速上手

### 1. 定义任意多种字体，自由拼接

字体数量没有限制——按场景需要定义几种就定义几种，调用即片段，`+` 即排版：

```python
from typoem import Font

cn   = Font("宋体",            size=9)
en   = Font("Times New Roman", size=10)
bold = Font("黑体",            size=11)
math = Font("Cambria",         size=9)
cap  = Font("Arial",           size=8)   # 可以继续加，没有上限

line = cn("正态分布") + en(" N(μ,σ²) ") + bold("显著") + math(" p<0.05")
```

`Font` 对象本身就是函数——调用即产生片段（`Span`），片段用 `+` 自由拼接成文本行（`TextLine`）。

---

### 2. 渲染到 PIL Image

```python
img = line.render(padding=8)   # 返回 PIL.Image.Image
img.save("output.png")
line.preview()                 # 弹窗预览
```

---

### 3. 渲染到 Matplotlib

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
line.draw(ax, x=0.5, y=0.5, transform=ax.transAxes)
plt.show()
```

---

### 4. bind(ax) — 零侵入 Matplotlib 集成

在已有绘图代码里只加一行 `ax = bind(ax)`，之后 `set_title / set_xlabel / set_ylabel / text` 全部直接接受 `TextLine`：

```python
from typoem import Font, bind
import matplotlib.pyplot as plt

cn = Font("宋体", 9)
en = Font("Arial", 10)

fig, ax = plt.subplots()
ax = bind(ax)                   # ← 唯一改动

ax.set_title(cn("实验结果") + en(" Results"))
ax.set_xlabel(cn("频率") + en(" Frequency"))
ax.set_ylabel(cn("幅值") + en(" Amplitude"))
ax.text(0.5, 0.5, cn("标注") + en(" note"), transform=ax.transAxes)

# 普通字符串照样工作，无需改动其他代码
ax.plot([1, 2, 3], [4, 5, 6])
plt.show()
```

---

### 5. 临时换字号

```python
title = cn.at(14)("大标题") + en.at(12)(" Big Title")
```

`font.at(size)` 返回一个临时字号的新 Font，不修改原对象。

---

### 6. AutoFont — 自动中英文分段

```python
from typoem import AutoFont

auto = AutoFont("宋体", "Arial")          # 也可传入已有 Font 对象
line = auto("中英文 Auto Mix 混排")
line.preview()
```

AutoFont 自动检测中英文区间，中文使用 cn 字体，其余使用 en 字体。

---

### 7. 查看系统字体

```python
from typoem import Font

print(Font.list_fonts())   # 列出系统所有可用字体路径
```

---

## 渲染后端

| 后端 | 触发条件 | 依赖 |
|---|---|---|
| Matplotlib | `draw(ax, ...)` 或 `bind(ax)` | `matplotlib >= 3.3` |
| PIL | `draw(img, ...)` 或 `render()` | `Pillow >= 8.0` |

两个后端均为可选，按实际需要安装即可。

---

## 字体查找顺序

1. 直接文件路径（如 `Font(r"C:\Windows\Fonts\simsun.ttc")`）
2. 内置别名表（`宋体 / 黑体 / Arial / Times New Roman` 等常用字体）
3. 系统字体目录文件名精确匹配
4. 系统字体目录文件名模糊匹配
5. **平台原生接口**：Windows 读注册表，Linux/macOS 用 `fc-list`（覆盖 Adobe、Office、用户自装字体）

---

## Cheat Sheet

```python
# 字体
f = Font(name_or_path, size=12)
f("文本")            # → Span
f.at(size)("文本")   # → Span（临时字号）
Font.list_fonts()    # → list[str]

# 片段拼接
span1 + span2        # → TextLine
span  + line         # → TextLine
line  + span         # → TextLine
line  + line         # → TextLine

# 渲染
line.draw(ax_or_img, x, y, **kwargs)
line.render(bg="white", padding=6)  # → PIL.Image.Image
line.preview()

# Matplotlib 集成
ax = bind(ax)
```

---

## 设计边界

typoem 专注于「学术图表标注与排版标签」这一场景，在设计上**有意不做**：

- 自动换行 / 段落布局
- OpenType shaping（HarfBuzz）
- 数学公式排版（请用 LaTeX / MathText）
- 海量文本对象的高性能渲染

克制是设计的一部分。

---

*typoem 希望让科研绘图中的排版回归自然。*

---

## License

MIT © 2026
