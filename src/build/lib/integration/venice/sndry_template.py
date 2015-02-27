sndry_header_desc = """[$Global]
CliVersion=2

[$Import.SND]
@SND.BookDate=%(snd_bookdate_length)s;1;DMYY
@SND.Remark=%(snd_remark_length)s;1
@SND.Book=%(snd_book_length)s;1

"""

sndry_header_data = """%(snd_bookdate)s;%(snd_remark)s;%(snd_book)s\n"""

sndry_line_desc = """
[$Import.ENT]
@ENT.AmountDocC=%(ent_amountdocc_length)s;1;2
@ENT.Account=%(ent_account_length)s;1
@ENT.Remark=%(ent_remark_length)s;1
"""

sndry_line_data = """%(ent_amountdocc)s;%(ent_account)s;%(ent_remark)s\n"""