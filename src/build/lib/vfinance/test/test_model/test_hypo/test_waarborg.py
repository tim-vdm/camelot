from ... import test_case

onroerend_goed_data = {
  'straat':'Beliardstraat 3',
  'postcode':'1000',
  'gemeente':'Etterbeek',
  'bestemming':'handelspand',
  'type':'rijwoning',
  'vrijwillige_verkoop':150000,
  'venale_verkoopwaarde':130000,
  'gedwongen_verkoop':100000,
}

waarborg_data = {
  'bedrag':80000.0,
  'saldo':60000.0,
  'aanhorigheden':10.0,
}

bijkomende_waarborg_data = {
  'type':'aandelen',
  'name':'10000 aandelen Fortis',
  'waarde':5000,
}

from vfinance.model.hypo.hypotheek import TeHypothekerenGoed, Waarborg, BijkomendeWaarborg

class WaarborgCase(test_case.SessionCase):
 
    def setUp(self):
        super(WaarborgCase, self).setUp()
        from vfinance.utils import setup_model
        setup_model()
        self.goed = TeHypothekerenGoed(**onroerend_goed_data)
        self.bijkomende_waarborg = BijkomendeWaarborg(**bijkomende_waarborg_data)
        self.waarborg = Waarborg(te_hypothekeren_goed_id=self.goed, **waarborg_data)
        TeHypothekerenGoed.query.session.flush()
    
    def testWaarborgTeHypothekerenGoed(self):
        self.assertEqual( len(self.goed.waarborgen), 1 )
