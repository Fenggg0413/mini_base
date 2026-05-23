# parser_db.py
# SQL parser for SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, DROP TABLE statements.

import ply.yacc as yacc

from . import common_db
from .lex_db import tokens

_parser_instance = None

precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
)


def _make_column_ref(value):
    return {'type': 'column', 'table': value.get('table'), 'name': value['name']}


# --- Top-level statement dispatch ---

def p_statement_insert(t):
    'Statement : InsertStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]

def p_statement_update(t):
    'Statement : UpdateStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]

def p_statement_delete(t):
    'Statement : DeleteStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]

def p_statement_create(t):
    'Statement : CreateStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]

def p_statement_drop(t):
    'Statement : DropStmt'
    common_db.global_syn_tree = t[1]
    t[0] = t[1]

def p_statement_select(t):
    'Statement : Query'
    t[0] = t[1]


# --- INSERT ---

def p_insert_with_columns(t):
    'InsertStmt : INSERT INTO IDENT LPAREN ColumnList RPAREN VALUES LPAREN ValueList RPAREN OptSemi'
    t[0] = {'type': 'insert', 'table': t[3], 'columns': t[5], 'values': t[9]}

def p_insert_without_columns(t):
    'InsertStmt : INSERT INTO IDENT VALUES LPAREN ValueList RPAREN OptSemi'
    t[0] = {'type': 'insert', 'table': t[3], 'columns': None, 'values': t[6]}

def p_value_list_many(t):
    'ValueList : Literal COMMA ValueList'
    t[0] = [t[1]] + t[3]

def p_value_list_one(t):
    'ValueList : Literal'
    t[0] = [t[1]]


# --- UPDATE ---

def p_update_stmt(t):
    'UpdateStmt : UPDATE IDENT SET UpdateList WhereOpt OptSemi'
    t[0] = {'type': 'update', 'table': t[2], 'assignments': t[4], 'where': t[5]}

def p_update_list_many(t):
    'UpdateList : UpdateItem COMMA UpdateList'
    t[0] = [t[1]] + t[3]

def p_update_list_one(t):
    'UpdateList : UpdateItem'
    t[0] = [t[1]]

def p_update_item(t):
    'UpdateItem : IDENT EQ Operand'
    t[0] = {'field': t[1], 'value': t[3]}


# --- DELETE ---

def p_delete_stmt(t):
    'DeleteStmt : DELETE FROM IDENT WhereOpt OptSemi'
    t[0] = {'type': 'delete', 'table': t[3], 'where': t[4]}


# --- CREATE TABLE ---

def p_create_stmt(t):
    'CreateStmt : CREATE TABLE IDENT LPAREN FieldDefList RPAREN OptSemi'
    t[0] = {'type': 'create_table', 'table': t[3], 'fields': t[5]}

def p_field_def_list_many(t):
    'FieldDefList : FieldDef COMMA FieldDefList'
    t[0] = [t[1]] + t[3]

def p_field_def_list_one(t):
    'FieldDefList : FieldDef'
    t[0] = [t[1]]

def p_field_def_int(t):
    'FieldDef : IDENT INT_TYPE'
    t[0] = (t[1], 2, 10)

def p_field_def_string(t):
    'FieldDef : IDENT STRING_TYPE LPAREN INT RPAREN'
    t[0] = (t[1], 0, t[4])

def p_field_def_bool(t):
    'FieldDef : IDENT BOOL_TYPE'
    t[0] = (t[1], 3, 1)


# --- DROP TABLE ---

def p_drop_stmt(t):
    'DropStmt : DROP TABLE IDENT OptSemi'
    t[0] = {'type': 'drop_table', 'table': t[3]}


# --- SELECT (enhanced) ---

def p_query(t):
    'Query : SELECT SelectList FROM TableList WhereOpt OrderByOpt OptSemi'
    t[0] = {
        'type': 'select',
        'columns': t[2],
        'tables': t[4],
        'where': t[5],
        'order_by': t[6],
    }
    common_db.global_syn_tree = t[0]

def p_select_list_star(t):
    'SelectList : STAR'
    t[0] = [{'type': 'star'}]

def p_select_list_columns(t):
    'SelectList : ColumnList'
    t[0] = t[1]

def p_column_list_many(t):
    'ColumnList : ColumnRef COMMA ColumnList'
    t[0] = [t[1]] + t[3]

def p_column_list_one(t):
    'ColumnList : ColumnRef'
    t[0] = [t[1]]

def p_table_list_many(t):
    'TableList : IDENT COMMA TableList'
    t[0] = [t[1]] + t[3]

def p_table_list_one(t):
    'TableList : IDENT'
    t[0] = [t[1]]


# --- WHERE with OR/NOT/parentheses ---

def p_where_opt(t):
    '''WhereOpt : WHERE ConditionList
                | empty'''
    if len(t) == 3:
        t[0] = t[2]
    else:
        t[0] = []

def p_condition_list_or(t):
    'ConditionList : ConditionList OR ConditionList'
    t[0] = {'type': 'or', 'left': t[1], 'right': t[3]}

def p_condition_list_and(t):
    'ConditionList : ConditionList AND ConditionList'
    t[0] = {'type': 'and', 'left': t[1], 'right': t[3]}

def p_condition_list_not(t):
    'ConditionList : NOT ConditionList'
    t[0] = {'type': 'not', 'child': t[2]}

def p_condition_list_paren(t):
    'ConditionList : LPAREN ConditionList RPAREN'
    t[0] = t[2]

def p_condition_list_single(t):
    'ConditionList : Condition'
    t[0] = t[1]


# --- Comparison operators ---

def p_condition(t):
    '''Condition : Operand EQ Operand
                 | Operand NEQ Operand
                 | Operand LT Operand
                 | Operand GT Operand
                 | Operand LTE Operand
                 | Operand GTE Operand'''
    op_map = {'=': '=', '<>': '!=', '!=': '!=', '<': '<', '>': '>', '<=': '<=', '>=': '>='}
    t[0] = {'type': 'condition', 'left': t[1], 'op': op_map.get(t[2], t[2]), 'right': t[3]}


# --- ORDER BY ---

def p_order_by_opt_some(t):
    'OrderByOpt : ORDER BY OrderList'
    t[0] = t[3]

def p_order_by_opt_none(t):
    'OrderByOpt : empty'
    t[0] = []

def p_order_list_many(t):
    'OrderList : OrderItem COMMA OrderList'
    t[0] = [t[1]] + t[3]

def p_order_list_one(t):
    'OrderList : OrderItem'
    t[0] = [t[1]]

def p_order_item_asc(t):
    'OrderItem : IDENT ASC'
    t[0] = {'field': t[1], 'direction': 'asc'}

def p_order_item_desc(t):
    'OrderItem : IDENT DESC'
    t[0] = {'field': t[1], 'direction': 'desc'}

def p_order_item_default(t):
    'OrderItem : IDENT'
    t[0] = {'field': t[1], 'direction': 'asc'}


# --- Operand and Literal ---

def p_operand_column(t):
    'Operand : ColumnRef'
    t[0] = _make_column_ref(t[1])

def p_operand_literal(t):
    'Operand : Literal'
    t[0] = t[1]

def p_column_ref_qualified(t):
    'ColumnRef : IDENT DOT IDENT'
    t[0] = {'type': 'column', 'table': t[1], 'name': t[3]}

def p_column_ref_unqualified(t):
    'ColumnRef : IDENT'
    t[0] = {'type': 'column', 'table': None, 'name': t[1]}

def p_literal_int(t):
    'Literal : INT'
    t[0] = {'type': 'literal', 'value': t[1], 'value_type': 'int'}

def p_literal_string(t):
    'Literal : STRING'
    t[0] = {'type': 'literal', 'value': t[1], 'value_type': 'string'}

def p_literal_bool(t):
    'Literal : BOOL'
    t[0] = {'type': 'literal', 'value': t[1], 'value_type': 'bool'}


# --- Utility ---

def p_opt_semi(t):
    '''OptSemi : SEMI
               | empty'''
    t[0] = None

def p_empty(t):
    'empty :'
    t[0] = None

def p_error(t):
    if t is None:
        raise SyntaxError('Unexpected end of SQL')
    raise SyntaxError("Syntax error near '%s'" % t.value)


def set_handle():
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = yacc.yacc(write_tables=0, debug=False, start='Statement')
    common_db.global_parser = _parser_instance
    if common_db.global_parser is None:
        print('wrong when yacc object is created')