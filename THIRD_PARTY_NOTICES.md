# 第三方组件与素材说明

- Vue 3.5.13：MIT License，Copyright (c) 2018-present Yuxi (Evan) You and Vue contributors。发布文件保留原始版权头；完整许可见 `frontend/vendor/VUE-LICENSE`。来源：https://unpkg.com/vue@3.5.13/dist/vue.global.prod.js。
- Python 依赖与版本见 `requirements.lock.txt`，各组件版权归原作者，许可随已安装发行包提供。主要组件：FastAPI（MIT）、Uvicorn（BSD-3-Clause）、Pillow（MIT-CMU）、pytest（MIT）、HTTPX（BSD-3-Clause）。
- 页面中的商品和头图均为项目脚本绘制的 SVG 示意插画；不是实物照片。演示数据、昵称和联系方式仅用于课程验收。
- 图标使用文字和 Unicode 字符；未引入商业字体或外部图库。
- 桌面版使用 pywebview 6.1（BSD-3-Clause）、pythonnet 3.2.1（MIT）及 PyInstaller 6.16.0（GPL 附带分发例外）。发布包附带相关第三方许可原文，来源为已安装发行包。WebView2 Runtime 为 Microsoft 组件，需要在目标系统单独安装，不包含在 EXE 中。具体构建依赖见 requirements-desktop.txt。
