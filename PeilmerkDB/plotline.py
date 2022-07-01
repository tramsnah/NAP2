'''
PlotLine class that can be used for intersection, and to plot on maps
'''
import numpy as np

class PlotLine:
    '''
    PlotLine class that can be used for intersection, and to plot on maps
    '''
    def __init__(self, xy, angleDeg):
        self._xy = xy
        self._angleDeg = angleDeg
    
        angleRad = self._angleDeg*np.pi/180
        self._cs = np.cos(angleRad)
        self._ss = np.sin(angleRad)
        
        self._xmin = None
        self._xmax = None

    def proj(self, xy):
        dx = (xy[0]-self._xy[0])
        dy = (xy[1]-self._xy[1])
        dist = abs(self._cs*dy-self._ss*dx)
        xproj = self._cs*dx+self._ss*dy
        return xproj, dist
    
    def project(self, xvalues, yvalues, maxDist):
        out = []
        self._xmin = 1e37
        self._xmax = -1e37
        for xy in zip(xvalues, yvalues):
            xproj, dist = self.proj(xy)
            self._xmin = min(self._xmin, xproj)
            self._xmax = max(self._xmax, xproj)
            out.append(xproj if dist<maxDist else np.nan)
        return out
        
    def getEndPoints(self):
        if (self._xmin is None):
            return None
            
        xy0 = (self._xy[0] + self._xmin*self._cs, self._xy[1] + self._xmin*self._ss)
        xy1 = (self._xy[0] + self._xmax*self._cs, self._xy[1] + self._xmax*self._ss)
        
        return [xy0,xy1]
        
    def getAnchor(self):
        return self._xy
