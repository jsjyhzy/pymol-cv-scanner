# AGENTS.md – 距离约束扫描 PyMOL 插件

> 本文件旨在帮助后续 AI Agent 快速了解本项目的背景、架构、关键决策及待办事项，从而高效地接手开发与维护工作。

---

## 项目概述

本插件为 PyMOL 提供了一个图形界面，用于对两组原子的质心距离进行**约束性能量最小化扫描**。用户可通过图形界面载入 Amber 格式的拓扑（`.prmtop`）和坐标（`.pdb`）文件，通过点选原子定义两组，然后设定距离范围、窗口数、力常数等参数，执行扫描。扫描结果以多状态 PDB 对象加载回 PyMOL，便于浏览不同距离下的优化构象。此外，插件支持一键生成**自包含的批处理脚本**，可提交至计算集群独立运行。

---

## 项目演变历史（关键里程碑）

1. **起点** – 一个独立的命令行脚本（基于 OpenMM），实现了 CV 扫描功能。
2. **首次集成** – 封装为 PyMOL 插件，使用 Tkinter 构建 GUI。
   - 问题：Tkinter 与 PyMOL 的 Qt 事件循环冲突，导致点击崩溃（GIL 相关问题）。
3. **GUI 迁移至 Qt** – 改用 PyQt5 重写 GUI，彻底解决事件循环冲突。
   - 同时采用 `multiprocessing` 执行 OpenMM 计算，隔离 GIL。
4. **原子组选择修复** – 修正 `get_names(selection=True)` 错误，改用 `cmd.get_model('sele')` 获取选中原子索引。
5. **多帧 PDB 写入修复** – 发现 `Context` 粒子数有时多于拓扑原子数，导致 `PDBFile.writeFile` 报错。改用手动逐模型写入（`MODEL/ENDMDL`），并加入位置截断逻辑。
6. **批处理脚本增强** – 增加“生成批处理脚本”按钮，可将当前所有参数导出为独立 Python 脚本。
   - 使用 gzip+base64 将输入文件嵌入脚本，便于集群传输。
   - 去除对 `Reference` 平台的强制指定，让 OpenMM 自动选择最优平台。
7. **模块化重构** – 将单文件拆分为 `__init__.py`, `gui.py`, `core.py`, `batch_script.py`, `utils.py` 及 `templates/` 目录，提高可维护性。
8. **模板化脚本生成** – 将批处理脚本主体移至独立的模板文件（`templates/scan_script_template.py`），便于语法检查和维护。
9. **增强与打包** – 新增隐式溶剂（OBC2，GUI 复选框 + 模板）、流式写帧、批处理脚本 `OPENMM_PLATFORM` 环境变量覆盖；改用 `Makefile`（tar/gzip 核心工具）打包为 Plugin Manager 可直接安装的 `.tar.gz`，并新增加载自检脚本。
10. **批处理脚本改为 zipapp** – 摒弃 gzip+base64 嵌入单文件脚本的方案，改为打包为自包含的 Python zipapp（`.pyz`）：`__main__.py` + 真实 prmtop/pdb 数据文件直接打入压缩 zip。生成的 CLI 支持 `--help`/`--params` 及全套扫描参数覆盖，OpenMM 惰性导入让 `--help`/`--params` 在未装 OpenMM 的机器上也可用。

---

## 当前架构（模块说明）

```
src/                        # 插件源码（打包时作为 distance_scan_plugin/ 包）
├── __init__.py             # 插件入口，注册菜单项（含 PyMOL 插件元数据头）
├── gui.py                  # PyQt5 主窗口类（DistanceScanPlugin）
├── core.py                 # OpenMM 核心计算（扫描函数、CV 计算）
├── batch_script.py         # 批处理 zipapp 生成（模板渲染 + zipapp 打包）
├── utils.py                # 工具函数（原子选择）
└── templates/
    └── scan_zipapp_main.py        # zipapp 的 __main__.py 模板（@@MARKER@@ 占位符）

Makefile                    # 打包/检查/测试入口（dist, check, test, test-pymol, clean）
scripts/
└── test_plugin_load.py     # 插件包结构与 PyMOL 加载自检脚本
```

- **`gui.py`** – 负责 UI 构建、用户交互、信号处理、进度管理、多进程启动。长度约 400 行，属于正常范围。
- **`core.py`** – 纯粹的计算逻辑，与 GUI 解耦，可独立测试。
- **`batch_script.py`** – 读取模板文件，填入参数（`@@MARKER@@` 占位符替换），用 `zipapp` 打包为自包含 `.pyz`。
- **`utils.py`** – 通用辅助函数（PyMOL 原子选择）。
- **模板文件** – 合法的 Python 代码，使用 `@@MARKER@@` 占位符；无需处理 `.format()` 的花括号转义。

---

## 关键技术决策（及理由）

| 决策 | 理由 |
|------|------|
| **使用 PyQt5 而非 Tkinter** | PyMOL 自身基于 Qt，Tkinter 会导致事件循环冲突和 GIL 崩溃。 |
| **多进程执行 OpenMM 计算** | 避免 GIL 阻塞 GUI，同时隔离 OpenMM 的线程行为，提高稳定性。 |
| **本地扫描强制使用 Reference 平台** | 在 PyMOL 主进程中，Reference 平台单线程且稳定，避免与 Qt 或 CUDA 上下文冲突。 |
| **批处理脚本自动选择平台，可用 `OPENMM_PLATFORM` 环境变量覆盖** | 集群通常有 GPU，OpenMM 自动选择 CUDA/OpenCL 可大幅提速；特殊集群可通过环境变量显式指定平台。 |
| **输入文件直接打入 zipfile** | 嵌入真实 `.prmtop`/`.pdb` 数据文件到 zipapp，实现脚本自包含（体积更小），无需额外上传文件。 |
| **手动逐模型写入 PDB（流式）** | 绕过 `PDBFile.writeFile` 多模型可能出现的原子数不匹配问题，并加入截断检查；每帧计算后立即写入，避免大体系 + 多窗口时的内存占用。 |
| **使用模板文件存储脚本主体** | 便于语法检查、修改和版本控制，避免在 Python 字符串中维护大型代码块。 |
| **禁用 `rigidWater=True`** | 避免引入虚拟位点，确保粒子数与拓扑原子数严格一致（尤其适用于干燥体系）。 |
| **可选隐式溶剂 OBC2** | 真空扫描可能导致蛋白结构畸变；启用时强制 `NoCutoff`（OBC2 与周期 PME 不兼容）。 |
| **打包为 tar.gz 插件包** | PyMOL 插件管理器支持 `.zip`/`.tar.gz` 归档；用 Linux 核心工具 tar/gzip 打包，Makefile 驱动，无需额外 Python 依赖。 |

---

## 已知问题 / 待改进项

- **批处理脚本的平台依赖库** – 某些集群可能缺少特定库（如 CUDA），`OPENMM_PLATFORM` 环境变量可手动指定平台绕过。
- **进度反馈** – 目前通过 Queue 传递窗口编号，但无法获取每个窗口的详细收敛信息，未来可扩展。
- **测试覆盖率** – 目前仅提供插件结构与 PyMOL 加载自检（`scripts/test_plugin_load.py`），缺乏针对 `core` 和 `utils` 逻辑的单元测试，建议后续添加。

---

## 开发与测试指南

### 环境要求
- PyMOL (>=2.5) 且已安装 PyQt5 支持（通常通过 `pmg_qt` 提供）。
- OpenMM (>=8.0) 和 NumPy（**仅本地扫描必需**）。
- 若机器上只安装了 PyMOL 而没有 OpenMM，插件仍可正常加载：`Run Scan` 与 `Compute CV` 按钮被禁用，但 **Generate Batch Script 仍可用**，可生成脚本到装有 OpenMM 的集群上运行（`core.py` 对 OpenMM/NumPy 使用惰性导入）。

### 安装插件

在项目根目录运行 `make`（或 `make dist`）生成
`dist/distance_scan_plugin-<版本>.tar.gz`，然后在 PyMOL 中：

**Plugin > Plugin Manager > Install New Plugin > 选择该 tar.gz 文件**

重启 PyMOL 后，可在 Plugin 菜单中看到 “Distance Constrained Minimization”。

### 开发与测试

```bash
make dist         # 打包为 dist/distance_scan_plugin-<版本>.tar.gz
make check        # py_compile 语法检查（无需 PyMOL）
make test         # 结构自检（无需 PyMOL，校验归档布局 + Python 语法）
make test-pymol   # 在 PyMOL (pymol -cq) 中实际加载插件并调用入口
make clean        # 删除 dist/
```

`make dist` 使用 Linux 核心工具（cp/find/tar/gzip）将 `src/` 组装为
`distance_scan_plugin/` 包并打包，无需 Python 打包辅助脚本。

### 本地调试
- 可在 `gui.py` 中添加 `if __name__ == "__main__":` 进行独立测试（需模拟 PyMOL 环境），但建议直接在 PyMOL 中测试。
- 修改 `core.py` 或 `batch_script.py` 后，重启 PyMOL 生效。

### 提交补丁
- 遵循现有模块划分，保持职责单一。
- 修改模板 `scan_zipapp_main.py` 时，用 `@@NAME@@` 占位符标记由插件注入的参数，避免 `.format()`/f-string 的括号转义问题。
- 由 AI 助手生成的提交，应在 commit message 末尾附上：
  `Co-authored-by: deepseek-v4-flash-free <jsjyhzy@gmail.com>`
- 若添加新功能，请同步更新本文档。

---

## 联系方式

本项目由用户 @huzheyang 主导开发，如有重大决策或疑问，可向其询问。AI Agent 维护者应基于本文档进行开发，避免重复踩坑。

---

**最后更新**：2026-08-05  
**状态**：稳定运行，核心功能完善；已支持隐式溶剂（OBC2）、流式写帧、批处理脚本平台环境变量，并可打包为 tar.gz 插件包。待扩展自动化单元测试。