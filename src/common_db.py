#----------------------------------------
# common_db.py
# author: Jingyu Han   hjymail@163.com
# modified by:
#--------------------------------------------
# the module provides the constants, class, data structures which
# are used for all the program
#--------------------------------------------------
import os

BLOCK_SIZE=4096 # the size of one block during reading files

# 所有运行产物（*.dat, all.sch, *.log, *.ind）集中存放的目录。
# 基于本文件位置定位到项目根下的 data/，与运行时 CWD 无关。
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data'))
os.makedirs(DATA_DIR, exist_ok=True)


def data_path(name):
    """拼接 data/ 目录下的文件路径，兼容 str 与 bytes 文件名。"""
    if isinstance(name, bytes):
        return os.path.join(DATA_DIR.encode('utf-8'), name)
    return os.path.join(DATA_DIR, name)


global_lexer=None   # the global lex, which is filled in the moudle lex_db.py
global_parser=None  # the global yacc, which is filled in the module yacc_db.py
global_syn_tree=None # the global syntax tree, which is filled in parser_db.py
global_logical_tree=None # global variable, which is to store the logical query plan tree
current_transaction_id=None # 全局事务ID

# ----------------------------------------------------------------------------------------
#  Validate and convert input value according to field type and length constraints.
#  Args:
#        value: Input value to be validated
#        field_type: Type of the field (0: String, 1: VarString, 2: Integer, 3: Boolean)
#        max_length: Maximum allowed length for the field
#  Returns:   tuple: (is_valid, converted_value(str), error_message)
# ----------------------------------------------------------------------------------------
def validate_and_convert_value(value, field_type, max_length):
    # Check length constraint
    if len(value) > max_length:
        return False, None, f"Error: Input length exceeds maximum length {max_length}"

    try:
        # Type conversion based on field type
        if field_type == 2:  # Integer type
            converted = int(value)
        elif field_type == 3:  # Boolean type
            if value.lower() not in ['true', 'false', '1', '0']:
                return False, None, "Error: Please enter true/false or 1/0"
            converted = bool(int(value)) if value in ['1', '0'] else value.lower() == 'true'
        else:  # String types (0 and 1)
            converted = value

        return True, str(converted), None
    except ValueError:
        return False, None, "Invalid input format, please try again"


#-----------------------------
# the following is the structure of tree node
#---------------------------------
class Node:
    def __init__(self,value,children,varList=None):
        self.value=value
        self.var=varList
        if children:
            self.children=children
        else:
            self.children=[]
            

#-------------------------
# show() function is to traverse through the tree
#---------------------------
def show(node_obj):
    if isinstance(node_obj,Node):# it is a Node object
        print (node_obj.value)
        if node_obj.var:
            print (node_obj.var)
        if node_obj.children:
            
            for i in range(len(node_obj.children)):
                show(node_obj.children[i])
    if isinstance(node_obj,str):# it is a string object
        print (node_obj)


