# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

from frappe.desk.doctype.desktop_icon.desktop_icon import is_desk_route, should_hide_workspace_icon
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestDesktopIcon(IntegrationTestCase):
	def test_is_desk_route_recognizes_desk_paths(self):
		self.assertTrue(is_desk_route("/desk/helpdesk"))
		self.assertFalse(is_desk_route("/helpdesk"))

	def test_should_hide_workspace_icon_for_portal_route(self):
		self.assertTrue(should_hide_workspace_icon("/helpdesk", "Helpdesk", "Helpdesk"))

	def test_should_hide_workspace_icon_for_matching_desk_workspace(self):
		self.assertTrue(should_hide_workspace_icon("/desk/helpdesk", "Helpdesk", "Helpdesk"))

	def test_should_keep_child_workspace_icon_for_non_matching_desk_workspace(self):
		self.assertFalse(
			should_hide_workspace_icon("/desk/helpdesk", "Ticket Reports", "Helpdesk")
		)
