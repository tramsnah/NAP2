'''
Module to hold several utility dialogs (e.g. to query
user for a double, a string, etc.)
All of the classes have a static 'Ask' method that is 
the external interface.
'''
import pickle
import tkinter
from tkinter import ttk # combobox


# TODO: save this to config file
class _CFG:
    '''
    Wrapper to hold dialog config information
    '''
    def __init__(self):
        self._DLG_xys=dict()

# Init instance
_cfg=_CFG()

def DumpP(F):
    '''
    Save (pickle) state to F
    '''
    version="1.0"
    pickle.dump(version, F)

    # Our state
    pickle.dump(_cfg, F)

def LoadP(F):
    '''
    Load (pickle) state from F
    '''
    version = pickle.load(F)
    assert(version=="1.0")

    # Our state
    _cfg = pickle.load(F)

class DlgException(BaseException):
    '''
    General superclass for exceptions in this module.
    '''
    def __init__(self, descr):
        BaseException.__init__(self)
        self._descr = descr

    def __str__(self):
        return self._descr
        
class CancelPressed(DlgException):
    '''
    Exception used internally to manage 
    the user pressing 'cancel'
    '''
    def __init__(self):
        DlgException.__init__(self, "Cancel Pressed")
        
class BaseDlg:
    '''
    Base class for simple dialogs

    Some geometry handling support
    '''
    def __init__(self, parent, title, dlgId="", prompt=""):
        # Main window
        self._win = tkinter.Toplevel(parent)
        self._win.title(title)
        
        # Restore geometry, if possible
        self.setGeometry(parent, dlgId)

        # Prompt
        tkinter.Label(self._win, text="Select "+prompt+":").pack(side=tkinter.TOP)
                    
        # Frame to organize spacing
        frame1 = tkinter.Frame(self._win, bd=10)
        frame1.pack(expand=True, side=tkinter.TOP, fill=tkinter.BOTH)
        
        mainWidget = self.fillWidget(frame1)
        
        # Frame to organize OK/Cancel buttons
        frame2 = tkinter.Frame(self._win, bd=10)
        frame2.pack(side=tkinter.BOTTOM,fill=tkinter.X)
        
        # And the buttons
        tkinter.Button(frame2, text='OK', command=self._ok).pack(side=tkinter.LEFT)
        tkinter.Button(frame2, text='Cancel', command=self._ok).pack(side=tkinter.RIGHT)
        
        # Key bindings
        self._win.bind('<Return>', self._ok_key_cb)
        self._win.bind('<Escape>', self._cancel_key_cb)
        
        # Make sure the close window button at top right goes the same path
        self._win.protocol("WM_DELETE_WINDOW", self._cancel)
        
        # Modal dialog,
        # only one window in the task bar
        self._win.transient(parent)    
        self._win.grab_set()
                
        # Set focus so we can start typing...
        mainWidget.focus_set()
        
        # Wait until we die
        self._win.wait_window()

        # We're dead now
        self._win = None
        self._id = ""
        
    def dCode(self):
        '''
        Abstract method. To be overloaded to return 
        dialog type.
        '''
        return ""
            
    def getGeometry(self):
        '''
        Get current geometry from window, and store, so
        it comes in the same place & size as before when reopened
        '''
        _cfg._DLG_xys[self.dCode()+self._id]=(self._win.winfo_x(),
                                              self._win.winfo_y(),
                                              self._win.winfo_width(),
                                              self._win.winfo_height()) 

    def setGeometry(self, parent, dlgId, force=True):
        '''
        Get current geometry, force on dialog, so
        it comes in the same place & size as before
        '''
        self._id = dlgId
        if (self.dCode()+self._id) in _cfg._DLG_xys:
            wininfo = _cfg._DLG_xys[self.dCode()+self._id]
            x = wininfo[0]
            y = wininfo[1]
            w = wininfo[2]
            h = wininfo[3]
            self._win.geometry("%dx%d+%d+%d" %(w,h,x,y))
        elif (force):
            x = parent.winfo_x()+50
            y = parent.winfo_y()+50
            self._win.geometry("+%d+%d" %(x,y))

    def fillWidget(self, frame):
        '''
        Abstract method, called by constructor to fill the dialog.
        '''
        return None

    # Callback for enter key
    def _ok_key_cb(self, enter): 
        self._ok()
        
    # Callback for cancel key
    def _cancel_key_cb(self, enter): 
        self._cancel()       
       
    def _ok(self):
        '''
        Called from OK press callback. 
        Can be overloaded for customization.
        '''
        if (not self.getValue()):
            return

        self.getGeometry()
        self._win.destroy()
        self._win = None
        
    def _cancel(self): 
        '''
        Called from Cancel press callback. 
        Can be overloaded for customization.
        '''
        self.getGeometry()
        self.discardValue()
        self._win.destroy()
        self._win = None
        raise CancelPressed 
        
    def getValue(self):
        return True
    
    def discardValue(self):
        pass       

class ChoiceMB(BaseDlg):
    '''
    Choice from lsit (optionmenu)
    '''
    def dCode(self):
        return "DLG_MB"
        
    def __init__(self, parent, title, choiceList, oVar, dlgId="", prompt="item"):    
        # Output variable and list
        self._var = oVar
        self._choiceList = choiceList
        
        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)
    
    # Method called from 'init'
    def fillWidget(self, frame):
        # Check default
        try:
            iDef=self._choiceList.index(self._var.get())
        except ValueError:
            self._var.set("")

        # Create the popup menu
        popupMenu = tkinter.OptionMenu(frame, self._var, *self._choiceList)#, default=default)
        popupMenu.pack(expand=True, fill=tkinter.BOTH)

        return popupMenu        

    @staticmethod
    def Ask(parent, title, choiceList, default="", dlgId="", prompt="value"):
        oVar = tkinter.StringVar()
        oVar.set(default)
        app = ChoiceMB(parent, title, choiceList, oVar, dlgId=dlgId, prompt=prompt)
        return oVar.get()
        
class ChoiceSL(BaseDlg):
    '''
    Choice from list (listbox)
    '''
    def dCode(self):
        return "DLG_LB"
        
    def __init__(self, parent, title, choiceList, oVar, dlgId="", prompt="item"):
        # Output variable etc.
        self._var = oVar
        self._choiceList=choiceList
        
        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)
        
    # Method called from 'init'
    def fillWidget(self, frame):
        # Create listbox
        self._listBox = tkinter.Listbox(frame, height=6, selectmode='single')
        self._listBox.pack(expand=True, side=tkinter.LEFT, fill=tkinter.BOTH)
        
        # Fill listbox
        for chc in self._choiceList: 
            self._listBox.insert(tkinter.END, chc)
        
        # Create scrollbar
        scrollbar = tkinter.Scrollbar(frame, orient=tkinter.VERTICAL)
        scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
            
        # attach listbox to scrollbar
        self._listBox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._listBox.yview)    
        
        # Check default
        try:
            iDef=self._choiceList.index(self._var.get())
            self._listBox.selection_set(iDef)
            self._listBox.see(iDef)
        except ValueError:
            self._var.set("")

        return self._listBox
            
    def getValue(self): 
        sel = self._listBox.get(self._listBox.curselection())
        self._var.set(sel)
        return True      

    @staticmethod
    def Ask(parent, title, choiceList, default="", dlgId="", prompt="value"):
        oVar = tkinter.StringVar()
        oVar.set(default)
        app = ChoiceSL(parent, title, choiceList, oVar, dlgId=dlgId, prompt=prompt)
        return oVar.get()
        

class ChoiceTwoCB(BaseDlg):
    '''
    Choice from 2 lists (comboboxes)
    '''
    def dCode(self):
        return "DLG_LB"
        
    def __init__(self, parent, title, choiceList1, oVar1, oVar2, 
                    choiceList2=None, dlgId="", prompt="item"):
        # Output variable etc.
        self._var1 = oVar1
        self._choiceList1=choiceList1
        self._var2 = oVar2
        if (choiceList2 is None):
            self._choiceList2=choiceList1
        else:
            self._choiceList2=choiceList2
        
        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)
        
        
    def _createBox(self, frame, var, choiceList):
        # Create box
        listBox = ttk.Combobox(frame, values=choiceList)
        listBox.pack(expand=True, side=tkinter.LEFT, fill=tkinter.BOTH)
        
        # Check default
        try:
            iDef=choiceList.index(var.get())
            listBox.current(iDef)
        except ValueError:
            var.set("")
            
        return listBox
    
    # Method called from 'init'
    def fillWidget(self, frame):
        # Create boxes
        self._listBox1 = self._createBox(frame, self._var1, self._choiceList1)
        tkinter.Label(frame, text="   ").pack(side=tkinter.LEFT)
        self._listBox2 = self._createBox(frame, self._var2, self._choiceList2)

        return self._listBox1
            
    def getValue(self): 
        sel = self._listBox1.get()
        self._var1.set(sel)
        sel = self._listBox2.get()
        self._var2.set(sel)
        return True      

    @staticmethod
    def Ask(parent, title, choiceList1, choiceList2=None, 
                    default1="", default2="", dlgId="", prompt="values"):
        oVar1 = tkinter.StringVar()
        oVar1.set(default1)
        oVar2 = tkinter.StringVar()
        oVar2.set(default2)
        app = ChoiceTwoCB(parent, title, choiceList1, oVar1, oVar2, 
                    choiceList2=choiceList2, dlgId=dlgId, prompt=prompt)
        return oVar1.get(),oVar2.get()


class ChoiceXY(BaseDlg):
    '''
    X,Y entry (coordinates)
    '''
    def dCode(self):
        return "DLG_XY"
        
    def __init__(self, parent, title, oVar, dlgId="", prompt="X,Y"):
        # Output variable (tuple)
        self._dVar = oVar
        self._sVar=(tkinter.StringVar(),tkinter.StringVar())
        self._sVar[0].set(str(self._dVar[0].get()))
        self._sVar[1].set((self._dVar[1].get()))

        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)
        
    def fillWidget(self, frame):
        # The two text boxes
        self._textBoxX = tkinter.Entry(frame, textvariable = self._sVar[0], width=5)
        self._textBoxX.pack(expand=tkinter.YES, fill=tkinter.BOTH, side=tkinter.LEFT)
        comma=tkinter.Label(frame, text=",")
        comma.pack(expand=False, side=tkinter.LEFT)
        self._textBoxY = tkinter.Entry(frame, textvariable = self._sVar[1], width=5)
        self._textBoxY.pack(expand=tkinter.YES, fill=tkinter.BOTH, side=tkinter.LEFT)
        
        return self._textBoxX

    def getValue(self): 
        try:
            self._dVar[0].set(float(self._sVar[0].get()))
            self._dVar[1].set(float(self._sVar[1].get()))
        except ValueError:
            return False
        return True   

    @staticmethod
    def Ask(parent, title, default=(0,0), dlgId="", prompt="value"):
        oVar = (tkinter.DoubleVar(),tkinter.DoubleVar())
        oVar[0].set(default[0])
        oVar[1].set(default[1])
        app = ChoiceXY(parent, title, oVar, dlgId=dlgId, prompt=prompt)
        return (oVar[0].get(),oVar[1].get())

class ChoiceDBL(BaseDlg):
    '''
    double entry
    '''
    def dCode(self):
        return "DLG_DBL"
        
    def __init__(self, parent, title, oVar, dlgId="", prompt="value"):
        # Output variable
        self._dVar = oVar
        self._sVar=tkinter.StringVar()
        self._sVar.set(str(self._dVar.get()))

        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)

    def fillWidget(self, frame):
        # Entry box
        self._textBox = tkinter.Entry(frame, textvariable = self._sVar)
        self._textBox.pack()
        
        return self._textBox

    def getValue(self): 
        try:
            self._dVar.set(float(self._sVar.get()))
        except ValueError:
            return False
        return True

    @staticmethod
    def Ask(parent, title, default=0.0, dlgId="", prompt="value"):
        oVar = tkinter.DoubleVar()
        oVar.set(default)
        app = ChoiceDBL(parent, title, oVar, dlgId=dlgId, prompt=prompt)
        return oVar.get()

class ChoiceINT(BaseDlg):
    '''
    integer entry
    '''
    def dCode(self):
        return "DLG_INT"
        
    def __init__(self, parent, title, oVar, dlgId="", prompt="value"):
        # Outpur variable
        self._iVar = oVar
        self._sVar=tkinter.StringVar()
        self._sVar.set(str(self._iVar.get()))

        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)

    def fillWidget(self, frame):
        # Entry widget
        self._textBox = tkinter.Entry(frame, textvariable = self._sVar)
        self._textBox.pack()
       
        return self._textBox

    def getValue(self): 
        self.getGeometry()
        try:
            d = float(self._sVar.get())
            self._iVar.set(int(d))
        except ValueError:
            return False
        if (self._iVar.get()!=d):
            return False
        return True

    @staticmethod
    def Ask(parent, title, default=0, dlgId="", prompt="value"):
        oVar = tkinter.IntVar()
        oVar.set(default)
        app = ChoiceINT(parent, title, oVar, dlgId=dlgId, prompt=prompt)
        return oVar.get()

class ChoiceSTR(BaseDlg):
    '''
    string entry
    '''
    def dCode(self):
        return "DLG_STR"
        
    def __init__(self, parent, title, oVar, dlgId="", prompt="value"):
        # Outpur variable
        self._sVar = oVar
        
        # Init base class (this will call fill Widget), and go into main loop
        BaseDlg.__init__(self, parent, title, dlgId=dlgId, prompt=prompt)

    def fillWidget(self, frame):
        # Entry widget
        self._textBox = tkinter.Entry(frame, textvariable = self._sVar)
        self._textBox.pack()
        return self._textBox

    @staticmethod
    def Ask(parent, title, default="", dlgId="", prompt="value"):
        oVar = tkinter.StringVar()
        oVar.set(default)
        app = ChoiceSTR(parent, title, oVar, dlgId=dlgId, prompt=prompt)
        return oVar.get()

if __name__ == '__main__':  

    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg, NavigationToolbar2Tk)
    # Implement the default Matplotlib key bindings.
    from matplotlib.backend_bases import key_press_handler
    from matplotlib.figure import Figure

    import numpy as np
       
     
    class MPLWindow:
        '''
        Test class for utildialogs
        '''
        def __init__(self):
            self._root = tkinter.Tk()
            self._root.wm_title("Embedding in Tk")

            fig = Figure(figsize=(5, 4), dpi=100)
            t = np.arange(0, 3, .01)
            ax = fig.add_subplot().plot(t, 2 * np.sin(2 * np.pi * t))

            self._canvas = FigureCanvasTkAgg(fig, master=self._root)  # A tk.DrawingArea.
            self._canvas.draw()

            # pack_toolbar=False will make it easier to use a layout manager later on.
            self._toolbar = NavigationToolbar2Tk(self._canvas, self._root, pack_toolbar=False)
            self._toolbar.update()

            # Implement the default Matplotlib key bindings.
            self._canvas.mpl_connect(
                "key_press_event", lambda event: print(f"you pressed {event.key}"))
            self._canvas.mpl_connect("key_press_event", key_press_handler)
            
            # Add the callback for right-click menu
            self._canvas.mpl_connect("button_press_event", self.button_press)

            # Add a quit button
            button = tkinter.Button(master=self._root, text="Quit", command=self._root.quit)

            # Packing order is important. Widgets are processed sequentially and if there
            # is no space left, because the window is too small, they are not displayed.
            # The canvas is rather flexible in its size, so we pack it last which makes
            # sure the UI controls are displayed as long as possible.
            button.pack(side=tkinter.BOTTOM)
            self._toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
            self._canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
            
            self._popupMenu = None
        
        def _createPopup(self):
            if not (self._popupMenu is None):
                return
                
            # Create the right click menu
            self._popupMenu = tkinter.Menu(self._canvas.get_tk_widget(), tearoff=0)
            self._popupMenu.add_command(label="OptionMenu",
                                        command=self._aap)
            self._popupMenu.add_command(label="Listbox",
                                        command=self._noot)
            self._popupMenu.add_command(label="XY",
                                        command=self._mies)
            self._popupMenu.add_command(label="Double",
                                        command=self._teun)
            self._popupMenu.add_command(label="Int",
                                        command=self._schaap)    
            self._popupMenu.add_command(label="Str",
                                        command=self._freek)
            self._popupMenu.add_command(label="2-Sel",
                                        command=self._aapje)
                                        
        def button_press(self, event):
            toolMode = self._toolbar.mode
            if (toolMode == "" and not (event.inaxes) is None):
                print(event)
                self._createPopup()
                try:
                    # Menu requires absolute pointer positions,and event.x,event.y are relative.
                    #x=event.x
                    #y=event.y
                    # Map canvas x,y to data x,y
                    print(event.inaxes.transData.inverted().transform((event.x, event.y)))
                    # Map data x,y to canvas x,y
                    print(event.inaxes.transData.transform((event.xdata, event.ydata)))
                    xd1,yd1=event.inaxes.transData.inverted().transform((event.x+1, event.y+1))
                    xscale=(event.xdata-xd1)
                    yscale=(event.ydata-yd1)
                    print("____Scale: ",xscale,yscale)
                    x=self._root.winfo_pointerx()
                    y=self._root.winfo_pointery()
                    self._popupMenu.tk_popup(x, y, 0)
                finally:
                    self._popupMenu.grab_release()
                
        def _aap(self):
            oStr = ChoiceMB.Ask(self._root, "ChoiceBox", 
                        ['one','two','three'], default="two", dlgId="frans")
            print("***OUTPUT:",oStr)
            
        def _noot(self):
            oStr = ChoiceSL.Ask(self._root, "ChoiceBox", 
                        ['a','b','c','d','one','two','three'], 
                                default="two", dlgId="frans")
            print("***OUTPUT:",oStr)
            
        def _aapje(self):
            oStr1, oStr2 = ChoiceTwoCB.Ask(self._root, "ChoiceBox", ['a','b','c','d','one','two','three'], 
                                default1="two", default2="a", dlgId="aapje")
            print("***OUTPUT:",oStr1, oStr2)
            
        def _mies(self):
            oXY = ChoiceXY.Ask(self._root, "XYBox", default=(11,31), dlgId="frens")
            print("***OUTPUT:",oXY)

        def _teun(self):
            oDbl = ChoiceDBL.Ask(self._root, "DblBox", default=4.32, dlgId="frins")
            print("***OUTPUT:",oDbl)
            
        def _schaap(self):
            oInt = ChoiceINT.Ask(self._root, "IntBox", default=321)
            print("***OUTPUT:",oInt)
            
        def _freek(self):
            oStr = ChoiceSTR.Ask(self._root, "StrBox", default="kees", dlgId="frans")
            print("***OUTPUT:",oStr)

    mw=MPLWindow()
    tkinter.mainloop()
    