'''
Class to to create overview maps and animations
of peilmerk (leveling) measurements
'''
from scipy.interpolate import griddata
import numpy as np
import datetime
import pickle
import csv
import progressbar as pb

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from matplotlib.ticker import MaxNLocator
from matplotlib.animation import FuncAnimation
from matplotlib.animation import FFMpegWriter

import pandas as pd

from . import peilmerkdatabase as PM
from . import interpolatefunctions as IP

T_ZERO=PM.T0
MAP_TTOL_MAP=100 # days
MAP_TTOL_PEILMERK=100 # days

class SubsMapper:
    '''
    Class to to create overview maps and animations
    of peilmerk (leveling) measurements
    '''
    def __init__(self, pmdb=None, fileName=None):
        self._pmdb=pmdb
        self._pmdbPath=fileName
        self._grid = None
        self._nlx=[]
        self._nly=[]
        self._cdict=None
        self._nlPath=""
        self._animPath=""

        if (pmdb is None) and (fileName is not None):
            self.loadDataBase(fileName)
    
    def setConfig(self, configMap):
        '''
        Provide config info. Map content:
        "animPath" - location of FFMPeg.exe
        "polygonFile" - location ovf csv file containing a contour to add (e.g. Netherlands outline)
        '''
        ## TODO: ALSO ALLOW XLS FILE
        if ("animPath" in configMap):
            self._animPath=configMap["animPath"]
        if ("polygonFile" in configMap):
            self._nlPath=configMap["polygonFile"]

    def loadDataBase(self, fileName):
        '''
        Load PeilmerkDataBase from 'fileName
        '''
        self._grid = None

        self._pmdbPath = fileName
        self._pmdb = PM.PeilDataBase()
        self._pmdb.load(self._pmdbPath)

    def collectMapData(self, refDated=0):
        '''
        Function to convert DB to grid
        '''
        print("    -----Digesting peilmerk database-------------")
        self._grid = self._pmdb.collectAlignedDataAsList(refDated=refDated)
        print("    Digestion complete")
        print("    ------------------")
        print()

    #####################################################################
    def saveGrid(self, fileName):
        '''
        Save grid calculated in collectMapData to a file (so it can be reused)
        '''
        if (self._grid is None):
            self.collectMapData(refDated=0) 

        print("    ----Writing digested data---",fileName)
        with open(fileName,"wb") as F:
            pickle.dump(self._grid,F)
        print("    ----Digestion file ", fileName, "written")
        print()

    
    def loadGrid(self, fileName):
        '''
        Read pre-gridded data
        '''
        print("    ----Loading---",fileName)
        with open(fileName,"rb") as F:
            self._grid=pickle.load(F)
        print("    ----Digestion file ", fileName, "read")
        print()
        
    def _fillZgrid(self, pmgrid, t, xmin, xmax, ymin, ymax, dxy, td0=0):
        '''
        Internal function to fill array
        '''
        nx=int((xmax-xmin)/dxy)
        ny=int((ymax-ymin)/dxy)
        xx=[xmin+jx*dxy for jx in range(0,nx+1)]
        yy=[ymin+jy*dxy for jy in range(0,ny+1)]
        xmid=np.linspace(xmin+0.5*dxy,xmax-0.5*dxy,nx)
        ymid=np.linspace(ymin+0.5*dxy,ymax-0.5*dxy,ny)

        xcl=[]
        ycl=[]
        xarr=[]
        yarr=[]
        zarr=[]
        i=0
        counts=np.zeros((nx,ny))
        dn=max(1,int(1000/dxy))
        for spm, cData in pmgrid.items():
            xy = cData[PM.COORD_KEY]
            x,y = xy[PM.X_KEY], xy[PM.Y_KEY]
            d = cData[PM.DIFF_KEY]
            hgts,srs = d[PM.ALIGN_ALL], d[PM.MEDIAN]
                
            # If dates cover the relevant period, add to the list
            if (hgts[-1][0]>=t-MAP_TTOL_MAP and hgts[0][0]<=td0+MAP_TTOL_MAP):
                xarr.append(x)
                yarr.append(y)
                dz=IP.Interpolate(hgts,td0)-IP.Interpolate(hgts,t)
                zarr.append(dz)
                i+=1

                # Keep track of point density, so we can stop interpolation too far from data
                ix=int((x-xmin)/dxy)    
                iy=int((y-ymin)/dxy)       
                for jx in range(ix-dn,ix+dn+1):
                    for jy in range(iy-dn,iy+dn+1):
                        if (jx>=0 and jx<nx and jy>=0 and jy<ny):
                            counts[jx,jy]+=1

            # Show points that were measured near this time as dots on the map
            if (len(srs)>0):
                tc=IP.GetClosest(srs,t)[0]
                if (abs(tc-t)<MAP_TTOL_PEILMERK):
                    xcl.append(x)
                    ycl.append(y)
        
        # Convert to numpy
        xarr=np.array(xarr)
        yarr=np.array(yarr)
        zarr=np.array(zarr)
        zgrid = griddata((xarr, yarr), zarr, (xmid[None,:],ymid[:,None]), method='linear')   

        # Blank where interpolation too far from data
        for ix in range(0,nx):
            for iy in range(0,ny):
                if (counts[ix,iy]==0):
                    zgrid[iy,ix]=np.nan
        
        # Convert list to numpy array for plotting
        xcl=np.array(xcl)
        ycl=np.array(ycl)
        
        return xcl, ycl, xx, yy, zgrid
        

    def _getNLShape(self):
        '''
        Load netherlands contour (if defined)
        '''
        polynum=0
        self._nlx=[]
        self._nly=[]
        if (self._nlPath==""):
            return
            
        print("    -----Loading Netherlands contour-------------")
        with open(self._nlPath) as csv_file:
            csv_dictreader = csv.DictReader(csv_file, delimiter=',',quotechar='"')
                
            for row in csv_dictreader:
                if(row["Poly"]!=""):
                    poly=int(row["Poly"])
                    x=float(row["X"])
                    y=float(row["Y"])
                    if (poly>polynum):
                        polynum+=1
                        self._nlx.append([])
                        self._nly.append([])
                    self._nlx[polynum-1].append(x)
                    self._nly[polynum-1].append(y)
        print()
                    
    def _getColorscale(self):
        '''
        Define the color scale we'll use
        '''
        # RGB is easier
        colors=dict()
        colors[0.00]=(  0,255,  0) # green
        colors[0.26]=(255,255,  0) # yellow
        colors[0.50]=(  0,  0,255) # blue
        colors[0.75]=(255,  0,  0) # red
        colors[1.00]=(110, 28, 28) # brown

        # then convert to cdict
        self._cdict=dict()
        self._cdict['red']=list()
        self._cdict['green']=list()
        self._cdict['blue']=list()
        for x in sorted(colors):
            self._cdict['red'].append((x,colors[x][0]/255,colors[x][0]/255))
            self._cdict['green'].append((x,colors[x][1]/255,colors[x][1]/255))
            self._cdict['blue'].append((x,colors[x][2]/255,colors[x][2]/255))

        #self._cdict = {'red':    [[0.0,  0.0, 0.0],
        #                    [0.33, 1.0, 1.0],
        #                    [0.67, 0.0, 0.0],
        #                    [1.0,  1.0, 1.0]],
        #         'blue':   [[0.0,  0.0, 0.0],
        #                    [0.33, 0.0, 0.0],
        #                    [0.67, 1.0, 1.0],
        #                    [1.0,  0.0, 0.0]],
        #         'green':  [[0.0,  1.0, 1.0],
        #                    [0.33, 1.0, 1.0],
        #                    [0.67, 0.0, 0.0],
        #                    [1.0,  0.0, 0.0]]}
        
    def createOverviewMap(self, t_0=None, y_0=None, t_cur=None, y_cur=None, plotName=None, 
                        bounds=None, dxy=100, vmax=0.25):
        '''
        Create overview map of subsidence grid (needs to have been loaded)

        Subsidence mapped is from t_0 to t_cur (datetime.date) or from year y_0 to year y_cur.

        bounds:     can be supplied in RD as tuple (xmin, ymin, xmax, ymax)
        dxy:        grid resolution
        vmax:       limit of color scale
        plotName:   output file name. If empty, runs interactively.
        '''
        # AOI and grid resolution
        if (bounds is None):
            #(ymin,ymax)=(520000,560000)
            #(xmin,xmax)=(194000,230000)
            (ymin,ymax)=(510000,605000)
            (xmin,xmax)=(150000,264000)
        else:
            (xmin, ymin, xmax, ymax) = bounds
        dxy=100

        # Time
        if (t_0 is None): 
            if (y_0 is None): 
                t_0 = T_ZERO
            else:
                t_0 = datetime.date(y_0,1,1)
        td_0=(t_0 - T_ZERO).days
        if (t_cur is None): 
            if (y_cur is None):
                t_cur = datetime.date(2019,1,1) # TODO
            else:
                t_cur = datetime.date(y_cur,1,1)
        td_cur=(t_cur - T_ZERO).days

        # Convert pre-gridded data
        xarr, yarr, xx, yy, zgrid = self._fillZgrid(self._grid, td_cur, xmin, xmax, 
                                                    ymin, ymax, dxy,td0=td_0)

        # Netherlands contour
        self._getNLShape()
        
        # Color scale
        self._getColorscale()
        cm=matplotlib.colors.LinearSegmentedColormap("mycmap",self._cdict)

        #####################################################################
        #
        # Generic container to pass data to the plotting function
        #
        #####################################################################
        class PlotWrapper:
            pass

        #####################################################################
        #
        # Initialize plot; Plot the Netherlands outline
        #
        #####################################################################
        pw=PlotWrapper()
        pw.cbar=None
        pw.im=None
        pw.pls=None
        pw.fig, pw.ax = plt.subplots()
        for i in range(len(self._nlx)):
            pw.ax.plot(self._nlx[i],self._nly[i],color="black")
        pw.fig.set_size_inches(9,4)

        pw.ax.set_ylim(ymin,ymax)
        pw.ax.yaxis.set_ticks(np.arange(ymin,ymax, 10000))
        pw.ax.set_xlim(xmin,xmax)
        pw.ax.xaxis.set_ticks(np.arange(xmin,xmax, 10000))

        #####################################################################
        #
        # Plot the data
        #
        #####################################################################
        pw.im=pw.ax.pcolormesh(xx, yy, zgrid,cmap=cm,vmax=vmax,vmin=-0.0)
        pw.pls=pw.ax.scatter(xarr,yarr,marker="o",s=0.1,color="black")

        #####################################################################
        #
        # Wrap up & show
        #
        #####################################################################pw.ax.yaxis.grid()
        pw.ax.xaxis.grid()
        pw.ax.yaxis.grid()
        pw.ax.set_title("Subsidence {}-{}".format(t_0.year,t_cur.year))

        if(pw.cbar==None):
            pw.cbar=pw.fig.colorbar(pw.im, ax=pw.ax)
            pw.cbar.set_label('[m]')
            
        for item in ([pw.ax.xaxis.label, pw.ax.yaxis.label] + # pw.ax.title, 
                     pw.ax.get_xticklabels() + pw.ax.get_yticklabels()):
            item.set_fontsize(7)

        if (plotName is None):
            plt.show()
            plt.clf()
        else:
            plt.ioff()
            plt.savefig(plotName)
            plt.close()
        
    def createSubsAnim(self, fileName, t_0=None, y_0=None, t_cur=None, y_cur=None, 
                        bounds=None, dxy=500, vmax=0.25):
        '''
        Create animated map of subsidence grid (needs to have been loaded)

        Subsidence mapped is from t_0 to t_cur (datetime.date) or from year y_0 to year y_cur.
        
        bounds:     can be supplied in RD as tuple (xmin, ymin, xmax, ymax)
        dxy:        grid resolution
        vmax:       limit of color scale
        fileName:   output file name (mp4)
        '''
        
        if (self._animPath==""):
            print("**** PATH TO ANIMATION PLUG IN NOT SET ***")
            return
            
        # Time
        if (t_0 is None): 
            if (y_0 is None): 
                t_0 = T_ZERO
            else:
                t_0 = datetime.date(y_0,1,1)
        if (t_cur is None): 
            if (y_cur is None):
                t_cur = datetime.date(2019,1,1)
            else:
                t_cur = datetime.date(y_cur,1,1)
            
        #####################################################################
        #
        # Generic container to pass data to the plotting function
        #
        #####################################################################
        class PlotWrapper:
            pass
        pw=PlotWrapper()
        pw.cbar=None
        pw.im=None
        pw.pls=None
        pw.curdate=t_0
        pw.startdate=t_0
        pw.vmax = vmax

        #####################################################################
        #
        # AOI and grid resolution
        #
        #####################################################################
        #(ymin,ymax)=(520000,560000)
        #(xmin,xmax)=(194000,230000)
        if (bounds is None):
            (pw.ymin,pw.ymax)=(510000,605000)
            (pw.xmin,pw.xmax)=(150000,264000)
        else:
            (pw.xmin, pw.ymin, pw.xmax, pw.ymax) = bounds
        pw.dxy=dxy

        #####################################################################
        #
        # Function to get the end of the month from date dt
        #
        #####################################################################
        def eom_d(dt):
            sometime_next_month= dt.replace(day=1) + datetime.timedelta(days=31)
            start_of_next_month= sometime_next_month.replace(day=1)
            return start_of_next_month - datetime.timedelta(days=1)

        # Netherlands contour
        self._getNLShape()
        
        # Color scale
        self._getColorscale()
        pw.cm=matplotlib.colors.LinearSegmentedColormap("mycmap",self._cdict)

        #####################################################################
        #
        # Function o plot 1 frame. Iterates a month at a time1
        #
        #####################################################################
        def myfunc(i, lpw):
            # Figure out when we are, and print for progress monitoring
            prevdate=lpw.curdate
            lpw.curdate=eom_d(lpw.curdate+datetime.timedelta(1))
            td_cur=(lpw.curdate - T_ZERO).days
            td_0=(lpw.startdate - T_ZERO).days
            print(str(lpw.curdate))
            pw.bar.update(i+1)
            
            # Remove previous decoration objects if needed
            if not (lpw.cbar is None): 
                lpw.cbar.remove()
                lpw.cbar=None
            
            if (lpw.pls != None):
                lpw.pls.remove()
                lpw.pls=None 

            if (lpw.im != None):
                lpw.im.remove()
                lpw.im=None 

            # Get gridded data for current timestep
            xarr, yarr, xx, yy, zgrid = self._fillZgrid(self._grid, td_cur, lpw.xmin, 
                                                    lpw.xmax, lpw.ymin, lpw.ymax, lpw.dxy,
                                                    td0=td_0)
            
            # Mesh 
            pw.im=pw.ax.pcolormesh(xx, yy, zgrid,cmap=pw.cm,vmax=pw.vmax,vmin=-0.0)
            pw.pls=pw.ax.scatter(xarr,yarr,marker="o",s=0.1,color="black")
            
            if(pw.cbar==None):
                pw.cbar=pw.fig.colorbar(pw.im, ax=pw.ax)
            pw.cbar.set_label('[m]')
            
            pw.ax.set_title("Subsidence: " + str(lpw.curdate.month)+"/"+str(lpw.curdate.year))
            
            for item in ([pw.ax.xaxis.label, pw.ax.yaxis.label] + # pw.ax.title, 
                     pw.ax.get_xticklabels() + pw.ax.get_yticklabels()):
                item.set_fontsize(7)
                   

        #####################################################################
        #
        # Initialize plot; Plot the Netherlands outline
        #
        #####################################################################
        pw.fig, pw.ax = plt.subplots()
        for i in range(len(self._nlx)):
            pw.ax.plot(self._nlx[i],self._nly[i],color="black")
        pw.fig.set_size_inches(9,4)

        pw.ax.set_ylim(pw.ymin,pw.ymax)
        pw.ax.yaxis.set_ticks(np.arange(pw.ymin,pw.ymax, 10000))
        pw.ax.set_xlim(pw.xmin,pw.xmax)
        pw.ax.xaxis.set_ticks(np.arange(pw.xmin,pw.xmax, 10000))

        #####################################################################
        #
        # Wrap up & show
        #
        #####################################################################pw.ax.yaxis.grid()
        pw.ax.xaxis.grid()
        pw.ax.yaxis.grid()

        #####################################################################
        #
        # Define the animation, and start it (save/show)
        #
        #####################################################################
        nFrames = (t_cur.year - t_0.year) * 12 + t_cur.month - t_0.month
        pw.bar = pb.ProgressBar(max_value=nFrames, initial_value=0, redirect_stdout=True).start()
        anim = FuncAnimation(pw.fig, myfunc, fargs=[pw], frames=nFrames, interval=20, repeat=False)
        plt.rcParams['animation.ffmpeg_path'] = self._animPath
        writervideo = FFMpegWriter(fps=10) 
        dpi = 600
        anim.save(fileName, writer=writervideo,dpi=dpi)

        #plt.show()

