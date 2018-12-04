# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

#
# Please note that these reports are not multi-currency !!!
#

from odoo import api, fields, models, tools
import pytz, datetime
import textile


class PurchaseOrderLine(models.Model):
    _inherit = ["purchase.order.line"]
    _name = "purchase.order.line"

    @api.multi
    def write(self, vals):
        if 'x_studio_comentarios' in vals:
            super(PurchaseOrderLine, self).write(vals)
            record = self.search([('id', '=', self.id)])
            salto = "\n\n" if record.x_studio_hist_comentarios and len(record.x_studio_hist_comentarios) > 0 else ""
            x_studio_hist_comentarios = record.x_studio_hist_comentarios if record.x_studio_hist_comentarios and len(record.x_studio_hist_comentarios) > 0 else ""
            datet = fields.datetime.now(tz = pytz.timezone(self.env.user.partner_id.tz)).strftime('%d-%m-%Y %H:%M:%S') if self.env.user.partner_id.tz else fields.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            vals.update({'x_studio_hist_comentarios': textile.textile("<strong>" + datet + " (" + self.env.user.partner_id.name + ")" + ":</strong> " + vals.get('x_studio_comentarios', '') + salto) + x_studio_hist_comentarios})
        return super(PurchaseOrderLine, self).write(vals)
    
    @api.model
    def create(self, vals):
        
        record = super(PurchaseOrderLine, self).create(vals)
        if 'x_studio_comentarios' in vals:
            salto = "\n\n" if record.x_studio_hist_comentarios and len(record.x_studio_hist_comentarios) > 0 else ""
            x_studio_hist_comentarios = record.x_studio_hist_comentarios if record.x_studio_hist_comentarios and len(record.x_studio_hist_comentarios) > 0 else ""
            datet = fields.datetime.now(tz = pytz.timezone(self.env.user.partner_id.tz)).strftime('%d-%m-%Y %H:%M:%S') if self.env.user.partner_id.tz else fields.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            record.write({'x_studio_hist_comentarios': textile.textile("<strong>" + datet + " (" + self.env.user.partner_id.name + ")" + ":</strong> " + vals.get('x_studio_comentarios', '') + salto) + x_studio_hist_comentarios})
        return record

class PurchaseReport(models.Model):
    _inherit = ["purchase.report"]

    x_studio_activacin = fields.Char('Activación', readonly=True)
    x_studio_comentarios = fields.Text('Comentarios', readonly=True)
    x_studio_dias_de_atraso = fields.Integer('Dias de Atraso', readonly=True)
    x_studio_estado = fields.Char('Estado', readonly=True)
    x_studio_estado_de_los_das = fields.Char('Estado de los días', readonly=True)
    x_studio_posicion_sap = fields.Char('Posición SAP', readonly=True)
    partner_ref = fields.Char('Documento compras', readonly=True)
    qty_received = fields.Float('Cantidad recibida', digits=(16, 3), readonly=True)

    def _select(self):
        select_str = """
            WITH currency_rate as (%s)
                SELECT
                    min(l.id) as id,
                    l.x_studio_activacin,
                    l.x_studio_comentarios,
                    l.x_studio_dias_de_atraso,
                    l.x_studio_estado,
                    l.x_studio_estado_de_los_das,
                    l.x_studio_posicin_sap as x_studio_posicion_sap,
                    l.qty_received,
                    s.partner_ref as partner_ref,
                    s.date_order as date_order,
                    s.state,
                    s.date_approve,
                    s.dest_address_id,
                    s.partner_id as partner_id,
                    s.user_id as user_id,
                    s.company_id as company_id,
                    s.fiscal_position_id as fiscal_position_id,
                    l.product_id,
                    p.product_tmpl_id,
                    t.categ_id as category_id,
                    s.currency_id,
                    t.uom_id as product_uom,
                    sum(l.product_qty/u.factor*u2.factor) as unit_quantity,
                    extract(epoch from age(s.date_approve,s.date_order))/(24*60*60)::decimal(16,2) as delay,
                    extract(epoch from age(l.date_planned,s.date_order))/(24*60*60)::decimal(16,2) as delay_pass,
                    count(*) as nbr_lines,
                    sum(l.price_unit / COALESCE(cr.rate, 1.0) * l.product_qty)::decimal(16,2) as price_total,
                    avg(100.0 * (l.price_unit / COALESCE(cr.rate,1.0) * l.product_qty) / NULLIF(ip.value_float*l.product_qty/u.factor*u2.factor, 0.0))::decimal(16,2) as negociation,
                    sum(ip.value_float*l.product_qty/u.factor*u2.factor)::decimal(16,2) as price_standard,
                    (sum(l.product_qty * l.price_unit / COALESCE(cr.rate, 1.0))/NULLIF(sum(l.product_qty/u.factor*u2.factor),0.0))::decimal(16,2) as price_average,
                    partner.country_id as country_id,
                    partner.commercial_partner_id as commercial_partner_id,
                    analytic_account.id as account_analytic_id,
                    sum(p.weight * l.product_qty/u.factor*u2.factor) as weight,
                    sum(p.volume * l.product_qty/u.factor*u2.factor) as volume
        """ % self.env['res.currency']._select_companies_rates()
        return select_str

    def _from(self):
        from_str = """
            purchase_order_line l
                join purchase_order s on (l.order_id=s.id)
                join res_partner partner on s.partner_id = partner.id
                    left join product_product p on (l.product_id=p.id)
                        left join product_template t on (p.product_tmpl_id=t.id)
                        LEFT JOIN ir_property ip ON (ip.name='standard_price' AND ip.res_id=CONCAT('product.product,',p.id) AND ip.company_id=s.company_id)
                left join uom_uom u on (u.id=l.product_uom)
                left join uom_uom u2 on (u2.id=t.uom_id)
                left join account_analytic_account analytic_account on (l.account_analytic_id = analytic_account.id)
                left join currency_rate cr on (cr.currency_id = s.currency_id and
                    cr.company_id = s.company_id and
                    cr.date_start <= coalesce(s.date_order, now()) and
                    (cr.date_end is null or cr.date_end > coalesce(s.date_order, now())))
        """
        return from_str

    def _group_by(self):
        group_by_str = """
            GROUP BY
                s.company_id,
                s.user_id,
                s.partner_id,
                s.partner_ref,
                u.factor,
                s.currency_id,
                l.price_unit,
                s.date_approve,
                l.date_planned,
                l.product_uom,
                s.dest_address_id,
                s.fiscal_position_id,
                l.product_id,
                p.product_tmpl_id,
                t.categ_id,
                s.date_order,
                s.state,
                u.uom_type,
                u.category_id,
                t.uom_id,
                u.id,
                u2.factor,
                partner.country_id,
                partner.commercial_partner_id,
                analytic_account.id,
                l.x_studio_activacin,
                l.x_studio_dias_de_atraso,
                l.x_studio_estado,
                l.x_studio_estado_de_los_das,
                l.x_studio_posicin_sap,
                l.x_studio_comentarios,
                l.qty_received
        """
        return group_by_str
