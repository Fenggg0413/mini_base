# 项目快速回忆框架（聚焦事务持久化与存储管理）

## 0. 目标与边界
- 目标：在最短时间内重新建立你对项目的工程级理解，能独立定位并修改事务持久化与存储管理逻辑。
- 边界：本框架刻意跳过 SQL 词法/语法解析模块（`lex_db.py`、`parser_db.py`、`query_plan_db.py`）。

---

## 1. 先建立全局心智图（15 分钟）
按下面顺序只看“职责”，先不深挖实现。

1. 入口与交互
- `main_db.py`：主菜单、事务开始/提交入口、调用存储层。

2. 事务层
- `transaction_db.py`：事务状态表、前像/后像日志、崩溃恢复（分析/重做/撤销）。

3. 存储层
- `storage_db.py`：`.dat` 文件页结构、记录插入/更新/删除、事务日志钩子。

4. 模式层（存储元数据）
- `schema_db.py` + `head_db.py`：`all.sch` 中表结构元数据的内存镜像与持久化。

5. 公共状态
- `common_db.py`：`BLOCK_SIZE`、`current_transaction_id`。

6. 验证脚本
- `test_transaction.py`：事务插入/更新与崩溃恢复演练。
- `test_db.py`：schema 增删改查演练。

---

## 2. 关键调用链（你要先背熟的）

### 2.1 事务主链
1. 启动系统
- `main_db.py` 启动时调用 `transaction_db.get_transaction_manager()`，构造事务管理器并触发恢复。

2. 开始事务
- 菜单 8 -> `begin_transaction()` -> `common_db.current_transaction_id = txn_id`。

3. 数据写入（同一事务中）
- 插入：`Storage.insert_record(..., txn_id)` -> `log_after_image()` -> 写 `.dat`。
- 更新：`Storage.update_record(..., txn_id)` -> `log_before_image()` -> 改页 -> `log_after_image()` -> 写 `.dat`。

4. 提交事务
- 菜单 9 -> `commit_transaction(txn_id)` -> 记录 `TXN_STATUS` 提交状态并 flush 日志。

5. 崩溃后恢复
- `TransactionManager.__init__` -> `_recover_transactions()`
  - 分析阶段：识别已提交/未完成事务。
  - 重做阶段：根据后像重放已提交事务。
  - 撤销阶段：根据前像回滚未提交事务。

### 2.2 存储主链
1. `Storage.__init__` 读取 `.dat` 的 block0 元信息与各数据块，构建 `record_list` / `record_Position`。
2. `insert_record` 计算目标 block/offset，更新 block 头、offset 表、记录区。
3. `update_record` 定位目标记录偏移，原地更新记录内容。
4. `delete_record` 走“内存删除 + 全块重写”的策略。

---

## 3. 三轮回忆法（60~120 分钟）

## 第一轮：结构回忆（20~30 分钟）
只回答这 6 个问题（不看细节代码）：
1. 事务 ID 在哪里生成、在哪里保存？
2. 提交状态写入了哪些文件？
3. insert 和 update 的 WAL 行为有什么差异？
4. 存储层如何从 `record index` 算出 `block_id + offset`？
5. 崩溃恢复重做和撤销分别依赖哪份日志？
6. schema 元数据写在哪个文件，结构分几段？

## 第二轮：调用链回忆（30~40 分钟）
跟一条真实路径逐函数跳转：
1. 菜单 8 开事务。
2. 插入 1 条记录（带 txn_id）。
3. 更新 1 条记录（带 txn_id）。
4. 菜单 9 提交。
5. 重启程序观察恢复打印。

目标：你能口述“每一步写了哪个文件的哪类信息”。

## 第三轮：故障回忆（30~50 分钟）
用 `test_transaction.py` 做 2 组实验：
1. 未提交前崩溃：预期恢复后撤销。
2. 提交后崩溃：预期恢复后重做保持。

每组实验记录：事务号、日志增长、数据文件变化、恢复输出。

---

## 4. 模块级阅读顺序（精确到函数）

### 4.1 事务模块：`transaction_db.py`
按这个顺序看：
1. `__init__`：日志句柄、大小、恢复入口。
2. `begin_transaction` / `commit_transaction` / `abort_transaction`。
3. `log_before_image` / `log_after_image`：日志记录格式（header + payload）。
4. `_recover_transactions`：分析阶段核心。
5. `_redo_committed_transactions`：后像重放。
6. `_undo_uncommitted_transactions`：前像回滚。
7. `_write_record_to_file`：最终物理写入。

### 4.2 存储模块：`storage_db.py`
按这个顺序看：
1. `__init__`：block0 + data block 装载。
2. `insert_record`：记录布局与写页流程。
3. `update_record`：定位偏移、前像/后像时机。
4. `delete_record`：重排 `record_Position` 与块重写。
5. `insert_records_from_input`：与 `current_transaction_id` 的耦合点。

### 4.3 schema 模块：`schema_db.py`
按这个顺序看：
1. `__init__`：`all.sch` 的 meta/head/body 解析。
2. `appendTable`：写表头 + 字段段。
3. `delete_table_schema` / `WriteBuff`：删除后偏移重算。

---

## 5. 你负责模块的“记忆锚点”（建议贴在工位）

1. 日志规则
- update: 先前像再写数据，再后像。
- insert: 仅后像（当前实现策略）。

2. 关键文件
- 事务日志：`before_image.log`、`after_image.log`
- 数据文件：`<table>.dat`
- 模式文件：`all.sch`

3. 全局状态
- 当前事务号：`common_db.current_transaction_id`

4. 恢复三件事
- 找到已提交事务集合。
- 重做已提交后像。
- 撤销未提交前像。

---

## 6. 一页检查清单（改代码前后都跑一遍）

### 改动前
1. 我是否明确改动影响的是 insert/update/delete 哪条路径？
2. 我是否确认了 txn_id 传递链不断裂？
3. 我是否知道这次改动会改变哪些持久化文件？

### 改动后
1. 无事务下，原功能行为不回归。
2. 有事务下，日志写入顺序符合预期。
3. 提交后重启，已提交修改能重做。
4. 未提交崩溃后重启，修改能撤销。
5. `all.sch` 与 `<table>.dat` 的元数据一致。

---

## 7. 你可以直接执行的回忆流程（最短 30 分钟版）
1. 读 `main_db.py` 里菜单 8/9 与更新路径（10 分钟）。
2. 读 `storage_db.py` 的 `insert_record`、`update_record`（10 分钟）。
3. 读 `transaction_db.py` 的日志与恢复函数（10 分钟）。
4. 运行 `test_transaction.py` 做一次“提交后恢复”演练（可选加时）。

完成标准：你能在白纸上画出“事务 API -> 日志 -> 数据页 -> 崩溃恢复”的闭环。
