import string
from re import *

class currency(float):
  def __init__(self, amount):
    self.amount = amount

  def __str__(self):
    temp = '%.2f' % self.amount
    profile = compile(r'(\d)(\d\d\d[.,])')
    while 1:
      temp, count = subn(profile, r'\1,\2', temp)
      if not count: break

    return temp

class euro(currency):
  """Little Euro formating class, inherit from currency"""

  def __str__(self):
    temp = '%.2f' % self.amount
    profile = compile(r'(\d)(\d\d\d[.,])')
    while 1:
      temp, count = subn(profile, r'\1,\2', temp)
      if not count: break

    t = string.maketrans(',.', '.,')
    temp = temp.translate(t)
    #eurosign = u'\u20ac'
    #temp += " " + eurosign

    return temp

