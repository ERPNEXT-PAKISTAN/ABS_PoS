"""Two real MariaDB connections; callback returns a marker, never a financial document.
Run from bench/sites: ../env/bin/python -m klik_pos.tests.check_concurrency
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import frappe
from klik_pos.api.checkout import run_checkout


def connect():
	site = os.environ.get('ABS_TEST_SITE')
	if not site:
		raise RuntimeError('Set ABS_TEST_SITE to an authorized local test site.')
	frappe.init(site=site)
	frappe.connect()
	frappe.set_user('Administrator')


def worker(request_id):
	connect()
	created = []
	def create(_):
		created.append(True)
		time.sleep(0.8)
		return {'success': True, 'marker': str(os.getpid())}
	result = run_checkout({'checkoutRequestId': request_id, 'test_only': True}, frappe._dict(name='ABS Test Counter', company='ABS Test Company'), create)
	frappe.db.commit()
	print(json.dumps({'created': bool(created), 'result': result}))
	frappe.destroy()


def main():
	request_id = 'abs-concurrency-' + uuid.uuid4().hex
	try:
		command = [sys.executable, '-m', __name__.replace('__main__', 'klik_pos.tests.check_concurrency'), '--worker', request_id]
		processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
		results = []
		for process in processes:
			out, err = process.communicate(timeout=30)
			assert process.returncode == 0, err
			results.append(json.loads(out.strip()))
		assert sum(r['created'] for r in results) == 1, results
		assert results[0]['result'] == results[1]['result'], results
		print('PASS: simultaneous MariaDB requests execute checkout once and replay the same result')
	finally:
		connect()
		key = hashlib.sha256(f'Administrator:{request_id}'.encode()).hexdigest()
		frappe.db.delete('ABS Checkout Request', {'name': key})
		frappe.db.commit()
		frappe.destroy()


if __name__ == '__main__':
	if '--worker' in sys.argv:
		worker(sys.argv[-1])
	else:
		main()
