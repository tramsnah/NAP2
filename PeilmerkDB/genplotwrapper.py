'''
Modile contains generic (abstract) base classes to facilitate managing various
kinds of plots
'''
from . import peilmerkdatabase as PM # For keys

class GenPlotManager:
    '''
    Generic (abstract) base class for objects that manage a number of
    (matlotlib) plots, in separate windows, managed by 'plt' or
    run in batch mode.
    The plots themselves will be wrapped in 'GenPlotWrapper'
    '''
    def __init__(self):
        self._plots=dict()
        
    def addWrapper(self, wrap):
        '''
        After its creation, a 'GenPlotWrapper' notifies us.
        '''
        assert(not (wrap.getName() in self._plots))
        self._plots[wrap.getName()] = wrap

    def forgetWrapper(self, wrap):
        '''
        After being closed, a 'GenPlotWrapper' notifies us.
        '''
        if (wrap.getName() in self._plots):
            #print("    GenPlotManager.forgetWrapper", wrap.getName())
            self._plots.pop(wrap.getName())
        else:
            pass
            #print("*** GenPlotManager.forgetWrapper", wrap.getName(), "already forgotten")

    def getWrapper(self, name):
        '''
        Get pointer to a 'GenPlotWrapper' by name
        '''
        if not (name in self._plots): return None
        return self._plots[name]

class GenPlotWrapper:
    '''
    Generic (abstract) base class for objects that create 
    (matlotlib) plots, in separate windows, managed by 'plt' or
    run in batch mode.
    The various 'GenPlotWrapper' objects are managed by 
    'GenPlotManager'
    '''
    def __init__(self, name, mgr, wType, pmkey="", dkey="", hkey="", skey="", xkey="", ykey=""):
        # Key defaults for data supplied in dataframes
        # done this way so they can be overruled
        if (pmkey is None or pmkey==""): pmkey = PM.PEILMERK_KEY
        if (dkey is None or dkey==""): dkey = PM.DATE_KEY
        if (hkey is None or hkey==""): hkey = PM.HGT_KEY       
        if (skey is None or skey==""): skey = PM.SURVEY_KEY 
        if (xkey is None or xkey==""): xkey = PM.X_KEY    
        if (ykey is None or ykey==""): ykey = PM.Y_KEY       
        self.dkey = dkey
        self.pmkey = pmkey
        self.hkey = hkey        
        self.skey = skey
        self.xkey = xkey        
        self.ykey = ykey

        self._name = name
        self._mgr = mgr
        self._type = wType
        self._title = ""
        
        mgr.addWrapper(self)

    def getName(self):
        '''
        Return name of plot wrapper/window.
        (Used as key by 'GenPlotManager')
        '''
        return self._name
        
    def getTitle(self):
        '''
        Return title of plot
        '''
        return self._title
        
    def setTitle(self, title):
        '''
        Set title of plot
        '''
        self._title = title
        
    def getFileExtension(self):
        '''
        Return extension of files to generate in batch mode.
        Must be overridden.
        '''
        assert(0) # Must be overridden
        return "png"
        
    def forgetMe(self):
        '''
        'close' method calls this method when the plot/window is closed,
        to remove admin related to this wrapper.
        '''
        #print("**** GenPlotWrapper.forgetMe", self.getName())
        self._mgr.forgetWrapper(self)
        
    def getColorScale(self, inverted=False):
        '''
        Define the color scale we'll use
        Example output:
            colors=dict()
            colors[0.00] = (  0,  0,255) # blue
            colors[0.08] = (128,128,255) # light blue
            colors[0.16] = (128,255,128) # light green
            colors[0.25] = (  0,255,  0) # green
            colors[0.37] = (128,255,  0) # lime
            colors[0.50] = (255,255,  0) # yellow
            colors[0.63] = (255,128,  0) # orange
            colors[0.75] = (255,  0,  0) # red
            colors[0.87] = (180, 14, 14) # burgundy
            colors[1.00] = (110, 28, 28) # brown
        '''
        # RGB is easier
        colors = dict()
        colors[0.00] = (  0,  0,255) # blue
        colors[0.08] = (128,128,255) # light blue
        colors[0.16] = (128,255,128) # light green
        colors[0.25] = (  0,255,  0) # green
        colors[0.37] = (128,255,  0) # lime
        colors[0.50] = (255,255,  0) # yellow
        colors[0.63] = (255,128,  0) # orange
        colors[0.75] = (255,  0,  0) # red
        colors[0.87] = (180, 14, 14) # burgundy
        colors[1.00] = (110, 28, 28) # brown
        
        # Invert
        if (inverted):
            c2 = dict()
            for p, col in colors.items():
                c2[1.0-p]=col
            colors = c2   
            
        return colors

    def close(self): 
        '''
        Base class action upon closure is to remove from any admin.
        Subclasses should overload to add behavior.
        '''
        #print("    GenPlotWrapper.close")
        self.forgetMe()
