import frappe
from frappe.tests import IntegrationTestCase

from raven.api.chat import build_member_entry, get_channel_members

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Raven User"]


class TestBuildMemberEntry(IntegrationTestCase):
	"""Pure-function checks for the row builder `get_channel_members` relies on."""

	def test_none_user_obj_returns_none(self):
		# No matching Raven User record for this member — the caller must be able
		# to skip it instead of indexing into None.
		self.assertIsNone(build_member_entry(None, {}))

	def test_matching_user_obj_returns_entry(self):
		user_obj = frappe._dict(
			name="test1@example.com",
			full_name="Test One",
			user_image=None,
			first_name="Test",
			type="User",
			availability_status="Available",
		)
		entry = build_member_entry(user_obj, {"is_admin": 1, "name": "RCM-1"})
		self.assertEqual(entry["name"], "test1@example.com")
		self.assertEqual(entry["is_admin"], 1)
		self.assertEqual(entry["channel_member_name"], "RCM-1")

	def test_missing_channel_member_fields_default(self):
		# The Open-channel branch passes `{}` when there's no explicit Raven
		# Channel Member row (every workspace member is implicitly a member).
		user_obj = frappe._dict(
			name="test1@example.com",
			full_name="Test One",
			user_image=None,
			first_name="Test",
			type="User",
			availability_status="Available",
		)
		entry = build_member_entry(user_obj, {})
		self.assertEqual(entry["is_admin"], 0)
		self.assertEqual(entry["allow_notifications"], 1)
		self.assertIsNone(entry["channel_member_name"])


class TestOpenChannelMembers(IntegrationTestCase):
	"""
	Regression test: a workspace member whose Raven User record is gone (e.g. a
	direct cleanup / data fix that skipped RavenUser.on_trash's own cascade) must
	be skipped from the Open channel's member list, not crash the whole request.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.get_doc("User", "test1@example.com").add_roles("Raven User")
		self.workspace = frappe.get_doc(
			{
				"doctype": "Raven Workspace",
				"workspace_name": "Chat Members Test Workspace",
				"type": "Private",
			}
		).insert()
		self.channel = frappe.get_doc(
			{
				"doctype": "Raven Channel",
				"channel_name": "chat-members-open-test",
				"type": "Open",
				"workspace": self.workspace.name,
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Raven Channel Member", {"channel_id": self.channel.name})
		frappe.db.delete("Raven Workspace Member", {"workspace": self.workspace.name})
		self.channel.delete()
		self.workspace.delete()

	def test_open_channel_skips_member_with_no_raven_user_record(self):
		user = "test1@example.com"
		frappe.get_doc(
			{"doctype": "Raven Workspace Member", "workspace": self.workspace.name, "user": user}
		).insert(ignore_permissions=True)

		# Simulate the broken state directly: a raw delete bypasses RavenUser.on_trash,
		# so the Workspace Member row survives with no matching Raven User doc.
		frappe.db.delete("Raven User", {"user": user})
		frappe.cache().delete_value(f"raven:workspace_members:{self.workspace.name}")

		members = get_channel_members(self.channel.name)

		self.assertNotIn(user, members)
