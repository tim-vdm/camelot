'''
@author: michael
'''
from functools import wraps
import itertools
from math import floor
from decimal import Decimal as D

import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, OneToMany, ManyToOne, using_options
from camelot.admin.action import list_action
from camelot.admin.validator.entity_validator import EntityValidator
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
from camelot.admin.action import CallMethod

from camelot.core.qt import Qt

from vfinance.admin.vfinanceadmin import VfinanceAdmin

def interpolate(method):
    """interpolation decorator (provides linear interpolation between integer values)
    """
    
    @wraps(method)  # to preserve names in stacktraces etc.
    def new_method(cls, x, *args):
        intpart  = floor(x)
        fracpart = x - intpart
        if fracpart == 0:
            return method(cls, x, *args)
        else:
            f_low  = method(cls, intpart, *args)
            f_high = method(cls, intpart + 1, *args)
            return f_low + fracpart*(f_high - f_low) 

    return new_method

class MortalityRateTableCalculator():

    def __init__(self, k, s, g, c, w):
        self.k = k
        self.s = s
        self.g = g
        self.c = c
        self.w = w   # end of mortality table (normally at age 119 (see technical note))

    # x = age in years (same for all other methods)
    @interpolate
    def fl_x(self, x):
        if x > self.w:
            return 0.0
        return self.k*(self.s**x)*(self.g**(self.c**x))

    def male_table():
        k = float('1000450.59')
        s = float('0.999106875782')
        g = float('0.999549614043')
        c = float('1.103798111448')
        w = 119
        return MortalityRateTableCalculator(k, s, g, c, w)
    male_table = staticmethod(male_table)

    def female_table():
        k = float('1000097.39')
        s = float('0.999257048061')
        g = float('0.999902624311')
        c = float('1.122')
        w = 119
        return MortalityRateTableCalculator(k, s, g, c, w)
    female_table = staticmethod(female_table)

############################################

class MortalityRateTableEntryValidator(EntityValidator):

    def objectValidity(self, entry):
        from camelot.core.utils import ugettext
        messages = super(MortalityRateTableEntryValidator,self).objectValidity(entry)
        if entry.year < 0:
            messages.append(ugettext("Year should always be greater or equal than zero."))
        if entry.l_x < 0:
            messages.append(ugettext("L_x should always be greater or equal than zero."))
        return messages

class MortalityRateTableEntry(Entity):
    using_options(tablename='insurance_mortality_rate_table_entry')
    year = schema.Column( sqlalchemy.types.Integer(), default = 0, nullable=False, index = True )
    l_x  = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=9), default = 0, nullable=False)
    used_in = ManyToOne('MortalityRateTable', required = True, ondelete = 'cascade', onupdate = 'cascade')

    class Admin(EntityAdmin):
        verbose_name = _('Mortality Rate Table Entry')
        list_display = ['year', 'l_x']
        validator = MortalityRateTableEntryValidator
        
        def get_related_toolbar_actions( self, toolbar_area, direction ):
            actions = EntityAdmin.get_related_toolbar_actions( self, toolbar_area, direction )
            if toolbar_area == Qt.RightToolBarArea and direction == 'onetomany':
                actions.append( list_action.ImportFromFile() )
            return actions


class MortalityRateTableValidator(EntityValidator):

    def objectValidity(self, table):
        messages = super(MortalityRateTableValidator,self).objectValidity(table)
        entries = [e for e in table.with_entries]
        entries.sort(key=lambda x:x.year)
        if len(entries):
            prevyear = entries[0].year - 1
            prev_l_x = entries[0].l_x
            monotonicity_error = False
            for entry in entries:
                if (entry.year - prevyear) != 1:
                    messages.append("Error: no data for year " + str(entry.year-1) + ".")
                if (not monotonicity_error) and (entry.l_x > prev_l_x):
                    messages.append("Error: l_x for year " + str(entry.year) + " greater than for year " + str(entry.year-1) + ". l_x should decrease monotonically as a function of time.")
                    monotonicity_error = True
                prevyear = entry.year
                prev_l_x = entry.l_x
        return messages

class MortalityRateTable(Entity):
    using_options(tablename='insurance_mortality_rate_table')
    name = schema.Column(sqlalchemy.types.Unicode(255), nullable=False, index=True)
    with_entries = OneToMany('MortalityRateTableEntry', cascade='all, delete, delete-orphan')
    used_in = OneToMany('vfinance.model.insurance.product.InsuranceCoverageAvailabilityMortalityRateTable', cascade='all, delete, delete-orphan')

    @transaction
    def generate_table(self, table_calc):
        # delete all current entries
        to_delete = [e for e in self.with_entries]
        for e in to_delete:
            self.with_entries.remove(e)
            e.delete()
        # generate new entries        
        for i in range(0, table_calc.w+1):
            entry = MortalityRateTableEntry(year = i, l_x = D(str(table_calc.fl_x(i))))
            self.with_entries.append(entry)

    def generate_male_table(self):
        self.generate_table(MortalityRateTableCalculator.male_table())

    def generate_female_table(self):
        self.generate_table(MortalityRateTableCalculator.female_table())

    def __unicode__(self):
        return self.name
    
    class Admin(VfinanceAdmin):
        verbose_name = _('Mortality Rate Table')
        list_display = ['name']    
        form_display = ['name', 'with_entries']
        # icons are optional ;-)
        form_actions = [CallMethod( _('Generate Default Male Table    '), lambda obj:obj.generate_male_table() ),
                        CallMethod( _('Generate Default Female Table'), lambda obj:obj.generate_female_table() )]
        validator = MortalityRateTableValidator


class MortalityTableBase( object ):
    """
    MortalityTable base class that contains all functions except l_x (should be provided by a descendant).
    """

    def fp_x(self, x):
        """
        probability that a life aged x will still be alive at age x+1
        
        :param x: age in years
        """
        return 1 - self.fq_x(x)

    def fq_x(self, x):
        """
        probability that a life aged x will be dead at age x+1
        
        :param x: age in years
        """
        return (self.fl_x(x) - self.fl_x(x+1))/self.fl_x(x)

    def ftp_x(self, t, x):
        """
        probability that a life aged x will stil be alive at age x+t
        
        :param t: time in years
        :param x: age in years
        """
        return 1 - self.ftq_x(t, x)

    def futq_x(self, u, t, x):
        """
        probability that a life aged x will survive to age x+u, but die before age x+u+t
        
        :param u: time in years
        :param t: time in years
        :param x: age in years
        """
        return self.ftp_x(u, x) - self.ftp_x(u+t, x)

    def ftq_x(self, t, x):
        """
        probability that a life aged x will be dead at age x+t
        
        :param t: time in years
        :param x: age in years
        """
        fl_x = self.fl_x(x)
        return (fl_x - self.fl_x(x+t))/fl_x

    @staticmethod
    def add_surmortalities(*args):
        """
        Function that returns the sum of all surmortalities, according to (for 2 arguments): result = (1+surm1)*(1+surm2) - 1.
        
        :param *args: any number of surmortalities in % (i.e. pass in 1.5 for 150%)
        """
        result = 1
        for surm in args:
            result *= (1 + surm)
        return result - 1

class MortalityTable( MortalityTableBase ):
    """
    Combine MortalityRateTable (model) with all calculation functions of MortalityTableBase.
    Provides surmortalities based on recalculated table.
    """

    def __init__(self, mortality_rate_table, surmortality = 0):
        # register name
        self.id = mortality_rate_table.id
        self.name = mortality_rate_table.name
        self.surmortality = surmortality
        # put all entries in table in dict
        self.l_x = {}
        for entry in mortality_rate_table.with_entries:
            self.l_x[entry.year] = float( str( entry.l_x ) )
        # add one zero entry (after last entry: all zeros)
        w = max( itertools.chain( self.l_x, [0] ) )  # highest year in dict
        self.l_x[w+1] = 0.0
        # recalc table to take into account surmortality
        if surmortality != 0:
            self._recalculate_table(surmortality)

    def _recalculate_table(self, surmortality):
        """
        calculate all q's and scale with surmortality
        """
        q = {}
        min_lx = min( itertools.chain( self.l_x, [200] ) )
        max_lx = max( itertools.chain( self.l_x, [0] ) )
        for i in range( min_lx, max_lx - 1):
            try:
                q[i] = min( (1 + surmortality)*(self.l_x[i] - self.l_x[i+1])/self.l_x[i], 1.0 )
            except ArithmeticError: # division by zero
                q[i] = 1.0
        # based on q's, recalculate table
        for i in range( min_lx, max_lx - 1):
            self.l_x[i+1]  = self.l_x[i] - q[i]*self.l_x[i]
        
    @interpolate
    def fl_x(self, x):
        try:
            return self.l_x[x]
        except KeyError:
            return 1.0

class MockMortalityTable( MortalityTableBase ):
    """Use to test the functions of MortalityTableBase by
    providing an implementation of l_x that returns a fixed
    sets of values
    """
    
    def __init__(self, l_x=lambda _x:1000, surmortality = 0):
        """
        :param l_x: a function returning l for an integer x
        """
        self._l_x = l_x
        # call base constructor
        MortalityTableBase.__init__(self, surmortality)
        
    @interpolate
    def fl_x(self, x):
        return self._l_x(x)
        
class MortalityTable2Lives(object):
    """
    Same as MortalityTable, but for contracts on two heads.
    This class should be used with contracts on two heads where the coverage exists until the first death.
    """
    
    def __init__(self, mortality_rate_table1, mortality_rate_table2, surmortality1 = 0, surmortality2 = 0):
        self.mt1 = MortalityTable(mortality_rate_table1, surmortality1)
        self.mt2 = MortalityTable(mortality_rate_table2, surmortality2)

    def fp_xy(self, x, y):
        """
        Probability that a life aged x and a life aged y will both still be alive after 1 year, i.e. at ages x+1 and y+1
        
        :param x: age in years of first person
        :param y: age in years of second person
        """
        return self.mt1.fp_x(x)*self.mt2.fp_x(y)

    def fq_xy(self, x, y):
        """
        Probability that a life aged x and a life aged y will not both still be alive after 1 year, i.e. at ages x+1 and y+1.
        In other words, the probabilty that at least one of them has died after 1 year.

        :param x: age in years of first person
        :param y: age in years of second person
        """
        return 1 - self.fp_xy(x, y)

    # ftp_x: probability that a life aged x will still be alive at age x+t
    def ftp_xy(self, t, x, y):
        return self.mt1.ftp_x(t, x)*self.mt2.ftp_x(t, y)

    def futq_xy(self, u, t, x, y):
        """
        Probability that a life aged x and a life aged y will both survive for u years,and at least one of them will die before
        u+t years have passed. 

        :param u: time in years
        :param t: time in years
        :param x: age in years of first person
        :param y: age in years of second person
        """
        return self.ftp_xy(u, x, y) - self.ftp_xy(u+t, x, y)

    def ftq_xy(self, t, x, y):
        """
        Probability that a life aged x and a life aged y will not both still be alive after t years, i.e. at ages x+t and y+t.
        In other words, the probabilty that at least one of them has died after t years.

        :param t: time in years
        :param x: age in years of first person
        :param y: age in years of second person
        """
        return 1 - self.ftp_xy(t, x, y)
