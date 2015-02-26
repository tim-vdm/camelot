# -*- coding: utf-8 -*-
import datetime
import hashlib


def calculate_proposal(proposal):
    return {
        'premium_schedule__1__amount': '1.0',
        'premium_schedule__2__amount': None,
    }


def create_agreement_code(proposal):
    amounts = calculate_proposal(proposal)
    values = {
        'code': "000/0000/00000",
        'signature': hashlib.sha256(str(datetime.datetime.now())).hexdigest()[32:]
    }

    values.update(amounts)

    return values
