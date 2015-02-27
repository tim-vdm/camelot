import collections
import datetime
import logging
from decimal import Decimal as D
import os

from .. import test_case, test_financial

from sqlalchemy import sql, create_engine

from camelot.test.action import MockModelContext

from vfinance.connector import hyposoft
from vfinance.connector.hyposoft.import_wizard import HyposoftOptions
from vfinance.model.hypo import periodieke_verichting

LOGGER = logging.getLogger('vfinance.test.test_connector.test_hyposoft')

class HyposoftImportCase(test_case.SessionCase):
    
    source = 'excel' #'sql'

    def test_import_2012(self):
        # run the import wizard
        if self.source=='excel':
            options = os.path.join(test_financial.test_data_folder, 'hyposoft', '2012')
        else:
            hs_options = HyposoftOptions()
            engine = create_engine('mssql+pyodbc://{0.username}:{0.password}@{0.host}/{0.database}?charset=utf8&port={0.port}'.format(hs_options))
            options = engine.connect()
        action = hyposoft.HyposoftImport(source=self.source)
        generator = action.model_run(None)
        for i, step in enumerate(generator):
            if i==0:
                generator.send(options)
            LOGGER.info(unicode(step))
        ## read hyposoft repayments
        previous_period_from_test_date = datetime.date(2012,11,1)
        previous_period_thru_test_date = datetime.date(2012,11,30)
        from_test_date = datetime.date(2012,12,1)
        thru_test_date = datetime.date(2012,12,31)
        ## create repayments for 2012
        hyposoft_repayments = collections.defaultdict(list)
        for row in action.rows(options, 'Vervaldagen.xlsx', table='VERBES'):
            if int(row['VerLyn']) == 0:
                continue
            if row['VerDat'] >= from_test_date and row['VerDat'] <= thru_test_date:
                hyposoft_repayments[row['Lening']].append(row)
            # hyposoft splits the first repayment in 2 repayments
            if row['VerDat'] >= previous_period_from_test_date and row['VerDat'] <= previous_period_thru_test_date and row['VerLyn']==1 :
                hyposoft_repayments[row['Lening']].append(row)
        hyposoft_dossiers = action.rows(options, 'Lening.xlsx', table='Lening')
        hyposoft_dossier_nummer_by_key = dict((d['Uniek'], (int(d['NU_Leningsnummer']), int(d['NU_Volgnummer']))) for d in hyposoft_dossiers)
        period = periodieke_verichting.Periode(startdatum=from_test_date,
                                               einddatum=thru_test_date)
        self.session.flush()
        create_repayments = periodieke_verichting.CreateRepayments()
        period_context = MockModelContext()
        period_context.obj = period
        list(create_repayments.model_run(period_context))
        # compare repayments with hyposoft repayments
        repayments = self.session.query(periodieke_verichting.Vervaldag).filter(sql.and_(periodieke_verichting.Vervaldag.doc_date >= from_test_date,
                                                                                         periodieke_verichting.Vervaldag.doc_date <= thru_test_date)).all()
        LOGGER.info('number of repayments {0}'.format(len(repayments)))
        repayments_by_number = dict(((int(r.dossier.nummer), int(r.dossier.rank)),r) for r in repayments)
        correct = 0
        faulty = 0
        no_vfinance_repayment = 0
        large_difference = 0
        hyposoft_repayments_list = list(hyposoft_repayments.values())
        hyposoft_repayments_list.sort(key=lambda rs:hyposoft_dossier_nummer_by_key[rs[0]['Lening']])
        for hyposoft_repayments_for_loan in hyposoft_repayments_list:
            hyposoft_repayments_for_loan.sort(key=lambda r:r['VerDat'])
            last_hyposoft_repayment = hyposoft_repayments_for_loan[-1]
            dossier_number = hyposoft_dossier_nummer_by_key[last_hyposoft_repayment['Lening']]
            hyposoft_ver_kap = sum(D('%.2f'%hyposoft_repayment['VerKap']) for hyposoft_repayment in hyposoft_repayments_for_loan)
            hyposoft_ver_int = sum(D('%.2f'%hyposoft_repayment['VerInt']) for hyposoft_repayment in hyposoft_repayments_for_loan)
            hyposoft_ver_rist = sum(D('%.2f'%hyposoft_repayment['VerRist']) for hyposoft_repayment in hyposoft_repayments_for_loan)
            hyposoft_repayment_tuple = (last_hyposoft_repayment['VerDat'], hyposoft_ver_kap, hyposoft_ver_int, hyposoft_ver_rist,)
            repayment = repayments_by_number.pop(dossier_number, None)
            if repayment:
                repayment_tuple = (repayment.doc_date,
                                   repayment.kapitaal, repayment.rente, repayment.korting*-1)
                if ((hyposoft_repayment_tuple[0] == repayment_tuple[0]) and
                    (abs(hyposoft_repayment_tuple[3]-repayment_tuple[3]) < D('0.01')) and
                    (abs(hyposoft_repayment_tuple[2]-repayment_tuple[2]) < D('0.01')) and
                    (abs(hyposoft_repayment_tuple[1]-repayment_tuple[1]) < D('0.01'))
                    ):
                    correct += 1
                else:
                    faulty += 1
                    LOGGER.info( '----' )
                    LOGGER.info('dossier number {0}, hyposoft repayment {1} {2}'.format(dossier_number, last_hyposoft_repayment['Uniek'], last_hyposoft_repayment['Lening']))
                    LOGGER.info( str(hyposoft_repayment_tuple) )
                    LOGGER.info( str(repayment_tuple) )
                    if (abs(hyposoft_repayment_tuple[3]-repayment_tuple[3]) + abs(hyposoft_repayment_tuple[1]-repayment_tuple[1])) >= D('0.1'):
                        LOGGER.info('*** LARGE ***')
                        large_difference += 1
            else:
                faulty += 1
                no_vfinance_repayment += 1
                LOGGER.info('----')
                LOGGER.info('dossier number {0}'.format(dossier_number))
                LOGGER.info('no vfinance repayment found')
                LOGGER.info(str(hyposoft_repayment_tuple))
        for dossier_number, repayment in repayments_by_number.items():
            repayment_tuple = (repayment.doc_date,
                               repayment.kapitaal, repayment.rente, repayment.korting*-1)
            faulty += 1
            LOGGER.info('----' )
            LOGGER.info('dossier number {0}'.format(dossier_number))
            LOGGER.info('no hyposoft repayment found' )
            LOGGER.info(str(repayment_tuple) )
             
        LOGGER.info('----' )
        LOGGER.info('correct {0}'.format(correct))
        LOGGER.info('faulty {0}'.format(faulty))
        
        self.assertEqual( no_vfinance_repayment, 0 )
        self.assertEqual( large_difference, 0 )
        