"""Transactional idempotency: row locks survive until the request commits."""
import hashlib
import json
import re
import frappe
from frappe import _


def run_checkout(data, profile, create):
	request_id = data.get('checkoutRequestId', '')
	if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', request_id):
		frappe.throw(_('Checkout request ID is required. Refresh ABS PoS and try again.'))
	payload = {k: v for k, v in data.items() if k != 'checkoutRequestId'}
	digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
	key = hashlib.sha256(f'{frappe.session.user}:{request_id}'.encode()).hexdigest()
	# A concurrent insert of the same key waits for commit/rollback. No cache lock
	# is released before Frappe commits the invoice and the saved response together.
	frappe.db.sql('''INSERT INTO `tabABS Checkout Request`
		(name, creation, modified, owner, modified_by, docstatus, idx, request_hash, pos_profile, company)
		VALUES (%s,NOW(6),NOW(6),%s,%s,0,0,%s,%s,%s)
		ON DUPLICATE KEY UPDATE name=name''',
		(key, frappe.session.user, frappe.session.user, digest, profile.name, profile.company))
	row = frappe.db.sql('SELECT request_hash,response_json FROM `tabABS Checkout Request` WHERE name=%s FOR UPDATE', key, as_dict=True)[0]
	if row.request_hash != digest:
		frappe.throw(_('This checkout ID belongs to a different cart. Resolve the previous checkout before starting another.'))
	if row.response_json:
		return json.loads(row.response_json)
	result = create(data)
	if result.get('success'):
		frappe.db.set_value('ABS Checkout Request', key, 'response_json', json.dumps(result, default=str))
	else:
		frappe.db.rollback()
	return result
