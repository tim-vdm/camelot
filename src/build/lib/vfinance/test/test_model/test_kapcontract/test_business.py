import unittest
from datetime import date

from integration.tinyerp.convenience import months_between_dates

from vfinance.model.kapcontract import contract_business as cb

class MonthsBetweenDatesCase(unittest.TestCase):
    
    def test_one(self):
        self.assertEqual(1, months_between_dates(date(year=2007, month=1, day=27), date(year=2007, month=2, day=28)))
        
    def test_two(self):
        self.assertEqual(1, months_between_dates(date(year=2007, month=1, day=28), date(year=2007, month=2, day=28)))

class VervaldagenCase(unittest.TestCase):
    
    def setUp(self):
        self.start_periode = date(year=2007, month=10, day=1)
        self.eind_periode = date(year=2007, month=10, day=31)
        self.startdatum = date(year=1987, month=6, day=1)
        
    def test_betaaldatum(self):
        result = cb.betaaldatum( self.startdatum, 25 )
        self.assertEqual( result, date(year=2012, month=6, day=1) )
        
    def test_vervaldag_in_periode_afgelopen(self):
        result = cb.vervaldag_in_periode(self.start_periode, self.eind_periode, self.startdatum, 5, 12)
        self.assertFalse(result)
        
    def test_vervaldag_in_periode_1(self):
        result = cb.vervaldag_in_periode(self.start_periode, self.eind_periode, self.startdatum, 25, 12)
        self.assertTrue(result)
        
    def test_vervaldag_in_periode_2(self):
        result = cb.vervaldag_in_periode(self.start_periode, self.eind_periode, self.startdatum, 25, 1)
        self.assertFalse(result)
        
    def test_aantal_betalingen(self):
        looptijd = 24
        am = cb.aantal_verlopen_maanden(date.today(), 'reduced', date(year=2007, month=4, day=1), date(year=1985, month=4, day=1), date(year=1983, month=4, day=1), looptijd)
        result = cb.aantal_betalingen('reduced', am, 4, looptijd)
        self.assertEqual(result, 8)
        
    def test_aantal_betalingen_dossier_1040022(self):
        start_datum = date(year=1983, month=1, day=1)
        today = date(year=2008, month=1, day=8)
        looptijd = 25
        am = cb.aantal_verlopen_maanden(today, 'processed', today, today, start_datum, looptijd)
        self.assertEqual(am, 300)
        ab = cb.aantal_betalingen('processed', am, 4, looptijd)
        self.assertEqual(ab, 100)
        
    def test_aantal_betalingen_dossier_1044704(self):
        start_datum = date(year=1998, month=10, day=1)
        today = date(year=2008, month=1, day=8)
        looptijd = 25
        am = cb.aantal_verlopen_maanden(today, 'processed', today, today, start_datum, looptijd)
        self.assertEqual(am, 111)
        ab = cb.aantal_betalingen('processed', am, 4, looptijd)
        self.assertEqual(ab, 38)

class TheoretischSaldoCase(unittest.TestCase):
    
    def setUp(self):
        self.today = date(year=2007, month=11, day=30)
        
    def test_theoretisch_saldo_contract_1045167(self):
        start_datum = date(day=1, month=2, year=2004)
        result = cb.theoretisch_saldo(self.today, 'processed', self.today, self.today, start_datum, 25, 4, 50)
        self.assertEqual(result, 800)

class MathematischeReserveCase(unittest.TestCase):
    
    def setUp(self):
        self.today = date(year=2007, month=7, day=30)
        
    def test_aantal_verlopen_maanden(self):
        afkoop_datum = date(year=1965, month=10, day=1)
        aantal = cb.aantal_verlopen_maanden(self.today, 'buyout', afkoop_datum, afkoop_datum, date(year=1945, month=10, day=1), 20)
        self.assertEqual(aantal, 240)
        
    def test_aantal_verlopen_maanden_2(self):
        afkoop_datum = date(year=2002, month=12, day=1)
        looptijd = 25
        aantal = cb.aantal_verlopen_maanden(self.today, 'buyout', afkoop_datum, afkoop_datum, date(year=2000, month=6, day=1), looptijd)
        self.assertEqual(aantal, 30)
        waarde = cb.afkoop_waarde('processed', 25, aantal, 3718.40, 0)
        self.assertAlmostEqual(waarde, 136.06, 1)

class TabellenCase(unittest.TestCase):
    
    def testAfkoopwaarde(self):
        self.assertEqual( cb.afkoop_waarde('processed', 25, 84, 1, 0), 0.16 )
        
    def testReductiewaarde(self):
        self.assertEqual( cb.reductie_waarde(25, 83, 1), 0.33 )
        
    def testTheoretischewaarde(self):
        self.assertEqual( cb.theoretische_waarde(25, 84, 1), 0.17 )
        
    def testMathematischeReserveOpDatum(self):
        kapitaal = 15000
        looptijd = 25
        status = 'processed'
        datum = date(year=2007,month=12,day=31)
        start_datum = date(year=2005,month=1,day=1)
        am = cb.aantal_verlopen_maanden(datum, status, datum, datum, start_datum, looptijd)
        self.assertEqual(am, 35)
        mr = cb.mathematische_reserve(datum, status, datum, datum, start_datum, datum, looptijd, kapitaal)
        self.assertAlmostEqual( mr, 1091.82, 10 )
        
    def testMathematischeReserveOpDatum2(self):
        """contract nummer 1044849"""
        kapitaal = 6197.34
        looptijd = 25
        status = 'reduced'
        datum = date(year=2007,month=12,day=31)
        #Het contract is nog niet afgekocht
        afkoop_datum = datum
        reductie_datum = date(year=2005,month=7,day=1)
        start_datum = date(year=2000,month=2,day=1)
        betaal_datum = cb.betaaldatum(start_datum, looptijd)
        amr = cb.aantal_maanden_reductie(datum, afkoop_datum, reductie_datum, betaal_datum)
        cb.aantal_verlopen_maanden(datum, status, afkoop_datum, reductie_datum, start_datum, looptijd)
        #self.assertEqual(am, 65)
        self.assertEqual(amr, 29)
        mr = cb.mathematische_reserve(datum, status, afkoop_datum, reductie_datum, start_datum, betaal_datum, looptijd, kapitaal)
        self.assertAlmostEqual( mr, 820.87, 2 )
        
    def testMathematischeReserveOpDatum3(self):
        """contract nummer 1036185"""
        kapitaal = 4957.87
        looptijd = 25
        status = 'reduced'
        datum = date(year=2006,month=12,day=31)
        start_datum = date(year=1977,month=1,day=1)
        reductie_datum = date(year=1980, month=4, day=1)
        am = cb.aantal_verlopen_maanden(datum, status, datum, reductie_datum, start_datum, looptijd)
        self.assertEqual(am, 39)
        tw = cb.theoretische_waarde(looptijd, am, kapitaal)
        self.assertAlmostEqual(tw, 0.058740*kapitaal, 2)
        betaal_datum = cb.betaaldatum(start_datum, looptijd)
        self.assertEqual(betaal_datum, date(year=2002,month=1,day=1))
        mr = cb.mathematische_reserve(datum, status, datum, reductie_datum, start_datum, betaal_datum, looptijd, kapitaal)
        self.assertAlmostEqual(mr, 658.41, 2)
        
    def testMathematischeReserveOpDatum4(self):
        """contract nummer 1039152
        """
        kapitaal = 6197.34
        looptijd = 25
        status = 'buyout'
        datum = date(year=2006,month=12,day=31)
        start_datum = date(year=1981,month=6,day=1)
        reductie_datum = datum
        am = cb.aantal_verlopen_maanden(datum, status, datum, reductie_datum, start_datum, looptijd)
        self.assertEqual(am, 300)
        betaal_datum = cb.betaaldatum(start_datum, looptijd)
        self.assertEqual(betaal_datum, date(year=2006,month=6,day=1))
        mr = cb.mathematische_reserve(datum, status, betaal_datum, reductie_datum, start_datum, betaal_datum, looptijd, kapitaal)
        #self.assertAlmostEqual(mr, 6197.34, 2)
        self.assertAlmostEqual(mr, 0, 2)