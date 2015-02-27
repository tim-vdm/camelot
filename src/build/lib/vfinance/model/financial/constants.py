'''
Created on May 25, 2010

@author: tw55413
'''

from decimal import Decimal as D

from vfinance.model.bank.constants import (bank_functional_settings_by_group,
                                           product_features, period_types)

precision = { 'amount':D('0.01'),
              'units':D('0.000001') }

security_features =    [(1,  'entry_rate',                            '%',      'Aangerekende instapkosten'),
                        (2,  'exit_rate',                             '%',      'Aangerekende uitstapkosten')]

security_features_enumeration = [(ff[0], ff[1]) for ff in security_features]
security_features_suffix = dict((ff[1], ff[2]) for ff in security_features)
security_features_description = dict((ff[1], ff[3]) for ff in security_features)

transaction_features_enumeration = [(tpf[0], tpf[1]) for tpf in product_features if tpf[3]]

amount_types = ['premium_minus_taxes', 'funded_premium', 'net_premium', 
                'taxation', 'entry_fee', 'premium_rate_1', 'premium_fee_1',
                'premium_rate_2', 'premium_fee_2', 'premium_rate_3', 'premium_fee_3',
                'premium_rate_4', 'premium_fee_4', 'premium_rate_5',
                'financed_commissions', 'distributed_medical_fee']

rate_types = ['taxation', 'financed_commissions']

agreement_statuses = [(1,  'draft'),
                      (2,  'complete'),
                      (3,  'verified'),
                      (4,  'incomplete'),
                      (5,  'canceled'),
                      (6,  'processed'),
                      (7,  'simulation'),
                      (8,  'negotiation'),
                      (9,  'shelve'),
                      (10, 'send')]

agreement_roles = [(1,  'subscriber'),
                   (2,  'renter'),
                   (3,  'insured_party'),
                   (4,  'beneficiary'),
                   (5,  'attorney'),
                   (6,  'asset_manager'),
                   (7,  'depository'),
                   (8,  'payer'),
                   (9,  'pledgee'), # ingeval de polis verpand is
                   (10, 'rightsholder'),
                   ]

item_clause_types = [(1, 'beneficiary'),
                     (2, 'attorney'),
                     (3, 'conventional_return'),
                     (4, 'other'),
                     #(5, 'transfer'),
                     (6, 'additional_information'),
                     ]

account_statuses = [ (1, 'draft'),
                     (2, 'active'), 
                     (3, 'closed'),
                     (4, 'delayed'),
                     ]

work_effort_statuses = [(1, 'open'),         # new notifications can be added
                        (2, 'closed'),       # no new notifications can be added
                        (2, 'completed'),    # the notifications were send
                        (3, 'canceled')]     # the work effort was canceled

account_roles = agreement_roles

#                                id,  name,                        group,                 custom_clause, exclusive 
functional_settings_by_group = [(1,  'exit_at_first_decease',      'exit_condition',      False,         True),
                                (2,  'exit_at_last_decease',       'exit_condition',      False,         True),
                                (3,  'mail_to_first_subscriber',   'mail_condition',      False,         False),
                                (4,  'mail_to_broker',             'mail_condition',      False,         False),
                                (5,  'mail_to_custom_address',     'mail_condition',      True,          False),
                                (6,  'mail_to_all_subscribers',    'mail_condition',      False,         False),
                                (7,  'start_at_first_payment',     'start_condition',     False,         True),
                                (8,  'start_at_from_date',         'start_condition',     False,         True),
                                (9,  'attribute_on_payment',       'attribute_condition', False,         True),
                                (10, 'attribute_on_schedule',      'attribute_condition', False,         True), 
                                (11, 'mail_to_all_rightsholders',  'mail_condition',      False,         False),
                                (12, 'exit_at_thru_date',          'exit_condition',      False,         True),
                                (13, 'broker_relation_required',   'broker_definition',   False,         True),
                                (14, 'fiscal_deductible',          'fiscal',              False,         True),
                                ] + bank_functional_settings_by_group

functional_settings = [(number, name) for number, name, _group, _custom_clause, _exclusive in functional_settings_by_group]

functional_setting_groups = set(group for _number, _name, group, _custom_clause, _exclusive in functional_settings_by_group)

group_by_functional_setting = dict((name, group) for _number, name, group, _custom_clause, _exclusive in functional_settings_by_group )

custom_clause_by_functional_setting = dict((name, custom_clause) for _number, name, _group, custom_clause, _exclusive in functional_settings_by_group )

exclusiveness_by_functional_setting_group = dict((group, exclusive) for _number, _name, group, _custom_clause, exclusive in functional_settings_by_group )

functional_setting_availability_types = [(1, 'required'),
                                         (2, 'standard'),
                                         (3, 'optional'),
                                         (4, 'selectable'),]
                
period_types_by_granularity = dict( (granularity, month) for month, granularity in period_types )

quotation_period_types = [(1, 'daily'),
                          (2, 'weekly'),
                          (3, 'monthly'),
                          (4, 'quarterly'),
                          (5, 'illiquid'),
                          (6, 'biweekly'),
                          ]

risk_types = [(1, 'unknown'),
              (2, 'class 0'),
              (3, 'class 1'),
              (4, 'class 2'),
              (5, 'class 3'),
              (6, 'class 4'),
              (7, 'class 5'),
              (8, 'class 6'),
              ]

security_statuses = [(1, 'draft'),
                     (2, 'complete'),
                     (4, 'verified'),
                     (5, 'incomplete'), 
                     (6, 'canceled'), ]

security_roles = [(1, 'depot'),]

security_order_statuses = [(1, 'draft'),
                           (2, 'complete'),
                           (3, 'verified'),]

#                     id  name                          related_to           fulfillment_type
notification_types = [(1, 'invoice',                    'premium_schedule',  []),
                      (2, 'statement',                  'account',           []),
                      (3, 'certificate',                'premium_schedule',  ('sales', 'depot_movement', 'financed_commissions_activation', 'funded_premium_activation') ),
                      (4, 'pre-certificate',            'premium_schedule',  ('premium_attribution',)),
                      (5, 'investment-confirmation',    'premium_schedule',  ('fund_attribution',) ),
                      (6, 'account-state',              'account',           []),
                      (7, 'account-movements',          'account',           []),
                      (8, 'transaction-completion',     'transaction',       []),
                      (9, 'custom-premium-schedule-1',  'premium_schedule',  ('sales', 'depot_movement') ),
                      (10, 'credit-insurance-proposal', 'premium_schedule',  []),]

notification_types_enumeration = [(nt[0],nt[1]) for nt in notification_types]

notification_type_fulfillment_types = dict( (nt,ft) for _id, nt, _rt, ft in notification_types )

notification_acceptance_statuses = [(1, 'draft'),
                                    (2, 'accepted'),
                                    (3, 'declined') ]

commission_types = [(1,  'premium_rate_1'),
                    (2,  'financed_commissions_rate'),
                    (3,  'funded_premium_rate_1'),
                    (4,  'management_rate'),
                    (5,  'premium_fee_1'),
                    (6,  'entry_fee'),
                    (7,  'premium_rate_2'),
                    (8,  'premium_fee_2'),
                    (9,  'premium_rate_3'),
                    (10, 'premium_fee_3'),
                    (11, 'premium_rate_4'),
                    (12, 'premium_fee_4'),
                    (13, 'premium_rate_5'),
                    ]

transaction_types = [(1, 'partial_redemption'),
                     (4, 'full_redemption'),
                     (2, 'decease'),
                     (3, 'switch'),
                     (5, 'financed_switch'),
                     (6, 'profit_attribution')]

transaction_statuses = [(1, 'draft'), (2, 'complete'), (3, 'verified'), (4, 'incomplete'), (5, 'canceled')]

quotation_statuses = transaction_statuses

transaction_distribution_types = [(1, 'amount',     'Euro', 2, True),
                                  (2, 'percentage', '%',    6, False) ]

transaction_distribution_type_enumeration = [(a,b) for a,b,_c,_d, _e in transaction_distribution_types]

transaction_distribution_type_suffix = dict((b,c) for _a,b,c,_d, _e in transaction_distribution_types)

transaction_distribution_type_precision = dict((b,d) for _a,b,_c, d, _e in transaction_distribution_types)

transaction_distribution_fund_percentage_editable = dict((b,e) for _a, b, _c, _d, e in transaction_distribution_types)

security_order_line_types = [(1, 'amount',     'Euro',     2),
                             (2, 'units',      'Units',    6) ]

security_order_line_type_enumeration = [(solt_enum_id,solt_enum_name) for solt_enum_id,solt_enum_name,_solt_enum_suffix,_solt_enum_precision in security_order_line_types]

security_order_line_type_suffix = dict((solt_suffix_name,solt_suffix_suffix) for _a,solt_suffix_name,solt_suffix_suffix,_d in security_order_line_types)

security_order_line_type_precision = dict((solt_precision_name,solt_precision_precision) for _a,solt_precision_name,_c,solt_precision_precision in security_order_line_types)


# document
# context (in print preview, pprint)
# xml met lijnnummers
document_output_types = [ (0, 'open document'), 
                          (1, 'open document with variables'), 
                          (2, 'show context'), 
                          (3, 'show xml'),
                          (4, 'save as files'),
                          (5, 'translations'),]

transaction_task_types = [
    (1, 'terminate_payment_thru_date')
    ]

transaction_task_type_enumeration = transaction_task_types
