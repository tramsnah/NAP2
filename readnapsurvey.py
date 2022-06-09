'''
Module contains classes/methods to convert Rijkswaterstaat (RWS)
files (both coordinates and differentiestaten) to
Pandas DataFrame format.
There are various format variations that are catered for, all ASCII.
A metafile (MS-Excel) is provided to inform on what's what.
'''
import csv
import os
import datetime
import pandas as pd

from . import pmexception as BE
from . import messagelogger as ML
from . import importutils as IU
from . import metafileheaders as MH
from . import peilmerkdatabase as PM

class LoadRWSCoordFailure(BE.PMException):
    '''
    Failure to load an Antea file
    '''
    def __init__(self, cause, filename):
        BE.PMException.__init__(self, "Failed to load RWS Coord file: " + 
                        cause + " in " + filename)

class LoadRWSMetafileFailure(BE.PMException):
    '''
    Failure in processing RWS NAP metafile
    '''
    def __init__(self, cause, filename):
        BE.PMException.__init__(self, "Failure to process RWS Metafile: " + 
                        cause + " in " + filename)

#########################################################################################

#########################################################################################

# Export/xoord keys # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

# Special marks for the two RWS data types
SERIES_NAP_HERZIEN="RWS"
SERIES_NAP_NIETHERZIEN="RWS_niet_herzien"

# RWS/NAP statuses for peilmerken
COORDSTATUSPUBL="publicabel"
COORDSTATUSVERV="vervallen"
COORDSTATUSZOND="zonder hoogte"

# New format (geoweb 5.5) is default for interchange
napcoordkeys=dict()
napcoordkeys["peilmerk"]="Peilmerk"
napcoordkeys["x"]="X-RD (m)"
napcoordkeys["y"]="Y-RD (m)"
napcoordkeys["status"]="status"

# Files have multiple formats...
napcoordkeysF=dict()
napunitF=dict()

# Old format (geoweb 5.1)
napcoordkeysF["F1"]=dict()
napcoordkeysF["F1"]["peilmerk"]="PNT_PNTID"
napcoordkeysF["F1"]["x"]="PNT_PUXCO"
napcoordkeysF["F1"]["y"]="PNT_PUYCO"
napcoordkeysF["F1"]["status"]="status"
napunitF["F1"]=1000.0 # 2017 files were in km

# Other format (geoweb 5.1)
napcoordkeysF["F2"]=dict()
napcoordkeysF["F2"]["peilmerk"]="Peilmerk"
napcoordkeysF["F2"]["x"]="X-RD (km)"
napcoordkeysF["F2"]["y"]="Y-RD (km)"
napcoordkeysF["F2"]["status"]="status"
napunitF["F2"]=1.0 # 2019 files were in m, despite header

# Other format (2018 survey export)
napcoordkeysF["F4"]=dict()
napcoordkeysF["F4"]["peilmerk"]="pnt_pntid"
napcoordkeysF["F4"]["x"]="pnt_puxco"
napcoordkeysF["F4"]["y"]="pnt_puyco"
napcoordkeysF["F4"]["mtype"]="pnt_pnttp"
napunitF["F4"]=1.0 

# Export/history keys # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

# Keys for export
NAPHIST_PEILMERK="peilmerk"
NAPHIST_PROJECT="project"
NAPHIST_DATE="date"
NAPHIST_HOOGTE="hoogte"
NAPHIST_HERZIEN="herzien"
NAPHIST_DATUM="datestr"

# NAP project history files are column-based
napprojkeys={}
napprojkeys[NAPHIST_PEILMERK]=[0,8]
napprojkeys[NAPHIST_HOOGTE]=[9,24]

# NAP history files are column-based
naphistkeys={}
naphistkeys[NAPHIST_PEILMERK]=[0,8]
naphistkeys[NAPHIST_DATUM]=[9,19]
naphistkeys[NAPHIST_PROJECT]=[21,31]
naphistkeys["owp"]=[32,34]
naphistkeys[NAPHIST_HOOGTE]=[35,45]
naphistkeys["fip"]=[46,47]
naphistkeys["fis"]=[48,49]
naphistkeys["fst"]=[50,51]
naphistkeys["height"]=[52,60]
naphistkeys["spd"]=[61,68]
naphistkeys["fag"]=[68,69]

# Export/meta keys # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

# Columns (lower case)   
FILE_KEY="datafile"
PATH_KEY="path"
FTYPE_KEY="filetype"
DATE_KEY="date"
DIST_KEY="disttoprev_m"

# File types (first 4 char, upper case)
HIST_TYPE_KEY="HIST"
PROJ_TYPE_KEY="PRHI"
MODS_TYPE_KEY="MODS"
PUBL_TYPE_KEY="PUBL"
VERV_TYPE_KEY="VERV"
ZOND_TYPE_KEY="ZOND"

#########################################################################################

class RWSLoader(IU.BaseLoader):
    '''
    Loader for RWS-NAP height files and coordlists.
    Both assumed to be provided as ASCII files.
    As formats vary, for each file metadata
    needs to be provided.
    '''
    def __init__(self, name="RWS"):
        IU.BaseLoader.__init__(self, "RWS", name)
        
    def readNAPCoordsCSVFile(self, filename, status):
        '''
        Read RWS peilmerk coordinates from CSV file
        into DataFrame.
        Heuristics applied to determine exact format.
        Output columns are 'x', 'y', 'peilmerk'
        '''
        # Deduce format heuristically
        with open(filename, 'r', encoding='ascii') as f:
            header_line=0
            delim=None
            while(header_line<5):
                line = f.readline()
                if not line:
                    break

                # find delimiter
                for s in ";,\t|":
                    ts=len(line.split(s))
                    if (ts>5):
                        delim=s
                        break
                if not (delim is None):
                    break
                header_line+=1
                
            # find format from key for x coordinate
            if (napcoordkeysF["F2"]["x"] in line):
                nFormat="F2"
            elif (napcoordkeysF["F1"]["x"] in line):
                nFormat="F1"
            elif (napcoordkeysF["F4"]["x"] in line):
                nFormat="F4"
            else:
                nFormat=""

        # Loop over the lines.
        # Store the rows in a list, then later convert to dataframe in one go
        # (faster than adding rows 1-by-1).
        mymap=[]
        with open(filename, 'r', encoding='ascii') as csv_file:
            # Skip spurious first line
            for i in range(header_line):
                csv_file.readline()

            csv_dictreader = csv.DictReader(csv_file, delimiter=delim,quotechar='"')
            
            # Data proper
            for row in csv_dictreader:
                # Avoid spaces in keys
                row2=dict()
                for key in row:
                    if(key is not None):
                        newkey=key.strip()
                        row2[newkey]=row[key]
                row=row2
                
                # Allow for empty lines
                if (nFormat != ""):
                    if (row[napcoordkeysF[nFormat]["peilmerk"]] is None): continue 
                    row[napcoordkeys["peilmerk"]] = row[napcoordkeysF[nFormat]["peilmerk"]]
                if(isinstance(row[napcoordkeys["peilmerk"]], str)):
                    row[napcoordkeys["peilmerk"]]=row[napcoordkeys["peilmerk"]].strip()
                if (row[napcoordkeys["peilmerk"]]==""): continue 
                
                try:
                    row[napcoordkeys["status"]]=status
                    if (nFormat != ""):
                        row[napcoordkeys["x"]] = row[napcoordkeysF[nFormat]["x"]]
                        row[napcoordkeys["y"]] = row[napcoordkeysF[nFormat]["y"]]
                        u=napunitF[nFormat]
                    else:
                        u=1.0
                    if(isinstance(row[napcoordkeys["x"]],str)):
                        row[napcoordkeys["x"]]=row[napcoordkeys["x"]].strip()
                    if(isinstance(row[napcoordkeys["y"]],str)):
                        row[napcoordkeys["y"]]=row[napcoordkeys["y"]].strip()
                    if (row[napcoordkeys["x"]]!="" or row[napcoordkeys["y"]]!=""):
                        row[napcoordkeys["x"]]=float(row[napcoordkeys["x"]])*u
                        row[napcoordkeys["y"]]=float(row[napcoordkeys["y"]])*u
                        mymap.append(row)
                    else:
                        ML.LogMessage("Skipping: " + row[napcoordkeys["peilmerk"]] + 
                                    ", No coordinates ")
                except KeyError:
                    raise LoadRWSCoordFailure("**** COORD FILE FORMAT ERROR *****", 
                                    filename)

        # Convert dictlist to dataframe
        napcoords = pd.DataFrame.from_records(mymap)

        return napcoords

    def _addNAPCoords(self, pmdb, filename, status):
        '''
        Add RWS peilmerk coordinates from CSV file to database 'pmdb'.
        Heuristics applied to determine exact format.
        columns are 'PM.X_KEY', 'PM.Y_KEY', 'PM.PEILMERK_KEY', 'PM.SRCFILE_KEY'.
        '''
        df = self.readNAPCoordsCSVFile(filename, status)
        
        # Map the keys
        df = df.rename({napcoordkeys["peilmerk"]: PM.PEILMERK_KEY}, axis=1)
        df = df.rename({napcoordkeys["x"]: PM.X_KEY}, axis=1)
        df = df.rename({napcoordkeys["y"]: PM.Y_KEY}, axis=1)
        
        # X and Y must be numeric
        df[PM.X_KEY] = pd.to_numeric(df[PM.X_KEY], errors='coerce')
        df[PM.Y_KEY] = pd.to_numeric(df[PM.Y_KEY], errors='coerce')
        
        # Check for NAN's or zeroes. Assume Y will be no different from X
        df_err = df[~(df[PM.X_KEY]>0) | df[PM.X_KEY].isnull()]
        if (len(df_err)>0):
            ML.LogMessage("Warning: Dropped {:d} lines with unreadable coords".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PM.PEILMERK_KEY].unique())     
        df = df[df[PM.X_KEY]>0 & ~df[PM.X_KEY].isnull()]
        
        # Log the source file
        df[PM.SRCFILE_KEY] = filename
        
        # Attribute the coordinates to the main (=herzien) NAP dataset
        pmdb.addSurveyData(SERIES_NAP_HERZIEN, coords=df)
            
        return len(df)
        
    def readNAPHistoryFile(self, filename):
        '''
        Read NAP history file.
        Heuristics applied to determine exact format.
        '''
        # Loop over the lines.
        # Store the rows in a list, then later convert to dataframe in one go
        # (faster than adding rows 1-by-1).
        mymap=[]
        count = 0
        with open(filename, 'r', encoding='ascii') as file1: 
            while True:
                count += 1
              
                # Get next line from file 
                line = file1.readline() 
              
                # if line is empty 
                # end of file is reached 
                if not line:
                    break
                # File contains headers and fluff. Assume all lines 
                # starting with '0' are actual data
                elif line[0]=="0":
                    row={}

                    # Get the NAP data from the line (fixed columns)
                    for mykey, nhist in naphistkeys.items():
                        txt = line[nhist[0]:nhist[1]]
                        row[mykey]=txt

                    # Map date, and add
                    mydate=row[NAPHIST_DATUM]
                    ddate = datetime.date(int(mydate[0:4]), int(mydate[5:7]), int(mydate[8:10]))
                    row[NAPHIST_DATE]=ddate
                    
                    # NAP was reviewed. This can be seen as '=' in project name
                    if ('=' in  row[NAPHIST_PROJECT]):
                        row[NAPHIST_HERZIEN]=True
                    else:
                        row[NAPHIST_HERZIEN]=False
                    
                    # Append row to dictlist
                    mymap.append(row)

        # Convert dictlist to dataframe
        naphistory = pd.DataFrame.from_records(mymap)

        return naphistory

    def readNAPProjectHistoryFile(self, filename):
        '''
        Read RWS file containing measurement data of a specific project
        (rather than the full historu for a given group of peilmerken)
        '''
        # Loop over the lines.
        # Store the rows in a list, then later convert to dataframe in one go
        # (faster than adding rows 1-by-1).
        mymap=[]
        count = 0
        with open(filename, 'r', encoding='ascii') as file1:  
            while (True):
                count += 1
              
                # Get next line from file 
                line = file1.readline() 
              
                # if line is empty 
                # end of file is reached 
                if not line:
                    break
                # File contains headers and fluff. Assume all 
                # lines starting with '0' are actual data
                elif line[0]=="0":
                    row={}
                    # Get the NAP data from the line (fixed columns)
                    for mykey, nproj in napprojkeys.items():
                        txt = line[nproj[0]:nproj[1]]
                        row[mykey]=txt
                    
                    # Append row to dictlist
                    mymap.append(row) 

        # Convert dictlist to dataframe
        naphistory = pd.DataFrame.from_records(mymap)
        
        return naphistory
        
        
    def _addNAPHistory(self, pmdb, filename):
        # Read history into dataframe
        df = self.readNAPHistoryFile(filename)
        
        # Map the keys
        df = df.rename({NAPHIST_PEILMERK: PM.PEILMERK_KEY}, axis=1)
        df = df.rename({NAPHIST_PROJECT: PM.PRJID_KEY}, axis=1)
        df = df.rename({NAPHIST_HOOGTE: PM.HGT_KEY}, axis=1)
        df = df.rename({NAPHIST_DATE: PM.DATE_KEY}, axis=1)
        
        # HGT must be numeric
        df[PM.HGT_KEY] = pd.to_numeric(df[PM.HGT_KEY], errors='coerce')
        
        # Check for NAN's 
        df_err = df[df[PM.HGT_KEY].isnull()]
        if (len(df_err)>0):
            ML.LogMessage("Warning: Dropped {:d} lines with unreadable heights".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PM.PEILMERK_KEY].unique())     
        df = df[~df[PM.HGT_KEY].isnull()]
        
        # Log the source file
        df[PM.SRCFILE_KEY] = filename
        
        # Split into herzien/niet herzien
        df_hz = df[df[NAPHIST_HERZIEN]]
        df_nh = df[~df[NAPHIST_HERZIEN]]
        
        # Then add them both separately
        pmdb.addSurveyData(SERIES_NAP_HERZIEN, heights=df_hz)
        pmdb.addSurveyData(SERIES_NAP_NIETHERZIEN, heights=df_nh)
           
        return len(df)
        
    def _addNAPProjectHistory(self, pmdb, filename, pdate, prjid, naptype=SERIES_NAP_HERZIEN):
        # Read history into dict
        df = self.readNAPProjectHistoryFile(filename)
        
        # Map the keys
        df = df.rename({NAPHIST_PEILMERK: PM.PEILMERK_KEY}, axis=1)
        df = df.rename({NAPHIST_HOOGTE: PM.HGT_KEY}, axis=1)
        
        # HGT must be numeric
        df[PM.HGT_KEY] = pd.to_numeric(df[PM.HGT_KEY], errors='coerce')
        
        # Check for NAN's 
        df_err = df[df[PM.HGT_KEY].isnull()]
        if (len(df_err)>0):
            ML.LogMessage("Warning: Dropped {:d} lines with unreadable heights".format(len(df_err)),
                           severity=1)
            print("    ", df_err[PM.PEILMERK_KEY].unique())     
        df = df[~df[PM.HGT_KEY].isnull()]
        
        # Map date, and add
        if (isinstance(pdate, datetime.datetime)):
            pdate = pdate.date()
        df[PM.DATE_KEY] = pdate
        
        # Keep track of project
        df[PM.PRJID_KEY] = prjid
        
        # Add it
        pmdb.addSurveyData(naptype, heights=df)
        
        return len(df)

    def readSurvey(self, pmdb, metaFileName, limitDist=1e38, skipTabs=None):
        '''
        Read NAP survey. THe files in the survey (mix of coordinate and height 
        data, as well as mods (name changes, removal od spurious points, marking peilmerken
        as unstable)) are specified in the MS-Excel file 'metaFileName'
        Data is added to 'pmdb'
        If limitDist is given, files outside of this distance from peilmerken
        that are already in 'pmdb', are ignored.
        'skipTabs' can contain a list of tabs in 'metaFileName' that can be skipped.
        All other tabs are scanned for 'FILE_KEY'.
        '''
        # Always skip 'README' tab
        if (skipTabs is None): lSkipTabs = list()
        else: lSkipTabs = list(skipTabs)
        lSkipTabs.append("README")
        
        with IU.ReadNotifier(self, metaFileName):
            lpmdb = PM.PeilDataBase("RWS_NAP")

            # Strip the path out of the filenames.
            # Paths in the metafile are relative to this path
            basepath = os.path.dirname(metaFileName)
            
            # Loop over the rows in the table
            ML.LogMessage("Loading NAP data from " + metaFileName)

            # Read the metafile. We'll get a dict of dataframes
            dfs = pd.read_excel(metaFileName, header=None, sheet_name=None)
            
            # The tab containing the metadata. Find it, get the actual metadata
            # as a dataframe
            topleftstring=FILE_KEY
            nmod = 0
            readTabs = []
            for df in self.findTableByTopLeft(dfs, topleftstring, skipTabs=lSkipTabs):
                # Keep track of tabs we've covered
                readTabs.append(df.tabName)
                
                # Compile list of mods, process them at the end
                modfiles={}

                # Convert the top row to header. Convert to lower case to make insensitive
                cols = df.iloc[0].to_list()
                cols = [x.lower() for x in cols]
                df.columns=cols
                df.drop(df.index[0], inplace = True)
                
                # Transpose (for easier indexing)
                df = df.transpose()
                
                # Warn what is coming
                lpmdb.registerSurvey(SERIES_NAP_HERZIEN, subSurveys=[SERIES_NAP_NIETHERZIEN], 
                            srvFile = metaFileName)
                
                # Loop over the input files
                for c in df:
                    # Get metadata for current file
                    row=df[c]

                    # Stick relative path together with base path
                    path, subfile = self.fixPath(metaFileName, row)
                    if (subfile == ""):
                        raise LoadRWSMetafileFailure(
                                        "Missing/incorrect file specification in line# "
                                        +str(c), metaFileName)

                    # first 4 chars are base type, 5th is modifier
                    try:
                        ftype=row[FTYPE_KEY][:4].upper()          
                    except KeyError:
                        raise LoadRWSMetafileFailure(
                                            "Missing/incorrect type specification in line# "
                                            +str(c), metaFileName)

                    
                    if (ftype == HIST_TYPE_KEY):
                        ML.LogMessage("Loading history file "+ path+subfile)
                        nload=self._addNAPHistory(lpmdb,path+subfile,)
                    elif (ftype == PROJ_TYPE_KEY):
                        ML.LogMessage( "Loading project history file "+ path+subfile)
                        try:    
                            pdate=row[DATE_KEY]
                        except KeyError:
                            raise LoadRWSMetafileFailure(
                                    "Missing/incorrect date specification for project in line# "
                                    +str(c), metaFileName)
                        prjid = path # TODO
                        nload = self._addNAPProjectHistory(lpmdb,path+subfile,
                                                        pdate,prjid)
                    elif (ftype == MODS_TYPE_KEY):
                        modfiles[path+subfile]={MH.PAD_KEY: False}
                    elif (ftype == PUBL_TYPE_KEY):
                        # Publicabel coordinates
                        ML.LogMessage( "Loading coord file (publicabel) "+ path+subfile)
                        nload = self._addNAPCoords(lpmdb,path+subfile,COORDSTATUSPUBL)
                    elif (ftype == VERV_TYPE_KEY):
                        # Vervallen coordinates
                        ML.LogMessage( "Loading coord file (vervallen) "+ path+subfile)
                        nload = self._addNAPCoords(lpmdb,path+subfile,COORDSTATUSVERV)
                    elif (ftype == ZOND_TYPE_KEY):
                        # Peilmerken without historic data
                        ML.LogMessage( "Loading coord file (zonder hoogte) "+ path+subfile)
                        nload =self._addNAPCoords(lpmdb,path+subfile,COORDSTATUSZOND)
                    else:
                        ML.LogMessage( "NOT loading unknown file "+ path+subfile, severity=1)
                        nload=0
                    ML.LogMessage( "loaded "+str(nload)+ " lines")
                    
                # Empty line for readability
                ML.LogMessage("")
                
                # Add the mods
                for f, mfil in modfiles.items():
                    nmod += self.processModFile(lpmdb, f, mfil)

            # The metafile may contain mods in other tabs.
            # Skip the tabs where we've already found data.
            cMeta = {MH.PAD_KEY: False}
            readTabs.extend(lSkipTabs)
            nmod += self.processModFile(lpmdb, metaFileName, cMeta, skipTabs=readTabs)
            ML.LogMessage( "processed "+str(nmod)+ " mods")    
           
            # Check the consisitency of the NAP dataset
            nocoord, nohist, issues = lpmdb.checkComplete()
            ML.LogMessage("")
            ML.LogMessage("no coordinates for "+str(len(nocoord))+" peilmerken: "+str(nocoord))
            ML.LogMessage("no history for "+str(len(nohist))+" peilmerken: "+str(nohist))
            print()
            
            # Merge into the existing DB
            pmdb.mergeDataBase(lpmdb, limitDist=limitDist)
            print("Loaded!")
            print()
            print()
