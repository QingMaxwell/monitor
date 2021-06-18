sudo mkdir -p /var/log/monitor
sudo apt install -y lm-sensors hddtemp nvme-cli sysstat python3-pip
sudo -H pip3 install numpy matplotlib

# TODO add 0 8 * * * /opt/monitor/report.sh into /var/spool/cron/root
#service cron restart
