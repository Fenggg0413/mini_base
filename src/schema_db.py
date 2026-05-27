#-----------------------------------------------
# schema_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: Ning wang, Yidan Xu
#-----------------------------------------------
# to process the schema data, which is stored in all.sch
# all.sch are divied into three parts,namely metaHead, tableNameHead and body
# metaHead|tableNameHead|body
#-------------------------------------------


import os
import ctypes
import struct
from . import head_db # it is main memory structure for the table schema
from . import common_db





#the following is metaHead structure,which is 12 bytes
"""
isStored    # whether there is data in the all.sch
tableNum    # how many tables
offset      # where the free area begins for body.
"""
META_HEAD_SIZE=12                                           #the First part in the schema file


#the following is the structure of tableNameHead
"""
tablename|numofFeilds|beginOffsetInBody|....|tablename|numofFeilds|beginOffsetInBody|
10 bytes |4 bytes    |4 bytes
"""
MAX_TABLE_NAME_LEN=10                                       # the maximum length of table name
MAX_TABLE_NUM=100                                           # the maximum number of tables in the all.sch
TABLE_NAME_ENTRY_LEN=MAX_TABLE_NAME_LEN+4+4                 # the length of one table name entry
TABLE_NAME_HEAD_SIZE=MAX_TABLE_NUM*TABLE_NAME_ENTRY_LEN     # the SECOND part in the schema file



# the following is for body, which stores the field information of each table and the field information is as follows
"""
field_name   # it is a string
field_type   # it is an integer, 0->str,1->varstr,2->int,3->bool
field_length # it is an integer
"""
MAX_FIELD_NAME_LEN=10                                       # the maximum length of field name
MAX_FIELD_LEN=10+4+4                                         #  the maximum length of one field
MAX_NUM_OF_FIELD_PER_TABLE=5                                # the maximum number of fields in one table
FIELD_ENTRY_SIZE_PER_TABLE=MAX_FIELD_LEN*MAX_NUM_OF_FIELD_PER_TABLE
MAX_FIELD_SECTION_SIZE=FIELD_ENTRY_SIZE_PER_TABLE*MAX_TABLE_NUM #the THIRD part in the schema file



BODY_BEGIN_INDEX=META_HEAD_SIZE+TABLE_NAME_HEAD_SIZE            # Intitially, where the field name, type and length are stored


# -----------------------------
# the table name is padded if its length is smaller than MAX_TABLE_NAME_LEN
# input:
#       tableName: the table name
# -------------------------------
def fillTableName(tableName):
    name = tableName.strip()
    if len(name) < MAX_TABLE_NAME_LEN:
        name = ' ' * (MAX_TABLE_NAME_LEN - len(name)) + name
    return name


class Schema(object):
    '''
    Schema class
    '''

    fileName = common_db.data_path('all.sch')  # the schema file name

    def viewTableNames(self):  # to list all the table names in the all.sch

        if common_db.VERBOSE:
            print ('viewtablenames begin to execute')
        for i in self.headObj.tableNames:
            if common_db.VERBOSE:
                print ('Table name is     ', i[0])
        if common_db.VERBOSE:
            print ('execute Done!')

    #------------------------
    # to show the schema of given table
    # input
    #       table_name
    #------------------------------
    def viewTableStructure(self, table_name):
        if common_db.VERBOSE:
            print(f'the structure of table {table_name} is as follows:')
        
        # Iterate through the table name list to find the matching table
        for i in range(len(self.headObj.tableNames)):
            tname = self.headObj.tableNames[i][0]
            if isinstance(tname, bytes):
                tname = tname.decode('utf-8')
            if tname.strip() == table_name.strip():
                field_list = self.headObj.tableFields[tname.strip()]
                
                # Print the header with proper formatting
                if common_db.VERBOSE:
                    print("\n{:<15} {:<15} {:<15}".format("Field Name", "Type", "Max Length"))
                if common_db.VERBOSE:
                    print("-" * 45)
                
                # Print each field's information with proper formatting
                for idx, field in enumerate(field_list):
                    try:
                        field_name = field[0]
                        if isinstance(field_name, bytes):
                            field_name = field_name.strip().decode('utf-8', errors='replace')
                        else:
                            field_name = field_name.strip()
                        
                        if not field_name:
                            field_name = f"field_{idx+1}"
                        
                        field_type = field[1]
                        field_length = field[2]
                        
                        type_str = "String" if field_type == 0 else \
                                "VarString" if field_type == 1 else \
                                "Integer" if field_type == 2 else \
                                "Boolean" if field_type == 3 else \
                                "Unknown"
                        
                        if common_db.VERBOSE:
                            print("{:<15} {:<15} {:<15}".format(field_name, type_str, field_length))
                    except Exception as e:
                        if common_db.VERBOSE:
                            print(f"Error displaying field: {e}")
                        if common_db.VERBOSE:
                            print(f"Raw field data: {field}")
                
                return field_list
        
        if common_db.VERBOSE:
            print(f"Table '{table_name}' not found in schema")
        return None

    # ------------------------------------------------
    # constructor of the class
    # ------------------------------------------------
    def __init__(self):
        if common_db.VERBOSE:
            print ('__init__ of Schema')

        if common_db.VERBOSE:
            print ('schema fileName is ' + Schema.fileName)
        # 'rb+' 要求文件已存在；首次运行 all.sch 不存在时用 'wb+' 创建空文件，
        # 后续读到空内容会走下方的初始化分支
        mode = 'rb+' if os.path.exists(Schema.fileName) else 'wb+'
        self.fileObj = open(Schema.fileName, mode)  # in binary format

        # read all data from schema file
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE  # the length of metahead, table name entries and feildName sections
        buf = ctypes.create_string_buffer(bufLen)
        buf = self.fileObj.read(bufLen)

        #the following is to print the content of the buffer
        if len(buf) == 0:  # for the first time, there is nothing in the schema file
            self.body_begin_index = BODY_BEGIN_INDEX
            buf = struct.pack('!?ii', False, 0, self.body_begin_index)  # is_stored, tablenum,offset

            self.fileObj.seek(0)
            self.fileObj.write(buf)
            self.fileObj.flush()

            # the following is to create a main memory structure for the schema

            tableNameList = []
            fieldNameList = {}  # it is a dictionary
            nameList = []
            fieldsList = {}
            self.headObj = head_db.Header(nameList, fieldsList,False, 0, self.body_begin_index)

            if common_db.VERBOSE:
                print ('metaHead of schema has been written to all.sch and the Header ojbect created')

        else:  # there is something in the schema file


            if common_db.VERBOSE:
                print ("there is something  in the all.sch")
            # in the following ? denotes bool type and  i denotes int type
            isStored, tempTableNum, tempOffset = struct.unpack_from('!?ii', buf, 0)

            if common_db.VERBOSE:
                print ("tableNum in schema file is ", tempTableNum)
            if common_db.VERBOSE:
                print ("isStored in schema file is ", isStored)
            if common_db.VERBOSE:
                print ("offset of body in schema  file is ", tempOffset)

            self.body_begin_index = tempOffset
            nameList=[]
            fieldsList={}
             # it is a dictionary

            if isStored == False:  # only the meta head exists, but there is no table information in the schema file
                self.headObj = head_db.Header(nameList, fieldsList, False, 0, BODY_BEGIN_INDEX)
                if common_db.VERBOSE:
                    print ("there is no table in the file")

            else:  # there is information of some tables

                if common_db.VERBOSE:
                    print( "there is at least one table in the schema file ")

                # the following is to fetch the tableNameHead from the buffer
                for i in range(tempTableNum):
                    # fetch the table name in tableNameHead
                    tempName, = struct.unpack_from('!10s', buf,
                                                   META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN)  # Note: '!' means no memory alignment
                    if common_db.VERBOSE:
                        print ("tablename is ", tempName)

                    # fetch the number of fields in the table in tableNameHead
                    tempNum, = struct.unpack_from('!i', buf, META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN + 10)
                    if common_db.VERBOSE:
                        print ('number of fields of table ', tempName, ' is ', tempNum)

                    # fetch the offset where field names are stored in the body
                    tempPos, = struct.unpack_from('!i', buf,
                                                  META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN + 10 + struct.calcsize('i'))
                    if common_db.VERBOSE:
                        print ("tempPos in body is ", tempPos)

                    tempNameMix = (tempName.rstrip(b'\x00').strip().decode('utf-8'), tempNum, tempPos)
                    nameList.append(tempNameMix)  # It is a triple

                    # the following is to fetch field information from body section and each field is  (fieldname,fieldtype,fieldlength)
                    if tempNum > 0: # the number of fields is greater than 0
                        fields = []  # it is a list
                        for j in range(tempNum):
                            tempFieldName,tempFieldType,tempFieldLength = struct.unpack_from('!10sii',
                                                                                             buf, tempPos + j * MAX_FIELD_LEN)

                            # Handle empty field names
                            if not tempFieldName.rstrip(b'\x00').strip():
                                tempFieldName = f"field_{j+1}"
                                if common_db.VERBOSE:
                                    print ('field name is empty, using default name:', tempFieldName)
                            else:
                                tempFieldName = tempFieldName.rstrip(b'\x00').strip().decode('utf-8')
                                if common_db.VERBOSE:
                                    print ('field name is', tempFieldName)

                            if common_db.VERBOSE:
                                print ('field type is', tempFieldType)

                            if common_db.VERBOSE:
                                print ('filed length is', tempFieldLength)

                            tempFieldTuple=(tempFieldName,tempFieldType,tempFieldLength)

                            fields.append(tempFieldTuple)


                        fieldsList[tempName.rstrip(b'\x00').strip().decode('utf-8')]=fields

                # the main memory structure for schema is constructed

                self.headObj = head_db.Header(nameList, fieldsList, True, tempTableNum, tempOffset)

    # ----------------------------
    # destructor of the class
    # ----------------------------
    def __del__(self):  # write the metahead information in head object to file

        if common_db.VERBOSE:
            print ("__del__ of class Schema begins to execute")

        # __init__ 若中途异常，fileObj/headObj 可能未赋值；防御访问以免在
        # 回收半构造对象时抛 AttributeError 掩盖原始异常
        file_obj = getattr(self, 'fileObj', None)
        if file_obj is None:
            return

        head_obj = getattr(self, 'headObj', None)
        if head_obj is not None:
            buf = ctypes.create_string_buffer(12)
            struct.pack_into('!?ii', buf, 0, head_obj.isStored, head_obj.lenOfTableNum, head_obj.offsetOfBody)
            file_obj.seek(0)
            file_obj.write(buf)
            file_obj.flush()

        file_obj.close()

    # --------------------------
    # delete all the contents in the schema file
    # ----------------------------------------
    def deleteAll(self):
        self.headObj.tableFields = {}
        self.headObj.tableNames=[]
        self.fileObj.seek(0)
        self.fileObj.truncate(0)
        self.headObj.isStored = False
        self.headObj.lenOfTableNum = 0
        self.headObj.offsetOfBody = self.body_begin_index
        self.fileObj.flush()
        if common_db.VERBOSE:
            print ("all.sch file has been truncated")

    # -----------------------------
    # insert a table schema to the schema file
    # input:
    #       tablename: the table to be added
    #       fieldList: the field information list and each element is a tuple(fieldname,fieldtype,fieldlength)
    # -------------------------------
    def appendTable(self, tableName, fieldList):  # it modify the tableNameHead and body of all.sch
        if common_db.VERBOSE:
            print ("appendTable begins to execute")
        tableName = tableName.strip()

        if len(tableName) == 0 or len(tableName) > 10 or len(fieldList)==0:
            if common_db.VERBOSE:
                print ('tablename is invalid or field list is invalid')
        else:

            fieldNum = len(fieldList)

            if common_db.VERBOSE:
                print ("the following is to write the fields to body in all.sch")
            fieldBuff = ctypes.create_string_buffer(MAX_FIELD_LEN * len(fieldList))
            beginIndex = 0
            for i in range(len(fieldList)):
                (fieldName,fieldType,fieldLength)=fieldList[i]
                # Convert bytes field names to str for internal use
                if isinstance(fieldName, bytes):
                    fieldName = fieldName.decode('utf-8')
                # Ensure field name is not empty
                if not fieldName or fieldName.strip() == '':
                    fieldName = f"field_{i+1}"
                
                # Ensure field name does not exceed 10 bytes
                if len(fieldName) > 10:
                    fieldName = fieldName[:10]
                # Pad field name to 10 bytes and encode for struct.pack
                filledFieldName = fieldName.ljust(10).encode('utf-8')
                
                # Pack field information into buffer
                struct.pack_into('!10sii', fieldBuff, beginIndex, filledFieldName, int(fieldType), int(fieldLength))

                beginIndex = beginIndex + MAX_FIELD_LEN

            writePos = self.headObj.offsetOfBody

            self.fileObj.seek(writePos)
            self.fileObj.write(fieldBuff)
            self.fileObj.flush()

            filledTableName = fillTableName(tableName)
            if isinstance(filledTableName, str):
                filledTableName = filledTableName.encode('utf-8')
            nameBuf = struct.pack('!10sii', filledTableName, fieldNum, self.headObj.offsetOfBody)

            self.fileObj.seek(META_HEAD_SIZE + self.headObj.lenOfTableNum * TABLE_NAME_ENTRY_LEN)
            nameContent = (tableName.strip(), fieldNum, self.headObj.offsetOfBody)

            self.fileObj.write(nameBuf)
            self.fileObj.flush()

            if common_db.VERBOSE:
                print ("to modify the header structure in main memory")
            self.headObj.isStored = True
            self.headObj.lenOfTableNum += 1
            self.headObj.offsetOfBody += fieldNum * MAX_FIELD_LEN
            self.headObj.tableNames.append(nameContent)
            # Store field list with str field names
            str_field_list = []
            for fname, ftype, flen in fieldList:
                if isinstance(fname, bytes):
                    fname = fname.decode('utf-8')
                str_field_list.append((fname, ftype, flen))
            self.headObj.tableFields[tableName]=str_field_list

    # -------------------------------
    # to determine whether the table named table_name exist, depending on the main memory structures
    # input
    #       table_name
    # output
    #       true or false
    # -------------------------------------------------------
    def find_table(self, table_name):
        table_names = [x[0].strip().decode('utf-8') if isinstance(x[0], bytes) else x[0].strip() for x in self.headObj.tableNames]
        return table_name.strip() in table_names

    def resolve_table_name(self, name):
        name = name.strip()
        for entry in self.headObj.tableNames:
            stored = entry[0]
            if isinstance(stored, bytes):
                stored = stored.strip().decode('utf-8')
            else:
                stored = stored.strip()
            if stored == name:
                return stored
        return None


    # ----------------------------------------------
    # to write the main memory information into the schema file
    # ------------------------------------------------

    def WriteBuff(self):
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE
        buf = ctypes.create_string_buffer(bufLen)
        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        
        for idx in range(len(self.headObj.tableNames)):
            tmp_tableName = self.headObj.tableNames[idx][0]
            if isinstance(tmp_tableName, str):
                tmp_tableName = tmp_tableName.strip()
            else:
                tmp_tableName = tmp_tableName.strip().decode('utf-8')
            if len(tmp_tableName) < 10:
                tmp_tableName = ' ' * (10 - len(tmp_tableName)) + tmp_tableName
            # struct.pack requires bytes for '10s' format
            tmp_tableName_bytes = tmp_tableName.encode('utf-8')

            struct.pack_into('!10sii', buf, META_HEAD_SIZE + idx * TABLE_NAME_ENTRY_LEN, tmp_tableName_bytes,
                             self.headObj.tableNames[idx][1],self.headObj.tableNames[idx][2])

            table_name = self.headObj.tableNames[idx][0].strip() if isinstance(self.headObj.tableNames[idx][0], str) else self.headObj.tableNames[idx][0].strip().decode('utf-8')
            field_list = self.headObj.tableFields[table_name]
            for idj in range(len(field_list)):
                (tempFieldName,tempFieldType,tempFieldLength) = field_list[idj]
                if isinstance(tempFieldName, str):
                    tempFieldName = tempFieldName.encode('utf-8')
                struct.pack_into('!10sii', buf, self.headObj.tableNames[idx][2]+idj*MAX_FIELD_LEN,
                                tempFieldName, tempFieldType, tempFieldLength)
        
        self.fileObj.seek(0)
        self.fileObj.write(buf)
        self.fileObj.flush()

    # ----------------------------------------------
    # to delete the schema of a table from the schema file
    # input
    #       table_name: the table to be deleted
    # output
    #       True or False
    # ------------------------------------------------
    def delete_table_schema(self, table_name):
        tmpIndex=-1
        for i in range(len(self.headObj.tableNames)):
            tname = self.headObj.tableNames[i][0]
            if isinstance(tname, bytes):
                tname = tname.strip().decode('utf-8')
            else:
                tname = tname.strip()
            if tname == table_name.strip():
                tmpIndex=i
        if tmpIndex>=0:

            # modify the main memory structure
            
            del self.headObj.tableNames[tmpIndex]
            del self.headObj.tableFields[table_name.strip()]
            self.headObj.lenOfTableNum-=1

            
            if len(self.headObj.tableNames)>0: # there is at least one table after the deletion
                name_list = [x[0].strip().decode('utf-8') if isinstance(x[0], bytes) else x[0].strip() for x in self.headObj.tableNames]
                field_num_per_table = [x[1] for x in self.headObj.tableNames]
                table_offset = [x[2] for x in self.headObj.tableNames]

                table_offset[0] = BODY_BEGIN_INDEX
                for idx in range(1,len(table_offset)):
                    table_offset[idx] = table_offset[idx-1] + field_num_per_table[idx-1]*MAX_FIELD_LEN
                    
                self.headObj.tableNames=list(zip(name_list,field_num_per_table,table_offset))
                self.headObj.offsetOfBody=self.headObj.tableNames[-1][2]+self.headObj.tableNames[-1][1]*MAX_FIELD_LEN
                self.WriteBuff()

            else:# there is no table after the deletion
                if common_db.VERBOSE:
                    print (False)
                self.headObj.offsetOfBody = BODY_BEGIN_INDEX
                self.headObj.isStored = False
                self.WriteBuff()
            return True
        else:
            if common_db.VERBOSE:
                print ('Cannot find the table!')
            return False

    # ---------------------------
    # to return the list of all the table names
    # input
    # output
    #       table_name_list: the returned list of table names
    # --------------------------------
    def get_table_name_list(self):
        return [x[0].strip().decode('utf-8') if isinstance(x[0], bytes) else x[0].strip() for x in self.headObj.tableNames]
