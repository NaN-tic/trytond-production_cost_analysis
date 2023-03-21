# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.product import price_digits
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    production_cost_analysis = fields.Many2One('production.cost.analysis',
        'Production Cost Analysis', readonly=True)

    def create_production_cost_analysis(self):
        pool = Pool()
        CostAnalysis = pool.get('production.cost.analysis')

        if self.production_cost_analysis:
            return self.production_cost_analysis
        cost = CostAnalysis()
        cost.number = self.number
        cost.inputs_costs = []
        cost.outputs_costs = []
        cost.product = self.product
        cost.cost_plan = self.cost_plan
        cost.list_price = self.product.list_price or 0
        cost.cost_price = (self.cost_plan and self.cost_plan.cost_price
            or self.product.cost_price or 0)
        return cost

    @classmethod
    def wait(cls, productions):
        CostAnalysis = Pool().get('production.cost.analysis')
        costs = []
        super().wait(productions)
        for production in productions:
            cost = production.production_cost_analysis
            if not cost:
                cost = production.create_production_cost_analysis()
                production.production_cost_analysis = cost
                production.save()
            costs.append(cost)
        CostAnalysis.create_cost_moves(costs)

    @classmethod
    def done(cls, productions):
        super().done(productions)
        costanalysis = Pool().get('production.cost.analysis')
        costs = set([x.production_cost_analysis for x in productions
            if x.production_cost_analysis])
        if costs:
            costanalysis.create_cost_moves(costs)
        for cost in costs:
            cost.calc_deviation()

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('production_cost_analysis', None)
        return super().copy(productions, default=default)

    def _split_production(self, number, quantity, uom, input2qty, output2qty):
        pool = Pool()
        CostAnalysis = pool.get('production.cost.analysis')

        production = super()._split_production(number, quantity, uom,
            input2qty, output2qty)
        if not self.production_cost_analysis:
            self.production_cost_analysis = \
                    self.create_production_cost_analysis()
            self.save()

        cost = self.production_cost_analysis
        production.production_cost_analysis = self.production_cost_analysis
        production.save()
        CostAnalysis.create_cost_moves([cost])
        return production


class ProductionCostAnalysis(ModelSQL, ModelView):
    'Production Cost Analysis'
    __name__ = 'production.cost.analysis'

    company = fields.Many2One('company.company', 'Company', required=True,
        readonly=True)
    number = fields.Char('Number', readonly=True)
    product = fields.Many2One('product.product', 'Product',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'},
        readonly=True)
    cost_price = fields.Numeric("Cost Price", digits=price_digits,
        readonly=True)
    list_price = fields.Numeric('List Price', digits=price_digits,
        readonly=True)
    cost_plan = fields.Many2One('product.cost.plan', 'Cost Plan',
        readonly=True)
    gross_margin = fields.Function(fields.Numeric('Gross Margin',
        digits=price_digits), 'get_calc_fields')
    gross_teoric_margin = fields.Function(fields.Numeric(
        'Teoric Gross Margin', digits=price_digits), 'get_calc_fields')
    gross_total = fields.Function(fields.Numeric(
        'Gross Total', digits=price_digits), 'get_calc_fields')
    gross_teoric_total = fields.Function(fields.Numeric(
        'Teoric Gross Total', digits=price_digits), 'get_calc_fields')
    price_hour = fields.Function(fields.Numeric(
        'Price Hour', digits=price_digits), 'get_calc_fields')
    teoric_price_hour = fields.Function(fields.Numeric(
        'Teoric Price Hour', digits=price_digits), 'get_calc_fields')
    outputs_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move', None, 'Teoric Output Costs',
        domain=[('type_', '=', 'out'), ('kind', '=', 'teoric')]),
        'on_change_with_outputs_costs')
    real_outputs_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move', None, 'Real Output Costs',
        domain=[('type_', '=', 'out'), ('kind', '=', 'real')]),
        'on_change_with_real_outputs_costs', )
    inputs_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move', None, 'Teoric Inputs Costs'),
        'on_change_with_inputs_costs')
    real_inputs_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move', None, 'Real Inputs Costs',
        domain=[('type_', '=', 'in'), ('kind', '=', 'real')]),
        'on_change_with_real_inputs_costs')
    costs = fields.One2Many('production.cost.analysis.move',
        'analysis', 'Cost Moves')
    output_deviation_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move.deviation', None,
        'Output Deviation Cost',
        domain=[('type_', '=', 'out')]),
        'on_change_with_output_deviation_costs')
    input_deviation_costs = fields.Function(fields.One2Many(
        'production.cost.analysis.move.deviation', None,
        'Incoming Deviation Cost',
        domain=[('type_', '=', 'in')]),
        'on_change_with_input_deviation_costs')
    deviation_costs = fields.One2Many(
        'production.cost.analysis.move.deviation', 'analysis',
        'Deviation Cost')
    operation_costs = fields.One2Many('production.cost.analysis.operation',
        'analysis', 'Operations')
    operation_teoric_costs = fields.Function(
        fields.One2Many('production.cost.analysis.operation',
        None, 'Teoric Operations'), 'on_change_with_operation_teoric_costs')
    operation_real_costs = fields.Function(
            fields.One2Many('production.cost.analysis.operation',
        None, 'Real Operations'), 'on_change_with_operation_real_costs')
    operation_deviation_costs = fields.One2Many(
        'production.cost.analysis.operation.deviation',
        'analysis', 'Deviation Operations')
    inputs = fields.Function(fields.One2Many('stock.move', None, 'Inputs'),
        'get_inputs')
    outputs = fields.Function(fields.One2Many('stock.move', None, 'Outputs'),
        'get_outputs')
    operations = fields.Function(fields.One2Many('production.operation', None,
        'Operations'), 'get_operations')
    productions = fields.One2Many('production',
        'production_cost_analysis', 'Productions')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'update': {}
        })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('costs')
    def on_change_with_inputs_costs(self, name=None):
        return [x.id for x in self.costs
             if x.type_ == 'in' and x.kind == 'teoric'
                and not x.stock_move]

    @fields.depends('costs')
    def on_change_with_outputs_costs(self, name=None):
        return [x.id for x in self.costs
            if x.type_ == 'out' and x.kind == 'teoric'
                and not x.stock_move]

    @fields.depends('costs')
    def on_change_with_real_outputs_costs(self, name=None):
        return [x.id for x in self.costs
            if x.type_ == 'out' and x.kind == 'real'
                and not x.stock_move]

    @fields.depends('costs')
    def on_change_with_real_inputs_costs(self, name=None):
        return [x.id for x in self.costs
                if x.type_ == 'in' and x.kind == 'real' and not x.stock_move]

    @fields.depends('costs', 'deviation_costs')
    def on_change_with_output_deviation_costs(self, name=None):
        return [x.id for x in self.deviation_costs if x.type_ == 'out']

    @fields.depends('costs', 'deviation_costs')
    def on_change_with_input_deviation_costs(self, name=None):
        return [x.id for x in self.deviation_costs if x.type_ == 'in']

    def get_inputs(self, name=None):
        inputs = []
        for production in self.productions:
            inputs += [x.id for x in production.inputs]
        return inputs

    def get_outputs(self, name=None):
        outputs = []
        for production in self.productions:
            outputs += [x.id for x in production.outputs]
        return outputs

    def get_operations(self, name=None):
        operations = []
        for production in self.productions:
            operations += [x.id for x in production.operations]
        return operations

    @fields.depends('operation_costs')
    def on_change_with_operation_teoric_costs(self, name=None):
        return [x.id for x in self.operation_costs
            if x.kind == 'teoric' and not x.operation]

    @fields.depends('operation_costs')
    def on_change_with_operation_real_costs(self, name=None):
        return [x.id for x in self.operation_costs
            if x.kind == 'real' and not x.operation]

    @classmethod
    def get_calc_fields(cls, costs, names):
        fields = {'gross_margin', 'gross_teoric_margin', 'gross_total',
            'gross_teoric_total', 'price_hour', 'teoric_price_hour', }

        res = {}
        for f in fields:
            res[f] = {}
        for cost in costs:
            for f in fields:
                res[f][cost.id] = 0
            real_output_qty = sum([x.quantity
                for x in cost.real_outputs_costs])  # TODO: compute_qty
            real_output_price = 0
            if real_output_qty:
                real_output_price = float(sum([float(x.unit_price) * x.quantity
                    for x in cost.real_outputs_costs])) / real_output_qty

            res['gross_margin'][cost.id] = Decimal(float(cost.list_price or 0)
                - (real_output_price or 0)
                ).quantize(Decimal(10) ** -price_digits[1])

            res['gross_teoric_margin'][cost.id] = Decimal((cost.list_price or 0)
                - (cost.cost_price or 0)).quantize(Decimal(10) ** -price_digits[1])
            res['gross_total'][cost.id] = (
                float(res['gross_margin'][cost.id]) * real_output_qty)
            res['gross_teoric_total'][cost.id] = (
                float(res['gross_teoric_margin'][cost.id]) * real_output_qty)

            top_total = sum([x.quantity for x in cost.operation_teoric_costs])
            rop_total = sum([x.quantity for x in cost.operation_real_costs])

            if rop_total:
                res['price_hour'][cost.id] = (
                    res['gross_total'][cost.id]/rop_total)
            if top_total:
                res['teoric_price_hour'][cost.id] = (
                    res['gross_teoric_total'][cost.id]/top_total)

        return res

    def update_output_teoric(self, output_moves):
        MoveCost = Pool().get('production.cost.analysis.move')
        to_delete = [x for x in self.costs if x.type_ == 'out'
            and x.kind == 'teoric' and x.stock_move in output_moves]
        move_cost = self.get_move_costs(output_moves, 'out', 'teoric')
        MoveCost.delete(to_delete)
        MoveCost.save(move_cost)

    def get_move_costs(self, moves, type_, kind):
        pool = Pool()
        MoveCost = pool.get('production.cost.analysis.move')
        res = dict(((x.stock_move, x.type_, x.kind), x)
            for x in self.costs if x.stock_move)
        result = []
        for move in moves:
            move_cost = res.get((move, type_, kind))
            if move_cost:
                continue
            cost_price = float(move.cost_price or move.product.cost_price or 0)
            move_cost = MoveCost()
            move_cost.analysis = self
            move_cost.cost_price = Decimal(cost_price).quantize(
                Decimal(10) ** -price_digits[1])
            move_cost.quantity = round(move.quantity, 2)
            move_cost.total = Decimal(cost_price * move.quantity).quantize(
                Decimal(10) ** -price_digits[1])
            move_cost.stock_move = move
            move_cost.product = move.product
            move_cost.type_ = type_
            move_cost.uom = move.product.default_uom
            move_cost.unit_price = move.unit_price or move.product.list_price
            if type == 'output':
                product = move.product
                production = move.production
                hours = [x.quantity for x in production.operations]
                move_cost.unit_price = move.quantity * (product.list_price -
                    product.cost_price) / hours
            move_cost.kind = kind
            result.append(move_cost)
        return result

    def calc_group(self, type_, kind):
        pool = Pool()
        MoveCost = pool.get('production.cost.analysis.move')
        to_delete = [x for x in self.costs if not x.stock_move
            and x.type_ == type_ and x.kind == kind]
        res = {}

        for move in self.costs:
            if not move.stock_move or move.type_ != type_ or move.kind != kind:
                continue

            smove = move.stock_move
            production = smove.production_input or smove.production_output

            if (type_ == 'in' and kind == 'teoric' and production and
                production.state not in  ('draft', 'waiting')) or (
                (type_ == 'out' and kind == 'teoric' and production and
                    production.state not in  ('draft', 'waiting'))):
                pass
            else:
                move.quantity = move.stock_move.quantity
                move.save()

            move_cost = res.get(move.product)
            if not move_cost:
                move_cost = MoveCost()
                move_cost.analysis = self
                move_cost.product = move.product
                move_cost.type_ = type_
                move_cost.kind = kind
                move_cost.uom = move.product.default_uom
                move_cost.unit_price = move.unit_price
                move_cost.cost_price = move.cost_price
                move_cost.quantity = move.quantity
                move_cost.total = move.total
                res[move.product] = move_cost
            else:
                move_cost.cost_price = Decimal(
                    (float(move.cost_price) * move.quantity
                    + float(move_cost.cost_price) * move_cost.quantity) / (
                        move.quantity + move_cost.quantity)).quantize(
                            Decimal(10) ** -price_digits[1])
                move_cost.quantity = round(move_cost.quantity + move.quantity, 2)
                if move_cost.quantity + move.quantity != 0:
                    move_cost.unit_price = Decimal((
                        float(move.unit_price) * move.quantity +
                        float(move_cost.unit_price) * move_cost.quantity) / (
                            move_cost.quantity + move.quantity)).quantize(
                                Decimal(10) ** -price_digits[1])
                move_cost.total += move.total

        MoveCost.delete(to_delete)
        return res.values()

    def calc_group_operation(self, kind):
        pool = Pool()
        OperationCost = pool.get('production.cost.analysis.operation')
        to_delete = [x for x in self.operation_costs if not x.operation
            and x.kind == kind]
        res = {}
        for op in self.operation_costs:
            if not op.operation or op.kind != kind:
                continue

            key = (op.operation_type, op.work_center_category)
            if key not in res:
                op_cost = OperationCost()
                op_cost.analysis = self
                op_cost.operation_type = op.operation_type
                op_cost.work_center_category = op.work_center_category
                op_cost.uom = op.uom
                op_cost.quantity = op.quantity
                op_cost.unit_price = op.unit_price
                op_cost.total = op.total
                op_cost.kind = kind
                res[key] = op_cost
            else:
                qty = op.quantity + op_cost.quantity
                if not qty:
                    op_cost.unit_price = 0
                else:
                    op_cost.unit_price = Decimal(
                        float(op.total + op_cost.total) / qty).quantize(
                            Decimal(10) ** -price_digits[1])
                op_cost.quantity = round(op_cost.quantity + op.quantity, 2)
                op_cost.total += op.total

        OperationCost.delete(to_delete)
        return res.values()

    @classmethod
    def create_cost_moves(cls, costs):
        MoveCost = Pool().get('production.cost.analysis.move')
        OperationCost = Pool().get('production.cost.analysis.operation')
        cost_operations = []
        cost_moves = []

        for cost in costs:
            cost_moves = cost.calc_teoric_moves()
            cost_moves += cost.calc_real_moves()
            cost_operations += cost.create_operation_cost_moves('teoric')
            cost_operations += cost.create_operation_cost_moves('real')
        MoveCost.save(cost_moves)
        OperationCost.save(cost_operations)
        cls.update(costs)

    def create_operation_cost_moves(self, kind):
        OperationCost = Pool().get('production.cost.analysis.operation')
        res = []
        productions = []
        if kind == 'teoric':
            productions = [x for x in self.productions if x.state in (
                'waiting', 'assigned')]
        elif kind == 'real':
            productions = [x for x in self.productions if x.state == 'done']
        else:
            return []
        costs = [x for x in self.operation_costs if x.kind == kind]
        operations = [x.operation for x in costs]
        for prod in productions:
            for op in prod.operations:
                if op in operations or (op.work_center_category and
                        op.work_center_category.type != 'employee'):
                    continue

                op_cost = OperationCost()
                op_cost.analysis = self
                op_cost.operation_type = op.operation_type
                op_cost.work_center_category = op.work_center_category
                op_cost.uom = op.work_center_category.uom
                op_cost.quantity = op.total_quantity
                op_cost.total = Decimal(op.total_quantity
                    * float(op.work_center_category.cost_price)).quantize(
                        Decimal(10) ** -2)
                op_cost.kind = kind
                op_cost.operation = op
                op_cost.unit_price = op.work_center_category.cost_price
                res.append(op_cost)
        return res

    @classmethod
    def update(cls, costs):
        MoveCost = Pool().get('production.cost.analysis.move')
        OperationCost = Pool().get('production.cost.analysis.operation')
        cost_groups = []
        cost_operations = []

        for cost in costs:
            cost_groups += cost.calc_group('in', 'teoric')
            cost_groups += cost.calc_group('out', 'teoric')
            cost_groups += cost.calc_group('in', 'real')
            cost_groups += cost.calc_group('out', 'real')
            cost_operations += cost.calc_group_operation('teoric')
            cost_operations += cost.calc_group_operation('real')
        MoveCost.save(cost_groups)
        OperationCost.save(cost_operations)
        for cost in costs:
            cost.calc_deviation()


    def calc_teoric_moves(self):
        inputs = []
        outputs = []
        cost_moves = []
        for prod in self.productions:
            if prod.state not in ('draft', 'waiting', 'assigned'):
                continue
            inputs += prod.inputs
            outputs += prod.outputs

        cost_moves = self.get_move_costs(inputs, 'in', 'teoric')
        cost_moves += self.get_move_costs(outputs, 'out', 'teoric')
        return cost_moves

    def calc_real_moves(self):
        inputs = []
        outputs = []
        for prod in self.productions:
            if prod.state != 'done':
                continue
            inputs += prod.inputs
            outputs += prod.outputs
        cost_moves = self.get_move_costs(inputs, 'in', 'real')
        cost_moves += self.get_move_costs(outputs, 'out', 'real')
        return cost_moves

    def get_deviation_op(self, teoric, real):
        pool = Pool()
        OpCostDev = pool.get('production.cost.analysis.operation.deviation')

        dev = OpCostDev()
        dev.analysis = self

        if teoric and not real:
            dev.quantity = teoric.quantity
            dev.quantity_deviation = round(-teoric.quantity, 2)
            dev.total = teoric.total
            dev.total_deviation = -teoric.total
            dev.unit_price = teoric.unit_price
            dev.unit_price_deviation = -(teoric.unit_price or 0)
            dev.uom = teoric.uom
            dev.operation_type = teoric.operation_type
            dev.work_center_category = teoric.work_center_category
        elif real and not teoric:
            dev.quantity = 0
            dev.quantity_deviation = real.quantity
            dev.total = 0
            dev.total_deviation = real.total
            dev.unit_price = 0
            dev.unit_price_deviation = real.unit_price
            dev.uom = real.uom
            dev.operation_type = real.operation_type
            dev.work_center_category = real.work_center_category
        else:
            dev.quantity = real.quantity
            dev.quantity_deviation = round(teoric.quantity - real.quantity,2)
            dev.uom = teoric.uom
            dev.total = real.total
            dev.total_deviation = Decimal((teoric.total or 0)
                - (real.total or 0)).quantize(
                Decimal(10) ** -price_digits[1])
            dev.unit_price = real.unit_price
            dev.unit_price_deviation = ((real.unit_price or 0)
                - (teoric.unit_price or 0))
            dev.operation_type = teoric.operation_type
            dev.work_center_category = teoric.work_center_category
        return dev

    def get_deviation_move(self, teoric, real, type_):
        pool = Pool()
        MoveCostDev = pool.get('production.cost.analysis.move.deviation')

        dev = MoveCostDev()
        dev.type_ = type_
        dev.analysis = self

        if teoric and not real:
            dev.quantity = teoric.quantity
            dev.quantity_deviation = round(-teoric.quantity, 2)
            dev.total = teoric.total
            dev.total_deviation = -teoric.total
            dev.unit_price = teoric.unit_price
            dev.unit_price_deviation = -teoric.unit_price
            dev.uom = teoric.uom
            dev.product = teoric.product
        elif real and not teoric:
            dev.quantity = 0
            dev.quantity_deviation = round(real.quantity, 2)
            dev.total = 0
            dev.total_deviation = real.total
            dev.unit_price = 0
            dev.unit_price_deviation = real.unit_price
            dev.uom = real.uom
            dev.product = real.product
        else:
            dev.product = real.product
            dev.quantity = real.quantity
            dev.quantity_deviation = round(real.quantity - teoric.quantity, 2)
            dev.uom = teoric.uom
            dev.total = real.total
            dev.total_deviation = Decimal(real.total - teoric.total).quantize(
                Decimal(10) ** -price_digits[1])
            dev.unit_price = teoric.unit_price
            dev.unit_price_deviation = real.unit_price - teoric.unit_price

        if (dev.total_deviation == 0 and dev.quantity_deviation == 0 and
                dev.unit_price_deviation == 0):
            return None

        return dev

    def calc_deviation(self):
        pool = Pool()
        MoveCostDev = pool.get('production.cost.analysis.move.deviation')
        OpCostDev = pool.get('production.cost.analysis.operation.deviation')
        to_delete = [x for x in self.deviation_costs]
        to_delete_operation = [x for x in self.operation_deviation_costs]

        to_save = []
        op_to_save = []
        for type_ in ('in', 'out'):
            teoric_moves = dict((x.product, x) for x in self.costs
                if x.type_ == type_ and x.kind == 'teoric'
                    and not x.stock_move)
            real_moves = dict((x.product, x) for x in self.costs
                if x.type_ == type_ and x.kind == 'real' and not x.stock_move)

            for tmove in teoric_moves.values():
                if tmove.product not in real_moves:
                    dev = self.get_deviation_move(tmove, None, type_)
                    if dev:
                        to_save.append(dev)
                    continue
                rmove = real_moves[tmove.product]
                if not (rmove.cost_price != tmove.cost_price
                        or rmove.quantity != tmove.quantity):
                    continue

                dev = self.get_deviation_move(tmove, rmove, type_)
                if dev:
                    to_save.append(dev)

            for rmove in real_moves.values():
                if rmove.product not in teoric_moves:
                    dev = self.get_deviation_move(None, rmove, type_)
                    if dev:
                        to_save.append(dev)

        teoric_op = dict(
            ((x.operation_type, x.work_center_category), x)
            for x in self.operation_costs
            if x.kind == 'teoric' and not x.operation)
        real_op = dict(
            ((x.operation_type, x.work_center_category), x)
            for x in self.operation_costs
            if x.kind == 'real' and not x.operation)

        for top in teoric_op.values():
            key = (top.operation_type, top.work_center_category)
            if key not in real_op:
                dev = self.get_deviation_op(top, None)
                op_to_save.append(dev)
                continue
            rop = real_op[key]
            if (rop.quantity == top.quantity):
                continue

            dev = self.get_deviation_op(top, rop)
            op_to_save.append(dev)

        for key, rop in real_op.items():
            if key not in teoric_op:
                dev = self.get_deviation_op(None, rop)
                op_to_save.append(dev)

        MoveCostDev.delete(to_delete)
        MoveCostDev.save(to_save)
        OpCostDev.delete(to_delete_operation)
        OpCostDev.save(op_to_save)


class ProductionCostAnalysisMove(ModelSQL, ModelView):
    'Production Cost Analysis Move'
    __name__ = 'production.cost.analysis.move'

    analysis = fields.Many2One('production.cost.analysis',
        'Base Production', required=True)
    type_ = fields.Selection([('in', 'In'), ('out', 'Out')], 'Type')
    kind = fields.Selection([('real', 'Real'), ('teoric', 'Teoric')], 'Kind')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, readonly=True, depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom', required=True)
    cost_price = fields.Numeric('Cost Price', digits=price_digits,
        readonly=True)
    total = fields.Numeric('Total', digits=price_digits,
        readonly=True)
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
            readonly=True)
    stock_move = fields.Many2One('stock.move', 'Stock Move',
        ondelete='CASCADE')

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class ProductionCostAnalysisMoveDeviation(ModelSQL, ModelView):
    'Production Cost Analysis Move deviation'
    __name__ = 'production.cost.analysis.move.deviation'

    analysis = fields.Many2One('production.cost.analysis',
        'Base Production', required=True)
    type_ = fields.Selection([('in', 'In'), ('out', 'Out')], 'Type')
    product = fields.Many2One('product.product', 'Product', required=True,
        readonly=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, readonly=True, depends=['unit_digits'])
    quantity_deviation = fields.Float('Quantity Deviation',
        digits=(16, Eval('unit_digits', 2)), required=True, readonly=True,
        depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom', required=True)
    total = fields.Numeric('Total', digits=price_digits,
        readonly=True)
    total_deviation = fields.Numeric('Total Deviation', digits=price_digits,
        readonly=True)
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        readonly=True)
    unit_price_deviation = fields.Numeric('Unit Price Deviation',
        digits=price_digits, readonly=True)

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class ProductionCostAnalysisOperation(ModelSQL, ModelView):
    'Production Cost Analysis Operation'
    __name__ = 'production.cost.analysis.operation'

    analysis = fields.Many2One('production.cost.analysis',
        'Base Production', required=True)
    operation_type = fields.Many2One('production.operation.type',
        'Operation Type', required=True, readonly=True)
    work_center_category = fields.Many2One('production.work_center.category',
        'Work Center Category', required=True, readonly=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, readonly=True, depends=['unit_digits'])
    total = fields.Numeric('Total', digits=price_digits,
        readonly=True)
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
            readonly=True)
    kind = fields.Selection([('real', 'Real'), ('teoric', 'Teoric')], 'Kind')
    operation = fields.Many2One('production.operation', 'Operation',
        ondelete='CASCADE')

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class ProductionCostAnalysisOperationDeviation(ModelSQL, ModelView):
    'Production Cost Analysis Operation Deviation'
    __name__ = 'production.cost.analysis.operation.deviation'

    analysis = fields.Many2One('production.cost.analysis',
        'Base Production', required=True)
    operation_type = fields.Many2One('production.operation.type',
        'Operation Type', required=True, readonly=True)
    work_center_category = fields.Many2One('production.work_center.category',
        'Work Center Category', required=True, readonly=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, readonly=True, depends=['unit_digits'])
    quantity_deviation = fields.Float('Quantity Deviation',
        digits=(16, Eval('unit_digits', 2)), required=True, readonly=True,
        depends=['unit_digits'])
    total = fields.Numeric('Total', digits=price_digits,
        readonly=True)
    total_deviation = fields.Numeric('Total Deviation', digits=price_digits,
                readonly=True)
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
            readonly=True)
    unit_price_deviation = fields.Numeric('Unit Price Deviation',
        digits=price_digits, readonly=True)

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2
