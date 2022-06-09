'''
Module contains classes/methods to convert Antea
files (both coordinates and differentiestaten) to
Pandas DataFrame format.
There are various format variations that are catered for, all MS-Excel.
A metafile (MS-Excel) is provided to inform on what's what, and
set format specifics.
Some specific heuristics is applied to reading dates (very variable
in Antea files)
'''
import datetime
import numpy as np
import pandas as pd

from . import pmexception as BE
from . import messagelogger as ML
from . import importutils as IU
from . import metafileheaders as MH
from . import peilmerkdatabase as PM

############################################################################################
# Month name mapping (inconsistent in Antea files, and mostly in Dutch)
monthmap=dict()
monthmap["jan"]="January"
monthmap["feb"]="February"
monthmap["maa"]="March"
monthmap["mar"]="March"
monthmap["apr"]="April"
monthmap["mei"]="May"
monthmap["may"]="May"
monthmap["jun"]="June"
monthmap["jul"]="July"
monthmap["aug"]="August"
monthmap["sep"]="September"
monthmap["oct"]="October"
monthmap["okt"]="October"
monthmap["nov"]="November"
monthmap["dec"]="December"

# Date time formats (they're inconsistent in Antea files)
dateformats=list()
dateformats.append("%B %y")
dateformats.append("%B %Y")
dateformats.append("%d %b %Y")
dateformats.append("%d %b %y")
dateformats.append("%d %B %Y")
dateformats.append("%d %B %y")
dateformats.append("%B %y")
dateformats.append("%B %Y")

dateLog = dict()

PEILMERK_KEY="Peilmerk"
NULLHGT_KEY="Nulhoogte"
NULLTIME_KEY="Nuljaar"

class LoadAnteaCoordFailure(BE.PMException):
    '''
    Failure to load an Antea file
    '''
    def __init__(self, cause):
        BE.PMException.__init__(self, "Failed to load Antea Coordinate file: " + cause)

    
class LoadAnteaDiffFailure(BE.PMException):
    '''
    Failure to load an Antea file
    '''
    def __init__(self, cause):
        BE.PMException.__init__(self, "Failed to load Antea Differentiestaat file: " + cause)
        
class KeyNotFoundException(BE.PMException):
    '''
    Failure to find mandatory key in metafile
    '''
    def __init__(self, descr):
        BE.PMException.__init__(self, descr=descr)


class AnteaLoader(IU.BaseLoader):
    '''
    Loader for Antea differentiestaten and coordlists.
    Both assumed to be provided as xlsx files.
    As columns/rows vary, for each survey metadata
    needs to be provided.
    '''
    def __init__(self, name):
        IU.BaseLoader.__init__(self, "Antea", name)
        
    def _fixDate(self, sdateIn, dateMap=None):      
        '''
        Map date (if needed) - heuristics
        Use dateMap if partial date was provided
        be robust against string or int representation
        '''
        # Make a copy, so we can manipulate & still see the original
        sdate = sdateIn

        # Silently ignore empty cells
        if (isinstance(sdate, float) and np.isnan(sdate)):
            return None
        if (isinstance(sdate, str) and (sdate[:7]=="Unnamed" or sdate.strip()=="")):
            return None
        
        # Zeroth level: check dateMap
        # Try various entries. If our date occurs in that, return the mapped value.
        if (not (dateMap is None) and sdate in dateMap):
            sdate=dateMap[sdate]
        if (isinstance(sdate, int) or isinstance(sdate, float)):
            sdate=str(sdate)
            if (not (dateMap is None) and sdate in dateMap):
                sdate=dateMap[sdate]
        if (isinstance(sdate,str)):
            sdate=sdate.strip()
            if (sdate in dateMap):
                sdate=dateMap[sdate]
            try:
                sdateT=int(sdate)
                if (not (dateMap is None) and sdate in dateMap):
                    sdateT=dateMap[sdateT]
                # if we've come this far
                sdate = sdateT
            except (KeyError,ValueError,TypeError):
                pass

        # If Pandas got it right the first time, we're done.
        # Do convert timestamp to date
        if(isinstance(sdate, pd.Timestamp)):
            sdate = sdate.to_pydatetime()
            return sdate.date()
        if (isinstance(sdate,datetime.datetime)):
            return sdate.date()
        if (isinstance(sdate,datetime.date)):
            return sdate

        # Second level - actual parsing
        sdate=str(sdate)
        sdateo=None
        
        # Split date in parts, either space or '-'
        parts=sdate.split()
        if(len(parts)==1):
            parts=sdate.split('-')
        if(len(parts)==1):
            ML.LogMessage("failed to parse date '"+ str(sdateIn)+ "'")
            return sdateo

        # Translate dutch month name (modify list along the way)
        ll = len(parts)
        for i in range(ll):
            key = parts[i][0:3].lower()
            if (key in monthmap):
                parts[i] = monthmap[key]
        
        # Put back together, and let strptime handle the rest
        sdate=" ".join(parts)
        for fmt in dateformats:
            try:
                #print("trying", sdate, fmt)
                sdateo=datetime.datetime.strptime(sdate,fmt)
            except ValueError:
                #print("    failed")
                sdateo=None
            if (sdateo is not None): break

        # TODO: better error handling?
        if (sdateo is None):
            ML.LogMessage("failed to parse date '"+ str(sdateIn)+ "'")
            return sdateo

        # Output is date, not datetime
        sdateo = sdateo.date()
        
        return sdateo

    def readAnteaDiffstaat(self, fileName, metaPars, path=""): 
        '''
        Read Antea differentiestaat (xlsx format).
        Format parameters (e.g. first line of data) are provided in 'metaPars',
        and come from the overarching metafile.
        '''     
        ML.LogMessage("")
        ML.LogMessage("Reading Antea differentiestaat '" + fileName+"'")
        
        print("****", metaPars[MH.NULLYEAR_COL_KEY], metaPars[MH.NULLNAP_COL_KEY])
        
        # Get parameters
        tabName=metaPars[MH.TAB_KEY]
        pad=self.getMetaKeyValue(metaPars, MH.PAD_KEY, False)
        cHeadOffset = self.getMetaKeyValue(metaPars, MH.COLHEADOFFSET_KEY, 0)
        dateRow=metaPars[MH.DATE_ROW_KEY]-1
        dataRow=metaPars[MH.FIRSTDATA_ROW_KEY]-1
        indexCol=metaPars[MH.PM_COL_KEY]-1
        useCols=[indexCol]
        hasNull=False
        if (not np.isnan(metaPars[MH.NULLYEAR_COL_KEY]) and metaPars[MH.NULLYEAR_COL_KEY]>0):
            hasNull=True
            useCols.extend([metaPars[MH.NULLYEAR_COL_KEY]-1,metaPars[MH.NULLNAP_COL_KEY]-1])
        dataCol=metaPars[MH.FIRSTNAP_COL_KEY]-1
        dCol=metaPars[MH.DATECOL_STEP_KEY]
        useCols.extend(range(dataCol, dataCol+99*dCol, dCol))
        
        # Load the file. Path either in filename or specified separately
        try:
            df = pd.read_excel(fileName, sheet_name=tabName, header=dateRow)
        except FileNotFoundError:
            df = pd.read_excel(path+fileName, sheet_name=tabName, header=dateRow)
        print("-----", dateRow, df)

        # Shift cols if needed
        # TODO: DEAL WITH MERGED CELLS PROPERLY
        cols = df.columns.to_list()
        col2 = list(cols)
        nCols=len(cols)
        print("???",cols)
        print(cHeadOffset)
        for i in range(max(0,-cHeadOffset),min(nCols, nCols-cHeadOffset)):
            col2[i] = cols[i+cHeadOffset]
        if (cHeadOffset > 0):
            for i in range(nCols-cHeadOffset, nCols):
                col2[i]="col_"+str(i)
        elif (cHeadOffset < 0):
            for i in range(0, -cHeadOffset):
                col2[i]="col_"+str(i)
        cols = col2
        print("****", cols)
        df.columns=cols
        print("@@@@", df)
        
        # Figure out which ones to drop.
        # We cannot specify this up front with use_cols, because we don't know
        # how many columns the spreadsheet has, until we have read it.
        to_drop=[]
        for i in range(0,nCols):
            if not (i in useCols): 
                to_drop.append(cols[i])
        df.drop(columns=to_drop, inplace=True)
        print("0000", df)

        # Fix key column names of the remainder
        cols = df.columns.to_list()
        print("???",cols)
        cols[0]=PEILMERK_KEY
        if (hasNull):
            cols[1]=NULLTIME_KEY
            cols[2]=NULLHGT_KEY
        
        # Get explicitly provided date mappings out of the header
        # Be careful, cells can be present but empty (np.nan)
        dateMap={}
        for i in range(1,20):
            aKey="datemap{:d}_a".format(i)
            bKey="datemap{:d}_b".format(i)
            try:
                cOld = metaPars[aKey]
                cNewI = metaPars[bKey]
                cNew = self._fixDate(cNewI, dateMap=dateMap)
                if not (cNew is None):
                    dateMap[str(cOld)] = cNew
                    dateMap[str(cNew.year)] = cNew
            except KeyError:
                pass
                
        # Sanitize header dates. Keep track of mappings along the way
        # Support year-only references.
        for i in range(3,len(cols)):
            cOld = cols[i]
            cNew = self._fixDate(cOld, dateMap=dateMap)
            if (isinstance(cNew, datetime.date)):
                cols[i] = cNew
                dateMap[str(cOld)] = cNew
                dateMap[str(cNew.year)] = cNew
        df.columns=cols
        print(cols)
        print("1111", df)
        
        # Get rid of the empty rows
        df.drop(index=range(0,dataRow-dateRow-1), inplace=True)
        df.dropna(subset = [PEILMERK_KEY], inplace=True)
        print("22222", df)
        
        # And also sanitize the dates in the null column
        if (hasNull):
            for i in range(0,len(df)):
                cOld = df.iat[i,1]
                cNew = self._fixDate(cOld, dateMap=dateMap)
                if (isinstance(cNew, datetime.date)):
                    df.iat[i,1] = cNew
                    dateMap[str(cOld)] = cNew
                    dateMap[str(cNew.year)] = cNew
                else:
                    df.iat[i,1] = np.nan
        print("****", df)
        
        # Determine spm. Sometimes leading 0's are omitted, and need to be added. 
        # And sometimes pm's with E inside are treated as floats.
        for i in range(0,len(df)):
            df.iat[i,0] = self.fixPeilmerkName(df.iat[i,0], pad)

        # Extract the null dataCol
        # Then remove them from the main frame
        df0 = None
        if (hasNull):
            df0 = df[[PEILMERK_KEY, NULLTIME_KEY, NULLHGT_KEY]]
            df.drop([NULLTIME_KEY, NULLHGT_KEY], axis=1, inplace=True)
        
        # Remove columns with unreadable dates
        cols = df.columns.to_list()
        to_drop = []
        for c in cols:
            if (c == PEILMERK_KEY):
                pass # Keep this
            elif not (isinstance(c, (datetime.date, datetime.datetime))):
                to_drop.append(c)
        if (len(to_drop)>0):
            ML.LogMessage(
                "Warning: Dropped {:d} columns with unreadable dates".format(len(to_drop)),
                           severity=1)
            print("    ", to_drop)
            df.drop(to_drop, axis=1, inplace=True)
        
        # Unpivot the main frame
        df2 = df.melt(id_vars=PM.PEILMERK_KEY, var_name=PM.DATE_KEY, value_name=PM.HGT_KEY)
        
        # Add the null heights
        if (hasNull):
            cols = df0.columns.to_list()
            cols[0]=PM.PEILMERK_KEY
            cols[1]=PM.DATE_KEY
            cols[2]=PM.HGT_KEY
            df0.columns=cols
            
            df = df2.append(df0)
        else:
            df = df2
        
        # Remove empties silently. These may be np.nan, or various kinds of
        # empty string
        df["len"] = df[PM.HGT_KEY].apply(lambda x: len(str(x).strip()))
        df = df[df["len"]>0]
        df.dropna(subset = [PM.HGT_KEY], inplace=True)
        df.drop("len", axis=1, inplace=True)
        
        # Sort for convenience
        df.sort_values([PM.PEILMERK_KEY, PM.DATE_KEY], axis=0, inplace=True)
        
        # And duplicates (nullvalues may also occur in data columns)
        df.drop_duplicates(inplace=True)
        
        # Make a copy, so we are free to manipulate
        df = df.copy()

        # Check all heights are actually numbers. Failues will be nan
        df[PM.HGT_KEY] = pd.to_numeric(df[PM.HGT_KEY], errors='coerce')
        df_err = df[df[PM.HGT_KEY].isnull()]
        if (len(df_err)>0):
            ML.LogMessage(
                "Warning: Dropped {:d} lines with unreadable heights".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PEILMERK_KEY].unique())
        df = df[~df[PM.HGT_KEY].isnull()]

        _OK_KEY = 'is OK'
        l = len(df)
        df[_OK_KEY] = df[PM.DATE_KEY].apply(lambda x: 
                isinstance(x, (datetime.date, datetime.datetime)))
        df_err = df[~df[_OK_KEY]]
        if (len(df_err)>0):
            ML.LogMessage(
                "Warning: Dropped {:d} lines with unreadable dates".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PEILMERK_KEY].unique())         
        df = df[df[_OK_KEY]]
        df.drop(_OK_KEY, axis=1, inplace=True)
        
        # Log the source file
        df[PM.SRCFILE_KEY] = fileName
        
        # And create a "project ID" colummn. For now use the date 
        # so each measurement campaign is a separate project ID
        # TODO: FIND BETTER UNIQUE IDENTIFIER
        print(df)
        df[PM.PRJID_KEY] = df.apply(lambda x: str(x[PM.DATE_KEY]), axis=1)
        
        # Leave empty line
        ML.LogMessage("")
        
        # Print datemap for QC
        print("Datemap:", dateMap)
        print()
        return df
        
    def readAnteaCoordfile(self, fileName, metaPars, path=""):
        '''
        Read antea coordinate file (xlsx format)
        File specifics (e.g. first row of data) are in dict 'metaPers, which
        originates in the overarching metafile.
        '''
        ML.LogMessage("")
        ML.LogMessage("Reading Antea coordinatenlijst '" + fileName + "'")
        
        # Get the parameters
        tabName=str(metaPars[MH.TAB_KEY])
        pad=self.getMetaKeyValue(metaPars,MH.PAD_KEY,False)
        dataRow=self.getMetaKeyValue(metaPars, MH.FIRST_ROW_KEY, 2)-1
        dataRow=self.getMetaKeyValue(metaPars, MH.FIRST_ROW_KEY, dataRow+1)-1
        indexCol=metaPars[MH.PM_COL_KEY]-1
        xCol=metaPars[MH.X_COL_KEY]-1
        yCol=metaPars[MH.Y_COL_KEY]-1
        zCol=self.getMetaKeyValue(metaPars,MH.Z_COL_KEY,0)-1
        v = self.getMetaKeyValue(metaPars,MH.BEPAAL_KEY,0)
        print("----", v, type(v), len(str(v)))
        bCol=self.getMetaKeyValue(metaPars,MH.BEPAAL_KEY,0)-1
        cCol=self.getMetaKeyValue(metaPars,MH.COMMENT_COL_KEY,0)-1
        useCols=[indexCol, xCol, yCol]
        useColsT=[MH.PM_COL_KEY, MH.X_COL_KEY, MH.Y_COL_KEY]
        # Also remember the order in the subset of columns
        zcolU = -1
        if (zCol>=0):
            useCols.append(zCol)
            useColsT.append(MH.Z_COL_KEY)
            zcolU=len(useCols)-1
        bcolU = -1
        if (bCol>=0):
            useCols.append(bCol)
            useColsT.append(MH.BEPAAL_KEY)
            bcolU=len(useCols)-1
        ccolU = -1
        if (cCol>=0):
            useCols.append(cCol)
            useColsT.append(MH.COMMENT_COL_KEY)
            ccolU=len(useCols)-1

        # Skip stuff 1 line above data
        headRow = None
        if (dataRow>0):
            headRow = dataRow-1

        # Read the file. Path either in filename, or supplied separately.
        # We need a two stage process to ensure the peilmerken are read as strings.
        # First use read_excel to get the column headers as used in the file, then
        # use xl.parse to make sure they are parsed as strings (we need the headers for this)
        try:
            df = pd.read_excel(fileName, sheet_name=tabName, usecols=useCols, header=headRow)
            xl = pd.ExcelFile(fileName)
        except FileNotFoundError:
            df = pd.read_excel(path+fileName, sheet_name=tabName, usecols=useCols, header=headRow)
            xl = pd.ExcelFile(path+fileName)
        column_list = []
        for i in df.columns:
            column_list.append(i)
        converter = {col: str for col in column_list}
        df = xl.parse(tabName, converters=converter, usecols=useCols, header=headRow)

        # Fix key column names, after checking we've retrieved all of them
        cols = df.columns.to_list()
        if (len(cols) != len(useCols)):
            print("Found:",  cols)
            print("Expected:", useColsT)
            raise LoadAnteaCoordFailure("Not all columns found")
        cols[0]=PM.PEILMERK_KEY
        cols[1]=PM.X_KEY
        cols[2]=PM.Y_KEY
        print("++++", tabName, cols)
        if (zcolU>=0):
            try:
                cols[zcolU]="Z"
            except IndexError:
                raise LoadAnteaCoordFailure("Optional coord column Z specified as "+str(zCol+1)+", but not found")
        if (bcolU>=0): 
            try:
                cols[bcolU]="Bepaling"
            except IndexError:
                raise LoadAnteaCoordFailure("Optional coord column 'Bepaling specified as "+str(bCol+1)+", but not found")
        if (ccolU>=0): 
            try:
                cols[ccolU]=PM.COMMENT_KEY
            except IndexError:
                raise LoadAnteaCoordFailure("Optional coord column 'Comment' specified as "+str(cCol+1)+", but not found")
        df.columns=cols
        if (zcolU<0): df["Z"] = np.nan
        if (bcolU<0): df["Bepaling"] = np.nan
        if (ccolU<0): df[PM.COMMENT_KEY] = np.nan
        
        # Determine spm. Sometimes leading 0's are omitted, and need to be added
        for i in range(0,len(df)):
            spm = df.iat[i,0]
            df.iat[i,0] = self.fixPeilmerkName(spm, pad)

        # Check all coords are actually numbers (some may be text). 
        # Others will be transfored to nan
        df[PM.X_KEY] = pd.to_numeric(df[PM.X_KEY], errors='coerce')
        df[PM.Y_KEY] = pd.to_numeric(df[PM.Y_KEY], errors='coerce')
        df_err = df[df[PM.X_KEY].isnull() | df[PM.Y_KEY].isnull()]
        if (len(df_err)>0):
            ML.LogMessage(
                "Warning: Dropped {:d} lines with unreadable coordinates".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PEILMERK_KEY].unique())
        df = df[(~ df[PM.X_KEY].isnull())& (~df[PM.Y_KEY].isnull())]
        
        # Ensure comments are strings
        df[PM.COMMENT_KEY].fillna("", inplace=True)
        df[PM.COMMENT_KEY] = df[PM.COMMENT_KEY].astype(str)

        # Log the source file
        df[PM.SRCFILE_KEY] = fileName

        # Leave empty line
        ML.LogMessage("")
        
        return df
        
    def readSurvey(self, pmdb, metaFileName, key, skipTabs=None):
        '''
        Read data from Antea survey 'key'.
        Data can be one or multiple coord files, and one or multiple differentiestaten.
        The list, together with format information (e.g. first row of data)
        is provided in the xlsx 'metaFileName'.
        All tabs of this spreadsheet are scanned for FILE_KEY, except
        the ones specified in 'skipTabs'. (The tab named 'README' is akways skipped.)
        In addition mods can be specified (name changes, deletion of spurious peilmerken,
        marking peilmerken as unstable.)
        '''
        # Always skip 'README' tab
        if (skipTabs is None): lSkipTabs = list()
        else: lSkipTabs = list(skipTabs)
        lSkipTabs.append("README")

        with IU.ReadNotifier(self, metaFileName):
            ML.LogMessage("")
            ML.LogMessage("Reading Antea '" + key + "' metadata from " + metaFileName)

            # Read the metafile. We'll get a dict of dataframes
            dfs = pd.read_excel(metaFileName, header=None, sheet_name=None)
            
            # The tab containing the metadata. Find it, get the actual metadata
            # as a dataframe
            topleftstring=MH.FILE_KEY
            nMod = 0
            readTabs = []
            for df in self.findTableByTopLeft(dfs, topleftstring, skipTabs=lSkipTabs):
                # Keep track of tabs we've covered
                readTabs.append(df.tabName)
                
                # Convert the top row to header. Convert to lower case to make insensitive
                cols = df.iloc[0].to_list()
                cols = [x.lower() for x in cols]
                df.columns=cols
                df.drop(df.index[0], inplace = True)

                # Convert the file column to header. Convert to lower case to make insensitive
                df[MH.FTYPE_KEY] = df[MH.FTYPE_KEY].str.upper()
                df.set_index(MH.FTYPE_KEY, inplace = True)
                
                # Transpose (for easier indexing)
                df = df.transpose()
                
                # Leave empty line
                ML.LogMessage("")   

                # Read the history file (differentiestaat). There may be multiple, 
                # make keys unique for easy referencing
                dfh = df[MH.HIST_TYPE_KEY]
                if (isinstance(dfh, pd.Series)):
                    dfh = dfh.to_frame()
                cols = dfh.columns.to_list()
                
                # Add number to colnames (simple way to make them unique)
                # modify list along the way
                ncols = len(cols)
                for i in range(ncols): cols[i] += "_" + str(i)
                dfh.columns = cols
                
                # Loop over all files
                df1 = pd.DataFrame()
                refPeilmerk = None
                for col in cols:
                    dfl = dfh[col]
                    
                    # Stick relative path together with base path
                    path, fileName = self.fixPath(metaFileName, dfl)
                
                    # And read the subsidence data
                    assert(len(dfl.shape)==1)
                    dfx = self.readAnteaDiffstaat(fileName, dfl, path=path)
                    df1 = df1.append(dfx)
                    
                    lRefPeilmerk = self.getMetaKeyValue(dfl, MH.REFPEILMERK_KEY, None)
                    if not (lRefPeilmerk is None):
                        if (not (refPeilmerk is None)) and (refPeilmerk != lRefPeilmerk):
                            ML.LogMessage("Multiple reference peilmerken given '" + 
                                    lRefPeilmerk+ "' vs. '" + refPeilmerk+ "'")
                        refPeilmerk = lRefPeilmerk
                    
                # Prefix "project ID" with survey key so it can be used globally
                df1[PM.PRJID_KEY] = df1.apply(lambda x: key+"_"+str(x[PM.PRJID_KEY]), axis=1)
             
                # Read the coordinate file. 
                dfc = df[MH.COORD_TYPE_KEY]
                if (isinstance(dfc, pd.Series)):
                    dfc = dfc.to_frame()
                cols = dfc.columns.to_list()

                # There may be multiple same columns, 
                # make keys unique for easy referencing
                # Modify list along the way
                ncols = len(cols)
                for i in range(ncols): cols[i] += "_" + str(i)
                dfc.columns = cols
                
                # Loop over all files
                df2 = pd.DataFrame()
                for col in cols:
                    dfl = dfc[col]

                    # Stick relative path together with base path
                    path, fileName = self.fixPath(metaFileName, dfl)

                    # And read the coordinates
                    assert(len(dfl.shape)==1)
                    dfx = self.readAnteaCoordfile(fileName, dfl, path=path)
                    df2 = df2.append(dfx)
                
                # Store the data
                lpmdb = PM.PeilDataBase(key)
                lpmdb.addSurvey(key, srvFile=metaFileName, refPeilmerk=refPeilmerk, 
                    heights=df1, coords=df2)
                
                # Finally, the modfiles. There may be multiple. It may 
                # also be in the current file.
                try:
                    dm = df[MH.MODS_TYPE_KEY]
                    
                    # One or multiple?
                    if (len(dm.shape)==1):
                        path, fileName = self.fixPath(metaFileName, dm)
                        nMod += self.processModFile(lpmdb, metaFileName, dm)
                    else:
                        # Make sure the column names are unique
                        cols = dm.iloc[0].to_list()
                        nCols = len(cols)
                        for i in range(0,nCols):    
                            cols[i]+="_"+str(i)
                        dm.columns=cols
                        for c in dm:
                            path, fileName = self.fixPath(metaFileName, dm[c])
                            self.processModFile(lpmdb, metaFileName, dm[c])
                            nMod += 1
                except KeyError:
                    pass
                    
            # Mods could also be contained in a seprate tab of the main meta xls
            # Skip the tabs where we've already found data.
            cMeta = {MH.PAD_KEY: False}
            readTabs.extend(lSkipTabs)
            nMod += self.processModFile(lpmdb, metaFileName, cMeta, skipTabs=readTabs)
            
            pmdb.mergeDataBase(lpmdb)
