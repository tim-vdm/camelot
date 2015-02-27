#
# Definitions
# ===========
#
# A mixin class : provides common methods to a set of classes, holds no
#   persisted properties
#
# An abstract class : provides common persisted properties to a set of classes,
#   the abstract class itself is not persisted on its own, an abstract class
#   can derive from a mixin class
#

import logging
import os
import warnings

from sqlalchemy import exc

warnings.simplefilter( action='ignore',
                       category=exc.SADeprecationWarning )

LOGGER = logging.Logger('vfinance.model')

#
# Make statuses globally not editable
#
from camelot.model.type_and_status import StatusHistoryAdmin
StatusHistoryAdmin.field_attributes['status_from_date'] = {'editable': False}
StatusHistoryAdmin.field_attributes['status_thru_date'] = {'editable': False}
StatusHistoryAdmin.field_attributes['classified_by'] = {'editable': False}

#
# Start model definition
#
import bank
import bond
import hypo
import kapbon
import kapcontract
import financial
import insurance

__all__ = [bank.__name__,
           bond.__name__,
           hypo.__name__,
           kapbon.__name__,
           kapcontract.__name__,
           financial.__name__,
           insurance.__name__]

#
# Setup the SQLAlchemy event listeners
#



# don't slowdown the startup time when no docstrings are needed
if os.environ.get('VFINANCE_DOCSTRING', None):
    from camelot.core.document import document_classes
    from camelot.core.orm import setup_all
    
    from bank import natuurlijke_persoon, rechtspersoon, dual_person
    
    from financial import agreement as financial_agreement
    from financial import package as financial_package
    from financial import premium as financial_premium
    from financial import product as financial_product
    from financial import feature as financial_feature
    from financial import fund as financial_fund
    
    from insurance import agreement as insurance_agreement
    
    setup_all()
    
    document_classes([natuurlijke_persoon.NatuurlijkePersoon,
                      rechtspersoon.Rechtspersoon,
                      dual_person.CommercialRelation,
                      financial_package.FinancialPackage,
                      financial_package.FinancialItemClause,
                      financial_package.FinancialNotificationApplicability,
                      financial_package.FunctionalSettingApplicability,
                      financial_product.FinancialProduct,
                      financial_product.ProductFeatureApplicability,
                      financial_product.ProductFundAvailability,
                      financial_product.ProductFeatureDistribution,
                      financial_product.ProductFeatureCondition,
                      financial_agreement.FinancialAgreement,
                      financial_agreement.FinancialAgreementRole,
                      financial_agreement.FinancialAgreementItem,
                      financial_agreement.FinancialAgreementAssetUsage,
                      financial_agreement.FinancialAgreementFunctionalSettingAgreement,
                      financial_premium.FinancialAgreementPremiumSchedule,
                      financial_premium.FinancialAccountPremiumSchedule,
                      financial_feature.FinancialAgreementPremiumScheduleFeature,
                      financial_feature.FinancialAccountPremiumScheduleFeature,
                      financial_feature.FinancialTransactionPremiumScheduleFeature,
                      financial_fund.FinancialAgreementFundDistribution,
                      financial_fund.FinancialAccountFundDistribution,
                      financial_fund.FinancialTransactionFundDistribution,
                      insurance_agreement.InsuranceAgreementCoverage,
                      ])
