'''
Created on Jun 23, 2010

@author: tw55413
'''

coverage_types = [(1, 'life_insurance')]

coverage_availability_types = [(1, 'required'),
                               (2, 'standard'),
                               (3, 'optional')]

coverage_level_types = [(1, 'fixed_amount'),
                        (2, 'percentage_of_account'),
                        (3, 'percentage_of_premiums'),
                        (4, 'percentage_of_planned_premiums'),
                        (5, 'amortization_table'),
                        (6, 'surplus_amount'),
                        (7, 'decreasing_amount'),]

coverage_level_suffixes = {'fixed_amount':'Euro',
                           'percentage_of_account':'%',
                           'percentage_of_premiums':'%',
                           'percentage_of_planned_premiums':'%',
                           'surplus_amount':'Euro',
                           'amortization_table':'%',
                           'decreasing_amount': 'Euro',
                           }

payment_types = [(1, 'fixed_payment'),
                 (2, 'bullet'),
                 (3, 'fixed_capital_payment'),
                 (4, 'cummulative')]  # incorrect spelling, but used like that in hypo/mortgage_table.py

mortality_rate_table_types = [(1, 'male'),
                              (2, 'female'),
                              (3, 'male_smoker'),
                              (4, 'female_smoker'),
                              (5, 'male_non_smoker'),
                              (6, 'female_non_smoker'),
                              ]

insured_loan_interval_types = [(1,  'Every month'), 
                               (3,  'Every three months'),
                               (6,  'Every six months'), 
                               (12, 'Every year')]

insured_loan_insurance_interval_types = [(0, 'Single payment'),
                                         (1, 'Every month'), 
                                         (3, 'Every three months'),
                                         (12, 'Every year')]
