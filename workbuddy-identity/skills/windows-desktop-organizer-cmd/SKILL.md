---
name: Windows桌面自动整理(CMD版)
description: This skill should be used when the user wants to organize, clean, sort, or archive files on their Windows desktop using native CMD batch scripts — with no extra software dependencies. It handles one-time manual cleanup, generating reusable .bat scripts, setting up Windows Task Scheduler automation, viewing or modifying scheduled tasks, and customizing file classification rules. Trigger when the user mentions desktop cleanup, auto-organizing files by type, CMD scripts for file sorting, scheduled desktop tasks, or any desktop tidying workflow on Windows.
---

# Windows 桌面自动整理技能（CMD版）

## 概述

本技能基于 Windows 原生 CMD 批处理命令，实现桌面文件的自动化分类整理。支持一键手动执行、生成自定义脚本、配置 Windows 任务计划程序定时自动执行。全程无需安装任何第三方软件。

---

## 可用脚本

所有脚本位于本技能的 `scripts/` 目录中：

| 脚本文件 | 功能 |
|---|---|
| `organize_desktop.bat` | **核心整理脚本**：按文件类型分类整理桌面，可直接运行或供用户保存使用 |
| `setup_scheduled_task.bat` | **定时任务设置脚本**：通过 Windows 任务计划程序设置自动执行整理 |
| `view_task_status.bat` | **任务状态查询脚本**：查看或删除现有的桌面整理定时任务 |

---

## 工作流程

### 场景一：用户请求一次性桌面整理

1. 读取 `scripts/organize_desktop.bat` 的内容
2. 将脚本内容直接输出给用户，清楚说明：
   - 脚本将把桌面文件分为 7 类（文档/图片/视频/音频/压缩包/代码/其他）
   - **不会移动 `.lnk` 快捷方式**，软件图标安全保留
   - 脚本路径基于 `%USERPROFILE%\Desktop`，自动适配所有用户名
3. 引导用户将脚本保存为 `.bat` 文件后双击运行，或以管理员身份运行命令提示符执行

### 场景二：用户想设置定时自动整理

1. 确认用户期望的执行时间（例如 `18:00`）和频率（`DAILY` 每天 / `WEEKLY` 每周）
2. 读取 `scripts/setup_scheduled_task.bat`，并根据用户指定的时间和频率调整脚本中的参数（`TASK_TIME` 和 `TASK_FREQ`）
3. 将调整后的脚本输出给用户，说明：
   - 需要**以管理员身份**运行该脚本才能创建任务计划
   - 任务名称默认为 `桌面自动整理`，可在脚本中修改
   - 该脚本依赖 `organize_desktop.bat` 与其在同一目录

### 场景三：用户查看或删除定时任务

1. 读取并输出 `scripts/view_task_status.bat`
2. 说明运行后可交互式查看任务状态，并选择是否删除

### 场景四：用户想自定义文件分类规则

1. 读取 `scripts/organize_desktop.bat` 内容
2. 根据用户需求修改分类规则，例如：
   - 新增文件类型扩展名到对应类别
   - 修改分类文件夹名称
   - 添加或删除整个分类大类
3. 输出修改后的完整脚本，并高亮标注改动位置

---

## 分类规则（默认）

| 分类文件夹 | 包含扩展名 |
|---|---|
| 文档文件 | `.doc` `.docx` `.pdf` `.txt` `.ppt` `.pptx` `.xls` `.xlsx` `.csv` `.md` `.odt` `.wps` |
| 图片文件 | `.jpg` `.jpeg` `.png` `.gif` `.bmp` `.webp` `.svg` `.ico` `.tiff` `.tif` `.heic` |
| 视频文件 | `.mp4` `.avi` `.mkv` `.mov` `.flv` `.wmv` `.m4v` `.ts` `.webm` |
| 音频文件 | `.mp3` `.wav` `.flac` `.aac` `.ogg` `.wma` `.m4a` |
| 压缩包文件 | `.zip` `.rar` `.7z` `.tar` `.gz` `.bz2` `.xz` `.iso` |
| 代码文件 | `.py` `.js` `.html` `.css` `.java` `.cpp` `.c` `.sh` `.json` `.xml` `.yaml` `.yml` |
| 其他文件 | 以上未涵盖的所有非 `.lnk` 文件 |

> **重要安全规则**：`.lnk` 快捷方式和 `.bat` 脚本本身**永远不会被移动**，以防误移软件图标和破坏脚本自身。

---

## 关键注意事项

- **所有操作均在用户桌面目录** (`%USERPROFILE%\Desktop`) 内进行，不影响系统其他位置
- **设置定时任务需要管理员权限**；一次性整理脚本无需管理员权限
- 建议在首次运行整理脚本前**备份重要桌面文件**
- 当用户提到"一键整理"、"定时清理桌面"、"CMD脚本分类文件"等关键词时即触发本技能
- 输出脚本时，始终以 ` ```batch ` 代码块格式呈现，便于用户复制

---

## 标准输出格式

完成后，按以下格式输出结果：

```
✅ 桌面整理CMD技能执行完成

【执行结果】
已为你生成对应的桌面整理CMD脚本，详情如下：
1. 分类规则：文档/图片/视频/音频/压缩包/代码/其他文件 7大类
2. 目标路径：%USERPROFILE%\Desktop 对应分类文件夹
3. 执行方式：Windows原生CMD命令，无需额外依赖

【使用方法】
1. 将以下脚本内容复制保存为 .bat 文件（如 organize.bat）
2. 双击运行，或右键"以管理员身份运行"

【可用CMD脚本】
（输出脚本内容）
```
