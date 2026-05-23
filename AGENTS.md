# AGENTS.md

## Project overview

mini_base is an educational miniature relational DBMS in Python. It implements schema management, page-based record storage, full SQL parsing (SELECT/INSERT/UPDATE/DELETE/CREATE/DROP + transactions + indexes), B+ tree indexes with query acceleration, and log-based transaction recovery. Not production software — a course project for understanding database internals.

## Running

```bash
python3 -m src.main_db          # SQL REPL
```

Run from the project root directory. Starts a SQL REPL (mini_base> prompt). Creates/reads data files in `data/` (auto-created by `common_db.DATA_DIR`).

## Testing

```bash
python3 -m pytest tests/ -v                       # full test suite (141 tests)
```

Key test files:
| File | Coverage |
|------|----------|
| `tests/test_index_db.py` | B+ tree core (insert, split, search) |
| `tests/test_index_integration.py` | Index catalog + delete entry |
| `tests/test_sql.py` | SQL parser + execution (CRUD, WHERE, ORDER BY) |
| `tests/test_sql_extended.py` | Extended SQL (BEGIN/COMMIT/ROLLBACK, CREATE/DROP INDEX, SHOW/DESCRIBE, REPL) |

The interactive scripts `tests/test_db.py` and `tests/test_transaction.py` call `input()` and will hang under pytest capture — mock `builtins.input` if you need to test them programmatically.

### Testing the index module

`test_index_db.py` uses `monkeypatch` on `common_db.DATA_DIR` to redirect `.ind` files to `tmp_path`. When writing new index tests, always:

1. Use the `fresh_index` or `idx` fixtures (they handle `monkeypatch` and cleanup).
2. For split/root-split tests, set `monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)` — 200 is too large for tests.
3. Don't try to instantiate `Storage` in pytest — its `__init__` calls `input()`. Integration tests needing storage must mock that.

## Architecture

### Module dependency graph

```
main_db → schema_db → head_db
        → storage_db → common_db
        → query_plan_db → storage_db, common_db, index_db, index_catalog, transaction_db
        → transaction_db → common_db
        → lex_db / parser_db → common_db
        → index_db → common_db
```

Key fact: `index_db` is fully implemented (insert, search, leaf/internal split, create_index) and integrated with the query engine via `query_plan_db.execute_select` (index-accelerated lookups on indexed fields with simple equality WHERE). `transaction_db` is also integrated via `query_plan_db.execute_begin_transaction/commit/rollback`.

### Data files

All runtime data lives in `data/`, resolved via `common_db.DATA_DIR` (an absolute path computed from `src/` package location, **not** `os.getcwd()`):

| File | Format | Purpose |
|------|--------|---------|
| `all.sch` | Binary, custom | Table schema definitions |
| `*.dat` | Binary, 4KB-blocks | Table records (block 0 = header) |
| `*.ind` | Binary, 4KB-blocks | B+ tree indexes (block 0 = meta) |
| `before_image.log` | Binary | Transaction before-images |
| `after_image.log` | Binary | Transaction after-images |

### Binary format constraints

- All on-disk data uses `struct.pack` with `!` (network/big-endian) byte order.
- Field names and keys are fixed 10-byte strings (`!10s`) — must be `bytes`, not `str`. Use `.encode('utf-8').ljust(10)` or `index_db._format_key()`.
- Block size is `common_db.BLOCK_SIZE = 4096`.

## Known issues & gotchas

1. **`Storage.__init__` calls `input()`** when a `.dat` file doesn't exist — it prompts for field count and names interactively. This makes it impossible to use in non-interactive contexts without mocking `builtins.input`.

2. **Transaction recovery is incomplete**: `begin_transaction()` doesn't write ACTIVE status to the log, so crashed uncommitted transactions can't be reliably identified. `delete_record()` has no transaction logging at all. `insert_record()` logs only after-images (no before-images), so undo is incomplete.

3. **Schema file `all.sch` is shared global state**: `Schema()` opens it exclusively. Tests that create/drop tables must clean up `data/all.sch` or use isolated temp directories.

4. **`common_db.py:27` comment references `yacc_db`** — the actual module is `parser_db`. Stale comment, not a bug.

## Conventions

- Python 3.8+ (used `|` union syntax is absent; f-strings are used).
- No type stubs, no linter config, no CI. Run `python3 -m pytest` manually to verify.
- Chinese comments and print messages are the norm — don't "translate" them.
- `struct.pack_into` / `struct.unpack_from` with explicit offsets — no memory-mapped I/O.