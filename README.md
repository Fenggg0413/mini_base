# mini_base

一个迷你关系型数据库系统，用 Python 实现了关系数据库的核心环节：模式管理、记录存储、SQL 解析与执行、索引以及基于日志的事务持久化。适合用来理解数据库内部是如何把一条 SQL 变成磁盘上的字节的。

## 功能

通过交互式菜单提供以下操作：

| 选项 | 功能 |
|------|------|
| 1 | 新建表结构并录入数据 |
| 2 | 删除指定表（结构 + 数据） |
| 3 | 查看表结构及全部数据 |
| 4 | 删除所有表 |
| 5 | 执行 `SELECT ... FROM ... [WHERE ...]` 查询 |
| 6 | 按字段关键字删除一行 |
| 7 | 按字段关键字更新一行 |
| 8 / 9 | 开启 / 提交事务 |

底层特性：

- **存储引擎**：每张表存为独立的 `表名.dat` 文件，按 4KB 块组织，块 0 存元信息与字段定义。
- **SQL 解析**：基于 [PLY](https://www.dabeaz.com/ply/) 的词法（`lex_db`）与语法（`parser_db`）分析，生成逻辑查询计划（`query_plan_db`）。
- **事务持久化**：前像 / 后像日志（`before_image.log` / `after_image.log`），支持崩溃后重做恢复。
- **索引**：`index_db` 提供索引文件（`.ind`）的雏形。

## 目录结构

```
mini_base/
├── src/                 # 数据库引擎
│   ├── main_db.py       # 程序入口与主菜单
│   ├── common_db.py     # 全局常量、数据路径（DATA_DIR / data_path）
│   ├── schema_db.py     # 模式管理（all.sch）
│   ├── head_db.py       # 模式的内存结构
│   ├── storage_db.py    # 记录存储引擎（*.dat）
│   ├── index_db.py      # 索引（*.ind）
│   ├── transaction_db.py# 事务与日志恢复
│   ├── lex_db.py        # SQL 词法分析
│   ├── parser_db.py     # SQL 语法分析
│   └── query_plan_db.py # 查询计划构建与执行
├── tests/               # 测试脚本
├── data/                # 运行数据：*.dat 表文件、all.sch 模式、*.log 日志
└── docs/                # 原始文档
```

所有数据文件统一存放在 `data/` 目录，由 `common_db.DATA_DIR` 定位，与运行时所在目录无关。

## 环境与运行

需要 Python 3.x，依赖 PLY：

```bash
pip install ply
```

从项目根目录以模块方式启动：

```bash
python -m src.main_db
```

`data/` 目录已附带示例表 `courses`、`students`、`takes`、`test`，启动后可直接用选项 3 或 5 查看 / 查询。

## 测试

```bash
python -m tests.test_db
python -m tests.test_transaction
```

