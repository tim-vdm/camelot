import dossierkosten
import melding_nbb
import periodieke_verichting
import product
import rappel_brief
import rentevoeten
import terugbetaling
import wijziging
import hypotheek
import beslissing
import aanvaarding
import akte
import fulfillment
import dossier

#
# For terminology, see
#
# http://en.wikipedia.org/wiki/Mortgage
# http://en.wikipedia.org/wiki/Loan
#

__all__ = [ melding_nbb.__name__,
            periodieke_verichting.__name__,
            product.__name__,
            rappel_brief.__name__,
            rentevoeten.__name__,
            terugbetaling.__name__,
            hypotheek.__name__,
            beslissing.__name__,
            aanvaarding.__name__,
            akte.__name__,
            dossier.__name__,
            dossierkosten.__name__,
            fulfillment.__name__,
            wijziging.__name__,
            ]

#
# Planning
#
# - Product verplicht maken + hierarchie in producten -> ok
# - Booking accounts configureerbaar
#   - Akte : ok
#   - Vervaldag : ok
#   - Rappel brief : ok
#   - Terugbetaling : ok
#   - Wijziging : ok
# - Bookingen omzetten naar sales -> delayed
#   - Akte : Diverse
#   - Vervaldag : Verkoop -> ok
#   - Rappel brief : Verkoop -> ok
#   - Terugbetaling : Verkoop
#   - Wijziging : Diverse
# - Op akte niveau meerdere kosten implementeren -> delayed
# - Wijziging en Terugbetaling samenvoegen zodat fulfillments kunnen 
#   worden gemaakt -> delayed
# - Direct debit mandates op aanvraag en dossier -> ok
# - Premium matching implementeren voor Hypo
#
