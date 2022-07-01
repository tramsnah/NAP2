'''
Auxiliaty object to manage timed callbacks to a tk widget

Usage example:
self._timer = _MPTimer(self._fig.canvas.get_tk_widget(), 1000, 
        lambda: MatPlotWrapper._on_hover_time(self, someArgument))
'''
import tkinter as tk

class MPTimer:
    '''
    Auxiliaty object to manage timed callbacks to a tk widget
    
    Usage example:
    self._timer = MPTimer(self._fig.canvas.get_tk_widget(), 1000, 
            lambda: MatPlotWrapper._on_hover_time(self, someArgument))

    In the callback, the reference to timer can be set to null (i.e. the timer can be
    forgotten).
    '''
    def __init__(self, master, time, callback):
        self._master = master
        self._callback = callback
        self._afterid = None
        self._triggered = None # 'inactive'
        
        # And start the timer if requested
        if (time is not None) and (time >0):
            self.start(time)
     
    def _timer_cb(self):   
        '''
        Timed callback is triggered.
        '''
        # Ensure it happens only once
        if (self._callback is None) or (self._triggered):
            return
            
        # Mark triggered state, and call the callback
        self._triggered = True
        self._callback()

    def start(self, time):
        ''' 
        (Re)start the timer
        '''
        # Stop the existing timer if there is one
        if (self._afterid is not None):
            self.stop()
            
        # Start the timer, Register our callback, so we can stop it later
        self._triggered = False
        self._afterid = self._master.after(time, self._timer_cb)
        
    def stop(self):
        ''' 
        Stop the timer
        '''
        # Reset triggered state to 'inactive'
        self._triggered = None
        
        # Make master forget about us
        self._master.after_cancel(self._afterid)
        self._afterid = None