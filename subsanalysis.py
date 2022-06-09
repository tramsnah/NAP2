'''
Class to to create various QC plots (line plots, intersections, maps of)
peilmerk (leveling) measurements

TODO: Handle 'moreLater' that is not completed!?
'''
import pickle
from re import A
import numpy as np
import pandas as pd
import datetime

from . import pmexception as BE
from . import peilmerkdatabase as PM
from . import genplotwrapper as GW
from . import geopandamapwrapper as GPW
from . import foliummapwrapper as FMW
from . import pmplotwrapper as PPW
from . import histowrapper as HWP
from . import crossplotwrapper as XWP
from . import intersectionwrapper as IWP
from . import plotline as PL

#####################################################################
class SubsAnalysisException(BE.PMException):
    '''
    General superclass for exceptions in this module.
    '''
    def __init__(self, descr):
        BE.PMException.__init__(self, descr)
        
#####################################################################
# Modes in which the analysis can be run
TO_FILE="file" # Outputs png files
EMBEDDED="embed" # Display in someone else's window
INTERACTIVE="interactive" # Use MatPlotlib

class SubsAnalState:
    '''
    Dummy class to hold state information
    '''
    pass

class SubsAnalysis(GW.GenPlotManager):
    '''
    Wrapper class to help in making subsidence analysis QC plots.
    '''
    def __init__(self):
        GW.GenPlotManager.__init__(self)
        self.pmdb = None
        
        self._state = SubsAnalState()
        self._state._fileName = None

        self._state._focusSurvey = None
        self._state._defStartYear = None
        self._state._defAfterYear = None
        self._state._defRefYear = None

        self._state._refShifts = dict()

        self._state._unitDiff = "mm" # for height differences
        self._state._unitHgt = "m" # for heights

        self._state._plotBaseName = ""
        self._pltCounter = 0 # for generating filenames

        self._state._mode = TO_FILE
        self._state._outFolder = ""

    def importDataBase(self, fileName = None):
        '''
        Load database

        Hardwired default... (for now)
        '''
        if (fileName is None):
            basePath = "C:\\Users\\Hans\\Documents\\Programma's\\NAP data\\"
            fileName = basePath+"database.pmdb"

        self._state._fileName = None

        self.pmdb = PM.PeilDataBase("PeilmerkDB")
        self.pmdb.load(fileName)

        self._state._fileName = fileName

    def dumpP(self, F):
        '''
        Save (pickle) state to F
        '''
        version="1.1"
        pickle.dump(version, F)

        # Our state
        pickle.dump(self._state, F)

    def loadP(self, F):
        '''
        Load (pickle) state from F
        '''
        version = pickle.load(F)
        assert(version=="1.0" or version=="1.0")

        # Our state
        self._state = pickle.load(F)
        
        # Upgrade file version if needed
        if (version=="1.0"):
            #for property, value in vars(self._state).items():
            #    print(property, ":", value)
            self._state._focusSurvey = None
            self._state._defStartYear = None
            self._state._defAfterYear = None
            self._state._defRefYear = None
            
        # db, if given
        if not (self._state._fileName is None):
            fileName = self._state._fileName
            self._state._fileName = None
            self.importDataBase(fileName=fileName)
            # TODO: exception handling
            
    def setOutFolder(self, fldrName):
        '''
        Set folder (path) for output files from this module
        '''
        self._state._outFolder = fldrName

    def getOutFolder(self):
        '''
        Get folder (path) for output files from this module
        '''
        return self._state._outFolder


    def _parseUnit(self, unit):
        '''
        Get scale factor, descriptor for 'unit' (internal)
        '''
        scaleFactor = 1
        fStr = "{:.4f}"
        if (unit == "mm"):
            scaleFactor = 1000
            fStr = "{:.1f}"
        elif (unit == "cm"):
            scaleFactor = 100
            fStr = "{:.2f}"
        return scaleFactor, fStr

    def setMode(self, mode):
        '''
        Interactive or batch
            TO_FILE         # Outputs png files (in batch)
            EMBEDDED        # Display in someone else's window ('inDialog'
                              must be supplied in plot calls)
            INTERACTIVE     # Use MatPlotlib for interactivity
        '''
        self._state._mode = mode
        
    def setInteractive(self):
        '''
        Interactive (convenience mode)
        '''        
        self.setMode(INTERACTIVE)

    def setPlotFileBase(self, name):
        '''
        Basename for output files (in batch mode)
        '''
        self._state._plotBaseName = name

    def _getPlotName(self, typeStr):
        '''
        Generate output file name (internal)
        '''
        self._pltCounter +=  1
        plotName = self._state._plotBaseName
        if (plotName != ""):
            plotName +=  "_"
        if not (self._state._focusSurvey is None):
            plotName+= self._state._focusSurvey+"_"
        plotName +=  "analysis_"+str(self._pltCounter)+"_"+typeStr

        if (self._state._outFolder !=  ""):
            plotName = self._state._outFolder + plotName

        return plotName

    def modifyReference(self, year, dz, srvy = None):
        '''
        Set shift for specific survey/year, to deal with
        misalignments in analysis.
        '''
        ## TODO: handle nested surveys!
        if (srvy is None):
            assert(self._state._focusSurvey is not None)
            srvy = self._state._focusSurvey
        if not (srvy in self._state._refShifts):
            self._state._refShifts[srvy] = dict()
        self._state._refShifts[srvy][year] = dz

    def setFocusSurvey(self, srvy):
        '''
        Set default survey to use
        '''
        self._state._focusSurvey = srvy

    def setDefaultRefYear(self, defYear):
        '''
        Set default yeer for differences to start (i.e. assume subs=0 in this year)
        '''
        self._state._defRefYear = defYear
        
    def setDefaultAfterYear(self, defYear):
        '''
        Set default yeer for point after which peilmerken must have data
        '''
        self._state._defAfterYear = defYear
        
    def setDefaultStartYear(self, defYear):
        '''
        Set default yeer for plots to start
        '''
        self._state._defStartYear = defYear    
        
    def getNumSurveys(self):
        '''
        Get # surveys in database
        '''
        if (self.pmdb is None): return 0
        
        return self.pmdb.getNumSurveys()

    def getSurveyList(self):
        '''
        Get list of surveys in the database
        '''
        if self.pmdb is None:
            return None
        return self.pmdb.getSurveyList()   

    def getNumPeilmerken(self):
        '''
        Get # peilmerken in database
        '''
        if (self.pmdb is None): return 0
        
        return self.pmdb.getNumPeilmerken()
    
    def getPeilmerkenWithinBounds(self, bounds):
        ''' 
        Get peilmerken in database withun bounds
        supplied as (xmin, ymin, xmax, ymax), in RD.
        Returned as GeoDataFrame.
        '''
        if self.pmdb is None:
            return None
        return self.pmdb.getPeilmerkenWithinBounds(bounds)
        
    def getSurveyYears(self, srvy):
        '''
        Get list of (calendar) years in which a survey has measurements
        '''
        if self.pmdb is None:
            return None
        return self.pmdb.getSurveyYears(srvy)
        
    def getClosestPeilmerkenAsFrame(self, xy, **kwargs):
        '''
        Get geodataframe of peilmerknames and matching list of distances that are 
        within maxdist, and have measurements in at least minPoints years. 
        The list is sorted on dist, and retruned as a dict, peilmerken in 
        PEILMERK_KEY, distances in DISY_KEY.
        '''
        if self.pmdb is None:
            return None
        return self.pmdb.getClosestPeilmerkenAsFrame(xy, **kwargs)
        
    def getPeilmerkXY(self, spm):
        '''
        Get X,Y (in RD) for peilmerk 'spm'
        '''
        if self.pmdb is None:
            return None
        return self.pmdb.getPeilmerkXY(spm)

    #####################################################################
    #
    # Maps
    #
    #####################################################################

    def openSurveyMap(self, inDialog=None, warp=False, mapType="mpl"):
        '''
        Initiate survey map plot
        '''
        fow = self.getWrapper("map")
        if not (fow is None):
            print("**** Mapwrapper still there", fow.isOpen())
            
        # Will add itself to our watch list
        if (mapType == "folium"):
            assert(inDialog is None)
            FMW.FoliumWrapper("map", self, warp=warp)
        else:
            GPW.GPWrapper("map", self, inDialog=inDialog, warp=warp)
            
    def addPointsToMap(self, df, **kwargs):
        '''
        Add points (in geodataframe gdf, or list of points) to map
        '''
        # Get map wrapper
        fow = self.getWrapper("map")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")
            
        zKey = "" # TODO

        # And pass it on
        fow.addPoints(df, **kwargs)
                       
    def addPolygonToMap(self, df, **kwargs):
        '''
        Add polygon (in geodataframe gdf, or list of points, or Polygon) to map
        '''
        # Get map wrapper
        fow = self.getWrapper("map")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")


        # And pass it on
        fow.addPolygon(df, **kwargs)

    def showSurveyOnMap(self, srvy = None, year = None, year2 = None,
                        color = "blue", marker = None, size = 5, 
                        bkgPoints = False, scaleMax = None, useForZoom = True,
                        line=None, includeUnstable=False, annotate=None):
        '''
        Add survey(s) to map
        '''
        # Get map wrapper
        fow = self.getWrapper("map")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")

        # Default survey(s)
        if (srvy is None):
            srvy = self._state._focusSurvey  
        if (isinstance(srvy,str)):
            srvy = [srvy]
            
        assert(not bkgPoints)
        
        # Loop over surveys
        idx = -1
        for lsrvy in srvy:
            idx += 1
            lmarker = marker
            if (lmarker is None): lmarker = idx
            
            # Get diff data
            zKey = ""
            df1 = None
            if not (year2 is None):
                assert(not (year is None))
                zKey=PM.DIFF_KEY
                df1 = self.pmdb.getSurveyDiffs(lsrvy, year1 = year, year2 = year2, refShifts = self._state._refShifts)
                
                # Remove unstable
                if (not includeUnstable): df1 = df1[~df1[PM.UNSTABLE_KEY]]
                
                # Apply units. Different for absolute NAP and subsidence
                unit = self._state._unitDiff
                scaleFactor, fStr = self._parseUnit(unit)
                df1.loc[:,PM.DIFF_KEY] *= scaleFactor
            elif not (year is None):
                df1 = self.pmdb.getSurveyPointsFrame(lsrvy, year = year)
            if (df1 is None) or (len(df1)==0):
                df1 = None
            
            # Get coords only
            df2 = None
            if not (year is None):
                df2 = self.pmdb.getSurveyPointsFrame(lsrvy, year = None)

            # Background
            if not (df2 is None):
                fow.addPoints(df2, layer = lsrvy+" (all)", marker = lmarker,
                        color = "grey", labelKey=PM.PEILMERK_KEY,
                        size = size, useForZoom = useForZoom)

            # Foreground
            if not (df1 is None):
                # Colormap if needed
                if (zKey != ""):
                    # Zvalues are negative
                    if (scaleMax is None):
                        scaleMax=-np.percentile(df1[PM.DIFF_KEY],5)
                        #scaleMax=-min(zValueMap.values())
                        
                        # At least 4 cm
                        scaleMax = max(scaleMax, 0.04*scaleFactor)
                        
                    # Make the plot
                    fow.addColormap("subs ["+self._state._unitDiff+"]", -scaleMax, 0, inverse = True)
                    
                # Proper label
                label = lsrvy + " " +str(year)
                if not (year2 is None):
                    label += "-" +str(year2)

                # Overlay with target subset
                fow.addPoints(df1, layer=label, color=color, zKey=zKey,
                                labelKey=PM.PEILMERK_KEY, size=size, marker=lmarker,
                                useForZoom=useForZoom)
        
        if (annotate is not None):
            annotations=[]
            coords=[]
            for text, coord in annotate.items():
                if (isinstance(coord, str)):
                    spm = text if (coord == "") else coord
                    coord = self.pmdb.getPeilmerkXY(spm)
                coords.append(coord)
                annotations.append(text)
            fow.addAnnotations(coords, annotations)
        
        if (line is not None):
            # Display the line (don't change map bounds)
            xys = line.getEndPoints()
            self.addPolygonToMap(xys, useForZoom=False)
            
            # And the anchor point
            xy = line.getAnchor()
            xys = [xy]
            self.addPointsToMap(xys, edgeColor='darkgreen', color = 'none', 
                                    marker='s', size=8) 

    def showMap(self, plotName=None, title=None):
        '''
        Finalize survey map plot
        '''
        fow = self.getWrapper("map")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")

        if (plotName is None):
            plotName = self._getPlotName("map")+"."+fow.getFileExtension()

        fow.show(title=title, fileName=None if (self._state._mode != TO_FILE) else plotName)

        if not (fow.isOpen()):
            #print("    Map FOW has closed already")
            self.forgetWrapper(fow) 

    def makeSurveyMap(self, inDialog=None, plotName=None, title=None, 
                        warp=False, mapType="mpl", **kwargs):
        '''
        Initiate, make, finalize survey map plot
        '''
        self.openSurveyMap(inDialog=inDialog, warp=warp, mapType=mapType)
        self.showSurveyOnMap(**kwargs)
        self.showMap(plotName=plotName, title=title)
        
    def getMapBounds(self, **kwargs):
        '''
        Get displayed bounds of map.
        If no map displayed, generates 'SubsAnalysisException'
        '''
        fow = self.getWrapper("map")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")
        
        return fow.getMapBounds(**kwargs)

    #####################################################################
    #
    # Histogram plots
    #
    #####################################################################
    
    def openHistogramPlot(self, inDialog=None):
        '''
        Initiate histogram plot
        '''
        # Will add itself to our watch list
        HWP.HistoWrapper("histo", self, inDialog=inDialog)
        
    def fillHistogramPlot(self, year1, year2, srvy = None, includeUnstable=False, **kwargs):
        '''
        Fill histogram plot
        '''
        # Need open plot
        fow = self.getWrapper("histo")
        if (fow is None):
            raise SubsAnalysisException("No open histogram plot")
            
        # Default survey
        if (srvy is None):
            srvy = self._state._focusSurvey 
        lsrvy = srvy
        
        # Get diffs
        zKey=PM.DIFF_KEY
        df1 = self.pmdb.getSurveyDiffs(lsrvy, year1 = year1, year2 = year2, refShifts=self._state._refShifts)
                        
        # Remove unstable
        if (not includeUnstable): df1 = df1[~df1[PM.UNSTABLE_KEY]]
        
        # Apply units. Different for absolute NAP and subsidence
        unit = self._state._unitDiff
        scaleFactor, fStr = self._parseUnit(unit)
        df1.loc[:,PM.DIFF_KEY] *= scaleFactor
        
        # At least 4 cm
        fow.setMinXRange(0.04*scaleFactor)
                
        # Curve name
        ltitle = lsrvy + " " +str(year1)+"-"+str(year2)
        xLabel = "diff ["+self._state._unitDiff+"]"

        #Plot!
        fow.addPoints(df1, zKey=zKey, layer=ltitle, xLabel=xLabel, **kwargs)
        
    def showHistogramPlot(self, plotName=None, title=""):
        '''
        Finalize histogram plot
        '''
        fow = self.getWrapper("histo")
        if (fow is None):
            raise SubsAnalysisException("No open histogram plot")

        if (plotName is None):
            plotName = self._getPlotName("histo")+"."+fow.getFileExtension()

        fow.show(title=title, fileName=None if (self._state._mode != TO_FILE) else plotName)

        if not (fow.isOpen()):
            #print("    Histo FOW has closed already")
            self.forgetWrapper(fow)
        
    def makeHistogramPlot(self, year1, year2,
                           inDialog=None, title="", plotName=None, **kwargs):
        '''
        Initiate, fill, finalize histogram plot
        '''
        self.openHistogramPlot(inDialog=inDialog)
        self.fillHistogramPlot(year1, year2, **kwargs)
        self.showHistogramPlot(title=title, plotName=plotName)                    

    #####################################################################
    #
    # Crossplots
    #
    #####################################################################
    
    def openCrossplot(self, inDialog=None):
        '''
        Initiate crossplot
        '''
        # Will add itself to our watch list
        XWP.CrossplotWrapper("xplot", self, inDialog=inDialog)
        
    def fillCrossplot(self, year1, year2, year3, year4, srvy = None, srvy2 = None, 
                        includeUnstable=False, trend=None, **kwargs):
        '''
        Fill crossplot
        '''
        # Need open plot
        fow = self.getWrapper("xplot")
        if (fow is None):
            raise SubsAnalysisException("No open crossplot")
            
        # Default survey
        if (srvy is None):
            srvy = self._state._focusSurvey 
        if (srvy2 is None):
            srvy2 = srvy
        lsrvy = srvy
        
        # And years
        if (year3 is None):
            year3 = year1
        if (year4 is None):
            year4 = year2
        
        # Get diffs
        zKeyX = PM.DIFF_KEY
        df2 = self.pmdb.getSurveyDiffs(srvy2, year1 = year3, year2 = year4, refShifts = self._state._refShifts)
        df1 = self.pmdb.getSurveyDiffs(lsrvy, year1 = year1, year2 = year2, refShifts = self._state._refShifts)
        
        # Remove unstable
        if (not includeUnstable): 
            df1 = df1[~df1[PM.UNSTABLE_KEY]]
            df2 = df2[~df2[PM.UNSTABLE_KEY]]
            
        # Merge the two datasets on PEILMERK
        df = pd.merge(df1, df2, on = PM.PEILMERK_KEY, how = "inner", suffixes=('', '_2'))
        zKeyY = PM.DIFF_KEY +"_2"
        
        # Apply units. Different for absolute NAP and subsidence
        unit = self._state._unitDiff
        scaleFactor, fStr = self._parseUnit(unit)
        df.loc[:,zKeyX] *= scaleFactor
        df.loc[:,zKeyY] *= scaleFactor
        
        # At least 4 cm
        fow.setMinXRange(0.04*scaleFactor)
        fow.setMinYRange(0.04*scaleFactor)
                
        # Curve name
        ltitle = lsrvy 
        if (srvy2 != lsrvy):
            ltitle += " vs. " + srvy2
        xLabel = "diff ["+self._state._unitDiff+"]"+ " " +str(year1)+"-"+str(year2)
        yLabel = "diff ["+self._state._unitDiff+"]"+ " " +str(year3)+"-"+str(year4)

        #Plot!
        fow.addPoints(df, zKeyX=zKeyX, zKeyY=zKeyY, layer=ltitle, xLabel=xLabel, yLabel=yLabel, 
                      labelKey=PM.PEILMERK_KEY, **kwargs)
                      
        # Add trend
        if (trend is not None):
            scaled_trend = [(xy[0]*scaleFactor,xy[1]*scaleFactor) for xy in trend]
            fow.addLine(scaled_trend)
        
    def showCrossplot(self, plotName=None, title=""):
        '''
        Finalize crossplot
        '''
        fow = self.getWrapper("xplot")
        if (fow is None):
            raise SubsAnalysisException("No open crossplot")

        if (plotName is None):
            plotName = self._getPlotName("xplot")+"."+fow.getFileExtension()

        fow.show(title=title, fileName=None if (self._state._mode != TO_FILE) else plotName)

        if not (fow.isOpen()):
            #print("    Crossplot FOW has closed already")
            self.forgetWrapper(fow)
        
    def makeCrossplot(self, year1, year2, year3, year4,
                           inDialog=None, title="", plotName=None, 
                           trend=None,**kwargs):
        '''
        Initiate, fill, finalize crossplot
        '''
        self.openCrossplot(inDialog=inDialog)
        self.fillCrossplot(year1, year2, year3, year4, trend=trend, **kwargs)
        self.showCrossplot(title=title, plotName=plotName)                    

    #####################################################################
    #
    # intersections
    #
    #####################################################################
    
    def intersectionLine(self, spm="", xy=(0,0), angleDeg=0):
        '''
        Initiate PlotLine that can be used for intersection, and to plot on maps
        '''
        # Default origin
        if (not (spm is None)) and (spm !=""):
            xy = self.pmdb.getPeilmerkXY(spm)
            
        return PL.PlotLine(xy, angleDeg)
    
    def openIntersection(self, spm="", line=None, xy=(0,0), angleDeg=0, inDialog=None):
        '''
        Initiate intersection
        '''
                
        # Default origin
        if (not (spm is None)) and (spm !=""):
            xy = self.pmdb.getPeilmerkXY(spm)
            
        # Will add itself to our watch list
        IWP.IntersectionWrapper("intersect", self, line=line, xy=xy, angleDeg=angleDeg,
                                inDialog=inDialog)
        
    def fillIntersection(self, year1, year2, srvy=None, 
                            includeUnstable=False, **kwargs):
        '''
        Fill Intersection
        '''
        # Need open plot
        fow = self.getWrapper("intersect")
        if (fow is None):
            raise SubsAnalysisException("No open Intersection")
            
        # Default survey
        if (srvy is None):
            srvy = self._state._focusSurvey 
        lsrvy = srvy
        assert((not (lsrvy is None)) and (lsrvy != ""))
        
        # Get diffs
        zKey = PM.DIFF_KEY
        df1 = self.pmdb.getSurveyDiffs(lsrvy, year1 = year1, year2 = year2, refShifts = self._state._refShifts)
        
        # Remove unstable
        if (not includeUnstable): df1 = df1[~df1[PM.UNSTABLE_KEY]]
        
        # Apply units. Different for absolute NAP and subsidence
        unit = self._state._unitDiff
        scaleFactor, fStr = self._parseUnit(unit)
        df1.loc[:,zKey] *= scaleFactor
        
        # At least 4 cm
        fow.setMinYRange(0.04*scaleFactor)
                
        # Curve name
        ltitle = lsrvy + " " +str(year1)+"-"+str(year2)
        yLabel = "diff ["+self._state._unitDiff+"]"
        xLabel = "["+self._state._unitHgt+"]"
        assert(self._state._unitHgt=="m")

        #Plot!
        fow.addPoints(df1, zKey=zKey, labelKey=PM.PEILMERK_KEY, layer=ltitle, 
                        xLabel=xLabel, yLabel=yLabel, **kwargs)
        
        return fow
        
    def showIntersection(self, plotName=None, title=""):
        '''
        Finalize Intersection
        '''
        fow = self.getWrapper("intersect")
        if (fow is None):
            raise SubsAnalysisException("No open Intersection")

        if (plotName is None):
            plotName = self._getPlotName("intersect")+"."+fow.getFileExtension()

        fow.show(title=title, fileName=None if (self._state._mode != TO_FILE) else plotName)

        if not (fow.isOpen()):
            #print("    Intersection FOW has closed already")
            self.forgetWrapper(fow)
        
    def makeIntersection(self, year1, year2, inDialog=None, spm="", 
                         line=None, xy=(0,0), angleDeg=0,
                         title="", plotName=None, moreLater=False, **kwargs):
        '''
        Initiate, fill, finalize Intersection
        '''
        if (self.getWrapper("intersect") is None):
            self.openIntersection(spm=spm, line=line, xy=xy, angleDeg=angleDeg, inDialog=inDialog)
        w = self.fillIntersection(year1, year2, **kwargs)
        if (not moreLater):
            self.showIntersection(title=title, plotName=plotName)  
        else:
            return w

    #####################################################################
    #
    # Peilmerk plots
    #
    #####################################################################

    def openPeilmerkPlot(self, inDialog=None, startDate=None, endDate=None):
        '''
        Initiate peilmerk plot
        '''
        # Open window. It will add itself to our watch list
        PPW.PmPlotWrapper("pmplot", self, inDialog=inDialog)
        fow = self.getWrapper("pmplot")
        
        # Default start date
        if (startDate is None):
            startDate = PM.T0

        fow.setTimePeriod(startDate, endDate)
        
    def getDisplayedPeilmerken(self):
        '''
        Get list of displayed points in peilmerkplot.
        If no peilmerkplot displayed, generates 'SubsAnalysisException'
        '''
        fow = self.getWrapper("pmplot")
        if (fow is None):
            raise SubsAnalysisException("No open peilmerk plot")
        
        return fow.getDisplayedSeries(PM.PEILMERK_KEY)
    

    def _fillPeilmerkPlotDF(self, df, skeys=""):
        '''
        Add data to peilmerk plot (internal).
        
        If column PM.HGT_KEY holds the z data, heights are assumed NAP and plotted in m.
        If column PM.DIFF_KEY holds the data, heights are assumed to be differences, 
        and plotted in cm.
        '''
        fow = self.getWrapper("pmplot")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")

        # Apply units. Different for absolute NAP and subsidence
        if (PM.HGT_KEY in df):
            zKey = PM.HGT_KEY
            unit = self._state._unitHgt
        else:
            assert(PM.DIFF_KEY in df)
            zKey = PM.DIFF_KEY
            unit = self._state._unitDiff
        scaleFactor, fStr = self._parseUnit(unit)

        df.loc[:,zKey] *= scaleFactor

        fow.setYLabel(unit)
        fow.setMinYRange(0.04*scaleFactor)
        fow.addPoints(df, skeys=skeys)
        
        return fow

    def fillPeilmerkPlot(self, spm, skeys="", **kwargs):
        '''
        Add data to peilmerk plot
        '''
        df = self.pmdb.getHeightsForPMAsFrame(spm, **kwargs, refShifts = self._state._refShifts)

        # Pass alignment argument to mark they are NAP heights
        self._fillPeilmerkPlotDF(df, skeys=skeys)

    def showPeilmerkPlot(self, plotName=None, title=""):
        '''
        Finalize peilmerk plotName
        '''
        fow = self.getWrapper("pmplot")
        if (fow is None):
            raise SubsAnalysisException("No open map plot")

        if (plotName is None):
            plotName = self._getPlotName("map")+"."+fow.getFileExtension()

        fow.show(title=title, fileName=None if (self._state._mode != TO_FILE) else plotName)

        if not (fow.isOpen()):
            #print("    PMPlot FOW has closed already")
            self.forgetWrapper(fow)

    def makeHeightPlotForPM(self, spm, startDate=None, endDate=None,
                            inDialog=None, title="", plotName=None, 
                            **kwargs):
        '''
        Initiate, show, finalize peimlerkplot (NAP or diff=subsidence).

        Possible values for 'alignment':
            PM.NO_ALIGNMENT:    NAP (= no alignment takes place)
            ...

        Location specified as peilmerk spm

        inDialog is either None, or points to an object with two methods:
            getWidget() - frame in which the plot is shown
            closeDialog() - called if the dialog is to be closed
        '''
        if (title==""):
            title=spm
        self.openPeilmerkPlot(inDialog=inDialog, startDate=startDate, endDate=endDate)
        self.fillPeilmerkPlot(spm, **kwargs)
        self.showPeilmerkPlot(title=title, plotName=plotName)

    def makeAlignedPlotsAround(self, focusList, **kwargs):
        '''
        run makaAlingedPlotAround for a series of points
        '''
        for p, q in focusList.items():
            xy=""
            spm=""
            title=""
            if q is None:
                spm = p
            elif (isinstance(q,str)):
                spm = q
                title = p
            else:
                xy = q
                title = p
                
            self.makeAlignedPlotAround(spm=spm, xy=xy, title=title, **kwargs)

    def makeAlignedPlotAround(self, spm="", xy="", startDate = None, endDate = None,
                            afterDate = None, refDate = None, alignment=None,
                            inDialog = None, title = "", moreLater=False, **kwargs):
        '''
        Initiate, show, finalize peimlerkplot (differences a.k.a. subsidence) around
        a certain location (specified by peilmerk 'spm' or cy tuple 'xy'.

        Possible values for 'alignment':
        ...
        startDate: srart plot x axis on this date
        endDate: end plot x axis on this date
        afterDate: ignore peilmerken with no data after this point
        refDate: align plots on this date (i.e. assume subsidence is zero on this date)
            ...
        '''
        # Defaults
        if (spm !=""):
            if (title==""):
                title="Around "+spm
            xy = self.pmdb.getPeilmerkXY(spm)
        elif (title==""):
            title="Around ({:.1f}, {:.1f})".format(xy[0], xy[1])
        if (startDate is None) and (self._state._defStartYear is not None):
            startDate = datetime.date(self._state._defStartYear,1,1)
        if (afterDate is None) and (self._state._defAfterYear is not None):
            afterDate = datetime.date(self._state._defAfterYear,1,1)
        if (refDate is None) and (self._state._defRefYear is not None):
            refDate = datetime.date(self._state._defRefYear,1,1)

        # Get list of closest peilmerken
        pmDf = self.pmdb.getClosestPeilmerkenAsFrame(xy, maxNumPMs=5, afterDate=afterDate, **kwargs)
        df = self.pmdb.getHeightsForPMFrameAsFrame(pmDf, afterDate=afterDate, refDate=refDate,
                                                alignment=alignment, refShifts = self._state._refShifts)
                
        self.openPeilmerkPlot(inDialog = inDialog, startDate = startDate, endDate = endDate)
        w = self._fillPeilmerkPlotDF(df, skeys=[PM.PEILMERK_KEY, PM.SURVEY_KEY])
        
        if (not moreLater):
            self.showPeilmerkPlot(title = title)
        else:
            return w
            
    def sa.show(self):
        '''
        Show any open plots
        '''
        
        for fow in self.wrappers():
            if (fow.getName()=="pmplot"):
                self.showPeilmerkPlot(title = title)
            else:
                assert(0)