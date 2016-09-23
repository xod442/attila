#!/bin/sh

# Dump all relevant debug information

echo "Debug info on `date`"

echo "########################"
echo "Current Status"
echo "########################"
service cvp status

echo "########################"
echo "Currently running Java processes"
echo "########################"
/cvp/jdk/bin/jps

echo "########################"
echo "Boot log"
echo "########################"
cat /var/log/boot.log

echo "########################"
echo "Last 100 lines of /tmp/cvp_install.log"
echo "########################"
tail -n 100 /tmp/cvp_install.log

echo "########################"
echo "Latest output from CVP logs"
echo "########################"
tail -n 100 /cvp/logs/*

echo "########################"
echo "Disk and memory info"
echo "########################"
echo "df -h"
df -h
echo "cat /proc/meminfo"
cat /proc/meminfo

echo "########################"
echo "Network settings"
echo "########################"
echo "/etc/hosts"
cat /etc/hosts
echo "/etc/resolv.conf"
cat /etc/resolv.conf

echo "systemctl status -l"
systemctl status -l

# Grab all of the logs and some config files.
tar --ignore-failed-read -cf /tmp/logs.tar /tmp/cvp_install* /etc/cvp.conf /cvp/cvp-config.yaml &> /dev/null
for PKG in . hbase hadoop tomcat zookeeper ; do
    if [ -d /cvp/$PKG/logs ] ; then
        tar --ignore-failed-read --append -f /tmp/logs.tar /cvp/${PKG}/logs &> /dev/null
    fi
done
gzip /tmp/logs.tar
    
exit 0
