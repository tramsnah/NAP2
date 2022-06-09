'''
Create message logger for package.

Partly stub, can be extended.
'''

import logging

_outFolder = ""
_logFile = ""
_level = []
_initDone = False

def SetOutFolder(fldrName):
    '''
    Set folder (path) for output files from this package.
    See 'GetFileName'.
    '''
    global _outFolder
    _outFolder = fldrName
    
def GetOutFolder():
    '''
    Get folder (path) for output files from this package.
    '''
    return _outFolder
    
_pltCounter=0
def GetFileName(baseName, ext):
    '''
    Get output filename from basefile
    Fixed path prefix is added (see 'setIOutFolder')
    '''
    global _pltCounter
    global _outPath
    
    _pltCounter += 1
    out = baseName+str(_pltCounter)+ext
    
    if (_outFolder != ""):
        out = _outFolder+"\\"+out
    return out

def SetLogFile(fName):
    '''
    Set filename for output of message log
    '''
    global _logFile
    
    _logFile = fName

def _initLogging():
    '''
    Kick off message logging
    '''
    global _initDone
    
    if (not _initDone):
        fName = _logFile
        
        if (_outFolder != ""):
            fName = _outFolder+"\\"+fName
            
        # By default overwrite existing file
        logging.basicConfig(filename=fName, filemode='w',level=logging.INFO)
        _initDone = True
    
def LogMessage(s, severity=0):
    '''
    Add message 's' to log
    'severity' is an index
    <0: debug
    =0: info
    >0: warning
    '''
    global _logFile, _level
    
    t = (" "*(4*len(_level))) + s
    if (severity>0):
        print(s)
    else:
        print(t)
    
    if (_logFile != ""):
        _initLogging()
        if (severity<0):
            logging.debug(t) 
        elif (severity>0):
            logging.warning(s) 
        else:
            logging.info(t) 
    
def IncreaseLevel(name):
    '''
    Increase logging nesting level.
    '''
    global _level
    
    _level.append(name)
    
def DecreaseLevel(name):
    '''
    Decrease logging nesting level.
    'name' should match the one used in 'IncreaseLevel'.
    '''
    global _level

    assert(_level[-1]==name)
    _level.pop()
