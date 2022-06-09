'''
General superclass for exceptions in this package.
'''
class PMException(Exception):
    '''
    General superclass for exceptions in this package.
    '''
    def __init__(self, descr=""):
        Exception.__init__(self)
        self._descr = descr

    def __str__(self):
        '''
        Implement base string representation.
        '''
        return self._descr