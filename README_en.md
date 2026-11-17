<p align="center"><a href="README.md">中文</a> · <strong>English</strong></p>

<div align="center">

<h1><img src="https://raw.githubusercontent.com/OMSociety/astrbot_plugin_qq_face/main/logo.png" width="192" alt="QQ Yellow Faces logo"><br>QQ Yellow Faces</h1>

**Read and send native OneBot QQ faces naturally** — dynamic catalogs · instance isolation · animated-sticker splitting

[![Version](https://img.shields.io/github/v/tag/OMSociety/astrbot_plugin_qq_face?label=version&color=4c8bf5)](https://github.com/OMSociety/astrbot_plugin_qq_face/releases)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4.24.1-6c5ce7)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-2da44e)](LICENSE)
[![Stars](https://img.shields.io/github/stars/OMSociety/astrbot_plugin_qq_face)](https://github.com/OMSociety/astrbot_plugin_qq_face/stargazers)
[![Issues](https://img.shields.io/github/issues/OMSociety/astrbot_plugin_qq_face)](https://github.com/OMSociety/astrbot_plugin_qq_face/issues)

</div>

## Features

| Feature | Description |
| --- | --- |
| **Native sending** | The model naturally writes `<face:name>` in a reply, and the plugin converts it to a OneBot `Face` before sending |
| **Inbound understanding** | Annotates received `Face` components as `[QQ表情:name]` in their original order so the model can understand where each face belongs |
| **Dynamic catalogs** | Endpoints supporting `fetch_sys_faces` update their catalogs independently per platform instance. The bundled catalog contains 294 unique numeric faces, and the last good cache remains available after a refresh failure |
| **Animated-sticker splitting** | Text following an animated sticker is sent in a separate message so the endpoint delivers the text in order. Classic yellow faces remain inline |
| **Instance isolation** | Catalogs, endpoint capabilities, and caches are isolated by AstrBot platform instance. The QQ face flow handles OneBot QQ platform instances |
| **Content protection** | Fenced blocks and inline code stay verbatim, unknown markers appear literally, and every recognized marker is converted in order |

## Supported platforms

| AstrBot platform or endpoint | Sending method | Catalog policy |
| --- | --- | --- |
| SnowLuma / aiocqhttp | Native OneBot `Face` | Dynamic catalog, cache, and animated-sticker splitting |
| NapCat, LL OneBot, Lagrange, go-cqhttp / aiocqhttp | Native OneBot `Face` | Bundled catalog with automatic updates when supported |
| Other OneBot QQ forks | Native OneBot `Face` | Enabled after `fetch_sys_faces` capability verification, or by instance override |
| Other AstrBot platforms | Skipped | Prompts and messages stay intact |

## Installation

AstrBot 4.24.1 or later is required. Runtime uses AstrBot and the Python standard library.

Search for **QQ Yellow Faces** in the AstrBot WebUI plugin market, then install and enable it.

## Usage

The primary command is `/表情`, with `/face` as its English alias.

### Send manually

```text
/表情 微笑
/表情 send 捂脸
/表情 264
```

### Inspect the catalog and status

```text
/表情 list
/表情 list 菜
/表情 status
```

### Natural conversation

The plugin adds a short syntax hint to the temporary request content while the persona and chat history stay intact. The model can write a marker when it fits the conversation:

```text
That sounds good <face:点赞>
```

The conversation receives text and a native `Face` component.

## Configuration

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `enable_inbound` | Boolean | `true` | Understand received OneBot QQ faces while preserving their positions |
| `platform_overrides` | JSON object text | Empty object | Per-instance `auto`, `enabled`, or `disabled` override |
| `face_aliases` | JSON object text | Empty object | Custom alias-to-canonical-name or numeric-ID mapping |
| `prompt_face_names` | String list | Built-in recommendation list | Face names or aliases recommended to the model |

Both JSON settings are entered as text in the WebUI, for example:

```json
{
  "qq-main": "enabled"
}
```

```json
{
  "smirk": "斜眼笑"
}
```

## Data and privacy

Dynamic-catalog caches are stored in AstrBot's `data/plugin_data/qq_face/catalogs/`. Their content is limited to public face metadata, and filenames are SHA-256 digests of platform instance IDs.

Face understanding uses the model already configured for the conversation. Dynamic-catalog refreshes only call `fetch_sys_faces` on the current OneBot endpoint.

## Development checks

Run these commands in a Python environment where AstrBot can be imported:

```powershell
ruff format --check .
ruff check .
python -m pytest
```

Tests cover catalog parsing and caching, instance isolation, platform avoidance, inbound ordering, code protection, animated-sticker splitting, and send idempotency.

## License

[MIT](LICENSE)

This third-party AstrBot plugin is maintained by OMSociety. AstrBot, QQ, and the related characters and faces belong to their respective rights holders.
