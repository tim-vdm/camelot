"""
Action steps to conduct interviews with users.  An interview is an alternative
to the traditional wizard.  In an interview the user is presented with a
sequence of questions, where the next question depends on the answers given
to the previous questions.  An interview can be the implementation of a
business procedure that needs to be followed.

Where in a traditional wizard, the user switches from one screen to the next,
The interview always adds more content to the existing screen, and allows 
easy keyboard only completion of the process.
"""

from camelot.admin.action import ActionStep

class StartInterview(ActionStep):
    
    def __init__( self, title ):
        pass

class AskQuestion(ActionStep):
    
    def __init__( self, fields ):
        pass
    
class AddAction(ActionStep):
    
    def __init__( self, action ):
        pass
    
class AddLabel(ActionStep):
    
    def __init__(self, fields ):
        pass
