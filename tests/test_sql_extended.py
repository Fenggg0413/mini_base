"""
test_sql_extended.py — TDD tests for extended SQL statements:
  BEGIN/COMMIT/ROLLBACK, CREATE INDEX, DROP INDEX,
  SHOW TABLES, SHOW INDEX, DESCRIBE, and REPL.
"""

import os
import io
import pytest
from unittest.mock import patch

from src import common_db, lex_db, parser_db, query_plan_db, storage_db, schema_db


# ─────── Fixtures ───────

@pytest.fixture(autouse=True)
def setup_parser():
    lex_db.set_lex_handle()
    parser_db.set_handle()


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Redirect DATA_DIR and Schema.fileName to tmp_path."""
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(schema_db.Schema, 'fileName', str(tmp_path / 'all.sch'))
    os.makedirs(str(tmp_path), exist_ok=True)
    if not os.path.exists(str(tmp_path / 'all.sch')):
        with open(str(tmp_path / 'all.sch'), 'wb') as f:
            pass
    yield tmp_path


@pytest.fixture
def test_table(tmp_data):
    """Create a test table 'students' with fields: name(str 20), age(int 10), grade(str 2)."""
    field_list = [
        ('name', 0, 20),
        ('age', 2, 10),
        ('grade', 0, 2),
    ]
    storage = storage_db.Storage.create_table('students', field_list)
    schema_obj = schema_db.Schema()
    schema_obj.appendTable('students', storage.getFieldList())
    del storage
    del schema_obj
    return tmp_data


# ─────── Cycle 1: Lexer Tests ───────

class TestExtendedLexer:
    def setup_method(self):
        lex_db.set_lex_handle()

    def test_begin_token(self):
        lexer = common_db.global_lexer
        lexer.input("BEGIN")
        tokens = [tok.type for tok in lexer]
        assert 'BEGIN' in tokens

    def test_commit_token(self):
        lexer = common_db.global_lexer
        lexer.input("COMMIT")
        tokens = [tok.type for tok in lexer]
        assert 'COMMIT' in tokens

    def test_rollback_token(self):
        lexer = common_db.global_lexer
        lexer.input("ROLLBACK")
        tokens = [tok.type for tok in lexer]
        assert 'ROLLBACK' in tokens

    def test_transaction_token(self):
        lexer = common_db.global_lexer
        lexer.input("TRANSACTION")
        tokens = [tok.type for tok in lexer]
        assert 'TRANSACTION' in tokens

    def test_index_token(self):
        lexer = common_db.global_lexer
        lexer.input("INDEX")
        tokens = [tok.type for tok in lexer]
        assert 'INDEX' in tokens

    def test_on_token(self):
        lexer = common_db.global_lexer
        lexer.input("ON")
        tokens = [tok.type for tok in lexer]
        assert 'ON' in tokens

    def test_show_token(self):
        lexer = common_db.global_lexer
        lexer.input("SHOW")
        tokens = [tok.type for tok in lexer]
        assert 'SHOW' in tokens

    def test_tables_token(self):
        lexer = common_db.global_lexer
        lexer.input("TABLES")
        tokens = [tok.type for tok in lexer]
        assert 'TABLES' in tokens

    def test_describe_token(self):
        lexer = common_db.global_lexer
        lexer.input("DESCRIBE")
        tokens = [tok.type for tok in lexer]
        assert 'DESCRIBE' in tokens


# ─────── Cycle 2: Transaction Parser Tests ───────

class TestTransactionParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_begin(self):
        ast = parser_db.set_handle().parse("BEGIN")
        assert ast['type'] == 'begin_transaction'

    def test_begin_transaction(self):
        ast = parser_db.set_handle().parse("BEGIN TRANSACTION")
        assert ast['type'] == 'begin_transaction'

    def test_commit(self):
        ast = parser_db.set_handle().parse("COMMIT")
        assert ast['type'] == 'commit'

    def test_rollback(self):
        ast = parser_db.set_handle().parse("ROLLBACK")
        assert ast['type'] == 'rollback'


# ─────── Cycle 3: Index Parser Tests ───────

class TestIndexParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_create_index(self):
        ast = parser_db.set_handle().parse("CREATE INDEX ON student(age)")
        assert ast['type'] == 'create_index'
        assert ast['table'] == 'student'
        assert ast['field'] == 'age'

    def test_drop_index(self):
        ast = parser_db.set_handle().parse("DROP INDEX ON student(age)")
        assert ast['type'] == 'drop_index'
        assert ast['table'] == 'student'
        assert ast['field'] == 'age'


# ─────── Cycle 4: Metadata Parser Tests ───────

class TestMetadataParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_show_tables(self):
        ast = parser_db.set_handle().parse("SHOW TABLES")
        assert ast['type'] == 'show_tables'

    def test_show_indexes_all(self):
        ast = parser_db.set_handle().parse("SHOW INDEX")
        assert ast['type'] == 'show_indexes'
        assert ast['table'] is None

    def test_show_indexes_from_table(self):
        ast = parser_db.set_handle().parse("SHOW INDEX FROM student")
        assert ast['type'] == 'show_indexes'
        assert ast['table'] == 'student'

    def test_describe(self):
        ast = parser_db.set_handle().parse("DESCRIBE student")
        assert ast['type'] == 'describe'
        assert ast['table'] == 'student'


# ─────── Cycle 5: Transaction Execution Tests ───────

class TestTransactionExecution:
    @pytest.fixture(autouse=True)
    def reset_txn(self, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)

    def test_begin_transaction(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        txn_id = query_plan_db.execute_sql("BEGIN")
        assert txn_id is not None
        assert common_db.current_transaction_id == txn_id

    def test_begin_transaction_keyword(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        txn_id = query_plan_db.execute_sql("BEGIN TRANSACTION")
        assert txn_id is not None

    def test_commit(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        query_plan_db.execute_sql("BEGIN")
        query_plan_db.execute_sql("COMMIT")
        assert common_db.current_transaction_id is None

    def test_rollback(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        query_plan_db.execute_sql("BEGIN")
        query_plan_db.execute_sql("ROLLBACK")
        assert common_db.current_transaction_id is None

    def test_commit_without_begin_raises(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        with pytest.raises(query_plan_db.SqlExecutionError, match="No active transaction"):
            query_plan_db.execute_sql("COMMIT")

    def test_rollback_without_begin_raises(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        with pytest.raises(query_plan_db.SqlExecutionError, match="No active transaction"):
            query_plan_db.execute_sql("ROLLBACK")

    def test_nested_begin_raises(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        query_plan_db.execute_sql("BEGIN")
        with pytest.raises(query_plan_db.SqlExecutionError, match="already active"):
            query_plan_db.execute_sql("BEGIN")


# ─────── Cycle 6: Index Execution Tests ───────

class TestIndexExecution:
    def test_create_index(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE foo (name str(10), age int)")
        result = query_plan_db.execute_sql("CREATE INDEX ON foo(age)")
        assert result is not False

    def test_create_index_nonexistent_table(self, tmp_data):
        with pytest.raises(query_plan_db.SqlExecutionError, match="does not exist"):
            query_plan_db.execute_sql("CREATE INDEX ON NoSuchTable(field)")

    def test_create_index_nonexistent_field(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE bar (name str(10))")
        with pytest.raises(query_plan_db.SqlExecutionError, match="does not exist"):
            query_plan_db.execute_sql("CREATE INDEX ON bar(nonexistent)")

    def test_create_index_duplicate(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE baz (name str(10), id int)")
        query_plan_db.execute_sql("CREATE INDEX ON baz(id)")
        with pytest.raises(query_plan_db.SqlExecutionError, match="already exists"):
            query_plan_db.execute_sql("CREATE INDEX ON baz(id)")

    def test_drop_index(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE qux (name str(10), id int)")
        query_plan_db.execute_sql("CREATE INDEX ON qux(id)")
        result = query_plan_db.execute_sql("DROP INDEX ON qux(id)")
        assert result is True

    def test_drop_nonexistent_index(self, tmp_data):
        with pytest.raises(query_plan_db.SqlExecutionError, match="No index found"):
            query_plan_db.execute_sql("DROP INDEX ON NoSuchTable(field)")


# ─────── Cycle 7: Metadata Execution Tests ───────

class TestMetadataExecution:
    def test_show_tables_empty(self, tmp_data):
        result = query_plan_db.execute_sql("SHOW TABLES")
        assert result == []

    def test_show_tables_with_table(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE demo (x int)")
        result = query_plan_db.execute_sql("SHOW TABLES")
        assert len(result) >= 1
        assert 'demo' in result

    def test_show_index_all(self, tmp_data):
        result = query_plan_db.execute_sql("SHOW INDEX")
        assert isinstance(result, list)

    def test_show_index_from_table(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE tbl (a str(10), b int)")
        query_plan_db.execute_sql("CREATE INDEX ON tbl(b)")
        result = query_plan_db.execute_sql("SHOW INDEX FROM tbl")
        assert any('b' in str(r) for r in result)

    def test_describe(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE mytable (name str(10), age int)")
        result = query_plan_db.execute_sql("DESCRIBE mytable")
        assert result is not None
        assert len(result) == 2

    def test_describe_nonexistent(self, tmp_data):
        with pytest.raises(query_plan_db.SqlExecutionError, match="does not exist"):
            query_plan_db.execute_sql("DESCRIBE nonexistent")


# ─────── Cycle 8: REPL Tests ───────

class TestREPL:
    def test_quit_command(self):
        from src import main_db
        with patch('builtins.input', side_effect=['.quit']):
            with patch('sys.stdout', new_callable=io.StringIO):
                main_db.main()

    def test_sql_execution_in_repl(self, tmp_data):
        from src import main_db
        with patch('builtins.input', side_effect=[
            'CREATE TABLE repl_test (x int)',
            '.quit'
        ]):
            with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                main_db.main()
                output = fake_out.getvalue()
                assert "created" in output.lower() or "table" in output.lower()

    def test_invalid_sql_shows_error(self, tmp_data):
        from src import main_db
        with patch('builtins.input', side_effect=[
            'INVALID SQL STATEMENT',
            '.quit'
        ]):
            with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                main_db.main()
                output = fake_out.getvalue()
                assert 'Error' in output or 'Syntax' in output

    def test_help_command(self):
        from src import main_db
        with patch('builtins.input', side_effect=['.help', '.quit']):
            with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                main_db.main()
                output = fake_out.getvalue()
                assert 'BEGIN' in output
                assert 'SELECT' in output

    def test_empty_line_is_ignored(self, tmp_data):
        from src import main_db
        with patch('builtins.input', side_effect=['', '.quit']):
            with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
                main_db.main()
                output = fake_out.getvalue()
                assert 'Error' not in output


# ─────── Cycle 9: End-to-End Integration Tests ───────

class TestEndToEndSQL:
    def test_full_crud_workflow(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE employee (name str(10), dept str(10), salary int)")
        query_plan_db.execute_sql("INSERT INTO employee VALUES ('Alice', 'Eng', 5000)")
        query_plan_db.execute_sql("INSERT INTO employee VALUES ('Bob', 'Sales', 4500)")
        query_plan_db.execute_sql("INSERT INTO employee VALUES ('Carol', 'Eng', 5500)")

        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM employee WHERE dept = 'Eng'")
        assert len(rows) == 2

        query_plan_db.execute_sql("UPDATE employee SET salary = 6000 WHERE name = 'Carol'")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM employee WHERE name = 'Carol'")
        assert len(rows) == 1

        query_plan_db.execute_sql("DELETE FROM employee WHERE name = 'Bob'")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM employee")
        assert len(rows) == 2

        query_plan_db.execute_sql("CREATE INDEX ON employee(salary)")
        query_plan_db.execute_sql("SHOW INDEX FROM employee")

        query_plan_db.execute_sql("DESCRIBE employee")

        query_plan_db.execute_sql("DROP TABLE employee")

    def test_transaction_workflow(self, tmp_data, monkeypatch):
        monkeypatch.setattr(common_db, 'current_transaction_id', None)
        query_plan_db.execute_sql("CREATE TABLE accounts (id int, balance int)")
        query_plan_db.execute_sql("INSERT INTO accounts VALUES (1, 1000)")

        query_plan_db.execute_sql("BEGIN")
        assert common_db.current_transaction_id is not None
        query_plan_db.execute_sql("COMMIT")
        assert common_db.current_transaction_id is None

    def test_show_tables_after_multiple_creates(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE t1 (a int)")
        query_plan_db.execute_sql("CREATE TABLE t2 (b str(5))")
        result = query_plan_db.execute_sql("SHOW TABLES")
        assert 't1' in result
        assert 't2' in result


def test_log_image_truncates_long_table_name(isolated_data_dir):
    """log_image 对超长表名应截断而非抛异常。"""
    from src import transaction_db
    tm = transaction_db.TransactionManager()
    txn = tm.begin_transaction()
    long_name = 'a' * 100
    tm.log_after_image(txn, long_name, b'dummy', 0, 0)
    tm.commit_transaction(txn)


def test_insert_delete_max_record_num_consistent(isolated_data_dir):
    """insert 和 delete 算出的 MAX_RECORD_NUM 必须一致。"""
    from src import storage_db
    sto = storage_db.Storage.create_table(
        't',
        [('a', 0, 100)],
    )
    record_head_len = 4 + 4 + 10
    record_content_len = 100
    record_len = record_head_len + record_content_len

    max_insert = storage_db._max_records_per_block(record_len)
    max_delete_via_helper = storage_db._max_records_per_block(record_len)
    assert max_insert == max_delete_via_helper

    for i in range(max_insert + 5):
        sto.insert_record([f'v{i:02d}'])
    del sto

    sto2 = storage_db.Storage('t')
    initial_count = len(sto2.record_list)
    sto2.delete_record(0, 'v00')
    del sto2

    sto3 = storage_db.Storage('t')
    assert len(sto3.record_list) == initial_count - 1
    sto3.insert_record(['v99'])
    del sto3

    sto4 = storage_db.Storage('t')
    assert len(sto4.record_list) == initial_count


def test_delete_record_data_blocks_written_before_header_update(isolated_data_dir, monkeypatch):
    """模拟在写完文件头但未写完数据块时崩溃。"""
    from src import storage_db
    sto = storage_db.Storage.create_table('t', [('a', 2, 4)])
    for i in range(20):
        sto.insert_record([str(i)])
    del sto

    sto = storage_db.Storage('t')

    write_log = []
    orig_seek = sto.f_handle.seek
    orig_write = sto.f_handle.write
    current_offset = [0]

    def tracked_seek(off, *a, **kw):
        current_offset[0] = off
        return orig_seek(off, *a, **kw)

    def tracked_write(data):
        write_log.append(current_offset[0])
        return orig_write(data)

    monkeypatch.setattr(sto.f_handle, 'seek', tracked_seek)
    monkeypatch.setattr(sto.f_handle, 'write', tracked_write)

    sto.delete_record(0, '5')

    last_header_write = max(i for i, off in enumerate(write_log) if off == 0)
    block_writes_after_header = [
        off for off in write_log[last_header_write + 1:] if off != 0
    ]
    assert not block_writes_after_header, \
        f"删除后还有数据块写入：{block_writes_after_header}"


def test_next_txn_id_persists_across_restart(isolated_data_dir):
    """重启 TransactionManager 后 next_txn_id 不应回到 1。"""
    from src import transaction_db

    tm1 = transaction_db.TransactionManager()
    txn_a = tm1.begin_transaction()
    tm1.log_after_image(txn_a, 't', b'x', 0, 0)
    tm1.commit_transaction(txn_a)

    txn_b = tm1.begin_transaction()
    tm1.log_after_image(txn_b, 't', b'y', 0, 0)
    tm1.commit_transaction(txn_b)
    last_id = txn_b
    del tm1

    tm2 = transaction_db.TransactionManager()
    new_txn = tm2.begin_transaction()
    assert new_txn > last_id, \
        f"重启后 next_txn_id 必须大于历史最大值，但拿到 {new_txn} <= {last_id}"


def test_recovery_finds_uncommitted_txn_with_only_before_image(isolated_data_dir):
    """只写了 before-image 就崩溃的事务必须被恢复识别为 active。"""
    from src import transaction_db

    tm = transaction_db.TransactionManager()
    txn = tm.begin_transaction()
    tm.log_before_image(txn, 't', b'old', 0, 0)
    del tm

    tm2 = transaction_db.TransactionManager()
    assert tm2.next_txn_id > txn, \
        f"恢复后 next_txn_id ({tm2.next_txn_id}) 必须大于 leaked txn ({txn})"


def test_update_records_by_indices_writes_log_and_maintains_index(isolated_data_dir):
    from src import storage_db, transaction_db, index_db, index_catalog

    sto = storage_db.Storage.create_table(
        'students',
        [('name', 0, 10), ('age', 2, 4)],
    )
    sto.insert_record(['Alice', '20'])
    sto.insert_record(['Bob', '21'])
    sto.insert_record(['Carol', '22'])
    del sto

    index_catalog.add_index('students', 'age')
    idx = index_db.Index('students', 'age')
    idx.create_index()
    idx.close()

    tm = transaction_db.get_transaction_manager()
    txn = tm.begin_transaction()
    sto2 = storage_db.Storage('students')
    updated = sto2.update_records_by_indices([1], 1, 99, txn_id=txn)
    assert updated == 1
    tm.commit_transaction(txn)
    del sto2

    idx2 = index_db.Index('students', 'age')
    assert idx2.search_index('99')
    assert not idx2.search_index('21')
    idx2.close()


def test_delete_records_by_indices_writes_log_and_maintains_index(isolated_data_dir):
    from src import storage_db, transaction_db, index_db, index_catalog

    sto = storage_db.Storage.create_table('t', [('a', 2, 4)])
    for i in range(5):
        sto.insert_record([str(i)])
    del sto

    index_catalog.add_index('t', 'a')
    idx = index_db.Index('t', 'a')
    idx.create_index()
    idx.close()

    tm = transaction_db.get_transaction_manager()
    txn = tm.begin_transaction()
    sto2 = storage_db.Storage('t')
    deleted = sto2.delete_records_by_indices([1, 3], txn_id=txn)
    assert deleted == 2
    tm.commit_transaction(txn)
    del sto2

    sto3 = storage_db.Storage('t')
    assert len(sto3.record_list) == 3


def test_execute_update_preserves_index_with_complex_where(isolated_data_dir):
    from src import query_plan_db, index_catalog, index_db
    query_plan_db.execute_sql("CREATE TABLE s (name str(10), age int);")
    for n, a in [('A', 18), ('B', 25), ('C', 30)]:
        query_plan_db.execute_sql(f"INSERT INTO s VALUES ('{n}', {a});")
    query_plan_db.execute_sql("CREATE INDEX ON s(age);")

    query_plan_db.execute_sql("UPDATE s SET age = 99 WHERE age > 20;")

    idx = index_db.Index('s', 'age')
    assert not idx.search_index('25')
    assert not idx.search_index('30')
    assert len(idx.search_index('99')) == 2
    idx.close()


def test_execute_update_writes_transaction_log(isolated_data_dir):
    from src import query_plan_db
    query_plan_db.execute_sql("CREATE TABLE s (name str(10), age int);")
    query_plan_db.execute_sql("INSERT INTO s VALUES ('A', 20);")

    query_plan_db.execute_sql("BEGIN;")
    query_plan_db.execute_sql("UPDATE s SET age = 99 WHERE name = 'A';")
    query_plan_db.execute_sql("ROLLBACK;")

    from src import storage_db
    sto = storage_db.Storage('s')
    assert sto.record_list[0][1] == 20, \
        f"ROLLBACK 后 age 应为 20，实际 {sto.record_list[0][1]}"


def test_recovery_undo_uncommitted_insert(isolated_data_dir):
    """BEGIN → UPDATE → 不 COMMIT → 重启，记录应被 undo。"""
    from src import query_plan_db, transaction_db, storage_db
    query_plan_db.execute_sql("CREATE TABLE t (a int);")
    query_plan_db.execute_sql("INSERT INTO t VALUES (42);")
    query_plan_db.execute_sql("BEGIN;")
    query_plan_db.execute_sql("UPDATE t SET a = 99 WHERE a = 42;")
    transaction_db.transaction_manager = None

    transaction_db.get_transaction_manager()
    sto = storage_db.Storage('t')
    assert any(r[0] == 42 for r in sto.record_list), \
        "未 COMMIT 的 UPDATE 应被 undo"


def test_recovery_redo_committed_update(isolated_data_dir):
    """BEGIN → UPDATE → COMMIT → 重启，after-image 应被 redo。"""
    from src import query_plan_db, transaction_db, storage_db
    query_plan_db.execute_sql("CREATE TABLE t (name str(10), v int);")
    query_plan_db.execute_sql("INSERT INTO t VALUES ('x', 1);")
    query_plan_db.execute_sql("BEGIN;")
    query_plan_db.execute_sql("UPDATE t SET v = 99 WHERE name = 'x';")
    query_plan_db.execute_sql("COMMIT;")

    transaction_db.transaction_manager = None
    transaction_db.get_transaction_manager()

    sto = storage_db.Storage('t')
    assert sto.record_list[0][1] == 99, \
        f"已 COMMIT 的 UPDATE 应被 redo, 实际 v={sto.record_list[0][1]}"


def test_recovery_after_explicit_rollback(isolated_data_dir):
    """BEGIN → UPDATE → ROLLBACK → 重启，记录应回滚到原值。"""
    from src import query_plan_db, transaction_db, storage_db
    query_plan_db.execute_sql("CREATE TABLE t (a int);")
    query_plan_db.execute_sql("INSERT INTO t VALUES (7);")
    query_plan_db.execute_sql("BEGIN;")
    query_plan_db.execute_sql("UPDATE t SET a = 99 WHERE a = 7;")
    query_plan_db.execute_sql("ROLLBACK;")

    transaction_db.transaction_manager = None
    transaction_db.get_transaction_manager()

    sto = storage_db.Storage('t')
    assert any(r[0] == 7 for r in sto.record_list), \
        "ROLLBACK 后记录应恢复原值"
