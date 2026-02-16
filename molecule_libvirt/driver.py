#  Copyright (c) 2015-2018 Cisco Systems, Inc.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
import getpass
import grp

from importlib.metadata import version as pkg_version

from molecule import logger, util
from molecule.api import Driver

LOG = logger.get_logger(__name__)


class LibVirt(Driver):
    """
    The class responsible for managing `libvirt`_ guests.  `libvirt`_
    is ``not`` the default driver used in Molecule.

    .. code-block:: yaml

        driver:
          name: libvirt
        platforms:
          - name: instance

    .. code-block:: bash

        $ pip install 'molecule-libvirt'

    Change the options passed to the ssh client.

    .. code-block:: yaml

        driver:
          name: libvirt
          ssh_connection_options:
            - '-o ControlPath=~/.ansible/cp/%r@%h-%p'

    .. important::

        Molecule does not merge lists, when overriding the developer must
        provide all options.

    Provide a list of files Molecule will preserve, relative to the scenario
    ephemeral directory, after any ``destroy`` subcommand execution.

    .. code-block:: yaml

        driver:
          name: libvirt
          safe_files:
            - foo

    .. _`libvirt`: https://libvirt.org/
    """  # noqa

    def __init__(self, config=None):
        # Base Driver derives package name from __module__ (molecule_libvirt)
        # but our PyPI package is molecule-libvirt-ng, so override after init.
        saved_module = self.__module__
        self.__module__ = "molecule_libvirt_ng"
        super().__init__(config)
        self.__module__ = saved_module
        self._name = "libvirt"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def login_cmd_template(self):
        connection_options = " ".join(self.ssh_connection_options)

        return (
            "ssh {{address}} "
            "-l {{user}} "
            "-p {{port}} "
            "-i {{identity_file}} "
            "{}"
        ).format(connection_options)

    @property
    def default_safe_files(self):
        return [self.instance_config]

    @property
    def default_ssh_connection_options(self):
        return self._get_ssh_connection_options()

    @property
    def required_collections(self) -> dict[str, str]:
        """Return collections dict containing names and versions required."""
        return {
            "community.libvirt": "1.3.0",
            "community.crypto": "2.0.0",
            "ansible.posix": "1.0.0",
            "ansible.utils": "2.0.0",
            "community.general": "5.0.0",
        }

    def login_options(self, instance_name):
        d = {"instance": instance_name}

        return util.merge_dicts(d, self._get_instance_config(instance_name))

    def ansible_connection_options(self, instance_name):
        try:
            d = self._get_instance_config(instance_name)

            return {
                "ansible_user": d["user"],
                "ansible_host": d["address"],
                "ansible_port": d["port"],
                "ansible_private_key_file": d["identity_file"],
                "ansible_connection": "ssh",
                "ansible_ssh_common_args": " ".join(self.ssh_connection_options),
            }
        except StopIteration:
            return {}
        except IOError:
            # Instance has yet to be provisioned, therefore the
            # instance_config is not on disk.
            return {}

    def _get_instance_config(self, instance_name):
        instance_config_dict = util.safe_load_file(self._config.driver.instance_config)

        return next(
            item for item in instance_config_dict if item["instance"] == instance_name
        )

    def sanity_checks(self):
        """Warn if user doesn't belong to a libvirt group."""
        username = getpass.getuser()
        groups = [group.gr_name for group in grp.getgrall() if username in group.gr_mem]
        libvirt_groups = {"libvirt", "libvirtd"}
        if not libvirt_groups.intersection(groups):
            LOG.warning(
                "Current user doesn't belong to a libvirt group (libvirt or libvirtd). "
                "This may cause permission issues. Running "
                "'usermod --append --groups libvirt `whoami`' "
                "and 'newgrp libvirt' may fix it."
            )
