"""
test_verbose.py — TDD tests for VERBOSE flag and shared Schema caching.
"""

import io
import os
import pytest
from unittest.mock import patch

from src import common_db, schema_db, storage_db, transaction_db, query_plan_db


# ─────── Fixtures ───────


@pytest.fixture
def clean_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR and Schema.fileName to tmp_path."""
    monkeypatch.setattr(common_db, 'VERBOSE', False)
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(schema_db.Schema, 'fileName', str(tmp_path / 'all.sch'))
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(str(tmp_path / 'all.sch'), 'wb') as f:
        pass
    return tmp_path


# ─────── Cycle 1: VERBOSE flag existence ───────


class TestVerboseFlag:
    def test_verbose_exists_and_defaults_to_false(self):
        assert hasattr(common_db, 'VERBOSE')
        assert common_db.VERBOSE is False


# ─────── Cycle 2-5: VERBOSE gates noise ───────


class TestVerboseTransaction:
    def test_recovery_silent_when_verbose_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common_db, 'VERBOSE', False)
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
        os.makedirs(str(tmp_path), exist_ok=True)
        for name in ('before_image.log', 'after_image.log'):
            with open(os.path.join(str(tmp_path), name), 'wb') as f:
                pass

        # Reset singleton
        transaction_db.transaction_manager = None

        with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
            txn = transaction_db.get_transaction_manager()
        output = fake_out.getvalue()
        assert '\u5f00\u59cb\u4e8b\u52a1\u6062\u590d' not in output  # 开始事务恢复
        assert '\u6062\u590d\u8fc7\u7a0b\u5b8c\u6210' not in output  # 恢复过程完成


class TestVerboseSchema:
    def test_schema_init_silent(self, clean_data_dir, monkeypatch):
        monkeypatch.setattr(common_db, 'VERBOSE', False)
        with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
            s = schema_db.Schema()
        output = fake_out.getvalue()
        assert '__init__ of Schema' not in output
        assert 'there is something' not in output
        assert 'tableNum in schema file' not in output
        assert 'isStored in schema file' not in output


class TestVerboseStorage:
    def test_storage_open_silent(self, clean_data_dir, monkeypatch):
        monkeypatch.setattr(common_db, 'VERBOSE', False)
        storage_db.Storage.create_table('test_silent', [('x', 2, 10)])

        with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
            s = storage_db.Storage('test_silent')
        output = fake_out.getvalue()
        assert 'has been opened' not in output
        assert 'number of fields' not in output
        assert 'data_block_num' not in output
        if getattr(s, 'f_handle', None) and getattr(s, 'open', False):
            s.f_handle.close()


# ─────── Cycle 6: Shared Schema ───────


class TestSharedSchema:
    def test_tables_persist_across_statements(self, clean_data_dir, monkeypatch):
        monkeypatch.setattr(common_db, 'VERBOSE', False)

        # Simulate main() initialization
        common_db.shared_schema = schema_db.Schema()

        query_plan_db.execute_sql("CREATE TABLE t1 (a int)")
        result = query_plan_db.execute_sql("DESCRIBE t1")
        assert result is not None
        assert len(result) == 1

        query_plan_db.execute_sql("CREATE TABLE t2 (b str(5))")
        tables = query_plan_db.execute_sql("SHOW TABLES")
        assert 't1' in tables
        assert 't2' in tables

    def test_shared_schema_persistence(self, clean_data_dir, monkeypatch):
        """When shared_schema is set, tables persist across SQL statements."""
        monkeypatch.setattr(common_db, 'shared_schema', schema_db.Schema())

        query_plan_db.execute_sql("CREATE TABLE per (x int)")
        tables = query_plan_db.execute_sql("SHOW TABLES")
        assert 'per' in tables

        query_plan_db.execute_sql("DROP TABLE per")


# ─────── Cycle 7: End-to-end silent output ───────


class TestEndToEndSilent:
    def test_full_crud_workflow_silent(self, clean_data_dir, monkeypatch):
        monkeypatch.setattr(common_db, 'VERBOSE', False)
        common_db.shared_schema = schema_db.Schema()

        with patch('sys.stdout', new_callable=io.StringIO) as fake_out:
            query_plan_db.execute_sql("CREATE TABLE e2e (name str(10), num int)")
            query_plan_db.execute_sql("INSERT INTO e2e VALUES ('alice', 42)")
            query_plan_db.execute_sql("SELECT * FROM e2e")
            query_plan_db.execute_sql("DESCRIBE e2e")
            query_plan_db.execute_sql("SHOW TABLES")
            query_plan_db.execute_sql("DROP TABLE e2e")
        output = fake_out.getvalue()

        # User-facing output should appear
        assert 'created' in output.lower() or 'Table' in output
        # DESCRIBE should print column headers
        assert 'Field' in output or 'Type' in output
        # DROP TABLE should print confirmation
        assert 'dropped' in output.lower() or 'DROP' in output

        # Noisy debug output should NOT appear
        assert '__init__ of Schema' not in output
        assert 'tableNum in schema file' not in output
        assert 'number of fields is' not in output
        assert 'has been opened' not in output
        assert 'Block_ID=' not in output
        assert 'filed length' not in output
