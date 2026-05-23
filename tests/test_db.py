"""
test_db.py — Schema 层的 pytest 集成测试。
覆盖 Schema 构造、增删表、查看结构、持久化/重载。
"""

import os
import pytest
from src import schema_db, common_db


@pytest.fixture
def clean_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR and Schema.fileName to tmp_path for isolation."""
    monkeypatch.setattr(common_db, 'VERBOSE', False)
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(schema_db.Schema, 'fileName', str(tmp_path / 'all.sch'))
    os.makedirs(str(tmp_path), exist_ok=True)
    yield tmp_path


@pytest.fixture
def empty_schema(clean_data_dir):
    """Create a fresh empty Schema in isolated tmp_path."""
    s = schema_db.Schema()
    yield s
    del s


class TestSchemaCreation:
    def test_fresh_schema_has_no_tables(self, empty_schema):
        tables = empty_schema.get_table_name_list()
        assert tables == []

    def test_fresh_schema_not_stored(self, empty_schema):
        assert empty_schema.headObj.isStored is False
        assert empty_schema.headObj.lenOfTableNum == 0

    def test_schema_file_created(self, clean_data_dir):
        sch_path = clean_data_dir / 'all.sch'
        assert not sch_path.exists()
        s = schema_db.Schema()
        assert sch_path.exists()
        del s


class TestTableOperations:
    def test_append_and_find_table(self, empty_schema):
        fields = [('sid', 0, 3), ('name', 1, 10)]
        empty_schema.appendTable('students', fields)
        assert empty_schema.find_table('students') is True
        assert empty_schema.find_table('nonexistent') is False

    def test_get_table_name_list(self, empty_schema):
        assert empty_schema.get_table_name_list() == []
        empty_schema.appendTable('students', [('sid', 0, 3)])
        empty_schema.appendTable('courses', [('cid', 0, 3)])
        tables = empty_schema.get_table_name_list()
        assert 'students' in tables
        assert 'courses' in tables
        assert len(tables) == 2

    def test_view_table_structure(self, empty_schema):
        fields = [('sid', 0, 3), ('name', 1, 10)]
        empty_schema.appendTable('students', fields)
        result = empty_schema.viewTableStructure('students')
        assert result is not None
        assert len(result) == 2
        assert result[0][0].strip() == 'sid'
        assert result[0][1] == 0
        assert result[0][2] == 3
        assert result[1][0].strip() == 'name'

    def test_view_table_structure_nonexistent(self, empty_schema):
        result = empty_schema.viewTableStructure('no_such_table')
        assert result is None

    def test_view_table_names(self, empty_schema):
        empty_schema.appendTable('t1', [('a', 2, 10)])
        empty_schema.appendTable('t2', [('b', 0, 5)])
        names = empty_schema.get_table_name_list()
        assert 't1' in names
        assert 't2' in names

    def test_head_obj_updated_after_append(self, empty_schema):
        empty_schema.appendTable('students', [('sid', 0, 3)])
        assert empty_schema.headObj.isStored is True
        assert empty_schema.headObj.lenOfTableNum == 1
        assert len(empty_schema.headObj.tableNames) == 1


class TestDeleteTable:
    def test_delete_existing_table(self, empty_schema):
        empty_schema.appendTable('students', [('sid', 0, 3)])
        empty_schema.appendTable('courses', [('cid', 0, 3)])
        assert empty_schema.find_table('students') is True

        result = empty_schema.delete_table_schema('students')
        assert result is True
        assert empty_schema.find_table('students') is False
        assert empty_schema.find_table('courses') is True
        assert empty_schema.headObj.lenOfTableNum == 1

    def test_delete_nonexistent_table(self, empty_schema):
        result = empty_schema.delete_table_schema('no_such_table')
        assert result is False

    def test_delete_last_table(self, empty_schema):
        empty_schema.appendTable('students', [('sid', 0, 3)])
        empty_schema.delete_table_schema('students')
        assert empty_schema.get_table_name_list() == []
        assert empty_schema.headObj.isStored is False
        assert empty_schema.headObj.lenOfTableNum == 0

    def test_delete_all_tables(self, empty_schema):
        empty_schema.appendTable('t1', [('a', 0, 3)])
        empty_schema.appendTable('t2', [('b', 0, 3)])
        empty_schema.appendTable('t3', [('c', 0, 3)])
        empty_schema.deleteAll()
        assert empty_schema.get_table_name_list() == []
        assert empty_schema.headObj.isStored is False


class TestSchemaPersistence:
    def test_tables_survive_reload(self, clean_data_dir):
        # Create schema, add tables, close
        s1 = schema_db.Schema()
        s1.appendTable('students', [
            ('sid', 0, 3),
            ('name', 1, 10),
            ('dept', 0, 6),
            ('age', 2, 3),
        ])
        s1.appendTable('courses', [
            ('cid', 0, 3),
            ('cname', 1, 20),
            ('dept', 1, 10),
            ('credit', 2, 3),
        ])
        del s1

        # Reload and verify
        s2 = schema_db.Schema()
        tables = s2.get_table_name_list()
        assert len(tables) == 2
        assert 'students' in tables
        assert 'courses' in tables

        # Verify student table structure
        fields = s2.viewTableStructure('students')
        assert fields is not None
        assert len(fields) == 4
        assert fields[0][0].strip() == 'sid'
        assert fields[1][0].strip() == 'name'
        assert fields[2][0].strip() == 'dept'
        assert fields[3][0].strip() == 'age'

        # Verify course table structure
        fields = s2.viewTableStructure('courses')
        assert fields is not None
        assert len(fields) == 4
        assert fields[0][0].strip() == 'cid'
        assert fields[1][0].strip() == 'cname'

        del s2

    def test_delete_persists_across_reload(self, clean_data_dir):
        s1 = schema_db.Schema()
        s1.appendTable('students', [('sid', 0, 3)])
        s1.appendTable('courses', [('cid', 0, 3)])
        del s1

        s2 = schema_db.Schema()
        s2.delete_table_schema('students')
        del s2

        s3 = schema_db.Schema()
        tables = s3.get_table_name_list()
        assert tables == ['courses']
        del s3


class TestSchemaEdgeCases:
    def test_empty_table_name(self, empty_schema):
        fields = [('sid', 0, 3)]
        empty_schema.appendTable('   ', fields)
        assert empty_schema.headObj.lenOfTableNum == 0  # 空表名不添加

    def test_field_name_with_whitespace(self, empty_schema):
        fields = [('  sid  ', 0, 3)]
        empty_schema.appendTable('test_ws', fields)
        tbl_fields = empty_schema.viewTableStructure('test_ws')
        assert tbl_fields[0][0].strip() == 'sid'
