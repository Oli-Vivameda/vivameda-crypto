# Installation and operation

The published scanner/wallet/learning components target Python 3.10+ on Linux with systemd. The offline suite is checked on Python 3.12. Additional exported monitor setup is documented in MONITORS.md; see COMPLETENESS.md for limitations. The templates here are new distribution templates, not a claim that every live unit is identical.

## Offline verification

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r research/requirements.txt
.venv/bin/python -m unittest discover -s scout -p 'test_*.py'
.venv/bin/python -m unittest discover -s research -p 'test_*.py'
.venv/bin/python -m unittest discover -s agent -p 'test_*.py'
python3 scripts/verify_release.py
```

The tests use synthetic fixtures and mocked provider responses. They send no Telegram messages and do not establish live provider availability or token safety.

## Dedicated host setup

These commands install the scanner, wallet collector and V2 tracker on a fresh Debian/Ubuntu-style host. Review before running as an administrator. Do not apply them over an existing deployment without backups. No wallet signing keys are needed. The scanner can send Telegram alerts once its admission rules pass.

```sh
sudo apt-get update
sudo apt-get install python3 python3-requests python3-venv
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin vivameda-scout
sudo install -d -m 755 /opt/vivameda-crypto-early-scout
sudo install -m 644 scout/*.py /opt/vivameda-crypto-early-scout/
sudo install -d -o vivameda-scout -g vivameda-scout -m 750 /opt/vivameda-crypto-early-scout/data /opt/vivameda-crypto-early-scout/logs
sudo install -m 644 deploy/vivameda-early-scout.service deploy/vivameda-scout-learning-v2.service /etc/systemd/system/
sudo install -o vivameda-scout -g vivameda-scout -m 600 credentials.example.json /opt/vivameda-crypto-early-scout/credentials.json
```

Edit that credentials file locally with your Telegram bot token and destination chat ID. Never paste it into an issue, commit, screenshot or log. Do not publish your runtime directories. The JSON schema is exactly `bot_token` and `chat_id`; the example contains empty strings.

Initialize the scanner database without starting a network loop:

```sh
sudo -u vivameda-scout /usr/bin/python3 -c "import sys; sys.path.insert(0, '/opt/vivameda-crypto-early-scout'); import early_scout; early_scout.db().close()"
sudo /usr/bin/python3 scout/install_wallet_intelligence.py --install
sudo systemctl enable --now vivameda-early-scout.service vivameda-scout-learning-v2.service
```

The wallet installer validates hashes, creates its dedicated account and directories, installs the four wallet units, adds scanner read access to wallet evidence via a systemd supplementary group, and starts the wallet timers. It restarts the scanner. On a clean empty database its collection pass may be idle. It does not install the survivor monitors. The system interpreter must have `requests`; the virtual environment above is for offline tests and research. The source pins the dependency version used for release checks, while apt selects its distribution-supported version.

## Health, evidence and stop

```sh
systemctl status vivameda-early-scout.service vivameda-scout-learning-v2.service
systemctl list-timers 'vivameda-wallet-*'
sudo cat /var/lib/vivameda-wallet-intelligence/data/worker_status.json
sudo journalctl -u vivameda-wallet-intelligence.service -n 30 --no-pager
sudo tail -n 30 /opt/vivameda-crypto-early-scout/logs/early_scout.log
```

An active process or passing tests does not establish full cluster/age coverage. Inspect report checks, uncovered holders, pending identities, provider errors and capacity observations. Do not clear UNKNOWN to force alerts.

To stop these components:

```sh
sudo systemctl stop vivameda-early-scout.service vivameda-scout-learning-v2.service vivameda-wallet-intelligence.timer vivameda-wallet-candidates.timer vivameda-wallet-intelligence.service vivameda-wallet-candidates.service
```

Before upgrades, stop the affected units, preserve root-owned source and unit copies, and use SQLite's backup API for each database (a live copy of only the main .sqlite file can miss WAL data). Keep backups private. Restore the matching source, units and database snapshot to roll back, then reload systemd and start the affected units. No installer here changes a running server merely by cloning the repository.

## Optional browser evidence

`scout/dex_browser_worker.py` is separate from the alert loop. It captures visible DexScreener content and always returns HOLD; it cannot certify checks. Its existing source expects `/opt/vivameda-browser/chrome-headless-shell-linux64/chrome-headless-shell`. Install a compatible browser at that path under a dedicated unprivileged account and install `scout/requirements-browser.txt` in its isolated environment. The browser sandbox must remain enabled. Site verification blocks are recorded, not bypassed. This optional component has not been fresh-install verified in this distribution.
