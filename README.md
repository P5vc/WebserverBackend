# Webserver Backend
The full, Priveasy django backend

------------

If installing from scratch (i.e. onto a server where a fresh OS (re)installation has been done), follow the [server configuration instructions](https://github.com/P5vc/ServerConfigurations "server configuration instructions") to set up the entire server, including this backend, from scratch.

If upgrading the already-existent backend on a Priveasy webserver, do the following:
- Make sure the migrations found on the base webserver match those found in this repository as well as those found on any duplicate webserver. If the base webserver is ahead, add the latest migrations to this repository.
- Make sure you securely back up `/home/ubuntu/Priveasy/Priveasy/settings/.env`. This file will be wiped and replaced with a blank version that will not have all of the necessary entries. Most of these entries are only added to the file during a full server re-configuration.
- Run the following command as user `ubuntu`: `cd /home/ubuntu && sudo rm -rf ATTRIBUTION README.md LICENSE Priveasy priveasyVPN && git clone https://github.com/P5vc/WebserverBackend.git && mv WebserverBackend/* ./ && rm -rf WebserverBackend`.
- Replace the `/home/ubuntu/Priveasy/Priveasy/settings/.env` file with the properly backed-up version, and make any adjustments for entries that may have been added in the new update.
- Run `source /home/ubuntu/priveasyEnv/bin/activate && cd /home/ubuntu && python Priveasy/manage.py check --deploy && python Priveasy/manage.py collectstatic && python Priveasy/manage.py makemigrations && python Priveasy/manage.py migrate && python Priveasy/manage.py installtasks` then follow any prompts that may appear. If new migrations were applied, commit those to this repository.
- Replace the `ssl_certificate` and `ssl_certificate_key` options in the `/home/ubuntu/Priveasy/config/nginx.conf` file with the correct, Let's Encrypt key location (only if this is the base webserver). The correct entries will probably be `/etc/letsencrypt/live/p5.vc/fullchain.pem` and `/etc/letsencrypt/live/p5.vc/privkey.pem`, respectively.
- Reboot the server.
