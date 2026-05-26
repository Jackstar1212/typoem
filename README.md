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

typoem 用一个极轻量的对象模型解决这些问题。

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

## 排版样式

样式既可以定义在 `Font` 上（影响该字体所有后续调用），也可以直接在 `Span` 上单独调整（只影响当前片段）。所有方法均返回新对象，不修改原对象，支持任意链式调用。

---

### 粗体 / 连续字重

```python
hei = Font("黑体", size=11)

# .bold() — 简单粗体开关（等价于 .weight(700)）
hei.bold()("加粗文字")

# .weight(w) — 精细字重（0~1000）
hei.weight()("默认自重")       # 不填 = 400
hei.weight(300)("变细")        # 可变字体时真变细，静态字体则警告并保持默认
hei.weight(500)("中等偏粗")
hei.weight(700)("标准粗体")
hei.weight(900)("更粗")

# 也支持简写
hei.b()("加粗")
hei.w(300)("变细")
hei.w(600)("字重 600")
```

> **伪字重原理**：对没有粗体字形的字体（宋体、仿宋、楷体等），
> PIL 后端通过多次偏移重绘（synthetic bold）实现；
> Matplotlib 后端通过 path effect 叠加笔画实现近似加粗。
> 无论字体有没有粗体变体，`.weight()` 都能工作。
>
> **关于变细（<400）**：两个后端均支持通过**可变字体**（Variable Fonts）真正控制字重——
> 若字体文件内含 `wght` 轴（如思源黑体、Noto Sans 等 OTF/TTF 可变字体），
> 任意 `weight(100~1000)` 值均会直接通过轴值渲染；
> PIL 后端直接设置轴值，Matplotlib 后端将该 span 以 PIL 光栅化后嵌入为图片，
> 完整融入 `AnnotationBbox` 排版体系。
> 静态字体：`>400` 走伪粗体，`<400` 发警告并保持默认字重 400。

---

### 斜体

```python
cn = Font("宋体", size=9)

cn.italic()("伪斜体")              # 默认倾斜量 0.25
cn.italic(slant=0.35)("更斜")     # 自定义倾斜系数，推荐 0.15–0.40
```

> 斜体通过 PIL 仿射剪切变形实现，适用于任何没有斜体字形的中文字体。

---

### 粗体 + 斜体同时使用（链式调用）

```python
hei = Font("黑体", size=11)
en  = Font("Times New Roman", size=10)

# 链式调用，顺序任意，效果叠加
hei.bold().italic()("粗斜黑体")
hei.weight(900).italic(0.3)("重粗大斜角")
en.italic(0.2).weight(700)("先斜再加粗")

# Span 级链式调用（对单个片段临时加样式）
(cn("普通正文") + en(" result").bold().italic())
```

---

### 下划线

```python
cn.underline()("单下划线")                            # 默认：1px 单线
cn.underline(width=2)("粗下划线")                    # 自定义线宽
cn.underline(count=2)("双下划线")                    # 两条线
cn.underline(count=2, width=1, gap=4)("宽间距双线")  # 控制间距
```

---

### 删除线

```python
cn.strikethrough()("删除线")
cn.strikethrough(width=2)("粗删除线")
```

---

### 组合装饰

```python
# 粗体 + 下划线
hei.bold().underline(width=2)("加粗下划线")

# 斜体 + 删除线
cn.italic().strikethrough()("斜体删除")

# 粗体 + 斜体 + 下划线（三叠）
en.weight(700).italic(0.3).underline(count=2)("全装饰")
```

---

### 上标 / 下标

字号自动缩小，位置自动偏移，常用于化学式、数学指数等：

```python
cn = Font("宋体", size=12)
en = Font("Arial", size=12)

# 上标：x²
cn("x") + en.sup()("2")

# 下标：CO₂
cn("CO") + en.sub()("2") + cn(" 浓度")

# 自定义缩放比例（默认 0.65）
en.sup(ratio=0.7)("上标更大")
en.sub(ratio=0.55)("下标更小")

# Span 级：对已有片段追加上下标
cn("H") + en("2").sub() + cn("O")    # H₂O
```

---

### 垂直偏移 / 基线微调

解决不同字体视觉基线不一致的问题，或用于特殊排版需求：

```python
# 单位：排版点（pt）；y 正方向为上
en.shift(y=2)("略微上移")
en.shift(y=-1.5)("略微下移")

# 实际应用：混排时手动对齐视觉基线
cn("当日累积位移量") + en.shift(y=1.5)("mm")

# 水平位移也支持（正方向向右）
cn.shift(x=4, y=0)("右移 4pt")
```

---

### 旋转

```python
cn.rotate(15)("逆时针 15°")
cn.rotate(-10)("顺时针 10°")

# 各片段可以有不同旋转角度
cn.rotate(10)("倾斜") + cn("正常") + cn.rotate(-10)("反倾斜")
```

---

### Span 级样式（对已生成片段追加样式）

所有样式方法在 `Span` 上同样可用，方便对已有片段临时修改：

```python
# 在拼接时直接附加样式
line = (
    cn("普通")
    + en(" result").bold()
    + cn(" 显著").italic().underline()
    + en(" p<0.05").weight(500)
)

# 化学式：Span 级上下标
cn("H") + en("2").sub() + cn("O") + en(" + ") + cn("CO") + en("2").sub()

# 带上标的数学表达式
cn("R") + en("2").sup() + en(" = 0.98")
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
from typoem import Font, bind, AutoFont

# ── 字体对象 ──────────────────────────────────────────────────────
f = Font(name_or_path, size=12)
f("文本")                          # → Span
f.at(size)("文本")                 # → Span（临时字号）
Font.list_fonts()                  # → list[str]

# ── 字重与粗体 ────────────────────────────────────────────────────
f.bold()                           # 标准粗体（等价于 weight(700)）
f.weight()                         # 默认自重（400）
f.weight(300)                      # 变细（可变字体）/ 警告（静态字体）
f.weight(500)                      # 精细字重（0~1000）
f.weight(700)                      # 标准粗
f.weight(900)                      # 很粗
f.b()                              # .bold() 简写
f.w(300)                           # .weight() 简写（变细）
f.w(600)                           # .weight() 简写（加粗）

# ── 斜体 ──────────────────────────────────────────────────────────
f.italic()                         # 伪斜体（slant=0.25）
f.italic(0.35)                     # 自定义倾斜量
f.i(0.35)                          # .italic() 简写

# ── 装饰线 ────────────────────────────────────────────────────────
f.underline()                      # 单下划线
f.underline(width=2, count=2, gap=4)  # 双线/自定义粗细间距
f.u(width=2, count=2)              # .underline() 简写
f.strikethrough()                  # 删除线
f.strikethrough(width=2)           # 自定义线宽
f.st(width=2)                      # .strikethrough() 简写

# ── 上下标 ────────────────────────────────────────────────────────
f.sup()                            # 上标（ratio=0.65）
f.sub()                            # 下标（ratio=0.65）
f.sup(ratio=0.7)                   # 自定义缩放比例

# ── 位移与旋转 ────────────────────────────────────────────────────
f.shift(y=2)                       # 垂直上移 2pt
f.shift(x=-1, y=1.5)              # 水平+垂直同时偏移
f.offset(y=2)                      # .shift() 语义别名
f.sh(y=2)                          # .shift() 简写
f.off(x=-1, y=1.5)                 # .offset() 简写
f.rotate(15)                       # 逆时针旋转 15°
f.r(15)                            # .rotate() 简写

# ── 链式调用（任意顺序、任意组合）─────────────────────────────────
f.bold().italic()
f.weight(700).italic(0.3).underline()
f.weight(900).shift(y=1)

# ── 片段与拼接 ────────────────────────────────────────────────────
span1 + span2                      # → TextLine
span  + line                       # → TextLine
line  + span                       # → TextLine
line  + line                       # → TextLine

# ── Span 级样式（对单个片段追加） ─────────────────────────────────
span.bold()   .italic()   .weight(w)
span.underline(count=2)  .strikethrough()
span.sup()    .sub()      .shift(y=2)    .rotate(10)
span.b()      .i(0.3)     .w(600)
span.u()      .st()       .sh(y=2)       .r(10)

# ── 渲染 ──────────────────────────────────────────────────────────
line.draw(ax_or_img, x, y, **kwargs)
line.render(bg="white", padding=6)     # → PIL.Image.Image
line.preview()

# ── Matplotlib 集成 ──────────────────────────────────────────────
ax = bind(ax)
ax.set_title(line)
ax.set_xlabel(line)
ax.set_ylabel(line)
ax.text(x, y, line, transform=ax.transAxes)

# ── 自动中英文分段 ────────────────────────────────────────────────
auto = AutoFont("宋体", "Arial")
auto("中英文 Auto Mix")               # → TextLine
```

### 0.2.1 变更说明

- **可变字体真实字重（两端、两后端）**：含 `wght` 轴的字体，任意 `weight(100~1000)` 均走真实轴值渲染；PIL 后端直接设置轴，Matplotlib 后端光栅化嵌入，`bind(ax)` 完全透明支持。静态字体 `>400` 走伪粗体，`<400` 警告保持 400。
- 旧写法（0~3 语义）已移除，请统一迁移到 `0~1000`。
- 推荐对照：`400=正常`，`500=中等偏粗`，`700=标准粗`，`900=很粗`。
- `bold()` 固定表示”标准粗体”，需要精细控制请用 `weight()` / `w()`。

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

