# ABS POS

ABS POS is a point-of-sale app for Frappe and ERPNext v16, maintained in [ERPNEXT-PAKISTAN/ABS_PoS](https://github.com/ERPNEXT-PAKISTAN/ABS_PoS). It is based on [KLiK PoS](https://github.com/Beveren-Software-Inc/KLiK_PoS). The repository name is `ABS_PoS`; the internal Frappe app, Python package and bench directory are still named **`klik_pos`**.

## What is included

- Retail POS with customers, items, barcode scanning, payment methods, cash received and change, invoice discounts and returns, subject to POS Profile settings.
- Item type filtering using the Item's `custom_type` Select field.
- Item History with recent sales, purchase and selected-customer transactions; stock balances by permitted warehouse; and a purchase-cost markup calculator.
- Material Transfer from the item Stock tab. Authorized users can select warehouses, quantity, remarks and required batch or serial numbers, then create and submit an ERPNext Stock Entry.
- Customer, address, item, item group and UOM Arabic fields, with bilingual customer details in POS.
- Sales dashboard, item-wise POS sales table and links to ERPNext reports.
- ABS branding and setup, POS Profile configuration and selectable Sales Invoice print formats.

The calculator rounds the selling price it saves to the nearest whole currency unit. See [item pricing](docs/item-pricing.md) for the calculation, permissions and tax handling.

## Requirements

- An existing Frappe/ERPNext v16 bench and site, with ERPNext installed on the site.
- Git and the Python, Node.js and Yarn environment required by that bench.
- Access to the bench and a site backup before installation or update. On production systems, schedule the update and process reload appropriately.

The optional ZATCA integration is separate. ABS POS can be installed without it; installing ABS POS alone does not establish ZATCA compliance. Test onboarding, invoice reporting, returns and print formats separately for each Saudi deployment. See [deployment and validation notes](docs/abs-pos-milestone-1.md).

## Install on a new site

Run these commands on the **bench server**, from your existing bench directory. Replace `your-site-name` with the site shown by `ls sites` (for example, `site1.local`). The site name is a bench identifier; use your own local URL or IP to access the site.

```bash
cd ~/frappe-bench
ABS_SITE=your-site-name

bench --site "$ABS_SITE" list-apps
bench --site "$ABS_SITE" backup --with-files

git clone --branch develop https://github.com/ERPNEXT-PAKISTAN/ABS_PoS.git apps/klik_pos
python3 - <<'PY'
from pathlib import Path
path = Path('sites/apps.txt')
contents = path.read_text()
if 'klik_pos' not in contents.splitlines():
    with path.open('a') as apps_file:
        if contents and not contents.endswith(('\n', '\r')):
            apps_file.write('\n')
        apps_file.write('klik_pos\n')
PY
bench setup requirements --python klik_pos
bench --site "$ABS_SITE" install-app klik_pos
bench --site "$ABS_SITE" migrate
bench build --app klik_pos
bench --site "$ABS_SITE" clear-cache
bench --site "$ABS_SITE" list-apps
```

The explicit clone directory matters: Bench versions may use the Git repository name as the folder name, while this app is installed as `klik_pos`. Do not run the clone if `apps/klik_pos` already exists; use the update instructions below.

### Recover from `No module named 'hrmsklik_pos'`

An older version of these instructions could join the last line in `sites/apps.txt` to `klik_pos` when the file had no final newline. If the error names `hrmsklik_pos`, back up and correct the app list, then finish the interrupted install. Run this on the affected bench, using the actual site name:

```bash
cd ~/frappe-bench
ABS_SITE=your-site-name
cp sites/apps.txt sites/apps.txt.before-abs-repair
python3 - <<'PY'
from pathlib import Path
path = Path('sites/apps.txt')
lines = path.read_text().splitlines()
fixed = []
for line in lines:
    if line == 'hrmsklik_pos':
        fixed.extend(['hrms', 'klik_pos'])
    else:
        fixed.append(line)
if 'klik_pos' not in fixed:
    fixed.append('klik_pos')
path.write_text('\n'.join(dict.fromkeys(fixed)) + '\n')
PY
cat sites/apps.txt
bench setup requirements --python klik_pos
bench --site "$ABS_SITE" list-apps
```

If `klik_pos` is absent from the site's app list, run `bench --site "$ABS_SITE" install-app klik_pos`. Then run `bench --site "$ABS_SITE" migrate`, `bench build --app klik_pos`, `bench --site "$ABS_SITE" clear-cache`, and reload the web processes. If the invalid name has a different prefix or you are unsure which apps belong in the file, restore the backup and inspect the app names before editing.

The repository contains a built POS frontend. To rebuild it when developing or when required after a source update:

```bash
cd ~/frappe-bench/apps/klik_pos/klik_spa
yarn install --frozen-lockfile
yarn build
cd ~/frappe-bench
bench --site "$ABS_SITE" clear-cache
```

After installing or changing Python code, reload your bench's web processes. On a production bench managed by Supervisor, `bench restart` may require the appropriate system permissions. In a development bench, restart the `bench start` process. Refresh the browser with **Ctrl+Shift+R**.

## Update an existing ABS or original KLiK installation

These steps preserve the installed app name and existing site data. They also work if your existing checkout's `origin` points to the original KLiK repository: the fork is added as a separate `abs` remote. First review any local changes; do not discard them. Repeat the site backup and migration for each site where `klik_pos` is installed.

```bash
cd ~/frappe-bench
ABS_SITE=your-site-name
bench --site "$ABS_SITE" list-apps
bench --site "$ABS_SITE" backup --with-files

cd apps/klik_pos
git status
git remote -v
git remote get-url abs || git remote add abs https://github.com/ERPNEXT-PAKISTAN/ABS_PoS.git
git remote get-url abs
git fetch abs develop
git switch develop
git merge --ff-only abs/develop
cd ../..

bench setup requirements --python klik_pos
bench --site "$ABS_SITE" migrate
bench build --app klik_pos
bench --site "$ABS_SITE" clear-cache
bench --site "$ABS_SITE" list-apps
```

Check that the displayed `abs` remote is the fork URL before merging. If `git status` shows local changes, preserve and resolve them before switching or merging. If the fast-forward merge fails, the histories have diverged; stop and review the changes instead of using `--reset` or `git reset --hard`. If the local branch is not named `develop`, review it before switching. Reload the web processes after updating, as described above.

For multiple sites, run `bench --site <site-name> backup --with-files` before updating and `bench --site <site-name> migrate` and `clear-cache` afterward for each installed site. Do not run `install-app` again on a site where `klik_pos` is already installed.

## Open and configure

Use your own site host and port. On a local site available at `127.0.0.1`, the routes are:

- POS: `http://127.0.0.1/abs_pos/pos`
- Setup: `http://127.0.0.1/abs_pos/setup`
- Reports: `http://127.0.0.1/abs_pos/reports`
- Desk workspace: `http://127.0.0.1/desk/klik-pos`

For a development bench, add the configured port, for example `http://127.0.0.1:8000/abs_pos/pos`. The ABS desktop icon opens the POS; use the workspace route to open its Desk links. The workspace route and available shortcuts can depend on the site's Frappe v16 Desk configuration and user permissions.

1. Open **ABS POS Settings** to configure branding and setup information.
2. Configure a native **POS Profile** with company, warehouse, selling price list, payment methods, assigned cashiers, customer groups where required, and the intended rate, discount, return and credit permissions. Select a print format if desired; an empty selection uses the original Thermal Printer PF.
3. Open a POS shift, select a customer and check a sale, tax, payment, print and shift closing in a suitable test environment before serving customers.
4. Item purchase costs, pricing changes, warehouse stock and stock transfers depend on native ERPNext permissions. The stock transfer posts a real submitted Stock Entry when the user selects **Create and submit transfer**.

## Development

The frontend source is in `klik_spa/`; the Frappe app is in `klik_pos/`. From the bench:

```bash
cd apps/klik_pos/klik_spa
yarn install --frozen-lockfile
yarn build
```

See [deployment and validation notes](docs/abs-pos-milestone-1.md) for implementation details and known acceptance limits. Those milestone notes describe the state at the time they were written and may not cover later changes.

## Attribution and license

ABS POS is derived from KLiK PoS by Beveren Software Inc. The original project and contributors retain their attribution. This repository includes the [GNU Affero General Public License v3](license.txt); review its terms when distributing or offering a modified version as a network service.
