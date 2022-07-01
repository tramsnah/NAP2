'''
Module provides main subsidence measurement browser GUI window. Usage:
    ws = MainWindow()
    ws.mainloop()
'''
import tkinter as tk
from tkinter import messagebox
import pickle
import numpy as np
from shapely.geometry import Point

from . import peilmerkdatabase as PM
from . import subsanalysis as SA
from . import utildialogs as UD
from . import embedplotindialog as ED
from . import messagelogger as ML
from . import mptimer as MPT

###############################################
        
class PlotDialog(ED.PlotWrapBase):
    '''
    Class for auxiliary object to manage communication betweem
    plot window and master window.
    '''
    def __init__(self, wmaster, title = "Plot Window"):
        ED.PlotWrapBase.__init__(self)
        self._master = wmaster
        
        self._win = tk.Toplevel(self._master)
        self._win.title(title)
        
        # Frame to organize spacing
        self._frame = tk.Frame(self._win, bd = 1)
        self._frame.pack(expand = True, side = tk.TOP, fill = tk.BOTH)

    def getWindow(self):
        '''
        Return the containing tk window
        '''
        return self._win
        
    def getWidget(self):
        '''
        Return the tk frame that is to contain the plot
        '''
        return self._frame
    
    def closePlot(self):
        '''
        Close the plot
        '''
        #print("    PlotDialog.closePlot", self._win)
        if not (self._win is None):
            win = self._win
            self._win = None
            win.destroy()

        self._frame = None
        
    def wait(self):
        '''
        Modal dialog, 
        only one window in the task bar
        '''
        self._win.transient(self._master)    
        self._win.grab_set()
                
        # Set focus so we can start typing...
        self._frame.focus_set()
        
        # Wait until we die
        self._win.wait_window()
        
    def isStandAloneWindow(self):
        '''
        True (default) since this is a wrapper for a standalone window
        '''
        return True

class PlotWrapBaseMap(ED.PlotWrapBase):
    '''
    Class for auxiliary object to manage communication betweem
    map widget (embedded in main window) and master window.
    '''
    def __init__(self, master):
        ED.PlotWrapBase.__init__(self)
        self._master=master
        
        # Get notifications on closing
        w = master.getBaseMapWidget()
        w.bind("<Destroy>", self.onDestroy)
        w.bind("<Unmap>", self.onUnmap)
        
    def getWindow(self):
        '''
        Return the containing tk window
        '''
        return self._master.getWindow()
        
    def getWidget(self):
        '''
        Return the tk frame to contain the plot
        '''
        return self._master.getBaseMapWidget()
    
    def closePlot(self):
        '''
        Close the plot widget
        '''
        #print("    PlotWrapBaseMap.closePlot")
        self._master.closeBaseMap()
        
    #def closePlotDown(self):
    #    print("    PlotWrapBaseMap.closePlotDown")
        
    def wait(self):
        '''
        Empty (as this wrapper is for a non-model widget)
        '''
        pass
            
    def isStandAloneWindow(self):
        '''
        False (as this wrapper is for an embedded plot)
        '''
        return False
        
    def buttonPress(self, event, mode):
        '''
        Pass buttonpress on to master (for right click menu)
        '''
        return self._master.buttonPress(event, mode)
        
    def onDestroy(self, event):
        '''
        Callback for QC only
        '''
        print("**** PlotWrapBaseMap.onDestroy")
        pass
    
    def onUnmap(self, event):
        '''
        Callback for QC only
        '''
        print("**** PlotWrapBaseMap.onUnmap")
        pass
        
class GuiState:
    '''
    Empty class to function as state container
    '''
    pass

class SubsBrowser(tk.Menu):
    '''
    Main tk GUI object for subsidence browser
    '''
    def __init__(self, wmaster):
        tk.Menu.__init__(self, wmaster)
        
        self._master = wmaster

        self._state = GuiState()

        fileMnu = tk.Menu(self, tearoff = False)
        fileMnu.add_command(label = "Load", underline = 1, command = self.loadState)
        fileMnu.add_command(label = "Save", underline = 1, command = self.saveState)
        fileMnu.add_command(label = "Exit", underline = 1, command = self.exit)
        self.add_cascade(label = "File", underline = 0, menu = fileMnu)
        
        editMnu = tk.Menu(self, tearoff = 0)  
        editMnu.add_command(label = "All", command = self.zoomAll) 
        editMnu.add_command(label = "Survey", command = self.zoomSurvey) 
        editMnu.add_command(label = "Time interval", command = self.zoomYears)           
        editMnu.add_command(label = "Peilmerk", command = self.zoomPM)  
        editMnu.add_command(label = "Well", command = self.zoomWell)  
        editMnu.add_command(label = "(x, y)", command = self.zoomXY)  
        self.add_cascade(label = "Focus", menu = editMnu) 

        plotMnu = tk.Menu(self, tearoff = 0)
        plotMnu.add_command(label = "Map", command = self.updateMap)
        plotMnu.add_command(label = "Histogram", command = self.showHistogram)
        plotMnu.add_command(label = "Crossplot", command = self.showCrossplot)
        self.add_cascade(label = 'Plot', menu = plotMnu)

        helpMnu = tk.Menu(self, tearoff = 0)  
        helpMnu.add_command(label = "Help", command = self.help) 
        helpMnu.add_command(label = "About", command = self.about)  
        self.add_cascade(label = "Help", menu = helpMnu) 
        
        # Make sure the close window button at top right goes the same path
        self._master.protocol("WM_DELETE_WINDOW", self.exit)

        # Load the DB
        self._sa = SA.SubsAnalysis()
        self._sa.setMode(SA.INTERACTIVE)
        
        # Admin for matplot
        self._fig = None
        self._canvas = None
        self._frame = None

        # Right click menu
        self._popupMenu = None
        self._popupX = None
        self._popupY = None
        self._popupXscale = None
        self._popupYscale = None
        
        # Status bar        
        self._label = tk.Label(self._master, anchor = tk.W, justify = tk.LEFT, 
                                font = "Helvetica 9 italic")
        self._label.pack(side = tk.BOTTOM, ipadx = 10, ipady = 10, anchor = tk.W, 
                                expand = False)

        # No timer yet
        self._timer = None
        
        # Init remaining fields
        self._state._focusSrvy = None
        self._state._y1=None
        self._state._y2=None
        self._focusXY = None
        self._focusPM = None
        self._focusWell = None 
        self._hlPml = None
        self._hlXY = None
        
        ## For tracking resize
        #self._frameWidth, self._frameHeight = 0, 0

        # More defaults
        self._ints_x = None
        self._ints_y = None
        self._ints_angle = 0.0
        
        # Load state. If it fails, set some default
        try:
            self.loadState()
        except (FileNotFoundError, TypeError, UnicodeDecodeError, 
                EOFError, AssertionError):
            print("Failed to load state")
            print("Defaulting initial state")
            self._sa.importDataBase()
            self._state._focusSrvy = "LZG_2021"
            self._state._y1 = 2012
            self._state._y2 = 2021

            self._master.geometry('700x500')

        # Make sure message area is up-to-date
        self.updateLabel()

    def updateLabel(self):
        '''
        Update message area at bottom of window
        '''
        text = "Number of surveys: {:d}\nNumber of peilmerken: {:d}".format(
                            self._sa.getNumSurveys(), 
                            self._sa.getNumPeilmerken())
        text += "\nFocus on {:s} from {:d} to {:d}".format(
                            self._state._focusSrvy, self._state._y1, self._state._y2)
        self._label.configure(text = text)
        
    def exit(self):
        '''
        Exiting the master window
        '''
        #print("    Exiting...")
        if not (self._timer is None):
            self._timer.stop()
            self._timer = None

        self.quit()

    def saveState(self):
        '''
        Saving the master window state
        '''
        #print("    Saving...")
        fileName = "subsbrowser.pkl"
        version="1.0"
        with open(fileName,"wb") as F:
            pickle.dump(version, F)

            # Our state
            pickle.dump(self._state, F)

            # Showing map?
            showMap = not (self._frame is None)
            pickle.dump(showMap, F)

            # Window size?
            wininfo = (self._master.winfo_x(),
                       self._master.winfo_y(),
                       self._master.winfo_width(),
                       self._master.winfo_height())
            pickle.dump(wininfo, F) 

            # Subsidence analysis
            self._sa.dumpP(F)

            # Dialog defaults
            UD.DumpP(F)

        ML.LogMessage("State file {:s} saved".format(fileName))

    def loadState(self):
        '''
        Saving the master window state
        '''
        #print("    Saving...")
        fileName = "subsbrowser.pkl" 
        showMap = False
        wininfo = None

        with open(fileName,"rb") as F:
            version = pickle.load(F)
            assert(version=="1.0")

            # Our state
            self._state = pickle.load(F)

            # Display map?
            showMap = pickle.load(F)

            # Window size?
            wininfo = pickle.load(F)

            # Subsidence analysis
            self._sa.loadP(F)

            # Dialog defaults
            UD.LoadP(F)

        if (showMap):
            self.updateMap()

        if not (wininfo is None):
            self._master.geometry('{:d}x{:d}'.format(wininfo[2], wininfo[3]))

        ML.LogMessage("State file {:s} loaded".format(fileName))

    def about(self):
        '''
        Display Help/About info
        '''
        messagebox.showinfo('About', 'Peilmerk DB GUI')  
        
    def help(self):
        '''
        Display Help/Help info
        '''
        messagebox.showinfo('Help', 'Peilmerk DB GUI') 
        
    def _getNiceScale(self, vmin, vmax):
        '''
        Get prettier vertical plot scale, given data interval
        '''
        delta = abs(vmax-vmin)
        ld = int(np.log10(delta))-1
        bs = pow(10, ld)
        numint = int(delta/bs) 
        if (numint>=10):
            bs *= 2
        numint = int(delta/bs) 
        if (numint>=10):
            bs *= 2.5
        omin = np.floor(min(vmin,vmax)/bs)*bs
        omax = np.ceil(max(vmin,vmax)/bs)*bs
        
        return omin, omax
    
    def showBasicSurveyMap(self):
        '''
        Show the selected survey map
        '''
        print('SubsBrowser.showBasicSurveyMap')
        # Create frame
        self._frame = tk.Frame(master = self._master, bd = 1, 
                            highlightbackground = "black", 
                            highlightthickness = 1) 
        self._frame.configure(bg='red')  
        self._frame.pack(side = tk.TOP, fill = tk.BOTH, expand = True) 
        
        ## Resize callback
        #self._resize_id = self._frame.bind("<Configure>", self.resize) 
        
        # Kick off plot
        self._sa.openSurveyMap(inDialog = PlotWrapBaseMap(self), warp=False)
        
        # Fill main survey
        self._sa.showSurveyOnMap(year=self._state._y1, year2=self._state._y2, srvy=self._state._focusSrvy, color="blue")
        
        # Highlight multi-point selection, if defined
        if not (self._hlPml is None):
            xys = []
            for spm in self._hlPml:
                try: # There may be pseudo-pm's
                    (x, y) = self._sa.getPeilmerkXY(spm)
                    xys.append(Point(x,y))
                except KeyError:
                    pass
            self._sa.addPointsToMap(xys, edgeColor='black', color = 'none', 
                                    marker='s', size=8) 

        # Highlight selected location, if defined
        if not (self._hlXY is None):
            xys = [Point(self._hlXY[0], self._hlXY[1])]
            self._sa.addPointsToMap(xys, edgeColor='red', color = 'none', 
                                    marker='s', size=8)   
            
        # Get displayed area (after selections shown, which may influence it)
        bounds=self._sa.getMapBounds(expand=1)
        xys=self._sa.getPeilmerkenWithinBounds(bounds)
        self._sa.addPointsToMap(xys, color = 'black', marker='s', 
                                size=1, useForZoom=False, zorder=0.5)

        # Highlight intersection line if defined
        if not (self._ints_x is None):
            # Determine line end points
            angleRad = self._ints_angle*np.pi/180
            cs = np.cos(angleRad)
            ss = np.sin(angleRad)
            if (abs(cs)>abs(ss)):
                lmin = (bounds[0]-self._ints_x)/cs
                lmax = (bounds[2]-self._ints_x)/cs
            else:
                lmin = (bounds[1]-self._ints_y)/ss
                lmax = (bounds[3]-self._ints_y)/ss 
            if (lmin>lmax):
                lmin,lmax = lmax, lmin
                
            # Anchor point must be on the line
            lmin=min(0,lmin)
            lmax=max(0,lmax)   
            xys=[]
            xys.append(Point(self._ints_x+lmin*cs, self._ints_y+lmin*ss))
            xys.append(Point(self._ints_x+lmax*cs, self._ints_y+lmax*ss))
            
            # Display the line (don't change map bounds)
            self._sa.addPolygonToMap(xys, useForZoom=False)
            
            # And the anchor point
            xys = [Point(self._ints_x, self._ints_y)]
            self._sa.addPointsToMap(xys, edgeColor='darkgreen', color = 'none', 
                                    marker='s', size=8)  
        
        # Create the right click menu
        #self._popupMenu = tk.Menu(self._canvas.get_tk_widget(), tearoff = 0)
        self._popupMenu = tk.Menu(self._frame, tearoff = 0)
        self._popupMenu.add_command(label = "Zoom focus in", 
                                    command = self.focusInCursor)
        self._popupMenu.add_command(label = "Zoom focus out", 
                                    command = self.focusOutCursor)
        self._popupMenu.add_separator()
        self._popupMenu.add_command(label = "Graph Around", 
                                    command = self.showAround)
        self._popupMenu.add_command(label = "Graph Peilmerk", 
                                    command = self.showPM)
        self._popupMenu.add_command(label = "Intersection", 
                                    command = self.showIntersection)
        
        # Show it        
        self._sa.showMap()

    # def resize(self, event):
        # if(event.widget == self._frame and
           # (self._frameWidth != event.width or 
            # self._frameHeight != event.height)):
            # print(f'SubsBrowser.resize: {event.widget=}: {event.height=}, {event.width=}\n')

            # # Typically multiple resize events. So wait a sec before resizing the map, since that 
            # # takes a bit of time
            # if (self._frameWidth != 7890877654):
                # if not (self._timer is None):
                    # self._timer.stop()
                # self._timer = MPT.MPTimer(self._frame, 500, 
                        # lambda: SubsBrowser._resize_timed(self, event))

            # self._frameWidth, self._frameHeight = event.width, event.height

    # def _resize_timed(self, event):
        # '''
        # Called (some time) after a resize event
        # '''
        # print('SubsBrowser._resize_timed')
        # self._timer = None

        # self.updateMap()

    def getBaseMapWidget(self):
        '''
        Return tk widget (frame) that is to contain map
        '''
        return self._frame    
    
    def getWindow(self):
        '''
        Return tk window of gui
        '''
        return self._master 
        
    def closeBaseMap(self):
        '''
        Close the map
        '''
        if (self._frame is None):
            #print("        SubsBrowser.closeBaseMap (no action)")        
            return
        
        #print("        SubsBrowser.closeBaseMap")
        self._frame.destroy()
        self._frame = None
        
    def updateMap(self):
        '''
        Force map refresh
        '''
        self.closeBaseMap()
        self.updateLabel()
        self.showBasicSurveyMap()
        
    def buttonPress(self, event, toolMode):
        '''
        Callback for button press on map.
        Used for e.g. right-click menu.
        '''
        if (toolMode ==  "" and not (event.inaxes) is None):
            try:
                # Menu requires absolute pointer positions, and event.x, event.y are relative.
                #x = event.x
                #y = event.y
                # Map canvas x, y to data x, y
                #print(event.inaxes.transData.inverted().transform((event.x, event.y)))
                # Map data x, y to canvas x, y
                #print(event.inaxes.transData.transform((event.xdata, event.ydata)))
                xd1, yd1 = event.inaxes.transData.inverted().transform((event.x+1, event.y+1))
                self._popupX = event.xdata
                self._popupY = event.ydata
                self._popupXscale = (event.xdata-xd1)
                self._popupYscale = (event.ydata-yd1)
                x = self._master.winfo_pointerx()
                y = self._master.winfo_pointery()
                #print("    RB click at ", self._popupX, self._popupY)
                self._popupMenu.tk_popup(x, y, 0)
            finally:
                self._popupMenu.grab_release()
    
    def clearHighlights(self):
        '''
        Clear highlights on map (e.g. selected point)
        '''
        self._hlPml = None
        self._hlXY = None
        self._ints_x = None
        self._ints_y = None
        
    def setHighlightXY(self, xy):
        '''
        Highlight location xy on map.
        '''
        self._hlXY = xy

    def setHighlightPMs(self, pml):
        '''
        Highlight list of pms 'pml' on map.
        '''
        self._hlPml = pml
    
    def showHistogram(self):
        '''
        Open histogram window(using current survey & time iterval)
        '''
        if (self._state._focusSrvy is None or self._state._focusSrvy == ""): return

        window = PlotDialog(self._master)
        self._sa.makeHistogramPlot(self._state._y1, self._state._y2, srvy = self._state._focusSrvy, inDialog = window)
        window.wait()
        window = None
        
    def showCrossplot(self):
        '''
        Open crossplot window(using current survey & time iterval for x). A time interval for
        y is queried.
        '''
        if (self._state._focusSrvy is None or self._state._focusSrvy == ""): return

        yrs=list(str(y) for y in self._sa.getSurveyYears(self._state._focusSrvy))
        yrs.sort()
        y3=0 # TODO
        y4=0 # TODO
        y3,y4=UD.ChoiceTwoCB.Ask(self._master, "Interval for y-axis", yrs, 
                                default1=str(y3), default2=str(y4), dlgId="xplot2year")
        y3=int(y3)
        y4=int(y4)
        window = PlotDialog(self._master)
        self._sa.makeCrossplot(self._state._y1, self._state._y2, y3, y4, 
                        srvy = self._state._focusSrvy, inDialog = window)
        window.wait()
        window = None
        
    def showAround(self):
        '''
        Open peilmerk plot to show data around a specific location.
        The location should have been stored before (e.g. in right-click
        menu popup)
        '''
        if (self._popupX is None): return

        # Where did we click?
        xy = (self._popupX, self._popupY)
        
        # Generate plot
        window = PlotDialog(self._master)
        self._sa.makeAlignedPlotAround(xy=xy, inDialog = window)
        
        # Show the selected points, as well as the clicked location, as highlights on the map
        pml = self._sa.getDisplayedPeilmerken()
        self.setHighlightPMs(pml)
        self.setHighlightXY(xy)
        self.updateMap()
        
        # Then wait until it is closed
        window.wait()
        window = None
        
        # Clear the highlights
        self.clearHighlights()
        self.updateMap()
        
    def showIntersection(self):
        '''
        Open intersection window(using current survey & time iterval).
        The anchor location should have been stored before (e.g. in right-click
        menu popup).
        The user is queried for the angle of the intersection.
        '''
        if (self._popupX is None): return

        # Get clicked location
        self._ints_x = self._popupX
        self._ints_y = self._popupY 
        
        # Get angle
        self._ints_angle = UD.ChoiceDBL.Ask(self._master, "Intersection Angle", 
                            default=self._ints_angle, 
                            dlgId="IntersectionAngle", prompt="Enter ange [degrees]")
        
        # Title
        title=self._state._focusSrvy+" "+str(self._state._y1)+"-"+str(self._state._y2)
        
        # Create the dialog to embed in
        window = PlotDialog(self._master)
        
        # Show the intersection
        bounds=self._sa.getMapBounds()
        self._sa.makeIntersection(self._state._y1, self._state._y2, 
                                  xy=(self._ints_x,self._ints_y), 
                                  angleDeg=self._ints_angle, 
                                  title=title, srvy = self._state._focusSrvy, 
                                  bounds=bounds, inDialog = window)
        self.updateMap()
        window.wait()
        window = None
        
        # Clear the highlights
        self.clearHighlights()
        self.updateMap()

    def showPM(self):
        '''
        Open peilmerk plot to show data at a specific peilmerk.
        The closest peilmerk to the location is shown.
        The location should have been stored before (e.g. in right-click
        menu popup). 
        '''
        if (self._popupX is None): return

        # Get closest points to current location
        x = self._popupX
        y = self._popupY
        df = self._sa.getClosestPeilmerkenAsFrame((x, y), maxDistance=2000, minYears = 2, 
                            afterDate = None, includeUnstable = False)
        spm = df.iloc[0][PM.PEILMERK_KEY]
        
        # Show the selected point as highlights on the map
        self.setHighlightPMs([spm])
        self.updateMap()
        
        # Open the window, and show the plot, then wait until it is closed
        window = PlotDialog(self._master)
        self._sa.makeHeightPlotForPM(spm, alignment = PM.ALIGN_MEDIAN, inDialog = window)
        window.wait()
        window = None
        
        # Clear the highlights
        self.clearHighlights()
        self.updateMap()
        
    def focusInCursor(self):
        '''
        Focus map in on specific location.
        The location should have been stored before (e.g. in right-click
        menu popup). 
        '''
        self._focusXY = (self._popupX, self._popupY)
        # Decrease area
        assert(0) # TODO

    def focusOutCursor(self):
        '''
        Focus map out on specific location.
        The location should have been stored before (e.g. in right-click
        menu popup). 
        '''
        self._focusXY = (self._popupX, self._popupY)
        # Increase area
        assert(0) # TODO
         
    def clearFocus(self):
        '''
        Clear focus, revert to full map
        '''
        self._state._focusSrvy = None
        self._focusXY = None
        self._focusPM = None
        self._focusWell = None

    def focusSurvey(self, cSrvy):
        '''
        Focus map on survey
        '''
        self._state._focusSrvy = cSrvy
            
    def updateYears(self, y1, y2):
        '''
        Set time interval for map
        '''
        self._state._y1 = y1
        self._state._y2 = y2
        self.updateLabel()

    def focusWell(self, cWell):
        '''
        Focus map on well
        '''
        self._focusWell = cWell
        self._focusXY = self._sa.getWellXY(self._focusWell)
 
    def focusPM(self, spm):
        '''
        Focus map on peilmerk
        '''
        self._focusPM = spm
        self._focusXY = self._sa.getSpmXY(self._focusPM)
        
    def zoomAll(self):
        '''
        Reset focus to view all
        '''
        self.clearFocus()
        self.updateMap()
        
    def zoomWell(self):
        '''
        Focus map on user-selected well
        '''
        wList = self._sa.getWellList()
        cWell = self.getUserSelection("Choose well", wList)
        self.focusWell(cWell)
        self.updateMap()

    def zoomSurvey(self):
        '''
        Focus map on user-selected survey
        '''
        sList = self._sa.getSurveyList()
        sList.sort()
        cSrvy = self.getUserSelection("Choose survey", sList, default = self._state._focusSrvy)
        #print("    Focusing on ", cSrvy)
        if (cSrvy != self._state._focusSrvy):
            yrs=list(str(y) for y in self._sa.getSurveyYears(cSrvy))
            yrs.sort()
            self._state._y1 = max(1970, int(yrs[0]))
            self._state._y2 = int(yrs[-1])
        self.focusSurvey(cSrvy)

        self.updateMap()

    def zoomYears(self):
        '''
        Let user choose time interval for map
        '''
        yrs=list(str(y) for y in self._sa.getSurveyYears(self._state._focusSrvy))
        yrs.sort()
        y1,y2=UD.ChoiceTwoCB.Ask(self._master, "Interval", yrs, 
                                default1=str(self._state._y1), default2=str(self._state._y2), 
                                dlgId="focus2year")
        y1 =int(y1)  
        y2 =int(y2)  
        self.updateYears(y1, y2)
        
    def zoomPM(self):
        '''
        Focus map on user-selected peilmerk
        '''
        cPm = self.getUserSelection("Enter Peilmerk", None)
        self.focusPM(cPm)
        self.updateMap()
 
    def zoomXY(self):
        '''
        Focus map on user-selected (x,y)
        '''
        cXy = self.getUserSelectionXY("Enter location XY (RD)")
        self._focusXY(cXy)
        self.updateMap()
        
    def getUserSelection(self, title, pList, default = ""):
        '''
        Open dialog to ask use for selection from list
        '''
        oStr = UD.ChoiceSL.Ask(self._master, title, pList, default=default)
        return oStr 

    def getUserSelectionXY(self, title, default = None):
        '''
        Open dialog to ask use for X,Y pair
        '''
        oXY = UD.ChoiceXY.Ask(self._root, title, default=default, dlgId="XY")
        return oXY   

class MainWindow(tk.Tk):
    '''
    Main tk window for subsidence browser.

    Actual work is done by SubsBrowser.
    '''
    def __init__(self):
        tk.Tk.__init__(self)
        menubar = SubsBrowser(self)
        self.config(menu = menubar)
        self.title('Peilmerk Database')
        
if __name__ ==  "__main__":
    wsMain = MainWindow()
    wsMain.mainloop()
