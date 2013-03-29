# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Nicira, Inc.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Aaron Rosen, Nicira Networks, Inc.

import uuid

from lxml import etree
from oslo.config import cfg
import webob

from nova.api.openstack.compute.contrib import security_groups
from nova.api.openstack import xmlutil
from nova import compute
from nova import context
import nova.db
from nova import exception
from nova.network import quantumv2
from nova.network.quantumv2 import api as quantum_api
from nova.network.security_group import quantum_driver
from nova.openstack.common import jsonutils
from nova import test
from nova.tests.api.openstack.compute.contrib import test_security_groups
from nova.tests.api.openstack import fakes
from quantumclient.common import exceptions as q_exc


class TestQuantumSecurityGroupsTestCase(test.TestCase):
    def setUp(self):
        super(TestQuantumSecurityGroupsTestCase, self).setUp()
        cfg.CONF.set_override('security_group_api', 'quantum')
        self.original_client = quantumv2.get_client
        quantumv2.get_client = get_client

    def tearDown(self):
        quantumv2.get_client = self.original_client
        get_client()._reset()
        super(TestQuantumSecurityGroupsTestCase, self).tearDown()


class TestQuantumSecurityGroups(
        test_security_groups.TestSecurityGroups,
        TestQuantumSecurityGroupsTestCase):

    def _create_sg_template(self, **kwargs):
        sg = test_security_groups.security_group_template(**kwargs)
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        return self.controller.create(req, {'security_group': sg})

    def _create_network(self):
        body = {'network': {'name': 'net1'}}
        quantum = get_client()
        net = quantum.create_network(body)
        body = {'subnet': {'network_id': net['network']['id'],
                           'cidr': '10.0.0.0/24'}}
        quantum.create_subnet(body)
        return net

    def _create_port(self, **kwargs):
        body = {'port': {}}
        fields = ['security_groups', 'device_id', 'network_id',
                  'port_security_enabled']
        for field in fields:
            if field in kwargs:
                body['port'][field] = kwargs[field]
        quantum = get_client()
        return quantum.create_port(body)

    def test_create_security_group_with_no_description(self):
        # Quantum's security group descirption field is optional.
        pass

    def test_create_security_group_with_blank_name(self):
        # Quantum's security group name field is optional.
        pass

    def test_create_security_group_with_whitespace_name(self):
        # Quantum allows security group name to be whitespace.
        pass

    def test_create_security_group_with_blank_description(self):
        # Quantum's security group descirption field is optional.
        pass

    def test_create_security_group_with_whitespace_description(self):
        # Quantum allows description to be whitespace.
        pass

    def test_create_security_group_with_duplicate_name(self):
        # Quantum allows duplicate names for security groups.
        pass

    def test_create_security_group_non_string_name(self):
        # Quantum allows security group name to be non string.
        pass

    def test_create_security_group_non_string_description(self):
        # Quantum allows non string description.
        pass

    def test_create_security_group_quota_limit(self):
        # Enforced by Quantum server.
        pass

    def test_get_security_group_list(self):
        self._create_sg_template().get('security_group')
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        list_dict = self.controller.index(req)
        self.assertEquals(len(list_dict['security_groups']), 2)

    def test_get_security_group_list_all_tenants(self):
        pass

    def test_get_security_group_by_instance(self):
        sg = self._create_sg_template().get('security_group')
        net = self._create_network()
        self._create_port(
            network_id=net['network']['id'], security_groups=[sg['id']],
            device_id=test_security_groups.FAKE_UUID)
        expected = [{'rules': [], 'tenant_id': 'fake_tenant', 'id': sg['id'],
                    'name': 'test', 'description': 'test-description'}]
        self.stubs.Set(nova.db, 'instance_get',
                       test_security_groups.return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       test_security_groups.return_server_by_uuid)
        req = fakes.HTTPRequest.blank('/v2/fake/servers/%s/os-security-groups'
                                      % test_security_groups.FAKE_UUID)
        res_dict = self.server_controller.index(
            req, test_security_groups.FAKE_UUID)['security_groups']
        self.assertEquals(expected, res_dict)

    def test_get_security_group_by_id(self):
        sg = self._create_sg_template().get('security_group')
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups/%s'
                                      % sg['id'])
        res_dict = self.controller.show(req, sg['id'])
        expected = {'security_group': sg}
        self.assertEquals(res_dict, expected)

    def test_delete_security_group_by_id(self):
        sg = self._create_sg_template().get('security_group')
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups/%s' %
                                      sg['id'])
        self.controller.delete(req, sg['id'])

    def test_delete_security_group_in_use(self):
        sg = self._create_sg_template().get('security_group')
        self._create_network()
        fake_instance = {'project_id': 'fake_tenant',
                         'availability_zone': 'zone_one',
                         'security_groups': [],
                         'uuid': str(uuid.uuid4()),
                         'display_name': 'test_instance'}
        quantum = quantum_api.API()
        quantum.allocate_for_instance(context.get_admin_context(),
                                      fake_instance,
                                      security_groups=[sg['id']])

        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups/%s'
                                      % sg['id'])
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.delete,
                          req, sg['id'])

    def test_associate_non_running_instance(self):
        # Quantum does not care if the instance is running or not. When the
        # instances is detected by quantum it will push down the security
        # group policy to it.
        pass

    def test_associate_already_associated_security_group_to_instance(self):
        # Quantum security groups does not raise an error if you update a
        # port adding a security group to it that was already associated
        # to the port. This is because PUT semantics are used.
        pass

    def test_associate(self):
        sg = self._create_sg_template().get('security_group')
        net = self._create_network()
        self._create_port(
            network_id=net['network']['id'], security_groups=[sg['id']],
            device_id=test_security_groups.FAKE_UUID)

        self.stubs.Set(nova.db, 'instance_get',
                       test_security_groups.return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       test_security_groups.return_server_by_uuid)
        body = dict(addSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v2/fake/servers/1/action')
        self.manager._addSecurityGroup(req, '1', body)

    def test_disassociate_by_non_existing_security_group_name(self):
        self.stubs.Set(nova.db, 'instance_get',
                       test_security_groups.return_server)
        body = dict(removeSecurityGroup=dict(name='non-existing'))

        req = fakes.HTTPRequest.blank('/v2/fake/servers/1/action')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.manager._removeSecurityGroup, req, '1', body)

    def test_disassociate_non_running_instance(self):
        # Quantum does not care if the instance is running or not. When the
        # instances is detected by quantum it will push down the security
        # group policy to it.
        pass

    def test_disassociate_already_associated_security_group_to_instance(self):
        # Quantum security groups does not raise an error if you update a
        # port adding a security group to it that was already associated
        # to the port. This is because PUT semantics are used.
        pass

    def test_disassociate(self):
        sg = self._create_sg_template().get('security_group')
        net = self._create_network()
        self._create_port(
            network_id=net['network']['id'], security_groups=[sg['id']],
            device_id=test_security_groups.FAKE_UUID)

        self.stubs.Set(nova.db, 'instance_get',
                       test_security_groups.return_server)
        self.stubs.Set(nova.db, 'instance_get_by_uuid',
                       test_security_groups.return_server_by_uuid)
        body = dict(removeSecurityGroup=dict(name="test"))

        req = fakes.HTTPRequest.blank('/v2/fake/servers/1/action')
        self.manager._removeSecurityGroup(req, '1', body)


class TestQuantumSecurityGroupRulesTestCase(TestQuantumSecurityGroupsTestCase):
    def setUp(self):
        super(TestQuantumSecurityGroupRulesTestCase, self).setUp()
        id1 = '11111111-1111-1111-1111-111111111111'
        sg_template1 = test_security_groups.security_group_template(
            security_group_rules=[], id=id1)
        id2 = '22222222-2222-2222-2222-222222222222'
        sg_template2 = test_security_groups.security_group_template(
            security_group_rules=[], id=id2)
        self.controller_sg = security_groups.SecurityGroupController()
        quantum = get_client()
        quantum._fake_security_groups[id1] = sg_template1
        quantum._fake_security_groups[id2] = sg_template2

    def tearDown(self):
        quantumv2.get_client = self.original_client
        get_client()._reset()
        super(TestQuantumSecurityGroupsTestCase, self).tearDown()


class TestQuantumSecurityGroupRules(
        test_security_groups.TestSecurityGroupRules,
        TestQuantumSecurityGroupRulesTestCase):

    def test_create_add_existing_rules_by_cidr(self):
        sg = test_security_groups.security_group_template()
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        self.controller_sg.create(req, {'security_group': sg})
        rule = test_security_groups.security_group_rule_template(
            cidr='15.0.0.0/8', parent_group_id=self.sg2['id'])
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-group-rules')
        self.controller.create(req, {'security_group_rule': rule})
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_create_add_existing_rules_by_group_id(self):
        sg = test_security_groups.security_group_template()
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        self.controller_sg.create(req, {'security_group': sg})
        rule = test_security_groups.security_group_rule_template(
            group=self.sg1['id'], parent_group_id=self.sg2['id'])
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-group-rules')
        self.controller.create(req, {'security_group_rule': rule})
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          req, {'security_group_rule': rule})

    def test_delete(self):
        rule = test_security_groups.security_group_rule_template(
            parent_group_id=self.sg2['id'])

        req = fakes.HTTPRequest.blank('/v2/fake/os-security-group-rules')
        res_dict = self.controller.create(req, {'security_group_rule': rule})
        security_group_rule = res_dict['security_group_rule']
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-group-rules/%s'
                                      % security_group_rule['id'])
        self.controller.delete(req, security_group_rule['id'])

    def test_create_rule_quota_limit(self):
        # Enforced by quantum
        pass


class TestQuantumSecurityGroupsXMLDeserializer(
        test_security_groups.TestSecurityGroupXMLDeserializer,
        TestQuantumSecurityGroupsTestCase):
    pass


class TestQuantumSecurityGroupsXMLSerializer(
        test_security_groups.TestSecurityGroupXMLSerializer,
        TestQuantumSecurityGroupsTestCase):
    pass


class TestQuantumSecurityGroupsOutputTest(TestQuantumSecurityGroupsTestCase):
    content_type = 'application/json'

    def setUp(self):
        super(TestQuantumSecurityGroupsOutputTest, self).setUp()
        fakes.stub_out_nw_api(self.stubs)
        self.controller = security_groups.SecurityGroupController()
        self.stubs.Set(compute.api.API, 'get',
                       test_security_groups.fake_compute_get)
        self.stubs.Set(compute.api.API, 'get_all',
                       test_security_groups.fake_compute_get_all)
        self.stubs.Set(compute.api.API, 'create',
                       test_security_groups.fake_compute_create)
        self.stubs.Set(quantum_driver.SecurityGroupAPI,
                       'get_instance_security_groups',
                       test_security_groups.fake_get_instance_security_groups)
        self.flags(
            osapi_compute_extension=[
                'nova.api.openstack.compute.contrib.select_extensions'],
            osapi_compute_ext_list=['Security_groups'])

    def _make_request(self, url, body=None):
        req = webob.Request.blank(url)
        if body:
            req.method = 'POST'
            req.body = self._encode_body(body)
        req.content_type = self.content_type
        req.headers['Accept'] = self.content_type
        res = req.get_response(fakes.wsgi_app(init_only=('servers',)))
        return res

    def _encode_body(self, body):
        return jsonutils.dumps(body)

    def _get_server(self, body):
        return jsonutils.loads(body).get('server')

    def _get_servers(self, body):
        return jsonutils.loads(body).get('servers')

    def _get_groups(self, server):
        return server.get('security_groups')

    def test_create(self):
        url = '/v2/fake/servers'
        image_uuid = 'c905cedb-7281-47e4-8a62-f26bc5fc4c77'
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        security_groups = [{'name': 'fake-2-0'}, {'name': 'fake-2-1'}]
        for security_group in security_groups:
            sg = test_security_groups.security_group_template(
                name=security_group['name'])
            self.controller.create(req, {'security_group': sg})

        server = dict(name='server_test', imageRef=image_uuid, flavorRef=2,
                      security_groups=security_groups)
        res = self._make_request(url, {'server': server})
        self.assertEqual(res.status_int, 202)
        server = self._get_server(res.body)
        for i, group in enumerate(self._get_groups(server)):
            name = 'fake-2-%s' % i
            self.assertEqual(group.get('name'), name)

    def test_create_server_get_default_security_group(self):
        url = '/v2/fake/servers'
        image_uuid = 'c905cedb-7281-47e4-8a62-f26bc5fc4c77'
        server = dict(name='server_test', imageRef=image_uuid, flavorRef=2)
        res = self._make_request(url, {'server': server})
        self.assertEqual(res.status_int, 202)
        server = self._get_server(res.body)
        group = self._get_groups(server)[0]
        self.assertEquals(group.get('name'), 'default')

    def test_show(self):
        url = '/v2/fake/servers'
        image_uuid = 'c905cedb-7281-47e4-8a62-f26bc5fc4c77'
        req = fakes.HTTPRequest.blank('/v2/fake/os-security-groups')
        security_groups = [{'name': 'fake-2-0'}, {'name': 'fake-2-1'}]
        for security_group in security_groups:
            sg = test_security_groups.security_group_template(
                name=security_group['name'])
            self.controller.create(req, {'security_group': sg})
        server = dict(name='server_test', imageRef=image_uuid, flavorRef=2,
                      security_groups=security_groups)

        res = self._make_request(url, {'server': server})
        self.assertEqual(res.status_int, 202)
        server = self._get_server(res.body)
        for i, group in enumerate(self._get_groups(server)):
            name = 'fake-2-%s' % i
            self.assertEqual(group.get('name'), name)

    def test_detail(self):
        url = '/v2/fake/servers/detail'
        res = self._make_request(url)

        self.assertEqual(res.status_int, 200)
        for i, server in enumerate(self._get_servers(res.body)):
            for j, group in enumerate(self._get_groups(server)):
                name = 'fake-%s-%s' % (i, j)
                self.assertEqual(group.get('name'), name)

    def test_no_instance_passthrough_404(self):

        def fake_compute_get(*args, **kwargs):
            raise exception.InstanceNotFound(instance_id='fake')

        self.stubs.Set(compute.api.API, 'get', fake_compute_get)
        url = '/v2/fake/servers/70f6db34-de8d-4fbd-aafb-4065bdfa6115'
        res = self._make_request(url)

        self.assertEqual(res.status_int, 404)


class TestQuantumSecurityGroupsOutputXMLTest(
        TestQuantumSecurityGroupsOutputTest):

    content_type = 'application/xml'

    class MinimalCreateServerTemplate(xmlutil.TemplateBuilder):
        def construct(self):
            root = xmlutil.TemplateElement('server', selector='server')
            root.set('name')
            root.set('id')
            root.set('imageRef')
            root.set('flavorRef')
            elem = xmlutil.SubTemplateElement(root, 'security_groups')
            sg = xmlutil.SubTemplateElement(elem, 'security_group',
                                            selector='security_groups')
            sg.set('name')
            return xmlutil.MasterTemplate(root, 1,
                                          nsmap={None: xmlutil.XMLNS_V11})

    def _encode_body(self, body):
        serializer = self.MinimalCreateServerTemplate()
        return serializer.serialize(body)

    def _get_server(self, body):
        return etree.XML(body)

    def _get_servers(self, body):
        return etree.XML(body).getchildren()

    def _get_groups(self, server):
        # NOTE(vish): we are adding security groups without an extension
        #             namespace so we don't break people using the existing
        #             functionality, but that means we need to use find with
        #             the existing server namespace.
        namespace = server.nsmap[None]
        return server.find('{%s}security_groups' % namespace).getchildren()


def get_client(context=None, admin=False):
    return MockClient()


class MockClient(object):

    # Needs to be global to survive multiple calls to get_client.
    _fake_security_groups = {}
    _fake_ports = {}
    _fake_networks = {}
    _fake_subnets = {}
    _fake_security_group_rules = {}

    def __init__(self):
        # add default security group
        if not len(self._fake_security_groups):
            ret = {'name': 'default', 'description': 'default',
                   'tenant_id': 'fake_tenant', 'security_group_rules': [],
                   'id': str(uuid.uuid4())}
            self._fake_security_groups[ret['id']] = ret

    def _reset(self):
        self._fake_security_groups.clear()
        self._fake_ports.clear()
        self._fake_networks.clear()
        self._fake_subnets.clear()
        self._fake_security_group_rules.clear()

    def create_security_group(self, body=None):
        s = body.get('security_group')
        if len(s.get('name')) > 255 or len(s.get('description')) > 255:
            msg = 'Security Group name great than 255'
            raise q_exc.QuantumClientException(message=msg, status_code=401)
        ret = {'name': s.get('name'), 'description': s.get('description'),
               'tenant_id': 'fake_tenant', 'security_group_rules': [],
               'id': str(uuid.uuid4())}

        self._fake_security_groups[ret['id']] = ret
        return {'security_group': ret}

    def create_network(self, body):
        n = body.get('network')
        ret = {'status': 'ACTIVE', 'subnets': [], 'name': n.get('name'),
               'admin_state_up': n.get('admin_state_up', True),
               'tenant_id': 'fake_tenant',
               'port_security_enabled': n.get('port_security_enabled', True),
               'id': str(uuid.uuid4())}
        self._fake_networks[ret['id']] = ret
        return {'network': ret}

    def create_subnet(self, body):
        s = body.get('subnet')
        try:
            net = self._fake_networks[s.get('network_id')]
        except KeyError:
            msg = 'Network %s not found' % s.get('network_id')
            raise q_exc.QuantumClientException(message=msg, status_code=404)
        ret = {'name': s.get('name'), 'network_id': s.get('network_id'),
               'tenant_id': 'fake_tenant', 'cidr': s.get('cidr'),
               'id': str(uuid.uuid4()), 'gateway_ip': '10.0.0.1'}
        net['subnets'].append(ret['id'])
        self._fake_networks[net['id']] = net
        self._fake_subnets[ret['id']] = ret
        return {'subnet': ret}

    def create_port(self, body):
        p = body.get('port')
        ret = {'status': 'ACTIVE', 'id': str(uuid.uuid4()),
               'mac_address': p.get('mac_address', 'fa:16:3e:b8:f5:fb'),
               'port_security_enabled': p.get('port_security_enabled'),
               'device_id': p.get('device_id', str(uuid.uuid4())),
               'security_groups': p.get('security_groups', [])}

        fields = ['network_id', 'security_groups', 'admin_state_up']
        for field in fields:
            ret[field] = p.get(field)

        network = self._fake_networks[p['network_id']]
        if not ret['port_security_enabled']:
            ret['port_security_enabled'] = network['port_security_enabled']
        if network['subnets']:
            ret['fixed_ips'] = [{'subnet_id': network['subnets'][0],
                                 'ip_address': '10.0.0.1'}]
        if not ret['security_groups']:
            for security_group in self._fake_security_groups.values():
                if security_group['name'] == 'default':
                    ret['security_groups'] = [security_group['id']]
                    break
        self._fake_ports[ret['id']] = ret
        return {'port': ret}

    def create_security_group_rule(self, body):
        # does not handle bulk case so just picks rule[0]
        r = body.get('security_group_rules')[0]
        fields = ['direction', 'protocol', 'port_range_min', 'port_range_max',
                  'ethertype', 'remote_ip_prefix', 'tenant_id',
                  'security_group_id', 'remote_group_id']
        ret = {}
        for field in fields:
            ret[field] = r.get(field)
        ret['id'] = str(uuid.uuid4())
        self._fake_security_group_rules[ret['id']] = ret
        return {'security_group_rules': [ret]}

    def show_security_group(self, security_group, **_params):
        try:
            sg = self._fake_security_groups[security_group]
        except KeyError:
            msg = 'Security Group %s not found' % security_group
            raise q_exc.QuantumClientException(message=msg, status_code=404)
        for security_group_rule in self._fake_security_group_rules.values():
            if security_group_rule['security_group_id'] == sg['id']:
                sg['security_group_rules'].append(security_group_rule)

        return {'security_group': sg}

    def show_security_group_rule(self, security_group_rule, **_params):
        try:
            return {'security_group_rule':
                    self._fake_security_group_rules[security_group_rule]}
        except KeyError:
            msg = 'Security Group rule %s not found' % security_group_rule
            raise q_exc.QuantumClientException(message=msg, status_code=404)

    def show_network(self, network, **_params):
        try:
            return {'network':
                    self._fake_networks[network]}
        except KeyError:
            msg = 'Network %s not found' % network
            raise q_exc.QuantumClientException(message=msg, status_code=404)

    def show_port(self, port, **_params):
        try:
            return {'port':
                    self._fake_ports[port]}
        except KeyError:
            msg = 'Port %s not found' % port
            raise q_exc.QuantumClientException(message=msg, status_code=404)

    def show_subnet(self, subnet, **_params):
        try:
            return {'subnet':
                    self._fake_subnets[subnet]}
        except KeyError:
            msg = 'Port %s not found' % subnet
            raise q_exc.QuantumClientException(message=msg, status_code=404)

    def list_security_groups(self, **_params):
        ret = []
        for security_group in self._fake_security_groups.values():
            names = _params.get('name')
            if names:
                if not isinstance(names, list):
                    names = [names]
                for name in names:
                    if security_group.get('name') == name:
                        ret.append(security_group)
            ids = _params.get('id')
            if ids:
                if not isinstance(ids, list):
                    ids = [ids]
                for id in ids:
                    if security_group.get('id') == id:
                        ret.append(security_group)
            elif not (names or ids):
                ret.append(security_group)
        return {'security_groups': ret}

    def list_networks(self, **_params):
        return {'networks':
                [network for network in self._fake_networks.values()]}

    def list_ports(self, **_params):
        ret = []
        device_id = _params.get('device_id')
        for port in self._fake_ports.values():
            if device_id:
                if device_id == port['device_id']:
                    ret.append(port)
            else:
                ret.append(port)
        return {'ports': ret}

    def list_subnets(self, **_params):
        return {'subnets':
                [subnet for subnet in self._fake_subnets.values()]}

    def list_floatingips(self, **_params):
        return {'floatingips': []}

    def delete_security_group(self, security_group):
        self.show_security_group(security_group)
        ports = self.list_ports()
        for port in ports.get('ports'):
            for sg_port in port['security_groups']:
                if sg_port == security_group:
                    msg = ('Unable to delete Security group %s in use'
                           % security_group)
                    raise q_exc.QuantumClientException(message=msg,
                                                       status_code=409)
        del self._fake_security_groups[security_group]

    def delete_security_group_rule(self, security_group_rule):
        self.show_security_group_rule(security_group_rule)
        del self._fake_security_group_rules[security_group_rule]

    def delete_network(self, network):
        self.show_network(network)
        self._check_ports_on_network(network)
        for subnet in self._fake_subnets.values():
            if subnet['network_id'] == network:
                del self._fake_subnets[subnet['id']]
        del self._fake_networks[network]

    def delete_subnet(self, subnet):
        subnet = self.show_subnet(subnet).get('subnet')
        self._check_ports_on_network(subnet['network_id'])
        del self._fake_subnet[subnet]

    def delete_port(self, port):
        self.show_port(port)
        del self._fake_ports[port]

    def update_port(self, port, body=None):
        self.show_port(port)
        self._fake_ports[port].update(body['port'])
        return {'port': self._fake_ports[port]}

    def list_extensions(self, **_parms):
        return {'extensions': []}

    def _check_ports_on_network(self, network):
        ports = self.list_ports()
        for port in ports:
            if port['network_id'] == network:
                msg = ('Unable to complete operation on network %s. There is '
                       'one or more ports still in use on the network'
                       % network)
            raise q_exc.QuantumClientException(message=msg, status_code=409)
