#%% About
'''
We will prefer to get data from the Informatics team API.
'''

#%% Preliminaries

# For documentation see http://gbadske.org:9000/dataportal/

import requests as req         # For sending HTTP requests

#%% View tables and field names

# Get list of all available tables
gbadske_tablelist_uri = 'http://gbadske.org:9000/GBADsTables/public?format=text'
gbadske_tablelist = req.get(gbadske_tablelist_uri).text.split(',')   # Get table list and convert to list

# ----------------------------------------------------------------------------
# Lookup the column names in a specific table
# ----------------------------------------------------------------------------
gbadske_fieldnames_uri = 'http://gbadske.org:9000/GBADsTable/public'

# Return the column names for a table
# Usage: table_columns = gbadske_get_column_names(table)
def gbadske_get_column_names(
        TABLE_NAME          # String: name of table
        ,RESP_TYPE='list'   # String: 'list' returns a list, 'string' returns a string
    ):
    fieldnames_params = {
       'table_name':TABLE_NAME
       ,'format':'text'
       }
    fieldnames_str = req.get(gbadske_fieldnames_uri , params=fieldnames_params).text
    fieldnames_list = req.get(gbadske_fieldnames_uri , params=fieldnames_params).text.split(',')
    if RESP_TYPE == 'list':
        return fieldnames_list
    elif RESP_TYPE == 'string':
        return fieldnames_str

# cols_biomass_oie = gbadske_get_column_names('biomass_oie' ,'string')

#%% Retrieve a table

gbadske_query_uri = 'http://gbadske.org:9000/GBADsPublicQuery/'

# -----------------------------------------------------------------------------
# Pieces
# -----------------------------------------------------------------------------
gbadske_query_table_name = 'biomass_oie'
gbadske_query_params = {
    'fields':gbadske_get_column_names(gbadske_query_table_name ,'string')   # All columns in table
    ,'query':"year=2017 AND member_country='Australia'"     # Note character column value must be in SINGLE QUOTES (double quotes don't work)
    ,'format':'file'
    }
gbadske_query_resp = req.get(gbadske_query_uri + gbadske_query_table_name , params=gbadske_query_params)

# Read table into pandas dataframe
gbadske_query_df = pd.read_csv(io.StringIO(gbadske_query_resp.text))

# -----------------------------------------------------------------------------
# Function
# -----------------------------------------------------------------------------
# Return a table as a pandas dataframe
# Usage: table_df = gbadske_import_to_pandas(table)
def gbadske_import_to_pandas(
        table_name      # String: name of table
        ,query=""       # String (optional): data query in DOUBLE QUOTES e.g. "year=2017 AND member_country='Australia'". Values for character columns value must be in SINGLE QUOTES.
        ,nrows=None     # Integer (optional): limit number of rows to read
    ):
    query_params = {
        'fields':gbadske_get_column_names(table_name ,'string')
        ,'query':query
        ,'format':'file'
        }
    query_resp = req.get(gbadske_query_uri + table_name , params=query_params)

    # Read table into pandas dataframe
    if nrows:
        query_df = pd.read_csv(io.StringIO(query_resp.text) ,nrows=nrows)
    else:
        query_df = pd.read_csv(io.StringIO(query_resp.text))

    return query_df

# biomass_oie_df = gbadske_import_to_pandas('biomass_oie' ,"year=2017 AND member_country='Australia'")
# biomass_oie_df = gbadske_import_to_pandas('biomass_oie' ,nrows=100)

#%% Create summaries

# Get list of all available tables
gbadske_tablelist_uri = 'http://gbadske.org:9000/GBADsTables/public?format=text'
gbadske_tablelist = req.get(gbadske_tablelist_uri).text.split(',')   # Get table list and convert to list

# =============================================================================
#### Write table list to Excel
# =============================================================================
with pd.ExcelWriter(os.path.join(RAWDATA_FOLDER ,'gbadske_tables_20220801.xlsx')) as writer:
    # First sheet: table list
    gbadske_tablelist_df = pd.DataFrame({'table_name':gbadske_tablelist})
    gbadske_tablelist_df.to_excel(writer ,sheet_name='Table List' ,index=False)

    # Subsequent sheets: column list for each table
    for table in gbadske_tablelist:
        print(f'> Processing table {table}')
        collist = gbadske_get_column_names(table)
        collist_df = pd.DataFrame({'column_name':collist})
        sheetname = table.replace('population' ,'pop')
        sheetname_short = sheetname[0:31]     # Sheet name must be <= 31 characters
        collist_df.to_excel(writer, sheet_name=sheetname_short ,index=False)

del collist ,collist_df

# =============================================================================
#### Write sample of each table to Excel
# =============================================================================
with pd.ExcelWriter(os.path.join(RAWDATA_FOLDER ,'gbadske_tables_100rows_20220801.xlsx')) as writer:
    for table in gbadske_tablelist:
        print(f'> Processing table {table}')
        if 'eth' not in table:      # Exclude Ethiopia-specific tables
            try:
                table_df = gbadske_import_to_pandas(table ,nrows=100)   # First 100 rows
            except:
                table_df = pd.DataFrame({'Status':'Error reading table'} ,index=[0])
            sheetname = table.replace('population' ,'pop')
            sheetname_short = sheetname[0:31]     # Sheet name must be <= 31 characters
            table_df.to_excel(writer, sheet_name=sheetname_short ,index=False)

del table_df
