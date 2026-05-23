# mini_base

基于南京邮电大学数据库系统课程实现的一个迷你关系型数据库系统，用 Python 实现了关系数据库的核心环节：模式管理、记录存储、SQL 解析与执行、B+ 树索引以及基于日志的事务持久化。

## 功能

提供 SQL REPL（Read-Eval-Print Loop）命令行交互，支持以下 SQL 语句：

| SQL 语句 | 说明 |
|----------|------|
| `CREATE TABLE table (col_def, ...)` | 创建表 |
| `DROP TABLE table` | 删除表（含数据 + 索引） |
| `INSERT INTO table [(cols)] VALUES (vals)` | 插入记录 |
| `SELECT ... FROM ... [WHERE ...] [ORDER BY ...]` | 查询（自动使用 B+ 树索引加速） |
| `UPDATE table SET col=val [WHERE ...]` | 更新记录 |
| `DELETE FROM table [WHERE ...]` | 删除记录 |
| `BEGIN [TRANSACTION]` / `COMMIT` / `ROLLBACK` | 事务控制 |
| `CREATE INDEX ON table(field)` | 创建 B+ 树索引 |
| `DROP INDEX ON table(field)` | 删除索引 |
| `SHOW TABLES` | 列出所有表 |
| `SHOW INDEX [FROM table]` | 查看索引 |
| `DESCRIBE table` | 查看表结构 |

Dot-commands: `.help` / `.quit`

## 目录结构

```
mini_base/
├── src/                    # 数据库引擎
│   ├── main_db.py          # SQL REPL 入口
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
│   ├── test_index_integration.py  # 索引集成测试（目录、删除）
│   ├── test_sql.py            # SQL 解析与执行测试（CRUD、WHERE、ORDER BY）
│   └── test_sql_extended.py   # 扩展 SQL 测试（事务、索引、REPL）
└── docs/                   # 原始文档
```

所有数据文件统一存放在 `data/` 目录，由 `common_db.DATA_DIR` 定位，与运行时所在目录无关。

## 环境与运行

需要 Python 3.x，依赖 PLY：

```bash
pip install ply
```

从项目根目录安装后直接启动：

```bash
pip install -e .
mini-base
```

也可用模块方式启动：`python -m src.main_db`

启动后进入 `mini_base>` 提示符，直接输入 SQL 语句或 dot-commands。

## 使用示例

```
mini_base> CREATE TABLE students (name str(10), age int, active bool);
mini_base> INSERT INTO students VALUES ('Alice', 20, '1');
mini_base> INSERT INTO students VALUES ('Bob', 22, '0');
mini_base> SELECT * FROM students;
mini_base> SELECT * FROM students WHERE age > 20;
mini_base> UPDATE students SET age = 23 WHERE name = 'Bob';
mini_base> DELETE FROM students WHERE name = 'Alice';

mini_base> BEGIN;
mini_base> INSERT INTO students VALUES ('Carol', 19, '1');
mini_base> COMMIT;

mini_base> CREATE INDEX ON students(age);
mini_base> SHOW INDEX FROM students;
mini_base> DESCRIBE students;
mini_base> SHOW TABLES;

mini_base> DROP INDEX ON students(age);
mini_base> DROP TABLE students;
mini_base> .quit
```

WHERE 子句支持 `=`, `!=`, `<`, `>`, `<=`, `>=`，`AND`/`OR`/`NOT` 以及括号分组，ORDER BY 支持 `ASC`/`DESC`。

## 测试

```bash
python -m pytest tests/ -v                           # 全部测试（141 个）
python -m pytest tests/test_index_db.py -v           # B+ 树核心测试
python -m pytest tests/test_index_integration.py -v  # 索引集成测试
python -m pytest tests/test_sql.py -v                # SQL 解析与执行测试
python -m pytest tests/test_sql_extended.py -v       # 扩展 SQL 测试
```
