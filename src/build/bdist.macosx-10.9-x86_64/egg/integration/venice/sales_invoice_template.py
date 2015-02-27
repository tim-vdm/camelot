
sales_invoice_header_desc = """[$Global]
CliVersion=2

[$Import.CST]
@CST.Number=%(cst_number_length)s;1;0

[$Import.SIH]
@SIH.DocType=%(sih_doctype_length)s;1;0
@SIH.Book=%(sih_book_length)s;1
@SIH.DocDate=%(sih_date_length)s;1;DMYY
@SIH.Currency=3;1
@SIH.Remark=%(sih_remark_length)s;1

"""

sales_invoice_header_data = """%(cst_number)s
%(sih_doctype)s;%(sih_book)s;%(sih_date)s;EUR;%(sih_remark)s
"""

sales_invoice_line_desc = """[$Import.SID]
@SID.ArtNum=%(sid_artnum_length)i;1
@SID.ArtDsc=%(sid_artdsc_length)i;1
@SID.PriceDocC=%(sid_pricedocc_length)i;1;2
@SID.Quantity=%(sid_quantity_length)s;1;0
"""

sales_invoice_line_data = "%(sid_artnum)s;%(sid_artdsc)s;%(sid_pricedocc)s;%(sid_quantity)s\n"
