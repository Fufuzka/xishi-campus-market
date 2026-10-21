# CloudStudio 导入与一键启动

网页测试版 0.2.0-beta.1 · 2026-10-21 · 尚非正式版

## 1. 仓库与项目结构

按用户明确选择，将原有 `Fufuzka/xishi-campus-market` 仓库改为公开，便于仅接受公开仓库的导入入口使用；不另建仓库、不迁移历史、不添加协作者。运行数据库、图片、认证证明、环境和密钥始终排除在 Git 之外。已有历史桌面 Release 仍标为历史测试版，不是当前网页部署入口。

公开导入地址：`https://github.com/Fufuzka/xishi-campus-market.git`。

截图里的范例使用 Vite，夕拾采用 FastAPI 同时提供 Vue 页面、静态资源和 API，所有请求为同源相对路径。不需要 Node、Vite、前端单独端口、`VITE_API_BASE_URL` 或 Vite proxy；复制范例的 `/api/v1` 会与夕拾现有 `/api` 路由不一致。

## 2. CloudStudio 操作

1. 选择 Python 3.11 或 3.12 环境（已有 3.11.1 可直接使用），从上面的公开 GitHub 地址导入仓库，选择 main 分支。
2. 在项目根目录打开终端，执行 `sh start.sh --cloud`。脚本自动创建 Python 虚拟环境、安装锁定依赖，并在 `0.0.0.0:8000` 启动一个服务，同时提供网页和接口。
3. 在平台端口／应用预览中打开 **8000** 端口的 HTTPS 预览地址。项目已有 `.vscode/preview.yml`，支持读取该配置的平台可直接点运行／启动。
4. 浏览器打开平台生成的完整 HTTPS 地址，检查 `/api/health`，再注册学生、提交认证图片、创建管理员审核并验收业务。

若平台只能从 Gitee 导入，需在你自己的 Gitee 账号中通过公开 GitHub 地址导入／同步；本次未代建 Gitee 仓库或登录其他账号。公开 GitHub 仓库本身不等于网站已在 CloudStudio 运行。

## 3. 测试数据和管理员

默认不生成演示账号，也不自动创建管理员。需要仅供课程演示的数据时，使用 `sh start.sh --cloud --demo`，并清楚标注演示环境；对已有用户的数据库，seed 不重复写入。

首次依赖安装后，另开终端创建管理员：

```sh
.venv/bin/python -m backend.create_admin your_admin_name
```

如果启动日志显示使用 `.venv-3.11`，请将上面命令中的 `.venv/bin/python` 换成 `.venv-3.11/bin/python`；以启动日志显示的实际环境目录为准。

密码交互输入，不写进代码或 Git，不把本机演示管理员的密码用于公开站点。普通用户仍只能由管理员人工审核认证。

## 4. 端口、HTTPS 与代理

默认一键命令使用 8000；需要其他端口时，例如 `PORT=8080 sh start.sh --cloud`，同时把平台预览端口和 preview.yml 调整为 8080。服务必须监听 0.0.0.0，预览地址里的端口必须一致。

Cloud 模式默认 `COOKIE_SECURE=1`，供 HTTPS 预览使用。不要使用 HTTP 预览地址验证登录 Cookie。在本机模拟云端启动时可显式设 `COOKIE_SECURE=0`，这只是本机 HTTP 测试选项。

平台如提供完整的 `X_IDE_SPACE_KEY`、`X_IDE_SPACE_REGION`、`X_IDE_SPACE_HOST`，脚本按官方规则自动生成 `MARKET_PUBLIC_ORIGIN`。平台的外部 HTTPS 来源与内部 HTTP 地址不同时，后端允许这个精确来源提交，仍拒绝其他来源，不开放任意跨站访问。

如这些变量不存在或实际预览地址不同，请把平台提供的真实站点根地址配置到环境变量：

```sh
export MARKET_PUBLIC_ORIGIN=https://your-real-preview-host
sh start.sh --cloud
```

地址不加 `/api`、页面路径、账号密码、查询参数或片段。脚本只读取导出的环境变量；根目录 `.env.example` 是说明模板，不会自动被当成 shell 脚本执行。

| 环境变量 | 作用 |
|---|---|
| PORT | 监听端口，默认 8000，1024–65535 |
| MARKET_HOST | Cloud 默认 0.0.0.0；普通本机默认 127.0.0.1 |
| MARKET_PYTHON | 可选 Python 3.11 或 3.12 可执行文件路径 |
| MARKET_VENV | 虚拟环境目录，默认 .venv；默认目录异常时自动选择 .venv-版本号，保留旧目录 |
| MARKET_DATA_DIR | 数据库、商品上传、认证证明的持久化目录，默认项目 data |
| MARKET_PUBLIC_ORIGIN | 可选精确 HTTPS 预览来源，脚本可从平台变量生成 |
| COOKIE_SECURE | Cloud 默认为 1；仅本机 HTTP 测试可设 0 |
| FORWARDED_ALLOW_IPS | 信任的代理 IP，默认 127.0.0.1，不默认信任所有客户端 |
| MARKET_SKIP_INSTALL | 仅预装依赖的测试环境使用 1，正常一键启动无需设置 |

## 5. 数据与运行状态

数据库、上传商品图片和认证证明都在 MARKET_DATA_DIR 下。若平台磁盘是临时的，应先配置持久化目录并做备份；工作环境停止、重置或到期时，预览服务也可能停止。课程演示预览与长期运行的公网生产部署应分别记录。

当前代码仍为测试版。本次准备与验证启动配置，并未登录你的 CloudStudio 工作区，也未生成真实远程访问地址。正式公网部署仍需完成原部署文档里的身份核验、限流、HTTPS、数据备份恢复及导师评审。

## 6. 验证和官方参考

本机通过 Git Bash 实际执行 `start.sh --cloud`，使用已有 Python 3.12 依赖和空隔离数据库，验证同端口页面及接口、无自动演示数据、精确 HTTPS 来源注册和登录 Cookie、非法来源拒绝、认证图片私有权限、认证提交、无自动管理员权限及退出，共 10 项。模拟测试的 HTTP 端口显式关闭 Secure Cookie，不冒称已经验证平台 HTTPS 证书。

新增 Ubuntu GitHub Actions 任务，从公开代码安装依赖并执行同一启动脚本与验收，结果见仓库 Actions。接口自动化覆盖代理来源配置和 Secure Cookie，Linux 任务状态以真实运行结果为准。

依据腾讯云官方 [配置运行文件](https://cloud.tencent.com/document/product/1039/131807) 使用 `.vscode/preview.yml` 的 apps、root、run、port、mainPort；依据 [URL 访问异常排查](https://cloud.tencent.com/document/product/1039/131933) 采用 0.0.0.0 监听及平台预览地址变量。用户提供的范例仅作为目标环境参考，不照搬其他项目的 Vite 配置。

## 7. Python 版本与创建环境失败

报错 `ensurepip is not available` 表示所选 Python 缺少虚拟环境的 pip 引导组件，不表示必须换成 3.12。已选择 `pyenv shell 3.11.1` 的工作区可执行：

```sh
git pull
pyenv shell 3.11.1
sh start.sh --cloud
```

脚本优先使用当前终端选择的 Python 3.11／3.12。若旧 `.venv` 创建失败或版本不同，会保留旧目录，自动创建／复用 `.venv-3.11` 等新环境。创建时优先使用 ensurepip；缺失时尝试使用现有 Python 的 pip 引导新虚拟环境，不安装系统级依赖。若两种方式均不可用，脚本明确报错，需选用带 ensurepip 或 pip 的 Python。
