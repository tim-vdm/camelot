
sales_header_desc = """[$Global]
CliVersion=2

[$Import.CST]
@CST.Number=%(cst_number_length)s;1;0

[$Import.ASL]
@ASL.DocDate=%(asl_docdate_length)s;1;DMYY
@ASL.BookDate=%(asl_bookdate_length)s;1;DMYY
@ASL.ExpDate=%(asl_expdate_length)s;1;DMYY
@ASL.Remark=%(asl_remark_length)s;1
@ASL.TotalDocC=%(asl_totaldocc_length)s;1;2
@ASL.BaseNotSubmitDocC=%(asl_basenotsubmitdocc_length)s;1;2
@ASL.VatDueNormDocC=%(asl_vatduenormdocc_length)s;1;2
@ASL.VatDedNormDocC=%(asl_vatdednormdocc_length)s;1;2
@ASL.Book=%(asl_book_length)s;1
@ASL.Currency=%(asl_currency_length)s;1

"""

sales_header_data = """%(cst_number)s
%(asl_docdate)s;%(asl_bookdate)s;%(asl_expdate)s;%(asl_remark)s;%(asl_totaldocc)s;%(asl_basenotsubmitdocc)s;%(asl_vatduenormdocc)s;%(asl_vatdednormdocc)s;%(asl_book)s;%(asl_currency)s\n"""

credit_header_desc = """[$Global]
CliVersion=2

[$Import.CST]
@CST.Number=%(cst_number_length)s;1;0

[$Import.ASL]
@ASL.DocDate=%(asl_docdate_length)s;1;DMYY
@ASL.BookDate=%(asl_bookdate_length)s;1;DMYY
@ASL.ExpDate=%(asl_expdate_length)s;1;DMYY
@ASL.Remark=%(asl_remark_length)s;1
@ASL.TotalDocC=%(asl_totaldocc_length)s;1;2
@ASL.BaseNotSubmitDocC=%(asl_basenotsubmitdocc_length)s;1;2
@ASL.VatDueNormDocC=%(asl_vatduenormdocc_length)s;1;2
@ASL.VatDedNormDocC=%(asl_vatdednormdocc_length)s;1;2
@ASL.Book=%(asl_book_length)s;1
@ASL.Currency=%(asl_currency_length)s;1
@ASL.DocType=%(asl_doctype_length)s;1;0

"""

credit_header_data = """%(cst_number)s
%(asl_docdate)s;%(asl_bookdate)s;%(asl_expdate)s;%(asl_remark)s;%(asl_totaldocc)s;%(asl_basenotsubmitdocc)s;%(asl_vatduenormdocc)s;%(asl_vatdednormdocc)s;%(asl_book)s;%(asl_currency)s;%(asl_doctype)s\n"""


sales_line_desc = """
[$Import.ENT]
@ENT.AmountDocC=%(ent_amountdocc_length)s;1;2
@ENT.Account=%(ent_account_length)s;1
@ENT.Remark=%(ent_remark_length)s;1
"""

sales_line_data = """%(ent_amountdocc)s;%(ent_account)s;%(ent_remark)s\n"""
