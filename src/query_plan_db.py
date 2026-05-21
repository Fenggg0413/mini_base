# query_plan_db.py
# Build and execute a logical plan for simple SQL queries.

import os

from . import common_db
from . import storage_db


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

    storage = storage_db.Storage(table_name.encode('utf-8'))
    fields = storage.getFieldList()
    records = storage.getRecord()

    column_meta = []
    for field_name, field_type, _field_len in fields:
        column_meta.append({
            'name': field_name.strip().decode('utf-8', errors='replace'),
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
    value = row[(table_norm, field_norm)]
    field_type = context['tables'][table_norm]['types'][field_norm]
    return value, field_type


def _compare_eq(left_value, left_type, right_value, right_type):
    if isinstance(left_type, int) and isinstance(right_type, str):
        right_value = _coerce_literal_for_column(right_value, left_type)
    elif isinstance(right_type, int) and isinstance(left_type, str):
        left_value = _coerce_literal_for_column(left_value, right_type)
    return left_value == right_value


def _apply_filter(rows, conditions, context):
    out = []
    for row in rows:
        ok = True
        for cond in conditions:
            left_value, left_type = _eval_operand(cond['left'], row, context)
            right_value, right_type = _eval_operand(cond['right'], row, context)
            if cond['op'] != '=':
                raise SqlExecutionError("Unsupported operator '%s'" % cond['op'])
            if not _compare_eq(left_value, left_type, right_value, right_type):
                ok = False
                break
        if ok:
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
            'conditions': ast['where'],
            'child': {
                'op': 'cross_join',
                'tables': ast['tables'],
            },
        },
    }


def _run_plan(plan):
    tables = plan['child']['child']['tables']
    scans = [_scan_table(table_name) for table_name in tables]
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

    conditions = plan['child']['conditions']
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
