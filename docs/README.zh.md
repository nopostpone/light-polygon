# light-polygon

[English](../README.md)

一个轻量级的算法竞赛出题工具，灵感来自 [Codeforces Polygon](https://polygon.codeforces.com/)。

完全离线，所有数据存储在本地。适合个人出题人或小团队使用。

> **注意：本项目尚未发布到 PyPI，目前只能从源码安装。**

## 安装

```bash
git clone https://github.com/nopostpone/light-polygon.git
cd light-polygon
pip install -e .
```

## 快速开始

```bash
# 1. 注册账号
lp user register alice

# 2. 登录
lp user login alice

# 3. 创建一道题
lp problem create two-sum --title "两数之和" --tl 2000 --ml 512

# 4. 写题面（Markdown，支持 LaTeX 数学公式）
lp statement edit two-sum

# 5. 上传参考答案
lp solution add two-sum solve.cpp --tag AC

# 6. 添加测试数据
lp test add two-sum --input 1.in --answer 1.out --sample --desc "样例 1"

# 7. 评测
lp judge run two-sum

# 8. 导出题面
lp statement export two-sum --format html
```

## 功能

- **用户管理** — 多用户注册登录，数据隔离
- **题目管理** — 创建、编辑、删除题目，设置时空限制
- **题面编辑** — Markdown + LaTeX 数学公式，导出 HTML / LaTeX
- **答案管理** — 上传多个参考答案，标记 AC / WA / TLE 等
- **测试数据** — 手工添加或 C++ 生成器自动批量生成（基于 testlib.h）
- **输入校验** — 可选的 validator.cpp 检查生成数据正确性
- **评测引擎** — 沙箱运行所有答案，对比输出，出评测报告
- **打包导出** — 一键打包为 zip，支持 Polygon 兼容格式

## 命令一览

| 命令 | 说明 |
|------|------|
| `lp user register/list/login/logout/whoami` | 用户管理 |
| `lp problem create/list/info/edit/delete` | 题目管理 |
| `lp statement edit/preview/export` | 题面编辑与导出 |
| `lp solution add/list/delete/tag` | 答案管理 |
| `lp test add/list/delete/sample` | 测试数据管理 |
| `lp test gen-config/generate` | 测试数据自动生成 |
| `lp judge run/history` | 评测 |
| `lp export package` | 打包导出 |

## 许可

MIT
