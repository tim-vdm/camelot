from vfinance.model.bank.constants import (bank_functional_settings_by_group,
                                           hypo_feature_offset, product_features)


#    id                         name                                         group               custom_clause, exclusive 
hypo_functional_settings_by_group = [
    (hypo_feature_offset + 1,  'flemish_region_guarantee',                   'state_guarantee',  False,         True),
    (hypo_feature_offset + 2,  'walloon_region_guarantee',                   'state_guarantee',  False,         True),
    (hypo_feature_offset + 3,  'brussels_capital_region_guarantee',          'state_guarantee',  False,         True),
    (hypo_feature_offset + 4,  'monthly_interest',                           'funding_loss',     False,         True),
    (hypo_feature_offset + 5,  'discounted_repayment',                       'funding_loss',     False,         True),
    (hypo_feature_offset + 6,  'geen_opzegging_gaande',                      'termination',      False,         True),
    (hypo_feature_offset + 7,  'opzegging_gevraagd',                          'termination',      False,         True),
    (hypo_feature_offset + 8,  'opzegging_met_advocaat',                     'termination',      False,         True),
    (hypo_feature_offset + 9,  'opzegging_met_collectieve_schuldregeling',   'termination',      False,         True),
    (hypo_feature_offset + 10, 'opzegging_met_onderling_akkoord',            'termination',      False,         True),
    ] + bank_functional_settings_by_group

hypo_functional_settings = [(number, name) for number, name, _group, _custom_clause, _exclusive in hypo_functional_settings_by_group]
hypo_group_by_functional_setting = dict((name, group) for _number, name, group, _custom_clause, _exclusive in hypo_functional_settings_by_group )

# extra feature nodig : kostenpercentage waarborgfonds, voor betaling waarborg

hypo_features = [pf[0:2] for pf in product_features if pf[0]>=hypo_feature_offset]

hypo_feature_names = [name for _number, name in hypo_features]

hypo_terugbetaling_intervallen = [ (12, 'mensualiteiten'), 
                                   (4, 'trimesterialiteiten'), 
                                   (1, 'annuiteiten') ]

hypo_types_aflossing = [ ('vast_kapitaal', 'Vast kapitaal'), 
                         ('vaste_aflossing', 'Vast bedrag'), 
                         ('bullet', 'Enkel intrest'), 
                         ('cummulatief', 'Alles op einddatum') ]

request_ranks = [(i,i) for i in range( 1, 11 )] + [(None,None), (0, 0)]
request_roles = [ (hypo_feature_offset + 1, 'borrower'),      # ontlener
                  (hypo_feature_offset + 2, 'guarantor'),     # borgsteller
                  (hypo_feature_offset + 3, 'lender_agent'),  # dossierbeheerder
                  (hypo_feature_offset + 4, 'lender_signing_agent'),  # instrumenterende notaris
                  (hypo_feature_offset + 5, 'borrower_signing_agent'),  # tussenkomende notaris
                  (hypo_feature_offset + 6, 'lender_lawyer'),
                  (hypo_feature_offset + 7, 'borrower_lawyer'),
                  (hypo_feature_offset + 8, 'guarantor_lawyer'),
                  ]
request_role_choices = [('borrower',               'Ontlener'),
                        ('guarantor',              'Borgsteller'),
                        ('lender_agent',           'Dossierbeheerder'),
                        ('lender_signing_agent',   'Instrumenterende notaris'),
                        ('borrower_signing_agent', 'Tussenkomende notaris'),
                        ('lender_lawyer',          'Advocaat maatschappij'),
                        ('borrower_lawyer',        'Advocaat ontlener'),
                        ('guarantor_lawyer',       'Advocaat borgsteller'),
                        ]

wettelijke_kaders = [ ('andere', 'Investeringskrediet'),
                      ('ar225', 'A.R. 225'),
                      ('wet4892', 'Wet 4/8/92') ]

hypotheek_states = [('draft', 'Draft'), ('complete', 'Volledige aanvraag'),
                    ('incomplete', 'Onvolledige aanvraag'),
                    ('approved', 'Goedgekeurd'), ('disapproved', 'Afgekeurd'),
                    ('send', 'Aanvaardingsbrief verstuurd'),
                    ('received', 'Aanvaardingsbrief ontvangen'),
                    ('valid', 'Akte goedgekeurd'), ('payed', 'Betaald'),
                    ('processed', 'Verleden'), ('canceled', 'Geannuleerd')]

reminder_levels = [(1, 'Normaal'), 
                   (2, 'Streng'), 
                   (3, 'Ingebrekestelling'), 
                   (4, 'Opzegging krediet')]
                            
lopend_krediet_statuses = [(1, 'lopende'), (2, 'over te nemen'), (3, 'terugbetaald')]

