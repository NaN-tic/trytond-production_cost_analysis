# This file is part production_cost_analysis module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase
from trytond.modules.company.tests import CompanyTestMixin


class ProductionCostAnalysisTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Production Cost Analysis module'
    module = 'production_cost_analysis'


del ModuleTestCase

