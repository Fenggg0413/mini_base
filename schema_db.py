#-----------------------------------------------
# schema_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: Ning wang, Yidan Xu
#-----------------------------------------------
# to process the schema data, which is stored in all.sch
# all.sch are divied into three parts,namely metaHead, tableNameHead and body
# metaHead|tableNameHead|body
#-------------------------------------------


import ctypes
import struct
import head_db # it is main memory structure for the table schema





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
# the table name is padded if its lenght is smaller than MAX_TABLE_NAME_WHEN
# input:
#       tableName: the table name       
# -------------------------------
def fillTableName(tableName): # it should be 10 bytes
    if len(tableName.strip())<MAX_TABLE_NAME_LEN:
        tableName=(' '*(MAX_TABLE_NAME_LEN-len(tableName.strip()))).encode('utf-8')+tableName.strip()
        return tableName


class Schema(object):
    '''
    Schema class
    '''

    fileName = 'all.sch'  # the schema file name
    count = 0  # there should be only one object in the program

    @staticmethod
    def how_many():  # give the count of instances
        return Schema.count


    def viewTableNames(self):  # to list all the table names in the all.sch

        print ('viewtablenames begin to execute')
        # to be inserted here
        for i in self.headObj.tableNames:
            print ('Table name is     ', i[0])
        print ('execute Done!')

    #------------------------
    # to show the schema of given table
    # input
    #       table_name
    #------------------------------
    def viewTableStructure(self, table_name):
        print('the structure of table '.encode('utf-8')+table_name+' is as follows:'.encode('utf-8'))
        
        # Iterate through the table name list to find the matching table
        for i in range(len(self.headObj.tableNames)):
            if self.headObj.tableNames[i][0].strip() == table_name.strip():
                # Get the field list for the table
                field_list = self.headObj.tableFields[table_name.strip()]
                
                # Print the header with proper formatting
                print("\n{:<15} {:<15} {:<15}".format("Field Name", "Type", "Max Length"))
                print("-" * 45)
                
                # Print each field's information with proper formatting
                for idx, field in enumerate(field_list):
                    try:
                        if isinstance(field[0], bytes):
                            field_name = field[0].strip().decode('utf-8', errors='replace')
                        else:
                            field_name = field[0].strip()
                            
                        # Handle empty field names
                        if not field_name:
                            field_name = f"field_{idx+1}"
                            
                        field_type = field[1]
                        field_length = field[2]
                        
                        # Convert numeric type to string representation
                        type_str = "String" if field_type == 0 else \
                                "VarString" if field_type == 1 else \
                                "Integer" if field_type == 2 else \
                                "Boolean" if field_type == 3 else \
                                "Unknown"
                        
                        # Use string formatting for aligned output
                        print("{:<15} {:<15} {:<15}".format(field_name, type_str, field_length))
                    except Exception as e:
                        print(f"Error displaying field: {e}")
                        print(f"Raw field data: {field}")
                
                return field_list
        
        # If table is not found
        if isinstance(table_name, bytes):
            table_name_str = table_name.decode('utf-8')
        else:
            table_name_str = table_name
        print(f"Table '{table_name_str}' not found in schema")
        return None

    # ------------------------------------------------
    # constructor of the class
    # ------------------------------------------------
    def __init__(self):
        print ('__init__ of Schema')

        print ('schema fileName is ' + Schema.fileName)
        self.fileObj = open(Schema.fileName, 'rb+')  # in binary format

        # read all data from schema file
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE  # the length of metahead, table name entries and feildName sections
        buf = ctypes.create_string_buffer(bufLen)
        buf = self.fileObj.read(bufLen)

        #the following is to print the content of the buffer
        buf.strip()
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

            print ('metaHead of schema has been written to all.sch and the Header ojbect created')

        else:  # there is something in the schema file


            print ("there is something  in the all.sch")
            # in the following ? denotes bool type and  i denotes int type
            isStored, tempTableNum, tempOffset = struct.unpack_from('!?ii', buf, 0)   #link:https://docs.python.org/2/library/struct.html

            print ("tableNum in schema file is ", tempTableNum)
            print ("isStored in schema file is ", isStored)
            print ("offset of body in schema  file is ", tempOffset)

            Schema.body_begin_index = tempOffset
            nameList=[]
            fieldsList={}
             # it is a dictionary

            if isStored == False:  # only the meta head exists, but there is no table information in the schema file
                self.headObj = head_db.Header(nameList, fieldsList, False, 0, BODY_BEGIN_INDEX)
                print ("there is no table in the file")

            else:  # there is information of some tables

                print( "there is at least one table in the schema file ")

                # the following is to fetch the tableNameHead from the buffer
                for i in range(tempTableNum):
                    # fetch the table name in tableNameHead
                    tempName, = struct.unpack_from('!10s', buf,
                                                   META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN)  # Note: '!' means no memory alignment
                    print ("tablename is ", tempName)

                    # fetch the number of fields in the table in tableNameHead
                    tempNum, = struct.unpack_from('!i', buf, META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN + 10)
                    print ('number of fields of table ', tempName, ' is ', tempNum)

                    # fetch the offset where field names are stored in the body
                    tempPos, = struct.unpack_from('!i', buf,
                                                  META_HEAD_SIZE + i * TABLE_NAME_ENTRY_LEN + 10 + struct.calcsize('i'))
                    print ("tempPos in body is ", tempPos)

                    tempNameMix = (tempName.strip(), tempNum, tempPos)
                    nameList.append(tempNameMix)  # It is a triple

                    # the following is to fetch field information from body section and each field is  (fieldname,fieldtype,fieldlength)
                    if tempNum > 0: # the number of fields is greater than 0
                        fields = []  # it is a list
                        for j in range(tempNum):
                            tempFieldName,tempFieldType,tempFieldLength = struct.unpack_from('!10sii',
                                                                                             buf, tempPos + j * MAX_FIELD_LEN)

                            # Handle empty field names
                            if not tempFieldName.strip():
                                tempFieldName = f"field_{j+1}".encode('utf-8')
                                print ('field name is empty, using default name:', tempFieldName)
                            else:
                                print ('field name is ', tempFieldName.strip())

                            print ('field type is', tempFieldType)

                            print ('filed length is', tempFieldLength)

                            tempFieldTuple=(tempFieldName,tempFieldType,tempFieldLength)

                            fields.append(tempFieldTuple)


                        fieldsList[tempName.strip()]=fields

                # the main memory structure for schema is constructed

                self.headObj = head_db.Header(nameList, fieldsList, True, tempTableNum, tempOffset)

    # ----------------------------
    # destructor of the class
    # ----------------------------
    def __del__(self):  # write the metahead information in head object to file

        print ("__del__ of class Schema begins to execute")

        buf = ctypes.create_string_buffer(12)

        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        self.fileObj.seek(0)
        self.fileObj.write(buf)
        self.fileObj.flush()
        self.fileObj.close()

    # --------------------------
    # delete all the contents in the schema file
    # ----------------------------------------
    def deleteAll(self):
        self.headObj.tableFields=[]
        self.headObj.tableNames=[]
        self.fileObj.seek(0)
        self.fileObj.truncate(0)
        self.headObj.isStored = False
        self.headObj.lenOfTableNum = 0
        self.headObj.offsetOfBody = self.body_begin_index
        self.fileObj.flush()
        print ("all.sch file has been truncated")

    # -----------------------------
    # insert a table schema to the schema file
    # input:
    #       tablename: the table to be added
    #       fieldList: the field information list and each element is a tuple(fieldname,fieldtype,fieldlength)
    # -------------------------------
    def appendTable(self, tableName, fieldList):  # it modify the tableNameHead and body of all.sch
        print ("appendTable begins to execute")
        tableName.strip()

        if len(tableName) == 0 or len(tableName) > 10 or len(fieldList)==0:
            print ('tablename is invalid or field list is invalid')
        else:

            fieldNum = len(fieldList)

            print ("the following is to write the fields to body in all.sch")
            fieldBuff = ctypes.create_string_buffer(MAX_FIELD_LEN * len(fieldList))
            beginIndex = 0
            for i in range(len(fieldList)):
                (fieldName,fieldType,fieldLength)=fieldList[i]
                # Ensure field name is not empty
                if not fieldName or fieldName.strip() == '':
                    fieldName = f"field_{i+1}"  # Use default name
                
                # Handle string encoding
                if isinstance(fieldName, str):
                    fieldName = fieldName.encode('utf-8')
                
                # Ensure field name does not exceed 10 bytes
                if len(fieldName) > 10:
                    fieldName = fieldName[:10]
                # Pad field name to 10 bytes
                filledFieldName = fieldName.ljust(10, b' ')
                
                # Pack field information into buffer
                struct.pack_into('!10sii', fieldBuff, beginIndex, filledFieldName, int(fieldType), int(fieldLength))

                beginIndex = beginIndex + MAX_FIELD_LEN

            writePos = self.headObj.offsetOfBody

            self.fileObj.seek(writePos)
            self.fileObj.write(fieldBuff)
            self.fileObj.flush()

            # self.headObj.offsetOfBody=self.headObj.offsetBody+fieldNum*MAX_FIELD_LEN

            print ("the following is to write table name entry to tableNameHead in all.sch")
            filledTableName = fillTableName(tableName)
            if isinstance(filledTableName, str):
                filledTableName = filledTableName.encode('utf-8')
            nameBuf = struct.pack('!10sii', filledTableName, fieldNum, self.headObj.offsetOfBody)

            self.fileObj.seek(META_HEAD_SIZE + self.headObj.lenOfTableNum * TABLE_NAME_ENTRY_LEN)
            nameContent = (tableName.strip(), fieldNum, self.headObj.offsetOfBody)

            self.fileObj.write(nameBuf)
            self.fileObj.flush()

            print ("to modify the header structure in main memory")
            self.headObj.isStored = True
            self.headObj.lenOfTableNum += 1
            self.headObj.offsetOfBody += fieldNum * MAX_FIELD_LEN
            self.headObj.tableNames.append(nameContent)
            # fieldTuple = tuple(fieldList)
            self.headObj.tableFields[tableName.strip()]=fieldList

    # -------------------------------
    # to determine whether the table named table_name exist, depending on the main memory structures
    # input
    #       table_name
    # output
    #       true or false
    # -------------------------------------------------------
    def find_table(self, table_name):
        Tables = map(lambda x: x[0], self.headObj.tableNames)
        if table_name in Tables:
            return True
        else:
            return False



        
    # ----------------------------------------------
    # to write the main memory information into the schema file
    # input
    #       
    # output
    #       True or False
    # ------------------------------------------------   

    def WriteBuff(self):
        bufLen = META_HEAD_SIZE + TABLE_NAME_HEAD_SIZE + MAX_FIELD_SECTION_SIZE
        buf = ctypes.create_string_buffer(bufLen)
        struct.pack_into('!?ii', buf, 0, self.headObj.isStored, self.headObj.lenOfTableNum, self.headObj.offsetOfBody)
        
        for idx in range(len(self.headObj.tableNames)):
            tmp_tableName = self.headObj.tableNames[idx][0]
            if len(tmp_tableName)<10:
                tmp_tableName = (' ' * (10 - len(tmp_tableName.strip()))).encode("utf-8") + tmp_tableName

            # write (tablename,numberoffields,offsetinbody) to buffer
            struct.pack_into('!10sii', buf, META_HEAD_SIZE + idx * TABLE_NAME_ENTRY_LEN, tmp_tableName,
                             self.headObj.tableNames[idx][1],self.headObj.tableNames[idx][2])

            # write the field information of each table into the buffer
            table_name = self.headObj.tableNames[idx][0].strip()
            field_list = self.headObj.tableFields[table_name]
            for idj in range(len(field_list)):
                (tempFieldName,tempFieldType,tempFieldLength) = field_list[idj]
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
            if self.headObj.tableNames[i][0].strip()==table_name.strip():
                tmpIndex=i
        if tmpIndex>=0:

            # modify the main memory structure
            
            del self.headObj.tableNames[tmpIndex]
            del self.headObj.tableFields[table_name.strip()]
            #print self.headObj.tableFields
            self.headObj.lenOfTableNum-=1

            
            if len(self.headObj.tableNames)>0: # there is at least one table after the deletion
                name_list = list(map(lambda x: x[0], self.headObj.tableNames))
                field_num_per_table = list(map(lambda x: x[1], self.headObj.tableNames))
                table_offset= list(map(lambda x: x[2], self.headObj.tableNames))

                table_offset[0] = BODY_BEGIN_INDEX
                for idx in range(1,len(table_offset)):
                    table_offset[idx] = table_offset[idx-1] + field_num_per_table[idx-1]*MAX_FIELD_LEN
                    
                self.headObj.tableNames=list(zip(name_list,field_num_per_table,table_offset))
                self.headObj.offsetOfBody=self.headObj.tableNames[-1][2]+self.headObj.tableNames[-1][1]*MAX_FIELD_LEN
                self.WriteBuff()

            else:# there is no table after the deletion
                print (False)
                self.headObj.offsetOfBody = BODY_BEGIN_INDEX
                self.headObj.isStored = False
            return True
        else:
            print ('Cannot find the table!')
            return False

    # ---------------------------
    # to return the list of all the table names
    # input
    # output
    #       table_name_list: the returned list of table names
    # --------------------------------
    def get_table_name_list(self):
        return map(lambda x:x[0],self.headObj.tableNames)
