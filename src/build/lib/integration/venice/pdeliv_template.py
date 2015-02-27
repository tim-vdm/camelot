
pdeliv_header_desc = '''[$Global]
CliVersion=2

[$Import.SUP]
@SUP.Number=%(sup_number_length)s;1;0

[$Import.PDH]
Repeat                   =   1
@PDH.DocDate             =  %(pdh_docdate_length)s;1;DMYY
@PDH.Currency            =  %(pdh_currency_length)s;1
@PDH.Book                =  %(pdh_book_length)s;1
@PDH.Remark              =  %(pdh_remark_length)s;1
@PDH.ReferenceSup        =  %(pdh_referencesup_length)s;1
[$Assign.PDH]
@PDH.DocType             = 0

'''

pdeliv_header_data = """%(sup_number)s
%(pdh_docdate)s;%(pdh_currency)s;%(pdh_book)s;%(pdh_remark)s;%(pdh_referencesup)s\n"""

pdeliv_line_desc = ''' 
[$Import.PDD]
@PDD.ArtNum              =  %(pdd_artnum_length)s;1
@PDD.Quantity            =  %(pdd_quantity_length)s;1;2
@PDD.PriceDocC           =  %(pdd_pricedocc_length)s;1;2
'''

pdeliv_line_data = """%(pdd_artnum)s;%(pdd_quantity)s;%(pdd_pricedocc)s\n"""
