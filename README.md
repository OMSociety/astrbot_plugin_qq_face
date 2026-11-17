<p align="center"><strong>中文</strong> · <a href="README_en.md">English</a></p>

<div align="center">

<h1><img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_qq_face/main/logo.png" width="192" alt="QQ 大黄脸 Logo"><br>QQ 大黄脸</h1>

**自然理解并发送 OneBot QQ 原生表情** —— 动态目录 · 多实例隔离 · 动态贴纸拆条

[![Version](https://img.shields.io/github/v/tag/OMSociety/astrbot_plugin_qq_face?label=version&color=4c8bf5)](https://github.com/OMSociety/astrbot_plugin_qq_face/releases)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.24.1-6c5ce7)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-2da44e)](LICENSE)
[![Stars](https://img.shields.io/github/stars/OMSociety/astrbot_plugin_qq_face)](https://github.com/OMSociety/astrbot_plugin_qq_face/stargazers)
[![Issues](https://img.shields.io/github/issues/OMSociety/astrbot_plugin_qq_face)](https://github.com/OMSociety/astrbot_plugin_qq_face/issues)

[核心特性](#核心特性) • [支持平台](#支持平台) • [安装](#安装) • [使用](#使用) • [配置](#配置) • [数据与隐私](#数据与隐私)

</div>

## 核心特性

| 特性 | 说明 |
| --- | --- |
| **原生发送** | 模型在回复中自然写入 `<face:表情名>`，插件在发送前转换成 OneBot `Face` |
| **入站理解** | 按消息原有顺序把收到的 `Face` 标注为 `[QQ表情:名字]`，帮助模型理解表情所在的位置 |
| **动态目录** | 支持 `fetch_sys_faces` 的协议端可按平台实例更新目录；内置目录包含 294 个去重数字表情，动态目录刷新失败时保留缓存 |
| **动态贴纸拆条** | 动态贴纸之后另起消息，确保后续正文按顺序送达；经典小黄脸保持文内混排 |
| **多实例隔离** | 目录、协议端能力和缓存按 AstrBot 平台实例隔离；QQ 表情流程仅处理 OneBot QQ 平台实例 |
| **内容保护** | 代码块和行内代码保持原文，未知标记按字面显示，所有已识别的标记均按顺序转换 |

## 支持平台

| AstrBot 平台或协议端 | 发送方式 | 目录策略 |
| --- | --- | --- |
| SnowLuma / aiocqhttp | OneBot 原生 `Face` | 支持动态目录、缓存和动态贴纸拆条 |
| NapCat、LL OneBot、Lagrange、go-cqhttp / aiocqhttp | OneBot 原生 `Face` | 使用内置目录；协议端支持时自动更新 |
| 其他 OneBot QQ fork | OneBot 原生 `Face` | 通过 `fetch_sys_faces` 验证后启用，也可按实例覆盖 |
| 其他 AstrBot 平台 | 跳过 | 提示词与消息保持原样 |

## 安装

要求 AstrBot 4.24.1 或更高版本。运行时仅使用 AstrBot 与 Python 标准库。

在 AstrBot WebUI 的插件市场搜索 **QQ 大黄脸**，安装并启用。

## 使用

主命令为 `/表情`，英文别名为 `/face`。

### 手动发送

```text
/表情 微笑
/表情 send 捂脸
/表情 264
```

### 查询目录与状态

```text
/表情 list
/表情 list 菜
/表情 status
```

### 自然对话

插件在临时请求内容中提供简短语法提示，人设与聊天历史保持原样。模型可以在适合语境时写出：

```text
这个方案听起来不错 <face:点赞>
```

会话最终收到文本和原生 `Face` 组件。

## 配置

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_inbound` | 布尔值 | `true` | 理解收到的 OneBot QQ 表情并保留位置 |
| `platform_overrides` | JSON 对象文本 | 空对象 | 平台实例覆盖，值为 `auto`、`enabled` 或 `disabled` |
| `face_aliases` | JSON 对象文本 | 空对象 | 自定义「别名 → 规范名或数字 ID」映射 |
| `prompt_face_names` | 字符串列表 | 内置推荐名单 | 向模型推荐的表情名或别名 |

两个 JSON 配置均在 WebUI 中以文本填写，例如：

```json
{
  "qq-main": "enabled"
}
```

```json
{
  "坏笑": "斜眼笑"
}
```

## 数据与隐私

动态目录缓存保存在 AstrBot 的 `data/plugin_data/qq_face/catalogs/`。缓存内容仅限公开表情元数据，文件名是平台实例 ID 的 SHA-256 摘要。

表情理解使用当前会话已经配置的模型；动态目录只向当前 OneBot 协议端请求 `fetch_sys_faces`。

## 开发检查

在可导入 AstrBot 的 Python 环境中运行：

```powershell
ruff format --check .
ruff check .
python -m pytest
```

测试覆盖目录解析与缓存、实例隔离、平台避让、入站顺序、代码保护、动态贴纸拆条和发送幂等性。

## 许可证

[MIT](LICENSE)

本项目是由 OMSociety 维护的第三方 AstrBot 插件。AstrBot、QQ 及相关角色和表情的权利归各自权利人所有。
