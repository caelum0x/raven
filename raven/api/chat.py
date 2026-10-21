import frappe
from frappe import _

from raven.api.raven_users import get_list
from raven.utils import get_channel_members as get_channel_members_util
from raven.utils import get_workspace_members


def build_member_entry(user_obj, channel_member) -> dict | None:
	"""One member's row for the member list, or None when there's no matching
	Raven User record (e.g. a workspace member whose Raven User record was
	removed). The caller must skip a None entry instead of indexing into it —
	a workspace can list a member with no Raven User doc, and that one bad
	row must never crash the whole list."""
	if user_obj is None:
		return None

	return {
		"name": user_obj.name,
		"full_name": user_obj.full_name,
		"user_image": user_obj.user_image,
		"first_name": user_obj.first_name,
		"type": user_obj.type,
		"availability_status": user_obj.availability_status,
		"is_admin": channel_member.get("is_admin", 0),
		"allow_notifications": channel_member.get("allow_notifications", 1),
		"channel_member_name": channel_member.get("name", None),
	}


@frappe.whitelist(methods=["GET"])
def get_channel_members(channel_id: str):
	# Check if the user has permission to view the channel
	# fetch all channel members
	# get member details from user table, such as name, full_name, user_image, first_name

	frappe.has_permission("Raven Channel", doc=channel_id, throw=True)

	member_object = {}

	# This is an array
	all_users = get_list()

	# This is a dictionary
	channel_members = get_channel_members_util(channel_id)

	channel_type = frappe.get_cached_value("Raven Channel", channel_id, "type")

	if channel_type == "Open":
		workspace = frappe.get_cached_value("Raven Channel", channel_id, "workspace")
		workspace_members = get_workspace_members(workspace)

		# All workspace members are members of an open channel - merge the workspace members with channel members
		for workspace_member in workspace_members:
			channel_member = channel_members.get(workspace_member, {})
			user_obj = next((u for u in all_users if u.name == workspace_member), None)

			entry = build_member_entry(user_obj, channel_member)
			if entry:
				member_object[entry["name"]] = entry

	else:
		for member in channel_members:
			channel_member = channel_members[member]
			user_obj = next((u for u in all_users if u.name == member), None)

			entry = build_member_entry(user_obj, channel_member)
			if entry:
				member_object[entry["name"]] = entry

	return member_object
