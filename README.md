# Termi Word

一个专为终端设计的极简背单词工具，基于 Textual TUI 框架，支持 FSRS 科学复习算法。

## 特性

- **终端原生** - 完全在终端中运行，无需浏览器或图形界面
- **科学复习** - 基于 FSRS 算法的间隔重复系统
- **键盘优先** - 所有操作均可通过键盘完成
- **离线运行** - 本地 SQLite 数据库，无需网络
- **多词书支持** - 支持导入和切换不同词书
- **拼写练习** - 听音拼写，强化记忆
- **学习日历** - 可视化学习进度

## 快捷键

### 全局快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+/` | 打开全局搜索 |
| `Ctrl+Z` | 退出应用 |
| `Esc` | 返回上一级 / 双击退出 |

### 主页面

| 快捷键 | 功能 |
|--------|------|
| `1` | 开始学习（新词+复习） |
| `2` | 仅复习 |
| `4` | 拼写练习 |
| `5` | 搜索单词 |
| `6` | 学习日历 |
| `7` | 设置 |
| `8` | 导入词书 |

### 学习/复习页面

| 快捷键 | 功能 |
|--------|------|
| `1` | 陌生 |
| `2` | 熟悉 |
| `3` | 记得 |
| `4` | 掌握 |
| `s` | 跳过当前词 |
| `Enter` | 确认评分 / 翻卡 |
| `Esc` | 返回主页面 |

### 搜索页面

| 快捷键 | 功能 |
|--------|------|
| `↑` `↓` | 选择单词 |
| `Enter` / `Space` | 查看单词详情 |
| `Backspace` | 删除搜索字符 |
| `Esc` | 返回 / 退出详情 |

### 设置页面

| 快捷键 | 功能 |
|--------|------|
| `↑` `↓` | 选择设置项 |
| `Enter` / `Space` | 编辑/切换 |
| `Esc` | 返回 / 取消编辑 |

## 配置说明

配置文件位于 `data/ui_config.json`，包含以下选项：

```json
{
  "active_deck": "IELTSluan_2",
  "daily_new_target": 20,
  "review_soft_limit": 50,
  "daily_spelling_target": 15,
  "spelling_enabled": true,
  "search_shortcut": "ctrl+slash",
  "panel_max_width": 120,
  "panel_min_height": 6,
  "panel_max_height": 16
}
```

- `active_deck` - 当前使用的词书名称
- `daily_new_target` - 每日学习新词数量
- `review_soft_limit` - 每日复习软上限
- `daily_spelling_target` - 每日拼写练习数量
- `spelling_enabled` - 是否启用拼写练习
- `search_shortcut` - 全局搜索快捷键（默认 `ctrl+slash`，即 `Ctrl+/`，可在设置中修改）
- `panel_max_width` - 面板最大宽度（默认 120，最小 20）
- `panel_min_height` - 面板最小高度（默认 6，范围 3-16）
- `panel_max_height` - 面板最大高度（默认 16，范围 6-16）

### 支持的搜索快捷键

| 配置值 | 显示 |
|--------|------|
| `ctrl+slash` | Ctrl+/ |
| `ctrl+p` | Ctrl+P |
| `ctrl+f` | Ctrl+F |
| `ctrl+k` | Ctrl+K |
| `ctrl+s` | Ctrl+S |
| `ctrl+q` | Ctrl+Q |

## 词书格式

词书使用 CSV 格式，必须包含以下字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| `w` | 单词 | abandon |
| `c` | 词性 | v. |
| `zh` | 中文释义 | 放弃；抛弃 |
| `en` | 英文释义 | to leave behind |
| `us` | 美式发音 | /əˈbændən/ |
| `core` | 核心词标记 | 1 |
| `ex` | 例句 | He abandoned his car in the snow. |
| `exz` | 例句翻译 | 他把车丢弃在雪地里。 |

### 导入词书

1. 将 CSV 文件放入 `data/` 目录
2. 文件名即为词书名称（如 `IELTSluan_2.csv`）
3. 启动应用时会自动导入选中的词书
4. 默认导入全部行

### 更新词书内容

如需修正词书中的错误：

1. 直接修改对应的 CSV 文件
2. 重新启动应用
3. 已存在的单词会被更新，不会修改学习记录（复习进度、评分等）

## 数据来源

- 雅思 3400 核心词: [GitHub](https://github.com/kajweb/dict/blob/master/book/1521164624473_IELTSluan_2.zip)
- 基础简单单词 850 词: [ogden.munch.love](https://ogden.munch.love/)

## 安装与运行

```bash
# 克隆项目
git clone <repository-url>
cd termi_word

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirments.txt

# 运行
python -m termi_word
```

## 项目结构

```
termi_word/
├── app.py              # 应用入口
├── config.py           # 配置常量
├── ui.py               # UI 工具函数
├── database/           # 数据库相关
│   ├── models.py       # 数据模型
│   └── repositories.py # 数据仓库
├── screens/            # 页面
│   ├── today.py        # 主页面
│   ├── review.py       # 学习/复习页面
│   ├── search.py       # 搜索页面
│   ├── settings.py     # 设置页面
│   ├── spelling.py     # 拼写练习
│   ├── calendar.py     # 学习日历
│   ├── word_detail.py  # 单词详情
│   └── import_panel.py # 导入面板
├── services/           # 业务逻辑
│   ├── config_service.py
│   ├── import_service.py
│   ├── search_service.py
│   ├── spelling_service.py
│   └── study_service.py
└── styles/             # 样式文件
    └── app.tcss
```

## 设计理念

- **克制优先** - 界面元素尽可能少，只展示必要信息
- **键盘至上** - 所有操作均可通过键盘完成
- **信息密度平衡** - 总高度严格控制在 6-16 行
- **终端低饱和美学** - 低饱和、低调克制，融入终端环境

## License

MIT
