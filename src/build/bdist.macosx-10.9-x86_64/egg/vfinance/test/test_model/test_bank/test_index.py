import unittest
import datetime
from decimal import Decimal as D
import os

from camelot.core.orm import Session
from camelot.test.action import MockModelContext

index_type_data = {'name':'E',
                   'description': 'index E',   
                  }

index_jan_2007 = D('1.00')
index_feb_2007 = D('1.10')
index_mar_2007 = D('1.15')

from vfinance.model.bank.index import IndexType, IndexHistory, ReadIndex
from ...test_financial import test_data_folder

class IndexCase(unittest.TestCase):
    
    def setUp(self):
        from vfinance.utils import setup_model
        setup_model()
        self.index_type = IndexType(**index_type_data)
        self.index_jan_2007 = IndexHistory( described_by=self.index_type, 
                                            from_date=datetime.date(2007, 1, 1), 
                                            value=index_jan_2007 )
        self.index_feb_2007 = IndexHistory( described_by=self.index_type, 
                                            from_date=datetime.date(2007, 2, 1), 
                                            value=index_feb_2007 )
        self.index_mar_2007 = IndexHistory( described_by=self.index_type, 
                                            from_date=datetime.date(2007, 3, 1), 
                                            value=index_mar_2007 )
        IndexType.query.session.flush()
    
    def test_read_index(self):
        session = Session()
        index = IndexType( name = 'OLO',
                           description = 'secundaire markt lineaire obligaties',
                           url = 'http://www.nbb.be/belgostat/PresentationLinker?Presentation=CSV&prop=treeview&Dom=232&Table=169&TableId=420000033&Lang=N',
                           url_described_by = 'belgostat' )
        context = MockModelContext()
        context.obj = index
        action = ReadIndex()
        # run the import multiple times
        for x in range(2):
            for i,step in enumerate( action.model_run( context ) ):
                if i==0:
                    step.get_object().filename = os.path.join( test_data_folder, 'index.csv' )
        index_history = session.query(IndexHistory).filter_by( duration = 120,
                                                               from_date = datetime.date( 2011, 12, 31 ),
                                                               described_by = index ).all()
        self.assertEqual( len(index_history), 1 )
        self.assertEqual( index_history[0].value, D('4.3') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2012, 1, 31 ), 1*12 ),  D('0.96') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2012, 1,  1 ), 1*12 ),  D('1.60') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2013, 1,  1 ), 1*12 ),  D('0.05') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2013, 1,  1 ), 0*12 ),  D('0.05') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2013, 1,  1 ), 15*12 ), D('2.85') )
        self.assertAlmostEqual( index.get_interpolated_value( datetime.date( 2012, 10, 1 ), 11*12 ), (D('2.55') + D('3.28'))/2 )
        
