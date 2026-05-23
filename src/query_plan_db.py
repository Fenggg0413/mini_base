# query_plan_db.py
# Build and execute a logical plan for SQL queries.
# Supports SELECT (with WHERE enhancements + ORDER BY), INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE.

import os

from . import common_db
from . import storage_db
from . import index_db
from . import index_catalog
from . import lex_db
from . import parser_db


class SqlExecutionError(Exception):
    pass


def _norm(name):
    return name.lower()


def _decode_if_bytes(value):
    if isinstance(value, bytes):
        return value.strip().decode('utf-8', errors='replace')
    return value


def _table_file_exists(table_name):
    return os.path.exists(common_db.data_path(table_name + '.dat'))


def _resolve_table_name(table_name):
    if _table_file_exists(table_name):
        return table_name

    expected = table_name.lower() + '.dat'
    for filename in os.listdir(common_db.DATA_DIR):
        if filename.lower() == expected:
            return filename[:-4]
    raise SqlExecutionError("Table '%s' does not exist" % table_name)


def _scan_table(table_name):
    table_name = _resolve_table_name(table_name)

    storage = storage_db.Storage(table_name)
    fields = storage.getFieldList()
    records = storage.getRecord()

    column_meta = []
    for field_name, field_type, _field_len in fields:
        name = field_name.strip() if isinstance(field_name, str) else field_name.strip().decode('utf-8', errors='replace')
        column_meta.append({
            'name': name,
            'type': field_type,
        })

    rows = []
    for record in records:
        row = {}
        for index, col in enumerate(column_meta):
            value = record[index]
            if col['type'] in (0, 1):
                value = _decode_if_bytes(value)
            row[(_norm(table_name), _norm(col['name']))] = value
        rows.append(row)

    return {
        'table': table_name,
        'table_norm': _norm(table_name),
        'columns': column_meta,
        'rows': rows,
        'storage': storage,
    }


def _index_scan_table(table_name, field_name, field_value):
    table_name_raw = _resolve_table_name(table_name)

    idx = index_db.Index(table_name_raw)
    results = idx.search_index(field_value)
    idx.close()

    if not results:
        storage = storage_db.Storage(table_name_raw)
        fields = storage.getFieldList()
        column_meta = []
        for fn, ft, _fl in fields:
            name = fn.strip() if isinstance(fn, str) else fn.strip().decode('utf-8', errors='replace')
            column_meta.append({'name': name, 'type': ft})
        return {
            'table': table_name_raw,
            'table_norm': _norm(table_name_raw),
            'columns': column_meta,
            'rows': [],
            'storage': storage,
        }

    storage = storage_db.Storage(table_name_raw)
    fields = storage.getFieldList()

    column_meta = []
    for fn, ft, _fl in fields:
        name = fn.strip() if isinstance(fn, str) else fn.strip().decode('utf-8', errors='replace')
        column_meta.append({'name': name, 'type': ft})

    rows = []
    seen = set()
    for blk_id, rec_id in results:
        pos_key = (blk_id, rec_id)
        if pos_key in seen:
            continue
        seen.add(pos_key)
        record = storage.get_record_by_position(blk_id, rec_id)
        if record is None:
            continue
        row = {}
        for i, col in enumerate(column_meta):
            value = record[i]
            if col['type'] in (0, 1):
                value = _decode_if_bytes(value)
            row[(_norm(table_name_raw), _norm(col['name']))] = value
        rows.append(row)

    return {
        'table': table_name_raw,
        'table_norm': _norm(table_name_raw),
        'columns': column_meta,
        'rows': rows,
        'storage': storage,
    }


def _cross_join(left_rows, right_rows):
    if not left_rows:
        return []
    if not right_rows:
        return []
    out = []
    for left in left_rows:
        for right in right_rows:
            merged = dict(left)
            merged.update(right)
            out.append(merged)
    return out


def _build_scan_context(scans):
    context = {
        'tables': {},
        'table_order': [],
        'field_candidates': {},
    }

    for scan in scans:
        table_norm = scan['table_norm']
        context['tables'][table_norm] = {
            'name': scan['table'],
            'columns': {},
            'types': {},
        }
        context['table_order'].append(table_norm)
        for col in scan['columns']:
            field_norm = _norm(col['name'])
            context['tables'][table_norm]['columns'][field_norm] = col['name']
            context['tables'][table_norm]['types'][field_norm] = col['type']
            context['field_candidates'].setdefault(field_norm, []).append((table_norm, field_norm))
    return context


def _resolve_column(column_ref, context):
    field_norm = _norm(column_ref['name'])
    table_name = column_ref.get('table')

    if table_name:
        table_norm = _norm(table_name)
        table_entry = context['tables'].get(table_norm)
        if table_entry is None:
            raise SqlExecutionError("Unknown table '%s'" % table_name)
        if field_norm not in table_entry['columns']:
            raise SqlExecutionError("Unknown column '%s.%s'" % (table_name, column_ref['name']))
        return table_norm, field_norm

    matches = context['field_candidates'].get(field_norm, [])
    if len(matches) == 0:
        raise SqlExecutionError("Unknown column '%s'" % column_ref['name'])
    if len(matches) > 1:
        raise SqlExecutionError("Ambiguous column '%s'" % column_ref['name'])
    return matches[0]


def _literal_to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        temp = value.strip().lower()
        if temp in ('true', '1'):
            return True
        if temp in ('false', '0'):
            return False
    raise SqlExecutionError("Cannot cast '%s' to bool" % value)


def _coerce_literal_for_column(literal_value, field_type):
    if field_type == 2:
        return int(literal_value)
    if field_type == 3:
        return _literal_to_bool(literal_value)
    return str(literal_value)


def _eval_operand(operand, row, context):
    if operand['type'] == 'literal':
        return operand['value'], operand.get('value_type')

    table_norm, field_norm = _resolve_column(operand, context)
    value = row.get((table_norm, field_norm))
    if value is None:
        raise SqlExecutionError("Column '%s' not found in row" % operand['name'])
    field_type = context['tables'][table_norm]['types'][field_norm]
    return value, field_type


def _compare_values(left_value, left_type, right_value, right_type, op):
    if isinstance(left_type, int) and isinstance(right_type, str):
        right_value = _coerce_literal_for_column(right_value, left_type)
    elif isinstance(right_type, int) and isinstance(left_type, str):
        left_value = _coerce_literal_for_column(left_value, right_type)

    if isinstance(left_value, bytes):
        left_value = left_value.strip().decode('utf-8', errors='replace')
    if isinstance(right_value, bytes):
        right_value = right_value.strip().decode('utf-8', errors='replace')

    if isinstance(left_value, bool):
        left_value = 1 if left_value else 0
    if isinstance(right_value, bool):
        right_value = 1 if right_value else 0

    if op == '=':
        return left_value == right_value
    elif op == '!=':
        return left_value != right_value
    elif op == '<':
        return left_value < right_value
    elif op == '>':
        return left_value > right_value
    elif op == '<=':
        return left_value <= right_value
    elif op == '>=':
        return left_value >= right_value
    else:
        raise SqlExecutionError("Unsupported operator '%s'" % op)


def _eval_condition(cond, row, context):
    if cond is None:
        return True

    if isinstance(cond, list):
        for c in cond:
            if not _eval_condition(c, row, context):
                return False
        return True

    ctype = cond.get('type', 'condition')

    if ctype == 'and':
        return _eval_condition(cond['left'], row, context) and _eval_condition(cond['right'], row, context)
    elif ctype == 'or':
        return _eval_condition(cond['left'], row, context) or _eval_condition(cond['right'], row, context)
    elif ctype == 'not':
        return not _eval_condition(cond['child'], row, context)
    elif ctype == 'condition':
        left_value, left_type = _eval_operand(cond['left'], row, context)
        right_value, right_type = _eval_operand(cond['right'], row, context)
        return _compare_values(left_value, left_type, right_value, right_type, cond['op'])
    else:
        raise SqlExecutionError("Unknown condition type '%s'" % ctype)


def _apply_filter(rows, conditions, context):
    if not conditions:
        return rows
    out = []
    for row in rows:
        if _eval_condition(conditions, row, context):
            out.append(row)
    return out


def _project_columns(columns, context):
    if len(columns) == 1 and columns[0]['type'] == 'star':
        selected = []
        for table_norm in context['table_order']:
            table_name = context['tables'][table_norm]['name']
            for field_norm, field_name in context['tables'][table_norm]['columns'].items():
                selected.append(((table_norm, field_norm), '%s.%s' % (table_name, field_name)))
        return selected

    selected = []
    for col in columns:
        table_norm, field_norm = _resolve_column(col, context)
        table_name = context['tables'][table_norm]['name']
        field_name = context['tables'][table_norm]['columns'][field_norm]
        selected.append(((table_norm, field_norm), '%s.%s' % (table_name, field_name)))
    return selected


def _invert_string(s):
    return ''.join(chr(0x10FFFF - ord(c)) for c in s)


def construct_logical_tree():
    ast = common_db.global_syn_tree
    if not ast:
        print('there is no data in the syntax tree in the construct_logical_tree')
        common_db.global_logical_tree = None
        return

    common_db.global_logical_tree = {
        'op': 'project',
        'columns': ast['columns'],
        'child': {
            'op': 'filter',
            'conditions': ast.get('where', []),
            'child': {
                'op': 'cross_join',
                'tables': ast['tables'],
            },
        },
    }


def _run_plan(plan):
    tables = plan['child']['child']['tables']
    conditions = plan['child']['conditions']

    if conditions and len(tables) == 1:
        indexed_fields = index_catalog.get_indexed_fields(tables[0].strip())
        use_index = False
        index_table = None
        index_field = None
        index_value = None

        if isinstance(conditions, dict) and conditions.get('type') == 'condition' and conditions['op'] == '=':
            left = conditions['left']
            right = conditions['right']
            if left['type'] == 'column' and right['type'] == 'literal':
                col_name = _norm(left['name'])
                for fname in indexed_fields:
                    if col_name == _norm(fname):
                        use_index = True
                        index_field = fname
                        index_value = right['value']
                        index_table = tables[0]
                        break
            elif right['type'] == 'column' and left['type'] == 'literal':
                col_name = _norm(right['name'])
                for fname in indexed_fields:
                    if col_name == _norm(fname):
                        use_index = True
                        index_field = fname
                        index_value = left['value']
                        index_table = tables[0]
                        break

        if use_index:
            try:
                scan = _index_scan_table(index_table, index_field, index_value)
                scans = [scan]
            except Exception:
                scans = [_scan_table(t) for t in tables]

    if not use_index:
        scans = [_scan_table(t) for t in tables]

    context = _build_scan_context(scans)

    rows = [{}]
    for scan in scans:
        if not scan['rows']:
            rows = []
            break
        if rows == [{}]:
            rows = scan['rows']
        else:
            rows = _cross_join(rows, scan['rows'])

    if conditions:
        rows = _apply_filter(rows, conditions, context)

    selected_columns = _project_columns(plan['columns'], context)
    output_fields = [item[1] for item in selected_columns]
    output_rows = []
    for row in rows:
        output_rows.append([row[item[0]] for item in selected_columns])

    return output_fields, output_rows, True


def execute_logical_tree():
    if not common_db.global_logical_tree:
        print('there is no query plan tree for the execution')
        return

    try:
        output_fields, output_rows, _ = _run_plan(common_db.global_logical_tree)
    except Exception as exc:
        print('WRONG SQL INPUT! %s' % str(exc))
        return

    print(output_fields)
    for row in output_rows:
        print(row)


# ─────── Unified SQL Execution Entry Point ───────

def execute_sql(sql_str):
    """Parse and execute any SQL statement."""
    lex_db.set_lex_handle()
    parser_db.set_handle()
    common_db.global_syn_tree = None
    common_db.global_logical_tree = None

    ast = common_db.global_parser.parse(sql_str.strip(), lexer=common_db.global_lexer)
    if ast is None:
        raise SqlExecutionError("Failed to parse SQL statement")

    stmt_type = ast.get('type')
    if stmt_type == 'select':
        return execute_select(ast)
    elif stmt_type == 'insert':
        return execute_insert(ast)
    elif stmt_type == 'update':
        return execute_update(ast)
    elif stmt_type == 'delete':
        return execute_delete(ast)
    elif stmt_type == 'create_table':
        return execute_create_table(ast)
    elif stmt_type == 'drop_table':
        return execute_drop_table(ast)
    else:
        raise SqlExecutionError("Unknown SQL statement type: '%s'" % stmt_type)


def execute_select(ast):
    """Execute a SELECT statement with enhanced WHERE and ORDER BY."""
    from . import schema_db

    tables = ast['tables']
    conditions = ast.get('where', [])
    order_by = ast.get('order_by', [])

    use_index = False
    index_table = None
    index_field = None
    index_value = None

    if conditions and len(tables) == 1:
        indexed_fields = index_catalog.get_indexed_fields(tables[0].strip())
        if isinstance(conditions, dict) and conditions.get('type') == 'condition' and conditions['op'] == '=':
            left = conditions['left']
            right = conditions['right']
            if left['type'] == 'column' and right['type'] == 'literal':
                col_name = _norm(left['name'])
                for fname in indexed_fields:
                    if col_name == _norm(fname):
                        use_index = True
                        index_field = fname
                        index_value = right['value']
                        index_table = tables[0]
                        break
            elif right['type'] == 'column' and left['type'] == 'literal':
                col_name = _norm(right['name'])
                for fname in indexed_fields:
                    if col_name == _norm(fname):
                        use_index = True
                        index_field = fname
                        index_value = left['value']
                        index_table = tables[0]
                        break

    if use_index:
        try:
            scan = _index_scan_table(index_table, index_field, index_value)
            scans = [scan]
        except Exception:
            scans = [_scan_table(t) for t in tables]
    else:
        scans = [_scan_table(t) for t in tables]

    context = _build_scan_context(scans)

    rows = [{}]
    for scan in scans:
        if not scan['rows']:
            rows = []
            break
        if rows == [{}]:
            rows = scan['rows']
        else:
            rows = _cross_join(rows, scan['rows'])

    if conditions:
        rows = _apply_filter(rows, conditions, context)

    selected_columns = _project_columns(ast['columns'], context)
    output_fields = [item[1] for item in selected_columns]

    if order_by:
        def sort_key(row):
            key = []
            for ob in order_by:
                col_ref = {'type': 'column', 'table': None, 'name': ob['field']}
                table_norm, field_norm = _resolve_column(col_ref, context)
                val = row.get((table_norm, field_norm), '')
                direction = ob.get('direction', 'asc')
                if direction == 'desc':
                    if isinstance(val, bool):
                        val = not val
                    elif isinstance(val, (int, float)):
                        val = -val
                    elif isinstance(val, str):
                        val = _invert_string(val)
                key.append(val)
            return key
        rows.sort(key=sort_key)

    output_rows = []
    for row in rows:
        output_rows.append([row[item[0]] for item in selected_columns])

    print(output_fields)
    for row in output_rows:
        print(row)

    return output_fields, output_rows, True


def execute_insert(ast):
    """Execute an INSERT statement."""
    from . import schema_db

    table_name = ast['table'].strip()
    columns = ast.get('columns')
    values = ast['values']

    schema_obj = schema_db.Schema()
    if not schema_obj.find_table(table_name):
        del schema_obj
        raise SqlExecutionError("Table '%s' does not exist" % table_name)

    storage = storage_db.Storage(table_name)
    field_list = storage.getFieldList()

    if columns is None:
        if len(values) != len(field_list):
            del storage
            del schema_obj
            raise SqlExecutionError("Column count mismatch: expected %d values, got %d" % (len(field_list), len(values)))
        value_strings = []
        for val_dict in values:
            value_strings.append(str(val_dict['value']))
    else:
        # columns may be a list of dicts from parser or a list of strings
        col_names = []
        for c in columns:
            if isinstance(c, dict):
                col_names.append(c['name'].lower())
            else:
                col_names.append(c.lower())

        if len(col_names) != len(values):
            del storage
            del schema_obj
            raise SqlExecutionError("Column count mismatch: %d columns but %d values" % (len(col_names), len(values)))

        col_val_map = {}
        for col_name, val_dict in zip(col_names, values):
            col_val_map[col_name] = str(val_dict['value'])

        value_strings = []
        for fname, ftype, flen in field_list:
            fname_clean = fname.strip().lower() if isinstance(fname, str) else fname.strip().decode('utf-8').lower()
            if fname_clean in col_val_map:
                value_strings.append(col_val_map[fname_clean])
            else:
                del storage
                del schema_obj
                raise SqlExecutionError("No value provided for field '%s'" % fname.strip())

    for i, (fname, ftype, flen) in enumerate(field_list):
        is_valid, converted, error_msg = common_db.validate_and_convert_value(value_strings[i], ftype, flen)
        if not is_valid:
            del storage
            del schema_obj
            raise SqlExecutionError("Invalid value for field '%s': %s" % (fname.strip(), error_msg))
        value_strings[i] = converted

    result = storage.insert_record(value_strings, txn_id=common_db.current_transaction_id)
    if result:
        print("1 row inserted.")
    else:
        print("Insert failed.")
    del storage
    del schema_obj
    return result


def execute_update(ast):
    """Execute an UPDATE statement."""
    from . import schema_db

    table_name = ast['table'].strip()
    assignments = ast['assignments']
    conditions = ast.get('where', [])

    schema_obj = schema_db.Schema()
    if not schema_obj.find_table(table_name):
        del schema_obj
        raise SqlExecutionError("Table '%s' does not exist" % table_name)

    storage = storage_db.Storage(table_name)
    field_list = storage.getFieldList()

    field_map = {}
    for i, (fname, ftype, flen) in enumerate(field_list):
        fname_clean = fname.strip().lower() if isinstance(fname, str) else fname.strip().decode('utf-8').lower()
        field_map[fname_clean] = (i, ftype, flen)

    update_pairs = []
    for assign in assignments:
        fname = assign['field'].strip().lower()
        if fname not in field_map:
            del storage
            del schema_obj
            raise SqlExecutionError("Unknown field '%s'" % assign['field'])
        fidx, ftype, flen = field_map[fname]

        val_dict = assign['value']
        if val_dict['type'] == 'literal':
            val_str = str(val_dict['value'])
            is_valid, converted, error_msg = common_db.validate_and_convert_value(val_str, ftype, flen)
            if not is_valid:
                del storage
                del schema_obj
                raise SqlExecutionError("Invalid value for field '%s': %s" % (assign['field'], error_msg))
            update_pairs.append((fidx, converted))
        else:
            del storage
            del schema_obj
            raise SqlExecutionError("UPDATE SET only supports literal values")

    context = {
        'tables': {},
        'table_order': [],
        'field_candidates': {},
    }
    table_norm = _norm(table_name)
    context['table_order'].append(table_norm)
    context['tables'][table_norm] = {
        'name': table_name,
        'columns': {},
        'types': {},
    }
    for fn, ft, _fl in field_list:
        fn_clean = fn.strip().lower() if isinstance(fn, str) else fn.strip().decode('utf-8').lower()
        context['tables'][table_norm]['columns'][fn_clean] = fn.strip()
        context['tables'][table_norm]['types'][fn_clean] = ft
        context['field_candidates'].setdefault(fn_clean, []).append((table_norm, fn_clean))

    records = storage.getRecord()
    matching_indices = []
    for i, record in enumerate(records):
        row = {}
        for j, (fn, ft, _fl) in enumerate(field_list):
            fn_clean = fn.strip().lower() if isinstance(fn, str) else fn.strip().decode('utf-8').lower()
            row[(table_norm, fn_clean)] = record[j]
        if _eval_condition(conditions, row, context) if conditions else True:
            matching_indices.append(i)

    if not matching_indices:
        print("0 rows updated.")
        del storage
        del schema_obj
        return 0

    # Strategy: delete table data, recreate, and re-insert with modifications
    # This avoids the over-update bug with storage.update_record() and
    # handles all WHERE condition types correctly (not just equality).
    updated_records = []
    for i, record in enumerate(records):
        rec_list = list(record)
        if i in set(matching_indices):
            for fidx, new_val in update_pairs:
                rec_list[fidx] = new_val
        updated_records.append(tuple(rec_list))

    # Delete all data and recreate
    storage.delete_table_data(table_name)
    new_storage = storage_db.Storage.create_table(table_name, field_list)

    for record in updated_records:
        value_strings = []
        for j, (fn, ft, fl) in enumerate(field_list):
            val = record[j]
            if ft == 2:
                value_strings.append(str(int(val)))
            elif ft == 3:
                value_strings.append('true' if val else 'false')
            else:
                if isinstance(val, bytes):
                    val = val.decode('utf-8').strip()
                value_strings.append(str(val).strip() if isinstance(val, str) else str(val).strip())
        new_storage.insert_record(value_strings, txn_id=None)

    total_updated = len(matching_indices)
    print("%d row(s) updated." % total_updated)
    del new_storage
    del storage
    del schema_obj
    return total_updated


def execute_delete(ast):
    """Execute a DELETE statement."""
    from . import schema_db

    table_name = ast['table'].strip()
    conditions = ast.get('where', [])

    schema_obj = schema_db.Schema()
    if not schema_obj.find_table(table_name):
        del schema_obj
        raise SqlExecutionError("Table '%s' does not exist" % table_name)

    storage = storage_db.Storage(table_name)
    field_list = storage.getFieldList()

    field_map = {}
    for i, (fname, ftype, flen) in enumerate(field_list):
        fname_clean = fname.strip().lower() if isinstance(fname, str) else fname.strip().decode('utf-8').lower()
        field_map[fname_clean] = (i, ftype, flen)

    context = {
        'tables': {},
        'table_order': [],
        'field_candidates': {},
    }
    table_norm = _norm(table_name)
    context['table_order'].append(table_norm)
    context['tables'][table_norm] = {
        'name': table_name,
        'columns': {},
        'types': {},
    }
    for fn, ft, _fl in field_list:
        fn_clean = fn.strip().lower() if isinstance(fn, str) else fn.strip().decode('utf-8').lower()
        context['tables'][table_norm]['columns'][fn_clean] = fn.strip()
        context['tables'][table_norm]['types'][fn_clean] = ft
        context['field_candidates'].setdefault(fn_clean, []).append((table_norm, fn_clean))

    # No conditions = delete all
    if not conditions:
        total_to_delete = len(storage.getRecord())
        if total_to_delete > 0:
            storage.delete_table_data(table_name)
            new_storage = storage_db.Storage.create_table(table_name, field_list)
            del new_storage
        print("%d row(s) deleted." % total_to_delete)
        del storage
        del schema_obj
        return total_to_delete

    # Simple equality condition — use delete_record directly
    if isinstance(conditions, dict) and conditions.get('type') == 'condition' and conditions['op'] == '=':
        left = conditions['left']
        right = conditions['right']
        field_idx = None
        val_str = None

        if left['type'] == 'column' and right['type'] == 'literal':
            fn = left['name'].strip().lower()
            if fn in field_map:
                field_idx = field_map[fn][0]
                val_str = str(right['value'])
        elif right['type'] == 'column' and left['type'] == 'literal':
            fn = right['name'].strip().lower()
            if fn in field_map:
                field_idx = field_map[fn][0]
                val_str = str(left['value'])

        if field_idx is not None:
            deleted_count = storage.delete_record(field_idx, val_str)
            print("%d row(s) deleted." % deleted_count)
            del storage
            del schema_obj
            return deleted_count

    # Complex conditions — delete all + re-insert non-matching
    records = storage.getRecord()
    non_matching = []
    for record in records:
        row = {}
        for j, (fn, ft, _fl) in enumerate(field_list):
            fn_clean = fn.strip().lower() if isinstance(fn, str) else fn.strip().decode('utf-8').lower()
            row[(table_norm, fn_clean)] = record[j]
        if not _eval_condition(conditions, row, context):
            non_matching.append(record)

    deleted_count = len(records) - len(non_matching)

    # Delete all data and recreate
    storage.delete_table_data(table_name)
    new_storage = storage_db.Storage.create_table(table_name, field_list)
    for record in non_matching:
        value_strings = []
        for j, (fn, ft, fl) in enumerate(field_list):
            val = record[j]
            if ft == 2:
                value_strings.append(str(int(val)))
            elif ft == 3:
                value_strings.append('true' if val else 'false')
            else:
                if isinstance(val, bytes):
                    val = val.decode('utf-8').strip()
                value_strings.append(str(val).strip() if isinstance(val, str) else str(val).strip())
        new_storage.insert_record(value_strings, txn_id=None)

    print("%d row(s) deleted." % deleted_count)
    del new_storage
    del storage
    del schema_obj
    return deleted_count


def execute_create_table(ast):
    """Execute a CREATE TABLE statement."""
    from . import schema_db

    table_name = ast['table'].strip()
    fields = ast['fields']

    if len(table_name) > 10:
        raise SqlExecutionError("Table name '%s' exceeds maximum length of 10" % table_name)
    if len(fields) > 5:
        raise SqlExecutionError("Maximum 5 fields per table, got %d" % len(fields))
    for fname, ftype, flen in fields:
        if len(fname) > 10:
            raise SqlExecutionError("Field name '%s' exceeds maximum length of 10" % fname)

    schema_obj = schema_db.Schema()
    if schema_obj.find_table(table_name):
        del schema_obj
        raise SqlExecutionError("Table '%s' already exists" % table_name)

    storage = storage_db.Storage.create_table(table_name, fields)
    field_list = storage.getFieldList()
    del storage

    schema_obj.appendTable(table_name, field_list)
    del schema_obj

    print("Table '%s' created." % table_name)
    return True


def execute_drop_table(ast):
    """Execute a DROP TABLE statement."""
    from . import schema_db

    table_name = ast['table'].strip()

    schema_obj = schema_db.Schema()
    if not schema_obj.find_table(table_name):
        del schema_obj
        raise SqlExecutionError("Table '%s' does not exist" % table_name)

    index_catalog.drop_table_indexes(table_name)

    storage = storage_db.Storage(table_name)
    storage.delete_table_data(table_name)
    del storage

    schema_obj.delete_table_schema(table_name)
    del schema_obj

    print("Table '%s' dropped." % table_name)
    return True