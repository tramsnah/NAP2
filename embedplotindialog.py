'''
Module for class to help in embedding a matplotlib plot
in a tk dialog, to be managed by a GUI.
'''
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler
import tkinter as tk

class PlotWrapBase:
    '''
    Abstract base class to manage communication between wrapped plot (matplotlib) and
    the controlling class. Provides the minimum interface for the EmbedPlotInDialog class.
    '''
    def __init__(self):
        pass
        
    def getWindow(self):
        '''
        To be overloaded to return tk window that contains the plot
        '''
        return None
        
    def getWidget(self):
        '''
        To be overloaded to return tk widget that contains the plot
        '''
        return None
    
    def closePlot(self):
        '''
        Implement code to close the plot
        '''
        pass
        
    def wait(self):
        '''
        Should be overloaded with wait loop in case of modal dialog
        '''
        pass
        
    def buttonPress(self, event, mode):
        '''
        Can be overloaded to process button press event
        '''
        pass
        
    def isStandAloneWindow(self):
        '''
        Overloaded to return True if associated plot is its own
        window, False if embedded (e.g. the map in the main window
        '''
        return False
        
class EmbedPlotInDialog:
    '''
    Class to help in embedding a matplotlib plot
    in a tk dialog. Manages event callbacks.
    Optional filterEvent callback allows e.g. coordinate
    transformation before the event is passed on to
    inDialog (a subclass of PlotWrapBase).
    '''
    def __init__(self, fig, inDialog, closeCmd=None, filterEvent=None):
        self._fig = fig
        self._inDialog = inDialog
        self._closeCmd = closeCmd
        self._filterEvent = filterEvent
        self.closing = False
        
        # Wrapper to embed figure
        widget = self._inDialog.getWidget()
        widget = self._inDialog.getWidget()
        self._canvas = FigureCanvasTkAgg(self._fig, master=widget)  # A tk.DrawingArea.
        #self._canvas.draw()
        
        # Get notifications when 'inDialog' widget is destroyed (from top down)
        widget.bind("<Destroy>", self.onDestroy)
        widget.bind("<Unmap>", self.onUnmap)

        # pack_toolbar=False will make it easier to use a layout manager later on.
        self._toolbar = NavigationToolbar2Tk(self._canvas, widget, pack_toolbar=False)
        self._toolbar.update()

        # Implement the default Matplotlib key bindings.
        #self._canvas.mpl_connect(
        #    "key_press_event", lambda event: print(f"    you pressed {event.key}"))
        self._canvas.mpl_connect("key_press_event", key_press_handler)

        # Add a 'close' button to the tool bar. Use frame to control margins
        bFrame = tk.Frame(master=self._toolbar, bd=3)
        button = tk.Button(master=bFrame, text="Close", command=self.close)
        
        # Make sure the close window button at top right goes the same path
        if (self._inDialog.isStandAloneWindow()):
            self._inDialog.getWindow().protocol("WM_DELETE_WINDOW", self.close)
        
        # Pack the button to the right of the standard toolbar
        # Packing order is important. Widgets are processed sequentially and if there
        # is no space left, because the window is too small, they are not displayed.
        # The canvas is rather flexible in its size, so we pack it last which makes
        # sure the UI controls are displayed as long as possible.
        bFrame.pack(side=tk.LEFT, fill=tk.Y)
        button.pack(side=tk.LEFT, fill=tk.Y)
        self._toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self._canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
                    
        # Add the callback for right-click menu
        self._canvas.mpl_connect("button_press_event", self.buttonPress)
        
    def buttonPress(self, event):
        '''
        Button press. Calls filterEvent (if defined)
        before passing the event on to the inDialog
        object.
        '''
        if not (self._filterEvent is None):
            event = self._filterEvent(event)
        self._inDialog.buttonPress(event, self._toolbar.mode)
    
    def close(self):
        ''' Close button pressed '''
        #print("    EmbedPlotInDialog.close", self.closing)
        self._notifyClose("close")
        
    def onDestroy(self, event):
        ''' Master widget destroyed '''
        #print("   EmbedPlotInDialog.onDestroy", self.closing)
        self._notifyClose("destroy")
    
    def _notifyClose(self, src):
        '''
        We will get here from 'close',clearly. Avoid recursion
        '''
        #print("   EmbedPlotInDialog._notifyClose", src, self.closing)
        if (self.closing): return
        self.closing = True
        
        # Tell the boss 
        if not (self._closeCmd is None):
            cmd = self._closeCmd
            self._closeCmd = None
            cmd()
        elif not (self._inDialog is None):
            # or someone else
            dlg = self.inDialog
            self._inDialog = None
            dlg.closePlot()
        self.closing = False
    
    def onUnmap(self, event):
        '''
        Unmap callback
        '''
        #print("**** EmbedPlotInDialog.onUnmap")
        pass