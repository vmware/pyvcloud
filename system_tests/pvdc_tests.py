# VMware vCloud Director Python SDK
# Copyright (c) 2018 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from uuid import uuid1

from pyvcloud.system_test_framework.base_test import BaseTestCase
from pyvcloud.system_test_framework.environment import CommonRoles
from pyvcloud.system_test_framework.environment import developerModeAware
from pyvcloud.system_test_framework.environment import Environment
from pyvcloud.system_test_framework.utils import \
    create_customized_vapp_from_template

from pyvcloud.vcd.client import NetworkAdapterType
from pyvcloud.vcd.client import TaskStatus
from pyvcloud.vcd.exceptions import OperationNotSupportedException
from pyvcloud.vcd.platform import Platform
from pyvcloud.vcd.vapp import VApp
from pyvcloud.vcd.vdc import VDC


class TestPVDC(BaseTestCase):
    """Test PVDC functionalities implemented in pyvcloud."""

    # All tests in this module should run as System Administrator.
    _org_client = None
    _sys_admin_client = None

    _new_vdc_name = 'org_vdc_' + str(uuid1())
    _new_vdc_href = None
    _non_existent_vdc_name = 'non_existent_org_vdc_' + str(uuid1())

    _test_runner_role = CommonRoles.VAPP_AUTHOR

    _test_vapp_name = 'test_vApp_' + str(uuid1())
    _test_vapp_first_vm_num_cpu = 2
    _test_vapp_first_vm_new_num_cpu = 4
    _test_vapp_first_vm_memory_size = 64  # MB
    _test_vapp_first_vm_new_memory_size = 128  # MB
    _test_vapp_first_vm_first_disk_size = 100  # MB
    _test_vapp_first_vm_name = 'first-vm'
    _test_vapp_first_vm_network_adapter_type = NetworkAdapterType.VMXNET3
    _test_vapp_href = None
    _test_vapp_first_vm_href = None

    _non_existent_vm_name = 'non_existent_vm_' + str(uuid1())

    def test_0000_setup(self):
        """Setup the org vdc required for the other tests in this module.

        Create one org vdc as per the configuration stated above. Test the
        method Org.create_org_vdc().

        This test passes if the vdc href is not None.
        """
        logger = Environment.get_default_logger()
        TestPVDC._sys_admin_client = Environment.get_sys_admin_client()
        org = Environment.get_test_org(TestPVDC._sys_admin_client)

        vdc_name = TestPVDC._new_vdc_name
        pvdc_name = Environment.get_test_pvdc_name()
        storage_profiles = [{
            'name': '*',
            'enabled': True,
            'units': 'MB',
            'limit': 0,
            'default': True
        }]
        vdc_resource = org.create_org_vdc(
            vdc_name,
            pvdc_name,
            storage_profiles=storage_profiles,
            uses_fast_provisioning=True,
            is_thin_provision=True)
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=vdc_resource.Tasks.Task[0])

        logger.debug('Created ovdc ' + vdc_name + '.')

        # The following contraption is required to get the non admin href of
        # the ovdc. vdc_resource contains the admin version of the href since
        # we created the ovdc as a sys admin.
        org.reload()
        for vdc in org.list_vdcs():
            if vdc.get('name').lower() == vdc_name.lower():
                TestPVDC._new_vdc_href = vdc.get('href')

        self.assertIsNotNone(TestPVDC._new_vdc_href)

    def test_0010_vm_setup(self):
        """Setup the vms required for the other tests in this module.

        Create a vApp with just one vm as per the configuration stated above.

        This test passes if the vApp and vm hrefs are not None.
        """
        logger = Environment.get_default_logger()
        TestPVDC._org_client = Environment.get_client_in_default_org(
            TestPVDC._test_runner_role)
        vdc = Environment.get_test_vdc(TestPVDC._org_client)

        logger.debug('Creating vApp ' + TestPVDC._test_vapp_name + '.')
        TestPVDC._test_vapp_href = create_customized_vapp_from_template(
            client=TestPVDC._org_client,
            vdc=vdc,
            name=TestPVDC._test_vapp_name,
            catalog_name=Environment.get_default_catalog_name(),
            template_name=Environment.get_default_template_name(),
            memory_size=TestPVDC._test_vapp_first_vm_memory_size,
            num_cpu=TestPVDC._test_vapp_first_vm_num_cpu,
            disk_size=TestPVDC._test_vapp_first_vm_first_disk_size,
            vm_name=TestPVDC._test_vapp_first_vm_name,
            nw_adapter_type=TestPVDC._test_vapp_first_vm_network_adapter_type)

        self.assertIsNotNone(TestPVDC._test_vapp_href)

        vapp = VApp(TestPVDC._org_client, href=TestPVDC._test_vapp_href)
        vm_resource = vapp.get_vm(TestPVDC._test_vapp_first_vm_name)
        TestPVDC._test_vapp_first_vm_href = vm_resource.get('href')

        self.assertIsNotNone(TestPVDC._test_vapp_first_vm_href)

    def test_0020_pvdc_setup(self):
        TestPVDC._config = Environment.get_config()
        TestPVDC._pvdc_name = self._config['pvdc']['pvdc_name']
        TestPVDC._resource_pool_names = \
            self._config['pvdc']['resource_pool_names']
        TestPVDC._vms_to_migrate = self._config['pvdc']['vms_to_migrate']
        TestPVDC._source_resource_pool = \
            self._config['pvdc']['source_resource_pool']
        TestPVDC._target_resource_pool = \
            self._config['pvdc']['target_resource_pool']

    def test_0030_attach_resource_pools(self):
        """Attach resource pool(s) to a PVDC."""
        platform = Platform(TestPVDC._sys_admin_client)
        task = platform.attach_resource_pools_to_provider_vdc(
            TestPVDC._pvdc_name,
            TestPVDC._resource_pool_names)
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=task)

    def test_0040_migrate_vms(self):
        """Migrate VM(s) from one resource pool to another."""
        platform = Platform(TestPVDC._sys_admin_client)
        task = platform.pvdc_migrate_vms(
            TestPVDC._pvdc_name,
            TestPVDC._vms_to_migrate,
            TestPVDC._source_resource_pool,
            TestPVDC._target_resource_pool)
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=task)

    def test_0045_wait(self):
        x = input("pausing for interactive test check: ")
        print("input read was: %s" % x)

    def test_0050_migrate_vms_back(self):
        """Migrate VM(s) from one resource pool to another."""
        platform = Platform(TestPVDC._sys_admin_client)
        task = platform.pvdc_migrate_vms(
            TestPVDC._pvdc_name,
            TestPVDC._vms_to_migrate,
            TestPVDC._target_resource_pool)
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=task)

    def test_0060_detach_resource_pools(self):
        """Disable and delete resource pool(s) from a PVDC."""
        platform = Platform(TestPVDC._sys_admin_client)
        task = platform.detach_resource_pools_from_provider_vdc(
            TestPVDC._pvdc_name,
            TestPVDC._resource_pool_names)
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=task)

    @developerModeAware
    def test_9997_teardown(self):
        """Delete the vApp created during setup.

        This test passes if the task for deleting the vApp succeed.
        """
        vapps_to_delete = []
        if TestPVDC._test_vapp_href is not None:
            vapps_to_delete.append(TestPVDC._test_vapp_name)

        vdc = Environment.get_test_vdc(TestPVDC._org_client)

        for vapp_name in vapps_to_delete:
            task = vdc.delete_vapp(name=vapp_name, force=True)
            result = TestPVDC._org_client.get_task_monitor().wait_for_success(
                task)
            self.assertEqual(result.get('status'), TaskStatus.SUCCESS.value)

    @developerModeAware
    def test_9998_teardown(self):
        """Test the method VDC.delete_vdc().

        Invoke the method for the vdc created by setup.

        This test passes if the task for deleting the vdc succeeds.
        """
        logger = Environment.get_default_logger()
        vdc = VDC(TestPVDC._sys_admin_client, href=TestPVDC._new_vdc_href)
        # Disable the org vdc before deleting it. In case the org vdc is
        # already disabled, we don't want the exception to leak out.
        try:
            vdc.enable_vdc(enable=False)
            logger.debug('Disabled vdc ' + TestPVDC._new_vdc_name + '.')
        except OperationNotSupportedException as e:
            logger.debug('vdc ' + TestPVDC._new_vdc_name +
                         ' is already disabled.')
            pass
        task = vdc.delete_vdc()
        TestPVDC._sys_admin_client.get_task_monitor().wait_for_success(
            task=task)
        logger.debug('Deleted vdc ' + TestPVDC._new_vdc_name + '.')

    def test_9999_cleanup(self):
        """Release all resources held by this object for testing purposes."""
        TestPVDC._org_client.logout()
        TestPVDC._sys_admin_client.logout()


if __name__ == '__main__':
    unittest.main()
