# parser_db.py
# SQL parser for simple SELECT-FROM-[WHERE] statements.

import ply.yacc as yacc

from . import common_db
from .lex_db import tokens

_parser_instance = None


def _make_column_ref(value):
    return {'type': 'column', 'table': value.get('table'), 'name': value['name']}


def p_query(t):
    'Query : SELECT SelectList FROM TableList WhereOpt OptSemi'
    ast = {
        'type': 'select',
        'columns': t[2],
        'tables': t[4],
        'where': t[5],
    }
    common_db.global_syn_tree = ast
    t[0] = ast


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


def p_where_opt(t):
    '''WhereOpt : WHERE ConditionList
                | empty'''
    if len(t) == 3:
        t[0] = t[2]
    else:
        t[0] = []


def p_opt_semi(t):
    '''OptSemi : SEMI
               | empty'''
    t[0] = None


def p_condition_list_many(t):
    'ConditionList : Condition AND ConditionList'
    t[0] = [t[1]] + t[3]


def p_condition_list_one(t):
    'ConditionList : Condition'
    t[0] = [t[1]]


def p_condition(t):
    'Condition : Operand EQ Operand'
    t[0] = {'left': t[1], 'op': '=', 'right': t[3]}


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
        _parser_instance = yacc.yacc(write_tables=0, debug=False)
    common_db.global_parser = _parser_instance
    if common_db.global_parser is None:
        print('wrong when yacc object is created')
