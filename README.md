# mini_base

一个迷你关系型数据库系统，用 Python 实现了关系数据库的核心环节：模式管理、记录存储、SQL 解析与执行、B+ 树索引以及基于日志的事务持久化。适合用来理解数据库内部是如何把一条 SQL 变成磁盘上的字节的。

## 功能

通过交互式菜单提供以下操作：

| 选项 | 功能 |
|------|------|
| 1 | 新建表结构并录入数据 |
| 2 | 删除指定表（结构 + 数据 + 索引） |
| 3 | 查看表结构及全部数据 |
| 4 | 删除所有表 |
| 5 | 执行 `SELECT ... FROM ... [WHERE ...]` 查询（自动使用索引加速） |
| 6 | 按字段关键字删除一行 |
| 7 | 按字段关键字更新一行 |
| 8 / 9 / 10 | 开启 / 提交 / 终止事务 |
| 11 | 在表的指定字段上创建 B+ 树索引 |
| 12 | 删除指定索引 |
| 13 | 查看所有已建索引 |

底层特性：

- **存储引擎**：每张表存为独立的 `表名.dat` 文件，按 4KB 块组织，块 0 存元信息与字段定义。
- **SQL 解析**：基于 [PLY](https://www.dabeaz.com/ply/) 的词法（`lex_db`）与语法（`parser_db`）分析，生成逻辑查询计划（`query_plan_db`）。
- **索引**：`index_db` 实现完整的 B+ 树索引（插入、搜索、删除、叶节点/内部节点分裂）。索引通过 `index_catalog` 管理目录，自动在插入/删除/更新时维护，并在等值查询时加速 SELECT。
- **事务持久化**：前像 / 后像日志（`before_image.log` / `after_image.log`），支持崩溃后重做恢复。

## 目录结构

```
mini_base/
├── src/                    # 数据库引擎
│   ├── main_db.py          # 程序入口与主菜单
│   ├── common_db.py        # 全局常量、数据路径（DATA_DIR / data_path）
│   ├── schema_db.py        # 模式管理（all.sch）
│   ├── head_db.py          # 模式的内存结构
│   ├── storage_db.py        # 记录存储引擎（*.dat），含索引自动维护
│   ├── index_db.py         # B+ 树索引实现（*.ind）
│   ├── index_catalog.py    # 索引目录管理（index.cat）
│   ├── transaction_db.py   # 事务与日志恢复
│   ├── lex_db.py           # SQL 词法分析
│   ├── parser_db.py        # SQL 语法分析
│   └── query_plan_db.py    # 查询计划构建与执行（含索引加速）
├── tests/                  # 测试脚本
│   ├── test_index_db.py       # B+ 树核心测试
│   └── test_index_integration.py  # 索引集成测试（目录、删除、加速）
├── data/                   # 运行数据：*.dat / *.ind / all.sch / *.log / index.cat
└── docs/                   # 原始文档
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

## 索引使用示例

```
选项 11 → 创建索引
  表名: students
  字段名: sid

选项 5 → 索引加速查询
  SELECT * FROM students WHERE sid = 's001'
  （自动检测 WHERE 条件中的索引字段，走 B+ 树查找而非全表扫描）

选项 13 → 查看所有索引
  students.sid

选项 12 → 删除索引
  表名: students
  字段名: sid
```

## 测试

```bash
python -m pytest tests/test_index_db.py -v          # B+ 树核心测试
python -m pytest tests/test_index_integration.py -v  # 索引集成测试
python -m pytest tests/ -v                           # 全部测试
```

注意：`test_db` 和 `test_transaction` 为交互式脚本，会调用 `input()`，不适合在 pytest 中运行。