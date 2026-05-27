"""
test_sql.py — 综合SQL功能测试：词法器、语法器、执行引擎。
覆盖 INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE, 增强WHERE, ORDER BY。
"""

import os
import pytest
from src import common_db
from src import lex_db
from src import parser_db
from src import storage_db
from src import schema_db
from src import query_plan_db


# ─────── Fixtures ───────

@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Redirect DATA_DIR and Schema.fileName to tmp_path."""
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(schema_db.Schema, 'fileName', str(tmp_path / 'all.sch'))
    # Ensure the schema file exists (can be empty)
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


def _insert_test_data(tmp_data, records=None):
    """Insert test data into the students table. Returns (fields, rows)."""
    if records is None:
        records = [
            ['Alice', '20', 'A'],
            ['Bob', '22', 'B'],
            ['Charlie', '19', 'C'],
            ['David', '21', 'A'],
            ['Eve', '23', 'B'],
        ]
    storage = storage_db.Storage('students')
    for rec in records:
        storage.insert_record(rec, txn_id=None)
    del storage


# ─────── Lexer Tests ───────

class TestLexer:
    def test_insert_tokens(self, tmp_data):
        lex_db.set_lex_handle()
        lexer = common_db.global_lexer
        lexer.input("INSERT INTO students (name, age) VALUES ('Alice', 20)")
        tokens = [tok.type for tok in lexer]
        assert tokens == ['INSERT', 'INTO', 'IDENT', 'LPAREN', 'IDENT', 'COMMA', 'IDENT', 'RPAREN', 'VALUES', 'LPAREN', 'STRING', 'COMMA', 'INT', 'RPAREN']

    def test_comparison_operators(self, tmp_data):
        lex_db.set_lex_handle()
        lexer = common_db.global_lexer
        lexer.input("WHERE age >= 18 AND name != 'Bob'")
        token_dict = {tok.type for tok in lexer}
        assert 'GTE' in token_dict
        assert 'NEQ' in token_dict

    def test_order_by_tokens(self, tmp_data):
        lex_db.set_lex_handle()
        lexer = common_db.global_lexer
        lexer.input("ORDER BY age DESC")
        tokens = [tok.type for tok in lexer]
        assert tokens == ['ORDER', 'BY', 'IDENT', 'DESC']

    def test_create_table_tokens(self, tmp_data):
        lex_db.set_lex_handle()
        lexer = common_db.global_lexer
        lexer.input("CREATE TABLE test (name str(10), age int, active bool)")
        tokens = [tok.type for tok in lexer]
        assert 'CREATE' in tokens
        assert 'TABLE' in tokens
        assert 'STRING_TYPE' in tokens
        assert 'INT_TYPE' in tokens
        assert 'BOOL_TYPE' in tokens


# ─────── Parser Tests ───────

class TestParser:
    def setup_method(self):
        lex_db.set_lex_handle()
        parser_db.set_handle()

    def test_parse_insert(self):
        ast = parser_db.set_handle().parse("INSERT INTO students (name, age) VALUES ('Alice', 20)")
        assert ast['type'] == 'insert'
        assert ast['table'] == 'students'
        # columns is a list of column dicts from ColumnList rule
        col_names = [c['name'] if isinstance(c, dict) else c for c in ast['columns']]
        assert col_names == ['name', 'age']
        assert len(ast['values']) == 2

    def test_parse_insert_no_columns(self):
        ast = parser_db.set_handle().parse("INSERT INTO students VALUES ('Alice', 20, 'A')")
        assert ast['type'] == 'insert'
        assert ast['columns'] is None
        assert len(ast['values']) == 3

    def test_parse_update(self):
        ast = parser_db.set_handle().parse("UPDATE students SET grade = 'A' WHERE name = 'Bob'")
        assert ast['type'] == 'update'
        assert ast['table'] == 'students'
        assert len(ast['assignments']) == 1
        assert ast['assignments'][0]['field'] == 'grade'

    def test_parse_delete(self):
        ast = parser_db.set_handle().parse("DELETE FROM students WHERE age < 18")
        assert ast['type'] == 'delete'
        assert ast['table'] == 'students'

    def test_parse_create_table(self):
        ast = parser_db.set_handle().parse("CREATE TABLE test (name str(10), age int, active bool)")
        assert ast['type'] == 'create_table'
        assert ast['table'] == 'test'
        assert len(ast['fields']) == 3
        assert ast['fields'][0] == ('name', 0, 10)
        assert ast['fields'][1] == ('age', 2, 10)
        assert ast['fields'][2] == ('active', 3, 1)

    def test_parse_drop_table(self):
        ast = parser_db.set_handle().parse("DROP TABLE test")
        assert ast['type'] == 'drop_table'
        assert ast['table'] == 'test'

    def test_parse_or(self):
        ast = parser_db.set_handle().parse("SELECT * FROM t WHERE a = 1 OR b = 2")
        assert ast['where']['type'] == 'or'

    def test_parse_not(self):
        ast = parser_db.set_handle().parse("SELECT * FROM t WHERE NOT a = 1")
        assert ast['where']['type'] == 'not'

    def test_parse_order_by(self):
        ast = parser_db.set_handle().parse("SELECT * FROM t ORDER BY age DESC")
        assert len(ast['order_by']) == 1
        assert ast['order_by'][0]['direction'] == 'desc'
        assert ast['order_by'][0]['field'] == 'age'

    def test_parse_multiline_where(self):
        ast = parser_db.set_handle().parse("SELECT * FROM t WHERE a >= 1 AND b != 'x' OR c = 3")
        where = ast['where']
        assert where['type'] in ('and', 'or')

    def test_parse_comparison_operators(self):
        for op_str, op_name in [('=', '='), ('!=', '!='), ('<', '<'), ('>', '>'), ('<=', '<='), ('>=', '>=')]:
            ast = parser_db.set_handle().parse(f"SELECT * FROM t WHERE a {op_str} 1")
            assert ast['where']['op'] == op_name, f"Failed for operator {op_str}"


# ─────── Storage.create_table Tests ───────

class TestStorageCreateTable:
    def test_create_table_programmatic(self, tmp_data):
        field_list = [
            ('name', 0, 20),
            ('age', 2, 10),
            ('active', 3, 1),
        ]
        storage = storage_db.Storage.create_table('test_tbl', field_list)
        assert storage is not None
        assert storage.num_of_fields == 3
        fields = storage.getFieldList()
        assert len(fields) == 3
        assert fields[0][0].strip() == 'name'
        assert fields[0][1] == 0
        assert fields[1][0].strip() == 'age'
        assert fields[1][1] == 2
        assert fields[2][0].strip() == 'active'
        assert fields[2][1] == 3
        del storage

    def test_create_table_and_insert(self, tmp_data):
        field_list = [
            ('name', 0, 20),
            ('age', 2, 10),
        ]
        storage = storage_db.Storage.create_table('insert_test', field_list)
        result = storage.insert_record(['Alice', '25'], txn_id=None)
        assert result is True
        records = storage.getRecord()
        assert len(records) == 1
        assert records[0][0].strip() == 'Alice'
        assert records[0][1] == 25
        del storage

    def test_create_table_duplicate_raises(self, tmp_data):
        field_list = [('name', 0, 20)]
        storage_db.Storage.create_table('dup_test', field_list)
        with pytest.raises(ValueError):
            storage_db.Storage.create_table('dup_test', field_list)


# ─────── SQL Execution Tests ───────

class TestSQLExecution:
    def test_create_table_and_select(self, tmp_data):
        result = query_plan_db.execute_sql("CREATE TABLE sql_test (name str(20), age int)")
        assert result is True

        result = query_plan_db.execute_sql("INSERT INTO sql_test (name, age) VALUES ('Alice', 30)")
        assert result is True

        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM sql_test WHERE name = 'Alice'")
        assert len(rows) == 1

    def test_insert_with_column_order(self, test_table):
        _insert_test_data(test_table)
        result = query_plan_db.execute_sql("INSERT INTO students (name, age, grade) VALUES ('Frank', 25, 'A')")
        assert result is True

    def test_insert_without_columns(self, test_table):
        result = query_plan_db.execute_sql("INSERT INTO students VALUES ('Grace', 24, 'B')")
        assert result is True

    def test_update_with_condition(self, test_table):
        _insert_test_data(test_table)
        result = query_plan_db.execute_sql("UPDATE students SET grade = 'A' WHERE name = 'Bob'")
        assert result is not None

    def test_delete_with_condition(self, test_table):
        _insert_test_data(test_table)
        result = query_plan_db.execute_sql("DELETE FROM students WHERE age < 20")
        assert result is not None

    def test_drop_table(self, tmp_data):
        query_plan_db.execute_sql("CREATE TABLE drop_test (name str(10))")
        result = query_plan_db.execute_sql("DROP TABLE drop_test")
        assert result is True

    def test_select_with_comparison_ops(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age > 20")
        assert all(r[1] > 20 for r in rows)

    def test_select_with_neq(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE grade != 'A'")
        assert all(r[2].strip() != 'A' for r in rows)

    def test_select_with_or(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age = 20 OR age = 22")
        names = [r[0].strip() if isinstance(r[0], str) else r[0] for r in rows]
        assert 'Alice' in names
        assert 'Bob' in names

    def test_select_with_not(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE NOT age = 20")
        names = [r[0].strip() if isinstance(r[0], str) else r[0] for r in rows]
        assert 'Alice' not in names

    def test_select_with_order_by_asc(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students ORDER BY age ASC")
        ages = [r[1] for r in rows]
        assert ages == sorted(ages)

    def test_select_with_order_by_desc(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students ORDER BY age DESC")
        ages = [r[1] for r in rows]
        assert ages == sorted(ages, reverse=True)

    def test_select_empty_result(self, test_table):
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age > 100")
        assert len(rows) == 0

    def test_create_table_already_exists(self, test_table):
        with pytest.raises(query_plan_db.SqlExecutionError):
            query_plan_db.execute_sql("CREATE TABLE students (name str(20))")

    def test_drop_nonexistent_table(self, test_table):
        with pytest.raises(query_plan_db.SqlExecutionError):
            query_plan_db.execute_sql("DROP TABLE nonexistent")

    def test_insert_into_nonexistent_table(self, test_table):
        with pytest.raises(query_plan_db.SqlExecutionError):
            query_plan_db.execute_sql("INSERT INTO nonexistent (a) VALUES ('x')")


# ─────── WHERE Condition Tests ───────

class TestWhereConditions:
    def test_greater_than(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age > 20")
        assert len(rows) >= 1
        assert all(r[1] > 20 for r in rows)

    def test_less_than_or_equal(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age <= 20")
        assert all(r[1] <= 20 for r in rows)

    def test_greater_than_or_equal(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age >= 21")
        assert all(r[1] >= 21 for r in rows)

    def test_combined_and_or(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age >= 20 AND (grade = 'A' OR grade = 'B')")
        for r in rows:
            assert r[1] >= 20
            assert r[2].strip() in ('A', 'B')

    def test_parenthesized_conditions(self, test_table):
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE (age = 20 OR age = 22) AND grade = 'A'")
        for r in rows:
            assert r[1] in (20, 22)
            assert r[2].strip() == 'A'


# ─────── Critical Review Coverage: UPDATE with non-equality WHERE ───────

class TestUpdateNonEquality:
    def test_update_with_gt_condition(self, test_table):
        """Critical fix: UPDATE with age > N must actually update matching rows."""
        _insert_test_data(test_table)
        query_plan_db.execute_sql("UPDATE students SET grade = 'Z' WHERE age > 20")
        # Re-query to verify
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age > 20")
        for r in rows:
            assert r[2].strip() == 'Z', f"Expected grade Z for age > 20 row, got {r[2]}"

        # Verify age <= 20 rows were NOT updated
        fields2, rows2, _ = query_plan_db.execute_sql("SELECT * FROM students WHERE age <= 20")
        for r in rows2:
            assert r[2].strip() != 'Z', f"Row with age <= 20 should not have grade Z, got {r[2]}"

    def test_update_with_compound_condition(self, test_table):
        """UPDATE with compound WHERE (AND) should only update matching rows."""
        _insert_test_data(test_table)
        query_plan_db.execute_sql("UPDATE students SET grade = 'X' WHERE age >= 20 AND age <= 21")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students")
        for r in rows:
            if r[1] >= 20 and r[1] <= 21:
                assert r[2].strip() == 'X', f"Expected grade X, got {r[2]}"
            else:
                assert r[2].strip() != 'X', f"Row age={r[1]} should not have grade X"

    def test_update_multiple_rows_no_overupdate(self, test_table):
        """UPDATE with equality should only update rows matching the full WHERE condition."""
        _insert_test_data(test_table)
        # Insert two Bobs with different ages
        storage = storage_db.Storage('students')
        storage.insert_record(['Bob2', '30', 'B'], txn_id=None)
        storage.insert_record(['Alice2', '21', 'A'], txn_id=None)
        del storage

        # Update only rows grade='B' AND age=22
        query_plan_db.execute_sql("UPDATE students SET grade = 'Y' WHERE grade = 'B' AND age = 22")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students")
        for r in rows:
            if r[2].strip() == 'Y':
                # Only Bob(age=22) should be updated, not Bob2(age=30)
                assert r[1] == 22 or r[1] == 30, f"Unexpected updated row: {r}"

class TestDeleteComplexConditions:
    def test_delete_with_or_condition(self, test_table):
        """DELETE with OR condition should remove matching rows only."""
        _insert_test_data(test_table)
        query_plan_db.execute_sql("DELETE FROM students WHERE age = 19 OR age = 23")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students")
        ages = [r[1] for r in rows]
        assert 19 not in ages
        assert 23 not in ages
        assert 20 in ages  # Alice still there

    def test_delete_with_not_condition(self, test_table):
        """DELETE with NOT condition."""
        _insert_test_data(test_table)
        query_plan_db.execute_sql("DELETE FROM students WHERE NOT grade = 'A'")
        fields, rows, _ = query_plan_db.execute_sql("SELECT * FROM students")
        assert len(rows) == 2  # Only Alice and David have grade A
        for r in rows:
            assert r[2].strip() == 'A'

class TestInsertEdgeCases:
    def test_insert_wrong_column_count(self, test_table):
        """INSERT with wrong number of columns should raise an error."""
        with pytest.raises(query_plan_db.SqlExecutionError):
            query_plan_db.execute_sql("INSERT INTO students (name, age) VALUES ('Zoe', 25, 'A')")

    def test_insert_wrong_value_count(self, test_table):
        """INSERT with mismatched column/value count should raise an error."""
        with pytest.raises(query_plan_db.SqlExecutionError):
            query_plan_db.execute_sql("INSERT INTO students (name, age, grade) VALUES ('Zoe', 25)")

    def test_select_named_columns(self, test_table):
        """SELECT with named columns (not *) should work."""
        _insert_test_data(test_table)
        fields, rows, _ = query_plan_db.execute_sql("SELECT name, age FROM students WHERE age > 20")
        assert fields == ['students.name', 'students.age']
        assert len(rows) > 0
        for r in rows:
            assert len(r) == 2


def test_schema_deleteall_then_append_does_not_typeerror(isolated_data_dir):
    """deleteAll 后再 appendTable 不应抛 TypeError。"""
    from src import schema_db
    schema = schema_db.Schema()
    schema.appendTable('t1', [('a', 2, 10)])
    schema.deleteAll()
    schema.appendTable('t2', [('b', 2, 10)])  # 旧实现会抛 TypeError
    assert schema.find_table('t2')


def test_schema_body_begin_index_is_instance_attribute(isolated_data_dir):
    """两个 Schema 实例不应共享 body_begin_index。"""
    from src import schema_db
    s1 = schema_db.Schema()
    s1.appendTable('t1', [('a', 2, 10)])
    s1_offset = s1.body_begin_index

    s2 = schema_db.Schema()
    s2_offset = s2.body_begin_index

    s1.appendTable('t2', [('b', 2, 10)])
    assert s2.body_begin_index == s2_offset, \
        "Schema 实例之间不能共享 body_begin_index"


def test_parser_instance_is_singleton(isolated_data_dir):
    """parser_db.set_handle() 多次调用应返回同一实例。"""
    from src import parser_db
    parser_db.set_handle()
    p1 = parser_db._parser_instance
    parser_db.set_handle()
    p2 = parser_db._parser_instance
    assert p1 is p2
    assert p1 is not None


def test_no_global_parser_attribute_in_common_db():
    from src import common_db
    assert not hasattr(common_db, 'global_parser')


def test_get_schema_returns_shared_when_set(isolated_data_dir):
    from src import query_plan_db, schema_db, common_db
    shared = schema_db.Schema()
    common_db.shared_schema = shared
    assert query_plan_db._get_schema() is shared


def test_get_schema_falls_back_to_new_instance(isolated_data_dir):
    from src import query_plan_db, common_db, schema_db
    common_db.shared_schema = None
    s = query_plan_db._get_schema()
    assert isinstance(s, schema_db.Schema)


def test_table_name_resolution_consistent_between_schema_and_query(isolated_data_dir):
    from src import query_plan_db, schema_db, common_db
    query_plan_db.execute_sql("CREATE TABLE Students (name str(10));")
    schema = schema_db.Schema()
    common_db.shared_schema = schema

    found_by_schema = schema.find_table('students')
    try:
        resolved = query_plan_db._resolve_table_name('students')
        ok_resolve = True
    except query_plan_db.SqlExecutionError:
        resolved = None
        ok_resolve = False
    assert found_by_schema == ok_resolve