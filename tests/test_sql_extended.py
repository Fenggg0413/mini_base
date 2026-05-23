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
        ast = common_db.global_parser.parse("BEGIN")
        assert ast['type'] == 'begin_transaction'

    def test_begin_transaction(self):
        ast = common_db.global_parser.parse("BEGIN TRANSACTION")
        assert ast['type'] == 'begin_transaction'

    def test_commit(self):
        ast = common_db.global_parser.parse("COMMIT")
        assert ast['type'] == 'commit'

    def test_rollback(self):
        ast = common_db.global_parser.parse("ROLLBACK")
        assert ast['type'] == 'rollback'


# ─────── Cycle 3: Index Parser Tests ───────

class TestIndexParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_create_index(self):
        ast = common_db.global_parser.parse("CREATE INDEX ON student(age)")
        assert ast['type'] == 'create_index'
        assert ast['table'] == 'student'
        assert ast['field'] == 'age'

    def test_drop_index(self):
        ast = common_db.global_parser.parse("DROP INDEX ON student(age)")
        assert ast['type'] == 'drop_index'
        assert ast['table'] == 'student'
        assert ast['field'] == 'age'


# ─────── Cycle 4: Metadata Parser Tests ───────

class TestMetadataParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_show_tables(self):
        ast = common_db.global_parser.parse("SHOW TABLES")
        assert ast['type'] == 'show_tables'

    def test_show_indexes_all(self):
        ast = common_db.global_parser.parse("SHOW INDEX")
        assert ast['type'] == 'show_indexes'
        assert ast['table'] is None

    def test_show_indexes_from_table(self):
        ast = common_db.global_parser.parse("SHOW INDEX FROM student")
        assert ast['type'] == 'show_indexes'
        assert ast['table'] == 'student'

    def test_describe(self):
        ast = common_db.global_parser.parse("DESCRIBE student")
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
                assert 'Error' not in output or 'Error' not in output.split('\n')[-2]


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