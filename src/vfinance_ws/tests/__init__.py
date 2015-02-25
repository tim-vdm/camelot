import os

if os.environ.get('DEBUGGER') == 'wingdb':
    import wingdbstub
    assert wingdbstub
