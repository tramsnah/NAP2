'''
Module with utilities for importing coordinate and differentiestaat
files
'''
import os
import numpy as np
import pandas as pd

from . import pmexception as BE
from . import messagelogger as ML
from . import metafileheaders as MH

class _FoundException(BE.PMException):
    '''
    Dummy exception to break out of loops after target found
    '''
    pass    

class KeyNotFoundException(BE.PMException):
    '''
    Dummy exception to break out of loops after target found
    '''
    pass  
    
class ReadNotifier:
    '''
    Simple class to inform loader of begin/end of a read
    to be used in 'with' statement
    '''
    def __init__(self, loader, loadingFileName):
        self.loader = loader
        self.fileName = loadingFileName
      
    def __enter__(self):
        self.loader.notifyStartRead(self.fileName)        
        return self.fileName # dummy
  
    def __exit__(self, exc_type, exc_inst, exc_traceback):
        self.loader.notifyEndRead(self.fileName)
        self.loader = None
        self.fileName = ""

class BaseLoader:
    '''
    Abstract base class for loaders of data into PeilmerkDatabase.
    '''
    def __init__(self, lType, name):
        self._type = lType
        self._name = name
        self._loading = []

    def notifyStartRead(self, fileName):
        '''    
        Called by readNotifier, to notify reading the file has started
        ''' 
        ML.IncreaseLevel(self._name)
        self._loading.append(fileName)

    def notifyEndRead(self, fileName):
        '''    
        Called by readNotifier, to notify reading the file has ended
        '''        
        ML.DecreaseLevel(self._name)
        self._loading.remove(fileName)
        
    def fixPath(self, defFileName, metaPars):
        '''    
        Aux function to find path from several soources
        '''
        # Strip the path out of the metafilenames.
        # Paths in the metafile are relative to this path
        defPath = os.path.dirname(defFileName)
    
        # Get filename from metaPars. If none specified,
        # assume it is in (another tab) of the metafile
        fileName = self.getMetaKeyValue(metaPars, MH.FILE_KEY, "")
            
        # Fill path specified? then we're done
        if (os.path.isabs(fileName)):
            return "", fileName
            
        # Look for path in the metaPars
        path = self.getMetaKeyValue(metaPars, MH.PATH_KEY, "")

        # If nont specified, use the path of the metafille
        if (path==""):
            path=defPath
        else:
            if (not os.path.isabs(path)):
                path=defPath+"\\"+path
        if (path[-1] != "\\"):
            path=path+"\\"
        return path, fileName

    def fixPeilmerkName(self, spmIn, pad):
        '''
        Utility to fix peilmerk name
        TODO: add functionality to automatically fix 'short' RWS names (e.g. 5G32)
        '''
        spm = str(spmIn).strip()
        if ("e+" in spm):
            n = spm.find("e+")
            exp = int(spm[n+2:])-1
            flt = int(float(spm[:n])*10+0.5)
            sNew= ('0000' + str(flt))[-3:]+"E"+('0000' + str(exp))[-4:]
            ML.LogMessage(
                "    Found wrong 'E' peilmerk '{:s}', guessing it means '{:s}'".
                    format(spm, sNew))
            spm = sNew
        if (pad and len(spm)<8):
            if isinstance(spm,float):
                spm=int(spm)
            spm =('0000000' + spm)[-8:]
        return spm    

    def getMetaKeyValue(self, metaPars, key, defValue):
        '''
        Utility to get value out of metadata dict
        '''
        if (metaPars is None): return defValue
        
        val = defValue
        try:
            val = metaPars[key]
            if (isinstance(val, str)):
                val = val.strip()
            if (val is np.nan or (isinstance(val, str) and val == "")): 
                val = defValue
        except KeyError:
            pass
            
        return val

    def findTableByTopLeft(self, dfs, topleftstring, tabName="", skipTabs=None):
        '''
        Generator function.
        Yields dataframe for each tab that contains 'topleftstring',
        containing all data below/right of that string.
        
        'skiptabs' may contain a list of tabs not to seacth.
        
        'tabName' may contain the tab to check. If empty all tabs are checked 
        except skipTabs
        
        The yielded dataframe has the tabName as an adhoc propeerty
        '''
        if (skipTabs is None): skipTabs = list()

        df = None
        
        # Find the required metadata. It may not start in the topleft cell
        # and we me not know the tab. Loop over tabs
        found = False
        for lTabName in dfs:
            if (lTabName in skipTabs): continue
            if (tabName != "" and lTabName != tabName): continue
            
            df = dfs[lTabName]
            try:
                (nrows,ncols) = df.shape
                for column in range(0,ncols):
                    for i in range(0,min(nrows,100)):
                        v = df.iat[i, column]
                        if (isinstance(v, str) and v.lower() == topleftstring.lower()):
                            found = True
                            ML.LogMessage(
                                "    Found survey metadata in '{:s}' at row {:d}, column {:d}".
                                    format(lTabName, i, column))

                            # Remove stuff above or left
                            if (column>0):
                                cols=range(0,column)
                                df.drop(df.columns[cols], axis=1, inplace=True)
                            if (i>0):
                                rows=range(0,i)
                                df.drop(index=rows, inplace=True)
                            df.tabName = lTabName
                            
                            # Yield the result
                            yield df
                            
                            # And move on to the next tab
                            raise _FoundException
                            
            except _FoundException:
                pass

        if (not found):
            raise KeyNotFoundException("Failed to find key '{:s}' in any tab".format(topleftstring))        
        
    
    def processModFile(self, lpmdb, fileName, metaPars, skipTabs=None, path="", padDefault=False):
        '''
        Utility to ptocess file with mods.
        Can be:
            ALIAS
            UNSTABLE
            DELETE
        '''
        ML.LogMessage("    Reading post-processing modifications from '" + fileName+"'")

        if (skipTabs is None): lSkipTabs=list()
        else: lSkipTabs=list(skipTabs)
        lSkipTabs.append("README")

        # Get parameters
        tabName = self.getMetaKeyValue(metaPars, MH.TAB_KEY, "") # TODO: should we use tabName?
        pad = self.getMetaKeyValue(metaPars, MH.PAD_KEY, padDefault)

        # Load the file. Path either in filename or specified separately
        try:
            dfs = pd.read_excel(fileName, header=None, sheet_name=None)
        except FileNotFoundError:
            dfs = pd.read_excel(path+fileName, header=None, sheet_name=None)

        # Find the data
        df = None
        topleftstring=MH.MTYPE_KEY
        for df in self.findTableByTopLeft(dfs, topleftstring, skipTabs=lSkipTabs):
            # Convert the top row to header. Convert to lower case to make insensitive
            cols = df.iloc[0].to_list()
            cols = [x.lower() for x in cols]
            df.columns=cols
            df.drop(df.index[0], inplace = True)

            # Default pad if not specified
            if not (MH.PAD_KEY in cols):
                df[MH.PAD_KEY] = pad
            if not (MH.MCOMMENT_KEY in cols):
                df[MH.MCOMMENT_KEY] = ""
                
            # Treat mods 1-by-1 (to cover for dependencies)
            nAlias = 0
            nDelete = 0
            nUnstable = 0
            for i in range(0,len(df)):
                spm = df[MH.MPEILMERK_KEY].iloc[i]
                mType = df[MH.MTYPE_KEY].iloc[i]
                mComment = df[MH.MCOMMENT_KEY].iloc[i]
                lPad  = df[MH.PAD_KEY].iloc[i]
                try:
                    spm = self.fixPeilmerkName(spm, lPad)
                    if (mType.upper()[:4] == MH.ALIAS_TYPE_KEY[:4]):
                        sNew = df[MH.ALIAS_KEY].iloc[i]
                        sNew = self.fixPeilmerkName(sNew, lPad)
                        nAlias += lpmdb.renamePeilmerk(spm, sNew, mComment)
                    elif (mType.upper()[:4] == MH.DELETE_TYPE_KEY[:4]):
                        nDelete += lpmdb.deletePeilmerk(spm, mComment)
                    elif (mType.upper()[:4] == MH.UNSTABLE_TYPE_KEY[:4]):
                        nUnstable += lpmdb.markPeilmerkUnstable(spm, mComment)
                except KeyError:
                    ML.LogMessage("    '{:s}' not found, {:s} not applied".
                            format(spm, mType), severity=1)
                    
            ML.LogMessage("    Processed modifications: {:d} aliases, {:d} deleted, {:d} unstable".
                        format(nAlias, nDelete, nUnstable))
        
        # Leave empty line
        ML.LogMessage("")

        return len(df)
        