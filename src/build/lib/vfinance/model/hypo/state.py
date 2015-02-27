"""
State changes compatible with TinyErp
"""
from camelot.core.exception import UserException
from camelot.admin.action import Action
from camelot.view import action_steps

class ChangeState( Action ):
    
    def __init__( self, verbose_name, new_state, old_states ):
        self.new_state = new_state
        self.old_states = old_states
        self.verbose_name = verbose_name
    
    def change_state( self, model_context, obj ):
        obj.state = self.new_state
        yield action_steps.FlushSession( model_context.session )
        
    def model_run( self, model_context ):
        for obj in model_context.get_selection():
            if obj.state not in self.old_states:
                raise UserException(u'Cannot go from %s tot %s'%( obj.state,
                                                                  self.new_state ))
            for step in self.change_state( model_context, obj ):
                yield step
                
    def get_state( self, model_context ):
        state = super( ChangeState, self ).get_state( model_context )
        if model_context.selection_count < 1:
            state.enabled = False
        for obj in model_context.get_selection():
            if obj is not None:
                if obj in model_context.session.new:
                    state.enabled = False
                if obj.state not in self.old_states:
                    state.enabled = False
        return state
