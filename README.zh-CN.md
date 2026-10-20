# 像素画转拼豆 (Pixel Art to Beads, PA2B)

[English](README.md) | 简体中文

一个极简的拼豆和十字绣图纸生成器，专为像素画设计。支持多个品牌，包括 MARD、Perler、DMC 等。

**[打开生成器](https://jenydu.github.io/pixel-art-to-beads/)**：全部在浏览器中运行，你的图片不会被上传。

**不使用 AI。** 这里没有用到任何 AI 或机器学习。图片只经过常规的信号处理和色彩计算，所以同一张图片总是得到同一份图纸，也不会有任何猜测或凭空生成的内容：你得到的就是你自己的像素画，只是被整理干净了。

## 和其他生成器有什么不同

大多数图纸生成器是把一张照片缩小成一格一格的拼豆，边缘会变糊，细节也会丢失。这个工具反过来：你的图片本来就是像素画，所以要做的是把原来的像素画还原出来。

网上的像素画很少是干净的。它可能被放大过奇怪的倍数、被拉伸、存成了 JPEG、因缩放而变模糊、截图时带着边框和阴影，或者画在编辑器的网格线上。这个工具会找出真正的像素网格，只看每个像素中间受损最小的部分，为每个像素还原出一种干净的颜色，然后匹配到你选的拼豆或绣线。即使一张32 x 32的小图被存成了1080 x 1920的截图，它也能还原出32 x 32的图纸。

## 功能

**清理图片**
- 找出真实的像素大小，包括非整数倍的放大、宽高不等的像素，并能容忍模糊和 JPEG 压缩痕迹。
- 裁掉边框：截图边框、投影和白色边距；编辑器里淡淡的网格线会被忽略。
- 清除白色或透明的背景，但保留画面内部的白色。
- “合并相近颜色”会把残留的杂色并入同一种颜色。
- 找不到像素网格的图片会当作普通照片，缩小成适合拼豆的格子数；你也可以随时自己设置网格大小（保持图片比例）。

**生成图纸**
- 用感知色差（CIELAB 色彩空间、CIEDE2000 公式）把每种颜色匹配到最接近的拼豆或绣线。
- 颜色替换：查看每种图片颜色变成了哪一种拼豆，并可以把其中任意一种换成另一种相近的拼豆。
- 图纸格子里可以显示色号或符号。Perler、DMC 这类色号很长或全是数字的品牌，默认使用符号。
- 拼豆板尺寸（默认 52）会把较大的图纸拆成多块板，每块都从 1 开始编号，完整图纸上用红线标出板与板的分界。
- 用量清单列出每种颜色的数量和合计，可按色号或按数量排序。

**查看与导出**
- 图纸会自动适应屏幕；可以用按钮、双指捏合或 Ctrl/Cmd + 滚轮缩放，拖动平移，并用“上一块 / 下一块”逐块查看或一次显示全部。
- “保存 PNG”和“保存 PDF”会在新标签页中打开结果，你可以在那里保存。第一页是整张图纸加用量清单；图纸跨多块拼豆板时，PDF 还会为每块板另加一页。屏幕上的图纸是矢量图，放大后依然清晰。
- 手机和电脑都可以使用，界面支持英文和简体中文。

## 支持的品牌

| 品牌 | 颜色数 | 色号形式 | 数据来源 |
| --- | ---: | --- | --- |
| MARD（完整版） | 291 | A1、B12、ZG3 | [beadcolors](https://github.com/maxcleme/beadcolors)，色值取自 [pixel-beads.com 的 MARD 色卡（2026 修订版）](https://www.pixel-beads.com/mard-bead-color-chart) |
| MARD（基础版） | 221 | A1 … H23、M1 … M15 | 完整版中的 A–H 和 M 系列，即 pixel-beads.com 所定义的标准 221 色 |
| Perler | 103 | 80-15179 | [beadcolors](https://github.com/maxcleme/beadcolors) |
| Perler Mini | 41 | 80-15179 | beadcolors |
| Perler Caps | 26 | 80-16086 | beadcolors |
| Hama Midi | 92 | H01 | beadcolors |
| Hama Mini | 78 | H01 | beadcolors |
| Hama Maxi | 25 | H01 | beadcolors |
| Nabbi | 30 | N01 | beadcolors |
| Artkal A（2.6 mm） | 145 | A01 | beadcolors |
| Artkal C（2.6 mm） | 174 | C01 | beadcolors |
| Artkal M（2.6 mm） | 220 | MA1 | beadcolors |
| Artkal R（5 mm） | 89 | R01 | beadcolors |
| Artkal S（5 mm） | 199 | S01 | beadcolors |
| Yant | 119 | Y002 | beadcolors |
| DMC（十字绣线） | 454 | 310、3865、B5200 | [threadcolors.com](https://threadcolors.com/)，由 `tools/scrape_threadcolors.py` 抓取 |

拼豆颜色来自 [beadcolors](https://github.com/maxcleme/beadcolors)，这是一个由社区维护的色卡集合（MIT 许可；贡献者署名见 `data/palettes/*.csv`），`build.py` 会把它复制到 `data/palettes/`。

所有颜色都只是屏幕上的近似值。真实的拼豆和绣线会因批次而不同，在不同光线下看起来也不一样，做大件作品之前请先对一对色样。

## 工作原理

1. **裁切**：去掉图片四周单一的浅色边框。
2. **检测网格**：沿每个方向，边缘强度会形成重复的图案，其周期就是像素大小，相位就是网格的偏移。只读取一部分抽样的行和列，所以再大的图也不会比小图慢。
3. **取样**：取每个格子中心的中位数颜色，清除背景，并合并几乎相同的颜色。
4. **匹配**：把每种颜色匹配到所选的色卡，然后统计数量并绘制。

Python 通过 [Pyodide](https://pyodide.org/) 在浏览器中运行（numpy 和 Pillow 的 WebAssembly 版本）；页面本身是普通的 HTML、CSS 和 JavaScript，无需构建。详见 `ARCHITECTURE.md`。

## 局限

- 非常模糊、内容又很稀疏的图片可能会提示“找不到网格”，这时请手动输入网格大小。
- 只放大了 2 倍或更少的图片无法自动检测。
- 单边超过约 4000 px 的图片可能会耗尽浏览器内存。

## 本地运行

```
pip install numpy pillow pytest openpyxl
python build.py                 # 同步 ../beadcolors/raw，生成 dmc.csv，准备 web/py
python -m http.server -d web    # 打开 http://localhost:8000
python cli.py image.png --brand mard_291 --board 52 --out out/    # 在终端运行同样的流程
python -m pytest
```

`python tools/scrape_threadcolors.py` 会重新下载 DMC 表格。推送到 `main` 后，`.github/workflows/pages.yml` 会把 `web/` 部署到 GitHub Pages（需在仓库设置里把 Pages 设为“GitHub Actions”）。
