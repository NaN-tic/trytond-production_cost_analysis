# This file is part production_cost_analysis module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import production


def register():
    Pool.register(
        # production.AnalysisMoveStockMove,
        production.Production,
        production.ProductionCostAnalysis,
        production.ProductionCostAnalysisMove,
        production.ProductionCostAnalysisMoveDeviation,
        production.ProductionCostAnalysisOperation,
        production.ProductionCostAnalysisOperationDeviation,
        module='production_cost_analysis', type_='model')
