from odoo.tests import common


class TestXmjj(common.TransactionCase):
    def setUp(self):
        super(TestXmjj, self).setUp()
        self.ModelDepartment = self.env['cwgk.department']
        self.ModelEmployee = self.env['cwgk.employee']
        self.ModelXmjj = self.env['cwgk.xmjj.master']
        self.ModelXmjjDetail = self.env['cwgk.xmjj.detail']

    def test_department(self):
        rs = self.ModelDepartment.create({
            'name': '部门'
        })
        self.assertIsNotNone(rs)

    def test_all(self):
        depart1 = self.ModelDepartment.create({
            'name': '部门'
        })
        d1 = self.ModelDepartment.browse(depart1.id).read()
        self.assertEqual('部门', d1[0]['name'])
        depart2 = self.ModelDepartment.create({
            'name': '项目组',
            'parent_id': depart1.id
        })
        rs1 = self.ModelDepartment.search_read(domain=[('id', '=', depart2.id)])
        self.assertEqual('项目组', rs1[0]['name'])
        emp1 = self.ModelEmployee.create({
            'name': '张三',
            'department_id': depart2.id
        })
        rs2 = self.ModelEmployee.search_read(domain=[('id', '=', emp1.id)])
        self.assertEqual('张三', rs2[0]['name'])
        self.assertTupleEqual(('张三', depart2.id, '部门'), (rs2[0]['name'],
                                                         rs2[0]['department_id'][0], rs2[0]['parent_department_name']))
        xmjj1 = self.ModelXmjj.create({
            'department_id': depart1.id,
            'jj_month': 201906,
            'detail_ids': [
                [0, '', {
                    'employee_id': emp1.id,
                    'jj': 10
                }]
            ]
        })
        rs = self.ModelXmjj.search_read(domain=[('id', '=', xmjj1.id)])
        self.assertDictEqual({'department_id': (depart1.id, '部门'), 'jj_month': 201906},
                             {'department_id': rs[0]['department_id'], 'jj_month': rs[0]['jj_month']})
        rs2 = self.ModelXmjjDetail.search_read(domain=[('id', 'in', rs[0]['detail_ids'])])
        self.assertEqual(1, len(rs2))
        self.assertDictEqual({'master_id': xmjj1.id, 'employee_id': (emp1.id, '张三'), 'employee_name': '张三'},
                             {'master_id': rs2[0]['master_id'][0], 'employee_id': rs2[0]['employee_id'],
                              'employee_name': rs2[0]['employee_name']})
