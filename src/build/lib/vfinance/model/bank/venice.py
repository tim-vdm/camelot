from camelot.core.conf import settings as _settings

def get_dossier_bank( settings=None ):
    """
    pass the settings argument to prevent settings being loaded
    from the db
    
    returns (dossier_context, constants)"""
    from integration.venice.venice import get_dossier_context
    if settings is None:
        settings = _settings

    secure = bool(int(settings.get('VENICE_SECURE')))
    initials = settings.get('VENICE_INITIALS')
    user = settings.get('VENICE_USER')
    password = settings.get('VENICE_PASSWORD').strip()
    folder = settings.get('VENICE_FOLDER')
    dossier = settings.get('VENICE_DOSSIER')
    version = settings.get('VENICE_VERSION')
    
    return get_dossier_context(version, secure, initials, user, password, folder, dossier)

def get_inspectable_years(dossier=None, years=None):
    """
    :param years: years to look back, if `None` is given, than 2 years are taken
    """
    if years is None:
        years = 2
    if dossier is None:
        dossier, _constants = get_dossier_bank()
    return dossier.GetYears()[(-1*years):]
